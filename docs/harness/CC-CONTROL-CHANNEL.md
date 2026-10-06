# The `cc:` route's stream-json control channel — 2.0.5 round 1

Research + implementation notes for `plans/briefs/2.0.5/round-1-cc-route-v2.md`
(spec: `plans/2.0.3-brief.md` section H, "`cc:` route v2"). Every wire shape
below marked **live-verified** came from two real invocations of the
installed `claude` binary — version **2.1.291**, Windows build host,
`CLAUDE_CONFIG_DIR` pointed at a scratch directory with no credentials (the
brief's own hard constraint: the two probes never touch the real
`~/.claude`). Both probes ran `-p --model claude-haiku-4-5 --max-turns 1
--input-format stream-json --output-format stream-json ...` under a 60s
`timeout`, one real one-word user turn each (`"ping"`); everything else in
each probe was `control_request` traffic, which costs no model call and
needs no credentials at all — the fact that both probes' own "ping" turn
failed with `authentication_failed` ("Not logged in — Please run /login",
the scratch config dir genuinely has no credentials) turned out not to
matter: every control-channel fact below is observable on a child that
cannot complete a real model turn, because `claude` validates/executes
every control operation locally, before it ever needs a successful model
call. `cc_tested.json`'s own version window (2.1.263–2.1.284) predates
2.1.291; this round does not widen it (the brief: only the orchestrator's
real-binary interop run at the tag does that) — a fact below marked
live-verified is true for 2.1.291 and *assumed*, not reconfirmed, for the
window's own range.

## 1. Wire shapes

**`control_request`** (halo → claude):
```json
{"type": "control_request", "request_id": "<str>", "request": {"subtype": "<name>", ...payload}}
```

**`control_response`**, success (claude → halo):
```json
{"type": "control_response",
 "response": {"subtype": "success", "request_id": "<str>", "response": {...}}}
```

**`control_response`**, error:
```json
{"type": "control_response",
 "response": {"subtype": "error", "request_id": "<str>", "error": "<message>"}}
```

