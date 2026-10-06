# Halo 2.0.5 round 1: `cc:` route v2 (the stream-json control channel)

Repo: `<repo>` (branch master; start from HEAD = the v2.0.4 release
commit). Read `plans/WORKER-RULES.md` FIRST and follow every rule in it
(test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies: one worker, touched modules
plus `python test_bridge.py`, no full suites.

Specification: `plans/2.0.3-brief.md` section "H. `cc:` route v2" (read it
in full; its seven numbered items are the deliverables below). The owner's
words are quoted there. `plans/ROADMAP.md` "REORDERED 2026-10-05" places it
first in the 2.0.5 control pack.

## Where the code is

`halo_harness/agent/cc_process.py` and `halo_harness/agent/cc_runtime.py`
(the route: spawn of the real `claude` binary in print mode with
`--input-format stream-json --output-format stream-json --permission-mode
bypassPermissions --tools "" --strict-mcp-config --mcp-config <bridge>`, the
framing, today's steer "queued for Claude Code" path and the
restart-with-summary path for model and mode changes), `agent/loop.py`
(where the route is selected and steers arrive), `halo_harness/providers/
cc_models.py` (enumeration only; leave it), `halo_harness/ccbridge/`
(server.py: Halo's tools bridged in as one MCP server; client.py;
`__main__.py`), `halo_harness/providers/cc_tested.json`
(the version window that passed the real-binary interop), `tests/helpers/
fake_claude_cc.py` (the fake `claude` the tests drive; extend it, never
replace it), `tests/test_cc_session.py`, `docs/HANDBOOK.md` paragraph
"Limitations of this v1", `docs/MODELS.md` cc: section, `docs/COSTS.md` (or
the cost section that exists) for the cost line.

## First step: establish the control-channel facts

Use the installed `claude` binary (`timeout 20 claude --version`) to pin
what the stream-json control channel accepts in print mode: the
`control_request` line shape (`{"type":"control_request","request_id":...,
"request":{"subtype":...}}`), the subtypes the installed version answers
(`interrupt`, `set_model`, `set_permission_mode`, others), the
`control_response` shape, whether `/compact` sent as a user message is
honoured in print mode, and which flag surfaces PreCompact/PostCompact hook
events. Budget for this: at most two real invocations, each
`--model claude-haiku-4-5 --max-turns 1` under `timeout 60`, with a one-word
prompt; everything else from `claude --help` and the Claude Agent SDK
protocol docs you can reach. Record the facts (version, subtypes, shapes,
URLs) in `docs/harness/CC-CONTROL-CHANNEL.md`; the code reads the version
window from `cc_tested.json`, never from a hard-coded version.

## Deliverables (H1-H7)

1. **Steer** through `control_request` `interrupt` followed by the steer as
   the next user message, so a `cc:` steer behaves like every other route's;
   today's "queued for Claude Code" path stays only as the fallback when the
   child's version lacks the channel (detected ONCE per process from the
   first control response or the version window, cached on the route).
2. **Model and permission-mode changes without a restart** via `set_model`
   and `set_permission_mode` where supported; otherwise the current
   restart-with-summary path, unchanged.
3. **Compaction**: `/compact` forwarded to the child as a user-message slash
   command when the installed version honours it; PreCompact/PostCompact
   surfaced in Halo's transcript (the same line native routes print, with
   the summary when the child provides one).
4. **History when switching into `cc:` mid-session**: research `--resume`
   against a transcript Halo writes; if the format is stable, do it behind
   the config key `cc.resume_native_history` (default off) and document the
   format version it was verified against; otherwise keep the summary and
   say so in the docs with the reason.
5. **Context duplication audit**: measure what the child loads on its own
   (cwd CLAUDE.md, rules, memory) against what Halo injects; pass only what
   Claude Code would not load itself; record the measured sizes (bytes per
   source, before and after) as a table in the research doc.
6. **Cost line**: `cc:` usage shows as "subscription turns" with Claude
   Code's own figure labelled "estimate", never as spend, in the status bar,
   `/cost`, `halo stats` and the session summary.
7. **Conformance**: a protocol test against the fake for every control
   message (request, response, unsupported subtype, malformed response,
   child exit mid-request). `cc_tested.json` is widened ONLY by the
   orchestrator's real-binary interop run at the tag, not by this round.
8. **Docs**: rewrite the HANDBOOK "Limitations of this v1" paragraph into a
   v2 paragraph (what still differs from native routes, and why), MODELS.md
   cc: section, the research doc above, CHANGELOG: open
   `## [2.0.5] - unreleased` at the top with "### cc: route v2".

## Tests (hermetic)

`tests/helpers/fake_claude_cc.py` gains the control channel behind an env
switch (`FAKE_CLAUDE_CC_CONTROL=1|0`) and a settable version string:
steer round trip (interrupt -> control_response -> next user message, the
cut reply never reaches the transcript as a finished turn), set_model and
set_permission_mode round trips, the fallback paths when the switch is off,
`/compact` plus the hook events, the cost label, the five conformance
shapes. No real binary in tests; `tests/test_cc_session.py` keeps setting
`BRIDGE_CLAUDE_EXE` to the fake when no `claude` is installed.

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere. Keep bypass +
  `--tools ""` + the bridged tools: that is what keeps Halo's rules
  authoritative; never re-enable Claude Code's own gating or built-ins.
- Halo never writes Claude Code's files (`~/.claude.json`, settings,
  sessions). The two probe invocations run with `CLAUDE_CONFIG_DIR` set to
  a scratch directory.
- No real paths, addresses, hostnames, user names, machine names or keys in
  any repo file; `halo audit privacy` exit 0; privacy scan and invariants
  green.
- No network in tests; never read the owner's key files.
- No new hard dependency. House size conventions: `agent/cc_runtime.py` is
  already past them (1160 lines), so the control channel goes in a new
  `agent/cc_control.py` and nothing new lands in `cc_runtime.py` beyond the
  calls into it.

## Verification before hand-back

Touched and new test modules, `python test_bridge.py`,
`python tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python tests/test_docs_commands.py`, `python -m halo_harness audit privacy`,
all green. Record `stat -c %s ~/.halo/history.jsonl` and
`ls ~/.halo/sessions | wc -l` at the start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-8: DONE / PARTIAL / ALREADY COVERED with
evidence and the pinning test names), FILES TOUCHED, WHAT YOU FOUND (the
control-channel facts in one paragraph, what the installed version refused,
anything left open and why, the exact real-binary interop check for the
orchestrator at the tag). No commit, no push.
