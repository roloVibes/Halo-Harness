# Privacy and the public repo

Read this when you check what Halo keeps out of the repo, or audit a checkout before you publish it.

Halo Harness is developed in the open. This page describes what the
harness itself never writes into the repo, and how to check a checkout
for anything that shouldn't be there before it's shared or pushed.

## What Halo never writes to the repo

- Every provider key/token lives in an environment variable or in
  `~/.halo/config.json`'s own credential fields -- never in a committed
  file. `halo_harness/redact.py`'s patterns catch every known key shape
  (`sk-ant-`, `sk-or-v1-`, `sk-proj-`, `ghp_`, `dapi`, `AKIA`, `hf_`,
  `xpl_`, a `Bearer` header, and a quoted `NAME=value`/`"NAME": "value"`
  assignment for any `*_API_KEY`/`*TOKEN*`/`*SECRET*`-shaped name) when
  redacting a session export, a bugreport, or a timeline -- see `halo
  export --sanitize` and `halo bugreport` in `docs/COMMANDS.md`.
- Session logs, the stats cache, MCP OAuth tokens, and every other piece
  of per-install state live under `~/.halo` -- never under the repo
  itself, and never read by anything this repo's own tests run (every
  test scopes its own state dir under `BRIDGE_TEST_HOME`).
- A real machine name, LAN address, account name, or hostname never
  appears in a commit -- see `halo audit privacy` below.

## One redaction for everything that leaves

**One redaction for everything that leaves (3.4.1.2).** The session export (Studio's Session -> Feed -> **Export**,
`/export`, `halo session export`), `halo export --sanitize`, `/export --sanitize`, the report card's Markdown,
`halo bugreport` and Record's page (3.6.0.3) all pass `halo_harness/privacy_redact.py`:
the key shapes (now also Groq, xAI and Perplexity keys, JWTs, a token in a URL such as Studio's `#t=` or a pack's
`?k=`, a bare random 30-character token, and the current values of your secret environment variables), then the paths
and names: a path inside the project becomes project-relative (`a.txt`, `src/b.py`; the project itself `.`), any other
path under your home `~/...`, in any spelling (either separator, any case of a Windows path, Git Bash's `/c/...`, WSL's
`/mnt/c/...`), and your user name and machine name become `<user>` and `<machine>` -- also inside URLs, `user@host`,
`..` paths, 8.3 short names (`JSMITH~1`), percent-encoded or full-width
text, the agent ids, the plan's names and dict keys; only a path the project rule made relative keeps its words, and
the title keeps your own. Control characters are dropped. `tests/test_privacy_redact.py` keeps the generator
that attacks it (case, separators, encodings, look-alikes, every kind of field). Not caught: a name split across two
fields, and look-alike letters NFKC does not fold (Cyrillic, Greek).

**A text cut short can keep part of a name.** Where Halo shortens a text and ends it with `...` (the report card and
Record's page keep the first 200 characters of an agent's task), and the cut lands inside your account name or machine
name, Halo looks only at the letters and digits right before the `...`: when there are three or more and your name
starts with them, they are masked; otherwise they stay. With the account `alexander`, `asked al...` stays as it is,
while `asked ale...` becomes `asked <user>...`. A name with a dash, dot or underscore is masked only while the cut is
still in its first part: with a machine named `gpu-box`, `on gpu...` becomes `on <machine>...`, but `on gp...`,
`on gpu-b...` and `on gpu-bo...` stay as they are.

**Another account's home folder.** The redaction knows your own home folder and your own names, not those of the
other accounts on the machine. What happens to a path in another account's home folder (say the file `notes.txt` in
the home of an account named `sam`):
- the session export (Session -> Feed -> **Export**, `/export`, `halo session export`) takes the account name out and
  writes `~/notes.txt`, which reads like a path in your own home;
- `halo export --sanitize` and Record's page leave the path as it is, the account name included.

If such a path matters, look for it in the file before you share it.