These three shapes match the Claude Agent SDK's own published protocol
(cross-checked against the `claude_agent_sdk` Python package's internal
`query.py`, which documents the SDK's OWN sender/receiver side of the exact
same `control_request`/`control_response` envelope and lists `interrupt`,
`set_model`, `set_permission_mode`, `initialize`, `get_context_usage`,
`mcp_status`, `rewind_files`, `mcp_reconnect`, `mcp_toggle`, `stop_task` as
outgoing subtypes and `can_use_tool`/`hook_callback`/`mcp_message` as
INCOMING ones the SDK answers — halo's own `cc:` child never needs those
three incoming ones: `--tools ""` means claude never asks `can_use_tool`,
`--settings disableAllHooks:true` means it never calls `hook_callback`, and
halo's own bridge is the only MCP server, reached over real stdio MCP, not
this channel's `mcp_message`). The SDK source is the best available
secondary source for the subtypes this round's probes did not reach live;
every fact below tagged **live-verified** was actually seen on the wire
against 2.1.291, never assumed from the SDK alone.

## 2. `system.init`'s own `capabilities` field (live-verified)

Every `system.init` line (the first thing `claude` prints once it starts,
and again after certain operations — §5) carries a `capabilities` array.
2.1.291's own list, verbatim:
```json
"capabilities": ["interrupt_receipt_v1", "interrupt_cancel_queued_v1",
                   "interrupt_send_now_v1", "msg_lifecycle_v1",
                   "sdk_mcp_tools_list_changed", "sdk_mcp_manifests",
                   "mcp_read_resource_v1", "mcp_tool_ui_meta_v1", "ui_surface_v1"]
```
This is a MUCH more precise, forward-compatible detection signal than a
version-window comparison, and `agent/cc_control.py`/`agent/cc_runtime.py`
use it as the PRIMARY one: the key being present at all (even an empty
list) proves this installed version speaks the control protocol;
`cc_tested.json`'s version window is for the real-binary interop GATE at
the tag, a separate concern. When the key is absent entirely (an older
claude that predates this field — simulated in tests by
`FAKE_CLAUDE_CC_CONTROL=0`, the hermetic default for every OTHER test in
`tests/test_cc_session.py`), `agent/cc_runtime.py` decides "unsupported"
**immediately**, from that one line, rather than paying a live probe's own
round-trip timeout on every later steer/`set_model` just to learn the same
thing the slow way.

## 3. Control request subtypes — what 2.1.291 actually answered

| subtype | live-verified response | halo's use |
|---|---|---|
| `interrupt` (idle) | `{"subtype":"success","response":{"still_queued":[]}}` | §4, the steer path |
| `interrupt` (mid-turn) | not reached live (needs a genuinely in-flight turn, which needs real auth) — the fake's own conformance double exercises the WORST case instead (§8) | §4 |
| `mcp_status` | `{"subtype":"success","response":{"mcpServers":[]}}` | not used in production this round (kept available) |
| `get_context_usage` | a full context-window breakdown (`categories`, `totalTokens`, `maxTokens`, `model`, `memoryFiles`, `mcpTools`, `autoCompactThreshold`, `isAutoCompactEnabled`, ...) | §6's measured baseline; not wired into any live halo feature this round |
| `set_model` | `{"subtype":"error","error":"Unable to validate model: Could not resolve authentication method...","error_code":"check_failed"}` — the SCRATCH config dir's missing credentials, not a protocol refusal; the control_response envelope itself is well-formed | §5 |
| `set_permission_mode` | `{"subtype":"success","response":{"mode":"plan"}}`, PLUS a side-effect `system.status` push: `{"type":"system","subtype":"status","status":null,"permissionMode":"plan",...}` | implemented, intentionally unused (§5) |
| an unknown/bogus subtype (`frobnicate_xyz`) | `{"subtype":"error","error":"Unsupported control request subtype: frobnicate_xyz"}` | the exact string `agent/cc_control._is_unsupported_subtype_error` matches by prefix |

**A malformed `control_request` is fatal to the child.** A control_request
line with no `request` object at all (`{"type":"control_request",
"request_id":"probe_noreq"}`) was sent as the probe's second conformance
check; the child's stdout produced nothing further and every subsequent
stdin write failed with `EINVAL` (a closed pipe) — strong evidence the
process exited outright rather than answering with a graceful
`control_response` error. The probe's own script bug meant the exact
stderr text was not captured (the budget is two real invocations; a third
just to see the stderr text was not spent) — but the *shape* of the
failure (silent exit, no response) is the operative fact, and it is why
halo's own `cc_control.py` only ever builds a well-formed `request` dict
(never hand-assembled by any caller) and why the conformance suite
exercises "child exit mid-request" against the HERMETIC fake's own
deterministic `__exit_mid_request__` hook instead of trying to reproduce
the real crash (which would make the suite's pass/fail depend on exactly
how a future claude version fails, not on halo's own handling of it).

## 4. Steer (brief item H1) — what shipped

`agent/cc_runtime.steer_cc` now tries the control channel FIRST: sends
`control_request interrupt`, waits (bounded) for its own `control_response`,
and ONLY THEN sends the steer text as the next "user" stdin line — the
same two-step shape every other route's own steer already has (cut, then
continue). `state.expect_interrupted_result` tells the result handler in
`agent/cc_runtime._events_for_stdout_obj` to treat the NEXT result
specially: never a visible error card, and (a real, independently-useful
bug fix made while wiring this in) `turn_is_error` now always reflects the
MOST RECENT result instead of sticking `True` forever once any
intermediate result happened to carry one — both matter because the
INTERRUPTED round's own result shape on a real binary was never observed
live (every probe that could have reached a genuine in-flight interrupt
needed real auth); the hermetic fake's own conformance double therefore
deliberately marks the cut round's result `is_error: true` — the WORST
case — specifically to prove halo's suppression holds even then
(`test_steer_via_control_channel_cuts_reply_cleanly_and_runs_followup`).
When the channel is not supported (`cc_control.subtype_known_unsupported`),
`steer_cc` falls straight through to v1's unchanged behaviour: send the
text, let claude queue it, notify "queued for Claude Code".

## 5. Model and permission-mode changes without a restart (brief item H2)

**`set_model`**: `agent/loop.py`'s `Session.set_model`, on a cc:→cc: MODEL
change, now calls `agent/cc_runtime.switch_model_live` first — a
`control_request set_model` round trip; on a `success` response the SAME
subprocess/`CcState` is kept (no `--resume` restart) — live-verified that
the request reaches real validation (it failed only on the scratch
config's missing credentials, never on the protocol shape); on anything
else (unsupported, timed out, a genuine validation error) it falls through
to the existing close+`--resume`+new-`--model` restart path, completely
unchanged, which is what `test_model_switch_cc_to_cc_restarts_with_resume_
and_new_model` still pins for the control-off case.

**`set_permission_mode` is implemented but deliberately never used in
production.** The round-trip itself works (§3) and is conformance-tested
against the fake, but this harness's `cc:` child is ALWAYS launched with
`--permission-mode bypassPermissions` by design — halo's own bridge
(`_resolve_and_dispatch_bridged_call`) is what gates every tool call, and
the brief's own hard constraint says: "Keep bypass + `--tools ""` + the
bridged tools: that is what keeps halo's rules authoritative; never
re-enable Claude Code's own gating or built-ins." Halo's "plan mode" for
`cc:` is, and remains, a prompt-level note (`PLAN_MODE_NOTE`, baked into
`--append-system-prompt` at process start) plus halo's own bridge-level
tool-call gating — switching the CHILD's own native permission mode to
`"plan"` would re-enable exactly the gating the constraint forbids.
`cc_control.request_control(state, "set_permission_mode", mode=...)` stays
available (and tested) for a future, narrower use that does not touch
live tool-gating; nothing calls it today.

## 6. Context duplication audit (brief item H5)

Measured, not estimated, except where noted:

| source | who loads it | size | duplicated? |
|---|---|---|---|
| Claude Code's own default system prompt, empty cwd, zero tools, no CLAUDE.md/memory | claude itself, always | **6,626 tokens** (`get_context_usage`, live-verified: `"System prompt": 6626` of a 200,000 `maxTokens` window) | n/a — this is the floor the child ALREADY pays before halo adds anything |
| cwd's CLAUDE.md / AGENTS.md / rules chain | claude itself (cwd auto-discovery) AND halo (`SessionContext.claude_md_text()`) | this repo has none to measure; sized only by the user's own files | **NOT duplicated for `cc:`**: `agent/cc_runtime._cc_system_addendum` never calls `claude_md_text()` (only a sub-agent's own `session_context.system_prompt` body is included, which REPLACES the generic blurb for that child, never adds to it) |
| memory (MEMORY.md + topic index) | claude itself (`--exclude-dynamic-system-prompt-sections`'s own docs name "memory paths" as one of its default system-prompt sections) AND halo (`memory_snapshot_text()`) | session-dependent | **NOT duplicated** — same reasoning, `_cc_system_addendum` never calls it |
| environment (cwd/OS/date/git) | claude itself (same flag's docs: "cwd, env info, ... git status") AND halo (`environment_snapshot_text()`) | session-dependent | **NOT duplicated** — same reasoning |
| halo's own bridging explanation (`CC_APPEND_SYSTEM_PROMPT`) | halo only — claude has no way to know its own built-ins are disabled or that `mcp__rolo__*` replaces them | **345 chars / ~86 tokens**, fixed | the one thing claude genuinely cannot learn on its own |
| skills/subagent-type/MCP-instructions/deferred-tool-name reminders | halo only — these are halo-specific concepts claude's own discovery never sees | variable, each name+description clipped to 100 chars | not available to claude any other way |
| **halo's whole addendum, worst case** | halo only | hard-capped at **3,500 chars (~875 tokens)** regardless of how many skills/agents/MCP servers exist (`_ADDENDUM_CHARS`) — a Windows live finding from an EARLIER milestone: an uncapped addendum once made the real `claude` command line itself too long to start at all | — |

**Conclusion**: the design already passes only what Claude Code would not
load itself — confirmed both by reading `_cc_system_addendum` (which
explicitly skips CLAUDE.md/memory/environment with a comment to that
effect) and by `claude --help`'s own `--exclude-dynamic-system-prompt-
sections` description, which names "cwd, env info, memory paths, git
status" as sections of claude's OWN default system prompt — i.e. claude
documents, in its own `--help`, that it already carries exactly the three
things halo deliberately does not re-send. No code change was needed for
this item; this table is the record the brief asked for.

One harmless (not wire-duplicating) loose end: `agent/loop.py`'s session
constructor logs a `claude_md`/`memory_index`/`environment`/`deferred_
tools` snapshot into `session.log` for EVERY session regardless of route
(native routes' `derive_request` reads them back later); a `cc:` session
never calls `derive_request` at all, so these four log nodes sit there
unused — visible in `/export`, never sent to the child. `_cc_system_
addendum` separately (re)computes its own deferred-tools reminder from
the live `session_catalog.deferred` set each time a cc: process starts,
which can read differently from that earlier, unused snapshot text if the
catalog changed in between — harmless (only the addendum's own copy is
ever sent) but worth a future round's attention if the dead log node is
ever worth skipping outright for a `cc:` session specifically.

## 7. Compaction (brief item H3)

Live-verified: `/compact` sent as a plain `"user"` stdin message is
answered LOCALLY — no model call needed when there is nothing to compact:
```
<<< {"type":"system","subtype":"status","status":"compacting", ...}
<<< {"type":"system","subtype":"status","status":null,
      "compact_result":"failed","compact_error":"Not enough messages to compact.", ...}
<<< {"type":"system","subtype":"init", ...}            # re-announced
<<< {"type":"assistant", "message":{...,"content":[{"type":"text","text":"Not enough messages to compact."}]},
      "local_command_run":{"command":"compact","args":""}}
<<< {"type":"result", ..., "local_command":"compact", "result":"Not enough messages to compact."}
```
`agent/cc_control.forward_compact` sends the slash command, reads this
sequence (ignoring the re-announced `system.init`), and yields
`events.compaction(phase="done"|"failed", ...)` — the live signal halo's
transcript reads is the plain `system.status` `compacting`/`compact_
result` pair, NOT a PreCompact/PostCompact HOOK callback: this child
always runs with `--settings '{"disableAllHooks": true}'` (by design —
halo's own hooks already cover every tool-call lifecycle point; Claude
Code's native ones would fire redundantly/inconsistently for a bridged
session), so there is no user hook script left for `--include-hook-
events` to surface a callback FOR. `--include-hook-events` was added to
`build_cc_argv` anyway (cheap, and forward-compatible if a future claude
version ever emits a BUILT-IN lifecycle notice over that channel even
with every hook disabled) — today, with 2.1.291, it changes nothing
observable. A successful compaction's own summary text (if the child
supplies one as `compact_summary`) rides on `events.compaction(phase=
"done", summary=...)`; this was never observed live (the scratch
credentials meant every `/compact` this round's probes tried genuinely
had "not enough messages", and a REAL summarization needs a real model
call) — the hermetic fake's own `FAKE_CLAUDE_CC_COMPACT_RESULT=success`
knob is what the test suite exercises instead, with a fake summary string.
Halo's own session log is never mutated by this (no `compacted` marker
the way native-route compaction writes one) — there is nothing to splice:
a `cc:` session's log is a complete, passive record, never replayed to
the child, so nothing is lost by leaving it exactly as it was; see
`cc_control.forward_compact`'s own docstring.

## 8. Conformance (brief item H7)

`tests/helpers/fake_claude_cc.py` gained the control channel behind
`FAKE_CLAUDE_CC_CONTROL` (default "0" — every pre-existing test in
`tests/test_cc_session.py` is unaffected) and a `FAKE_CLAUDE_CC_VERSION`
knob. `tests/test_cc_session.py` pins all five shapes the brief asks for:

| shape | test |
|---|---|
| request/response round trip | `test_control_channel_detected_from_system_init_capabilities`, `test_set_model_live_swap_when_control_channel_supports_it` |
| steer round trip (interrupt → control_response → next user message, the cut reply never a finished turn) | `test_steer_via_control_channel_cuts_reply_cleanly_and_runs_followup` |
| unsupported subtype | `test_conformance_unsupported_control_subtype_shape` (the live-verified exact wording) |
| malformed response | `test_conformance_malformed_control_response_never_matches_a_waiter` |
| child exit mid-request | `test_conformance_child_exit_mid_request_returns_none_not_a_hang` |

Plus the fallback paths (`test_control_channel_marked_unsupported_when_
fake_control_off` and every pre-existing steer/model-switch test, which
never set `FAKE_CLAUDE_CC_CONTROL` and therefore still pin v1's unchanged
behaviour byte for byte), `/compact` both outcomes, and the cost label
(`test_subscription_cost_tracked_separately_never_as_spend`).

## 9. History when switching into `cc:` mid-session (brief item H4) — NOT implemented, and why

Researched, not shipped. `--resume <id>` already works TODAY for
resuming a conversation `claude` itself previously held (a crash/restart
within an ALREADY-`cc:` session, `agent/cc_runtime.ensure_cc_state`) —
that native transcript exists on disk because claude wrote it itself.
The case this brief item actually asks about is different: a session that
started on `or:`/`ant:`/some other route and is switching INTO `cc:` for
the FIRST time has no such native transcript anywhere — `--resume` would
have nothing of claude's own to resume. The only way to give the child
"native history" in that case would be for HALO to fabricate a transcript
file in Claude Code's own on-disk format (under `CLAUDE_CONFIG_DIR`'s
`projects/<hash>/<session-id>.jsonl`) from halo's own log, so that a
fresh `--resume` picks it up. That is, in substance, Halo writing one of
Claude Code's own session files — which this SAME brief's hard constraints
forbid outright ("Halo never writes Claude Code's files (`~/.claude.json`,
settings, sessions)"). No version of this feature was found that avoids
that conflict, so the existing behaviour (`prepare_conversation_so_far`
primes the fresh/reused process with a capped plain-text summary) is kept,
unchanged, and `cc.resume_native_history` was deliberately NOT added as a
config key — an always-off switch with no safe "on" implementation would
be dead, misleading config surface rather than a real option.

## 10. Exact real-binary interop check for the orchestrator at the tag

Against a REAL, logged-in `claude` (not the scratch `CLAUDE_CONFIG_DIR`
this round used): start a `cc:` session, send a prompt that takes a few
seconds (e.g. "write a 300-word paragraph about X"), steer it mid-reply,
and confirm (a) the reply visibly cuts rather than the steer queuing
behind a finished one, (b) no error card appears for the cut, (c) the
steer's own reply completes normally afterward. Then `/model cc:<other-
alias>` mid-session and confirm (from `halo_harness.log`/the session's own
meta nodes, or simply timing) no new subprocess started. Then `/compact`
on a long-enough real conversation and confirm a REAL summary string
shows up on `phase="done"`. Widen `cc_tested.json`'s `max` to the real
version actually used once all three pass.
