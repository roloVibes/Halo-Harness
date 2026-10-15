# Security

## Reporting an issue

Use this repository's issue tracker on GitHub. For anything that gives an
attacker a head start, open the issue with a one-line summary only ("security:
<area>"), no exploit detail, and ask for a private channel there; or use the
repository's private vulnerability reporting (Security tab) when it is
enabled. Include `halo --version`, the platform and the smallest steps that
show it. The latest 2.0.x release is the supported one.

## What Halo protects against

- Provider keys leaking into tool children, exports made with `--sanitize`,
  bug reports and logs: keys are stripped from the environment of Bash, hooks
  and status lines, and `redact.py` redacts known key shapes (best-effort).
- Your own deny, ask and allow rules: they are evaluated in every mode and
  deny always wins; auto mode with no rules allows everything by design.
- Edited `.mcp.json` entries after approval (approvals are keyed by the
  entry's hash and the project folder it was approved in) and untrusted
  project settings (`env`, `hooks`, `disableAllHooks`, `plansDirectory`,
  `permissions.allow` and `permissions.defaultMode` are dropped from an
  untrusted folder, as are a project team template's `mode` and allow rules).
- A stranger on Signal, a swapped phone, a replayed or delayed command, and
  another local account reaching the control sockets (see below).

The 2.0.10 review lists where each of these is still incomplete.
## What it does not protect against

- Anything running as your account: it reads every file Halo writes and
  every control socket. Bash, hooks, plugins and MCP servers run as you,
  unconfined.
- A model acting on instructions it finds in content it reads: Halo applies
  your rules and does not judge commands.
- A compromised provider, gateway, Signal account, phone or computer; secrets
  sit in plain files (no OS keyring in this release).

## Remote control (2.0.9) in five lines

1. Since 3.0.5.0 every session opens its control socket (`fleet.enabled`;
   `--private` or `/private on` for one that should not); it is a Unix
   socket (mode 0600, directory 0700) or Windows loopback TCP plus a random
   token, never a network address. The phone bridge is off by default
   (`remote.enabled`).
2. The Signal bridge answers nobody it has not paired: contact request,
   approval on the computer, a one-time six-digit code, pinned on the ACI.
3. Every command after pairing ends `#<counter>:<mac>` (HMAC, rising
   counter, 5-minute window); a changed safety number blocks the peer.
4. A paired, signed phone can do everything the keyboard can, including
   answering permission cards: treat the phone and the signing secret like
   the keyboard. Unpair a lost phone with `halo remote signal unpair`.
5. Full threat model, layer by layer: [docs/REMOTE.md](docs/REMOTE.md).

## The fleet hub (3.0.5.0) in four lines

1. Nothing listens on the LAN until you start a hub (`halo fleet serve` or
   `halo studio --fleet`); it serves only the fleet protocol, never Studio's
   loopback API, and offline mode refuses it.
2. A harness joins only with a one-time six-word code; the pair key comes
   from a code-authenticated key exchange, every request and every command
   is HMAC-signed (time window, nonce, sequence), and TLS is pinned to the
   hub's fingerprint when `cryptography` is installed (else HMAC-only).
3. A joined harness sends only its `fleet.share` level and applies a hub's
   commands only per `fleet.allow_control` (default `ask`: a card for you);
   a hub never gets a tool permission or learns a rule.
4. `halo fleet kick` revokes a member's key; `halo fleet leave` forgets a
   hub. Details: [docs/FLEET.md](docs/FLEET.md).

## Where keys live and who can read them

| What | Where | Readable by |
|---|---|---|
| Provider keys | `~/.config/halo/env` (0600, dir 0700) | your account, root |
| Signal signing secrets, signal-cli keys, registration PIN | `~/.halo/remote/` (0700; files 0600) | your account, root |
| MCP OAuth tokens | `~/.halo/mcp/oauth/*.json` (0700 / 0600) | your account, root |
| Fleet pair keys | `~/.halo/fleet/keys/` (joiner), `~/.halo/fleet/hub/members.json` (hub), both 0600 | your account, root |
| Settings, prompt history | `~/.halo/config.json`, `history.jsonl` (0600) | your account, root |
| Session transcripts, edit snapshots, logs | `~/.halo/sessions/`, `bridge.log` | currently follow your umask (often group/world readable); tightening is tracked in the review |

The 2.0.10 review of Halo's own attack surface, with every finding, its
evidence and the fix rounds: [docs/harness/SECURITY-REVIEW-2.0.10.md](docs/harness/SECURITY-REVIEW-2.0.10.md).