**An account named by a common word (3.6.0.1).** When your account name is a generic word (`admin`, `user`, `dev`,
`build`, `runner` ...), the redaction removes it in home folders and in logins only: `name@machine`,
`machine\name` where `machine` is this computer's own name (a domain account such as `CORP\name` keeps the word), a
share `\\machine\name`, an account slot of `ssh -l`, `sudo -u`, `docker -u`, `psql -U`, `mysql -u`, `runas` /
`net use /user:` (wherever the command stands on the line), of `su`, `chown`, `id`, `passwd`, `groups`, `finger`,
`useradd` and kin (at the start of a command), and keys such as `user=` or `owner=`. Other commands that take an
account (`crontab -u`, `getent passwd`, `net user`) are not on that list. Anywhere else (an `ls -l` owner column, a
process list, an `/etc/passwd` line, an ssh config `User` line, a role value, a path or route word, ordinary prose)
the word stays, because there it cannot be
told from the ordinary word, and a generic word identifies nobody. So if you want every occurrence gone, search the
file for the word yourself before you share it.

## `halo audit privacy`

Run it before sharing a checkout, opening a pull request from a fork, or
cutting a release:

```sh
halo audit privacy
```

A clean tree prints one line and exits 0; anything it finds prints one
line per finding (`path:line: <kind>: <masked excerpt>`, the matched
value always replaced with `<redacted>`) and exits 1. `--history` runs
the same checks over every blob any ref of the clone reaches (branches,
tags, remotes) instead of just the working tree -- useful before a repo
goes public, since a file deleted with a plain `git rm` is still sitting
in every earlier commit.

Since 3.4.1.2 every run says first whether your private term list was
loaded (`name checks: ON (n private term(s) ...)` or `name checks: OFF`
and why), the name terms cover the whole tree (plans, notes, scripts,
packs, SVG text), a finding names a term by its number (`term #3`), never
the term, and files that are not text are counted as not checked.
`--commits` reads every commit's author and committer address and its
message: an address that is not a GitHub noreply one and a private term
in a message are reported (masked, counted per address); they fail the
audit only on a commit that is not yet on `origin/master`, since an older
one can only be fixed by a history rewrite. `scripts/prepush.py` runs the
working tree and `--commits` in a scratch home and hands your term list
over by file name (`HALO_PRIVACY_TERMS_FILE`).
`--json` gives the same fields as one machine-readable object; `--since
REV` narrows a history scan to `REV..HEAD`. See `docs/COMMANDS.md`'s own
`halo audit` entry for every flag, and `tests/privacy_scan_allowlist.txt`
for the mechanism that exempts a deliberate, already-vetted fixture
value (a fake key, a placeholder LAN hostname) from either mode.

## If the audit finds something in history

A file already committed and later deleted, or a line already pushed
and later edited, is still sitting in every commit before that point --
deleting it again or editing the line doesn't remove it from history.
Fixing that needs a history rewrite (`git filter-repo`), which is
disruptive on purpose: every clone must re-clone or hard-reset, and
every commit hash changes. Halo's own history went through exactly this
once; the plan that rewrite followed is kept at `plans/2.0.4-history-
rewrite-plan.md` as a worked example of the shape such a plan takes
(paths to purge entirely, text replacements, tags to re-create, clones
to reset, and the verification steps). Running `halo audit privacy`
again never triggers a rewrite by itself -- a human decides when one is
warranted and runs it deliberately, with a backup made first and the
rewrite announced, never asked, since every existing clone is affected.

## Your own term list stays out of the repo

The machine-name check needs YOUR names (hosts, gear, projects, your own
name) and those are never stored in this public repository: a history
rewrite's text replacement would corrupt the rule file, and the list itself
is identifying. Give them to the audit through one of:

- `HALO_PRIVACY_TERMS`: terms separated by `;`; a `ci:` entry switches the
  rest to case-insensitive matching.
- `HALO_PRIVACY_TERMS_FILE`: the path of a file in the format below (3.4.1.2:
  how the pre-push gate hands your real list to an audit in a scratch home).
- `<state dir>/privacy-terms.txt` (normally `~/.halo/privacy-terms.txt`): one
  term per line, a line `ci:` switching to case-insensitive, `#` comments.

With none present the machine-name check is OFF and every run says so in
one line (CI has no list by design, so its log says OFF); every generic rule
(user-profile paths, private and link-local addresses, LAN and `.local`
hostnames, stray OS cache files, key- and token-shaped strings, e-mail
addresses) still applies.
