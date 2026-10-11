# Halo 2.0.10 review, round 2: the security review of the harness's own attack surface (findings doc)

Repo: `<repo>` (branch master; start from HEAD after round 1 `f88a012`,
clean). Read `plans/WORKER-RULES.md` FIRST. This round is a REVIEW, not a
fix pass: it writes `docs/harness/SECURITY-REVIEW-2.0.10.md` (numbered
findings with evidence) and `SECURITY.md` at the repo root, and changes
NOTHING under `halo_harness/` or `tests/`. The fix rounds follow from the
findings doc exactly as the 2.0.7 review fix pass did (one round per
area, each finding pinned, a SWEEP at the end).

Scope: `plans/2.0.9-review-privacy-brief.md` section A2, every bullet.
Standing contract from `plans/HANDOFF.md` (2.0.7): deny rules hold in
every mode; auto mode with no rules stays allow; classifier-shaped
suggestions (allowlists of "safe" commands, heuristics about dangerous
paths, refusal text) are REJECTED and must not appear as findings --
the permission bullet is about the CORRECTNESS of the user's own rules,
never new gates. No safety or refusal language anywhere in the doc.

## Method

1. Read the threat model you are reviewing against: `docs/REMOTE.md`
   (the six layers), `docs/harness/INVARIANTS.md` if present
   (`ls docs/harness | grep -i invar`), `docs/PERMISSIONS.md` or the
   permissions section of docs/HANDBOOK.md, `halo_harness/redact.py`,
   `docs/harness/SWEEP.md`-style precedent at
   `plans/briefs/2.0.7-fixpass/SWEEP.md` (the finding format that
   worked: number, title in bold, location `file:line`, what happens,
   repro or evidence, suggested fix in one line, severity).
2. Walk each A2 area with the code open, by symbol not by memory:
   - Credentials: `grep -rn "api_key\|token\|secret\|Authorization" halo_harness/`
     -> every read, cache, log, display (bugreport, timeline, debug,
     `--verbose`), send; `env_compat.py`, the env-file loader, keyring
     use; `redact.py` coverage vs the real request/log shapes
     (`providers/http.py`, `history.py`, `telemetry.py`, `bugreport*.py`).
   - Subprocesses and shells: `tools/bash.py`, `tools/powershell*.py`,
     hooks (`hooks*.py`), MCP server spawn (`mcp/manager.py`,
     `mcp/stdio*.py`), `agent/cc_process.py` + `codex_process.py` argv,
     `scripts/install-halo.sh|.ps1`, `remote/signal_transport.py` argv,
     `remote/signal_install.py` (archive extraction), `plugin_fetch.py`:
     quoting, env inheritance, cwd, process groups and kill.
   - File tools: `tools/read.py|write.py|edit.py|glob.py|grep.py|
     notebook*.py`, `shadow.py`, `worktree*.py`, session logs
     (`agent/log.py`), `~/.halo` permissions (`launch_state.py`,
     `history.py`, `filelock.py`, `remote/*`): traversal, symlinks, the
     working-dir rules the user configured, 0600/0700 where it matters.
   - Trust boundaries: MCP tool results and catalogs (`mcp/*`,
     `agent/repair.py`), claude.ai connectors (`connectors*.py`), OAuth
     storage/refresh (`mcp/oauth.py`), the ccbridge MCP
     (`ccbridge/server.py`), hook payloads, settings precedence
     (`config/settings*.py`), `.mcp.json` approval, plugin fetch.
   - Remote control (2.0.9): `remote/` end to end against docs/REMOTE.md's
     threat model -- pairing, ACI pinning, the HMAC window and counter,
     the control socket token/permissions, rate limits, the audit log,
     the stop file, the phrase/link handling. Seed finding: `halo review`
     already confirmed that `remote/signing.py` `phrase_to_secret`
     accepts an empty phrase or any word count and returns a bogus secret
     instead of raising -- include it as finding 1 with its repro.
   - Permission engine: `permissions*.py` -- rule pattern matching,
     precedence (deny > ask > allow? verify what the docs promise),
     mode switching, queued asks, the `/permissions` editor round-trip;
     ONLY correctness of the user's rules.
   - Supply chain: `pyproject.toml` pins, the CI workflow
     (`.github/workflows/suites.yml`) for a `pip-audit` step, the curl
     one-liner's integrity story in README/scripts.
3. For each area also run the new reviewer as a second opinion and fold
   in anything it confirms that you missed: `python -m halo_harness
   review <paths of that area> --level medium --dimensions security
   --model or:z-ai/glm-5.3-flash --json` (one run per area, from the repo
   root, with `PYTHONPATH` set; each costs cents and takes 3-6 minutes;
   skip an area if a run errors and say so). Attribute such findings
   "(confirmed by halo review)".

## Deliverables

1. `docs/harness/SECURITY-REVIEW-2.0.10.md` (<= 250 lines per write; two
   writes if needed): a short scope + method header, then findings
   numbered 1..N grouped by the seven areas, each with location,
   behaviour, evidence/repro, one-line fix, severity (high / medium /
   low), and a final "Residual risks" section (what the design does not
   protect against, stated plainly). Aim for the real list, not a long
   one: a finding needs a concrete failure scenario.
2. `SECURITY.md` at the repo root (<= 60 lines): how to report an issue
   (the GitHub repo's issue tracker; no personal addresses), what the
   harness protects against and what it does not, the remote-control
   threat model in five lines, where keys live and who can read them.
3. In the hand-back, the proposed fix-round split (areas -> rounds, each
   under ~12 findings) so the orchestrator can brief them directly.

## Verification before hand-back

`python -m tests.test_privacy_scan`, `python -m tests.test_docs_links`,
`python -m tests.test_docs_hygiene` green; `git status --short` shows
ONLY the two new docs. Hand back ONCE, under 60 lines, then end your
run: RESULT LINES (1-3), the finding count per area with the high ones
listed by number and title, the fix-round split, WHAT YOU FOUND beyond
the scope. No commit, no push.
