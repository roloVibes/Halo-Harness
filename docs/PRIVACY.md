# Privacy and the public repo

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

## `halo audit privacy`

Run it before sharing a checkout, opening a pull request from a fork, or
cutting a release:

```sh
halo audit privacy
```

A clean tree prints one line and exits 0; anything it finds prints one
line per finding (`path:line: <kind>: <masked excerpt>`, the matched
value always replaced with `<redacted>`) and exits 1. `--history` runs
the same checks over every commit reachable from HEAD instead of just
the working tree -- useful before a repo goes public, since a file
deleted with a plain `git rm` is still sitting in every earlier commit.
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
- `<state dir>/privacy-terms.txt` (normally `~/.halo/privacy-terms.txt`): one
  term per line, a line `ci:` switching to case-insensitive, `#` comments.

With neither present the machine-name check is inactive; every generic rule
(user-profile paths, private and link-local addresses, LAN and `.local`
hostnames, stray OS cache files, key- and token-shaped strings, e-mail
addresses) still applies.
