# Halo 2.0.10 review, round 3 (fix pass 1): trust boundaries 6-10, credentials 17-20

Repo: `<repo>` (branch master; start from HEAD after round 2 `7b6b78c`,
clean). Read `plans/WORKER-RULES.md` FIRST and follow every rule in it
(test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies.

The source of truth for every finding is `docs/harness/SECURITY-REVIEW-
2.0.10.md` (sections B and D; read each finding's location, failure
scenario and one-line fix in full -- never fix from this brief's titles
alone). Standing contract (plans/HANDOFF.md, 2.0.7): deny rules hold in
every mode; auto mode with no rules stays allow; classifier-shaped
suggestions are rejected. These fixes are about the correctness of the
trust gate the docs already promise, and about secrets not leaking --
not new gates. No safety or refusal language anywhere.

## Findings to fix (each at the source, each pinned in `tests/test_security_round3.py`, split 3b at the 250-line cap)

Trust boundaries (`mcp/`, `config/settings.py`, `init_cli.py`):
- **6** (high) an untrusted repo approves its own `.mcp.json` servers
  (`enableAllProjectMcpServers` not trust-gated; `-p` auto-approves).
- **7** (high) a project `statusLine.command` runs in an untrusted folder.
- **8** (high) OAuth endpoints from server metadata reach
  `webbrowser.open` and the token POST unchecked (scheme/host checks).
- **9** (medium) `__` in server names collides in the `mcp__` namespace.
- **10** (medium) a project `.halo/team.json` chooses the Databricks host
  `halo init` stores a token for.

Credentials (`redact.py`, `providers/http.py`, the env strip, file modes):
- **17** (high) both redactors leak real secret shapes (`"NAME": "value"`
  inside tool results, `https://user:tok@host`, backslash and numeric
  values, the `bridge.log` formatter that redacts "Bearer" and keeps the
  key) -- fix against the real request and log shapes the review names.
- **18** (medium) HTTP redirects carry `Authorization` to the new host.
- **19** (low) signal-cli and `.mcp.json` `${VAR}` expansion skip the
  secret-stripping environment.
- **20** (low) secret files are written then chmod'd; `add_allow_rule`
  drops the file mode.

If a finding turns out wrong against the current code, mark it REJECTED
with the evidence; if a fix would be a new gate rather than a
correctness fix, say so and leave it.

## Deliverables

1. The fixes above, at the source, each with a pinning test that fails
   on the old code (say which you checked).
2. CHANGELOG `[2.0.10] - unreleased` "### Security review fix pass, round
   1 (trust boundaries + credentials)" with one bullet per finding.
3. The findings doc: add a status line under each fixed finding
   ("Fixed in round 3: <one line>") -- the doc stays the record.
4. docs where behaviour changes (HANDBOOK trust section, docs/MCP.md or
   the MCP section, docs/CONFIG.md) in one or two lines each.

## Verification before hand-back

The new test module(s), `tests.test_mcp_*` (list them), `tests.test_settings*`,
`tests.test_trust*` if present, `tests.test_redact*`, `tests.test_privacy_scan`,
`tests.test_review2_round4` (the deny-rule integrity contract from 2.0.7),
`tests.test_h15_provider_enablement`, `tests.test_set_model_creds`, every
touched module's tests, `python test_bridge.py`, `python -m tests.test_invariants`,
`python -m tests.test_docs_links`, `python -m halo_harness audit privacy`,
and `python -m pyflakes halo_harness/ bridge.py | grep "undefined name"`
printing nothing. Run `python test_tui.py` only if `tui/` changed. Hand
back ONCE, under 60 lines, then end your run: RESULT LINES (one per
finding: DONE / REJECTED with the pinning test), FILES TOUCHED, WHAT YOU
FOUND. No commit, no push.
