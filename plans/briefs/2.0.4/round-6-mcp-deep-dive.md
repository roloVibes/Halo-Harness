# Halo 2.0.4 round 6: MCP connectivity deep dive

Repo: `<repo>` (branch master; start from HEAD after round 5). Read
`plans/WORKER-RULES.md` FIRST and follow every rule in it (test
environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies: one worker, touched modules
plus `python test_bridge.py`, no full suites.

Specification: `plans/ROADMAP.md` section "ADDED 2026-10-05 ~12:05 (rolo):
2.0.4 round 'MCP connectivity deep dive'" (read it in full). The owner's
words: "I still cannot reconnect to many of the mcps. we need like a doctor
deep dive option to fix these with the use of an llm". Item (1) of that
section (the status-bar counter) was fixed in the 2.0.3 fix passes (events
omit an unknown count; lazy "cached" servers count; a lazy first connect
pushes a fresh count): verify it with the existing tests and move on. Item
(2), the diagnosis corpus from the owner's real failing servers, is the
orchestrator's (never in the repo); this round builds the tool that reads
such a corpus.

## Where the code is

`halo_harness/mcp/manager.py` (McpManager, connect/reconnect, backoff,
status rows), `halo_harness/mcp/__init__.py` (availability), `mcp_setup.py`,
`mcp_cli.py` (`halo mcp list|test|add|remove|fix`), `doctor.py` (the doctor
sections and `--mcp`), `tui/dialogs/mcp_status.py` (the `/mcp` dialog with
r/R reconnect and the repair actions), `providers/learned_rules.py` (the
learned-rules store round 2 and 3 extended), `tests/helpers/fake_mcp_server.py`
(the fake stdio server) and `tests/test_mcp_manager.py` /
`tests/test_mcp_compat_matrix.py` (existing coverage).

## Deliverables

1. **A server that fails to connect stays listed as down**, with its last
   error and the time, in `halo mcp list`, `/mcp` and the status bar's total
   (N/total never drops a configured server). Pin it with the fake server
   scripted to fail its handshake.
2. **`halo doctor --mcp deep [name]` and `/mcp doctor [name]`**: per server,
   in order, each step bounded by a timeout and recorded with its evidence:
   resolve the command (PATH lookup, Windows `.cmd`/`.ps1` shims, the
   interpreter the shim points at, node/python/uv versions), spawn with a
   timeout, run the stdio handshake (initialize, list tools) or the
   HTTP/SSE and websocket equivalents (port open, TLS, the first bytes),
   capture all stdout and stderr, diff the child's environment against the
   user's shell (missing PATH entries, missing env vars the config names),
   and check the config entry's shape against Claude Code's own
   (`.claude.json` user scope, project `.mcp.json`, plugins, managed).
   Print the evidence as one block per server (masked: no key values).
3. **The model proposes ONE fix per failing server**: the evidence block
   plus the server's config entry go to the session model (or the judge
   role when one is configured) with a fixed prompt asking for one concrete
   fix in a plain sentence of one of these kinds: config edit (exact
   key/value), missing package (exact install command), wrong path (exact
   path), port or URL change, env var to set (name only). The proposal is
   shown; it is applied only on a yes (`--apply` on the CLI, a key in
   `/mcp`); after applying, the server is re-tested; a fix that worked is
   recorded in the learned-rules store keyed by the failure signature
   (command basename + error class + stderr fingerprint) so the same
   failure is fixed automatically next time, announced in one line.
4. **`/mcp` shows "deep dive" as an action** and the last diagnosis per
   server (one line: when, the verdict, the fix proposed or applied).
5. **Corpus reader**: `halo doctor --mcp deep --from <dir>` runs the
   diagnosis over a directory of captured `halo mcp test` outputs and
   server logs (the shape `halo bugreport` and `halo mcp test` already
   write), so the orchestrator can feed the owner's real failures without
   the servers present. Document the directory layout in docs.
6. Docs: docs/MCP.md (or the MCP section of the docs that exists) with the
   deep-dive steps, the fix kinds, the learned-rules behaviour and the
   corpus layout; docs/COMMANDS.md and docs/SLASH-COMMANDS.md entries;
   CHANGELOG `[2.0.4]` "### MCP deep dive".

## Tests (hermetic)

The fake stdio server scripted for each failure mode: command not found,
shim pointing at a missing interpreter, handshake timeout, initialize
error, tools/list error, immediate exit with stderr, wrong env var; an
HTTP/SSE fake with a closed port and a bad TLS answer; the proposal step
driven by a mock model returning each fix kind; `--apply` round trips the
config edit and the re-test; the learned-rule replay fixes the same
signature without the model; the corpus reader on a fixture directory;
the `/mcp` dialog pilot showing the action and the last-diagnosis line.
No network, no real servers, no real model.

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere; a proposed fix is
  described and applied on a yes, never gated by any other judgement.
- No real paths, addresses, hostnames, user names, machine names or keys in
  any repo file; `halo audit privacy` exit 0; privacy scan and invariants
  green; evidence blocks mask key-shaped values.
- No network in tests; never read the owner's key files.
- Never block the UI thread: every probe runs in a worker with timeouts.
- No new hard dependency. Keep modules under the house size conventions
  (a new `mcp/doctor_deep.py` plus a `mcp/doctor_probe.py` is the expected
  split).

## Verification before hand-back

Touched and new test modules, `python test_bridge.py`,
`python tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python tests/test_docs_commands.py`, `python tests/test_docs_slash_commands.py`,
`python -m halo_harness audit privacy`, all green. Record
`stat -c %s ~/.halo/history.jsonl` and `ls ~/.halo/sessions | wc -l` at the
start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-6: DONE / PARTIAL / ALREADY COVERED with
evidence and the pinning test names), FILES TOUCHED, WHAT YOU FOUND
(anything the manager's current reconnect path does that loses a server,
anything left open and why, and the exact manual check for the owner: run
`halo doctor --mcp deep` on a box with failing servers and apply one fix).
No commit, no push.
