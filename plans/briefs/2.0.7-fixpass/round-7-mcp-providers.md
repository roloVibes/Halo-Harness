# Halo 2.0.7 fix pass, round 7: review findings 43-47 (MCP), 33/38-40 (provider tail), P2 tail

Repo: `<repo>` (branch master; start from HEAD after round 6, clean). Read
`plans/WORKER-RULES.md` FIRST and follow every rule in it (test environment:
`BRIDGE_TEST_HOME=<fresh scratch dir>`, `BRIDGE_TEST_NO_BACKGROUND_NET=1`,
`OLLAMA_HOST=http://127.0.0.1:1`). `plans/CYCLE.md` "Budget discipline"
applies. The owner's review is `<review file>` (outside the repo; read the
numbered findings, never copy its text into the repo). Standing contract
from `plans/HANDOFF.md` ("WHERE THINGS STAND -- 2026-10-09"): deny rules
hold in every mode, auto mode with no rules stays allow, the review's
classifier-shaped suggestions are rejected.

## Findings to fix (each at the source, each pinned by a test in `tests/test_review2_round7.py`)

- **43-45** MCP HTTP/SSE and websocket connectors carry credentials and
  streams through `mcp/connectors.py` (read the three findings: header
  handling, redirect behaviour, stream lifetime).
- **46** the TCP preflight ignores `HTTP(S)_PROXY` (`mcp/http_sse.py`
  ~243-287): a proxied host must not be probed directly.
- **47** a timed-out plugin clone is cached as valid forever and the git
  command lacks the `--` separator (`plugin_fetch.py` ~82-104).
- **33** escalation `set_model` half-switch; **38** `xp:` count_tokens;
  **39** proxy credential scopes; **40** non-JSON 200 handling (provider
  tail; read each finding for the exact location).
- **P2 tail**: ollama `_get_json` HTTPException; `http.py` non-final-404
  connection leak and bad-route caching; `oai_stream` cache-write pricing;
  `mcp/oauth` single-request callback; `mcp_cli` one project-key form;
  `gym_tool_tasks` docstring.

## Verification before hand-back

The new module, every touched module's tests, `python test_bridge.py`,
`python tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python -m halo_harness audit privacy`, all green; no network in tests.
Hard constraints: no safety or refusal language, no real paths or names,
no new dependency. Hand back RESULT LINES (one per finding: DONE / PARTIAL
/ REJECTED with the reason and the pinning test), FILES TOUCHED, WHAT YOU
FOUND. No commit, no push.
