"""tests.helpers.fake_claude_cc -- H11/H11b Part C: a fake `claude`
executable for the `cc:` route's tests. Run as a subprocess exactly the
way `agent.cc_process.build_cc_argv` invokes the real one
(`BRIDGE_CLAUDE_EXE` points a test at `"<python> <this file>"`):

  * `<fake> auth status` -- the real `claude auth status` JSON shape,
    controlled by env vars (`FAKE_CLAUDE_CC_LOGGED_IN` default "1",
    `FAKE_CLAUDE_CC_AUTH_METHOD` default "claude.ai").
  * `<fake> --version` -- H11b finding 23: a real `claude --version` line.
  * `<fake> -p --model X --output-format stream-json --input-format
    stream-json ... --mcp-config <json> ...` -- emulates the real
    protocol (including `--replay-user-messages` echoes, cumulative
    `total_cost_usd`, `--resume`/`--session-id` validation) AND actually
    acts as a real MCP client: it spawns the "rolo" stdio server named in
    `--mcp-config` (the REAL `python -m halo_harness.ccbridge`) and
    performs real `tools/list`/`tools/call` over stdio, reacting to a real
    `notifications/tools/list_changed` by re-listing (H11b finding 6).

Per-round behaviour is driven by a trigger grammar in the prompt text:
  * `TOOL:<name>:<json-args>` -- call `mcp__rolo__<name>` once.
  * `TOOL2:<name1>:<json1>|<name2>:<json2>` -- call two tools in sequence;
    BETWEEN calls, any line that has ALREADY arrived on stdin (sent while
    this round is running) is echoed and folded into this SAME round's
    one final result (H11b critical finding 1's "absorbed" shape) --
    a single-call/plain-text round never checks, so a line sent while ONE
    of those is running becomes its own SEPARATE next round instead
    (finding 1's "queued behind a running turn" shape).
  * `WAITFOR:<name>:<json-args>` -- wait (bounded) for a real
    `notifications/tools/list_changed`, re-list, then call `<name>`.
  * `SLEEP:<seconds>` -- sleep before replying.
  * `ERROR:<subtype>` -- an error-shaped reply: only a final `assistant`
    message (no stream deltas) plus `result` with `is_error: true`.
  * `/compact[ <instructions>]` -- the local-command shape (brief item
    H3): a `system.status` "compacting" line, then a terminal one
    carrying `compact_result`/`compact_error` or `compact_summary`
    (`FAKE_CLAUDE_CC_COMPACT_RESULT`, "fail" default -- the live-
    verified "Not enough messages to compact." shape -- or "success"),
    then the ordinary local-command `assistant`+`result` pair.
  * anything containing "pong" -- replies "pong"; anything else --
    "noted".

`--session-id`/`--resume` validation (finding 9) is OPT IN, via
`FAKE_CLAUDE_CC_REGISTRY` (a path): unset (every existing test) means
every id is accepted, exactly like before this milestone.

Halo 2.0.5 round 1 (cc: route v2): the stream-json CONTROL CHANNEL
(`control_request`/`control_response`) behind `FAKE_CLAUDE_CC_CONTROL`
("1" to turn it on; unset/anything else -- every existing test -- keeps
this fake behaving EXACTLY as before, including never answering a
`control_request` at all, the correct stand-in for an old claude that
pre-dates the channel). When on:
  * `system.init` gains a `capabilities` list (a representative subset
    of the REAL installed 2.1.291's own list --
    `docs/harness/CC-CONTROL-CHANNEL.md` has the full one).
  * `interrupt`/`set_model`/`set_permission_mode`/`mcp_status`/
    `get_context_usage` get real `control_response` success shapes;
    any OTHER subtype gets the live-verified "Unsupported control
    request subtype: <name>" error shape.
  * `interrupt` also cuts the round CURRENTLY streaming (if any) --
    conformance brief item H7's "the cut reply never reaches the
    transcript as a finished turn".
  * Two subtype names are TEST-ONLY conformance hooks, never sent by
    real halo code: `__exit_mid_request__` (the process exits with NO
    response at all -- "child exit mid-request") and
    `__malformed_response__` (a `control_response` with no
    `request_id` at all -- "malformed response", unmatchable by
    design).
`FAKE_CLAUDE_CC_VERSION` (default "2.1.284-fake") overrides both
`--version`'s own output and `system.init`'s `claude_code_version`, so
a test can simulate a version below `cc_tested.json`'s window.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import uuid

_EOF = object()


def _auth_status_json() -> dict:
    logged_in = os.environ.get("FAKE_CLAUDE_CC_LOGGED_IN", "1").strip().lower() not in ("0", "false", "no", "")
    return {
        "loggedIn": logged_in,
        "authMethod": os.environ.get("FAKE_CLAUDE_CC_AUTH_METHOD", "claude.ai"),
        "apiProvider": "firstParty",
        "email": os.environ.get("FAKE_CLAUDE_CC_EMAIL", "test@example.com"),
        "subscriptionType": os.environ.get("FAKE_CLAUDE_CC_SUBSCRIPTION_TYPE", "max"),
    }


def _write(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _control_enabled() -> bool:
    return os.environ.get("FAKE_CLAUDE_CC_CONTROL", "0").strip() == "1"


def _fake_version() -> str:
    return os.environ.get("FAKE_CLAUDE_CC_VERSION", "2.1.284-fake")


# A representative subset of the REAL installed 2.1.291's own
# `system.init.capabilities` list (docs/harness/CC-CONTROL-CHANNEL.md
# has the full one) -- enough for `agent/cc_control.channel_supported`'s
# own detection to see a non-empty list and conclude "this version has
# the channel", without hard-coding every capability this fake doesn't
# actually need to emulate.
_FAKE_CAPABILITIES = ["interrupt_receipt_v1", "interrupt_cancel_queued_v1",
                       "interrupt_send_now_v1", "msg_lifecycle_v1"]

_CONTROL_SUPPORTED_SUBTYPES = {"interrupt", "set_model", "set_permission_mode",
                                 "mcp_status", "get_context_usage"}


class _ControlState:
    """Per-process (this fake has exactly one `claude` process per test
    the same as the real binary), mirrors what `agent/cc_control.py`'s
    own per-CcState bookkeeping tracks on the HALO side -- `interrupt_
    event` is what `_finish_round` below checks to cut a round already
    streaming (brief item H1's own conformance case)."""

    def __init__(self) -> None:
        self.interrupt_event = asyncio.Event()
        self.model: "str | None" = None
        self.permission_mode = "bypassPermissions"


async def _handle_control_request(obj: dict, session_id: str, control: "_ControlState") -> None:
    """Answered the moment it arrives, concurrently with whatever round
    (if any) is currently streaming -- `_serve_turns`'s own reader hands
    this off as its own `asyncio.create_task`, never blocking on it, the
    same way the real claude binary answers a control_request mid-turn."""
    request_id = obj.get("request_id")
    request = obj.get("request")
    if not isinstance(request_id, str) or not isinstance(request, dict):
        # Live-verified: the REAL binary's own process exits outright on
        # exactly this shape (no `request` object at all) -- this fake
        # stays a RELIABLE double instead of also crashing the test
        # process; `tests/test_cc_session.py`'s own "child exit mid-
        # request" case uses the dedicated `__exit_mid_request__`
        # subtype below instead, which is deterministic.
        return
    subtype = request.get("subtype")
    if subtype == "__exit_mid_request__":
        os._exit(1)  # no response, ever -- the process is simply gone
    if subtype == "__malformed_response__":
        _write({"type": "control_response", "response": {"subtype": "success", "response": {}}})
        return
    if subtype not in _CONTROL_SUPPORTED_SUBTYPES:
        _write({"type": "control_response", "response": {
            "subtype": "error", "request_id": request_id,
            "error": f"Unsupported control request subtype: {subtype}",
        }})
        return
    if subtype == "interrupt":
        control.interrupt_event.set()
        _write({"type": "control_response", "response": {
            "subtype": "success", "request_id": request_id, "response": {"still_queued": []}}})
    elif subtype == "set_model":
        control.model = request.get("model")
        _write({"type": "control_response", "response": {
            "subtype": "success", "request_id": request_id, "response": {"model": control.model}}})
    elif subtype == "set_permission_mode":
        control.permission_mode = request.get("mode")
        _write({"type": "control_response", "response": {
            "subtype": "success", "request_id": request_id, "response": {"mode": control.permission_mode}}})
        # Live-verified side effect: a successful set_permission_mode
        # ALSO pushes a plain status notice carrying the new mode.
        _write({"type": "system", "subtype": "status", "status": None,
                 "permissionMode": control.permission_mode, "session_id": session_id})
    elif subtype == "mcp_status":
        _write({"type": "control_response", "response": {
            "subtype": "success", "request_id": request_id, "response": {"mcpServers": []}}})
    elif subtype == "get_context_usage":
        _write({"type": "control_response", "response": {
            "subtype": "success", "request_id": request_id,
            "response": {"totalTokens": 0, "maxTokens": 200000}}})


def _parse_argv(argv: "list[str]") -> dict:
    opts: dict = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--model", "--session-id", "--resume", "--mcp-config", "--settings",
                  "--append-system-prompt", "--permission-mode", "--max-turns"):
            opts[a.lstrip("-")] = argv[i + 1] if i + 1 < len(argv) else ""
            i += 2
            continue
        if a == "--tools":
            opts["tools"] = argv[i + 1] if i + 1 < len(argv) else ""
            i += 2
            continue
        if a == "--fork-session":
            opts["fork-session"] = True
            i += 1
            continue
        i += 1
    return opts


def _log_argv(argv: "list[str]") -> None:
    """W4b connectors-bridge tests: `FAKE_CLAUDE_CC_ARGV_LOG` (a path), when
    set, gets one JSON-array line appended per invocation -- the simplest
    way for a test to assert the EXACT command line a real caller built
    (`--allowedTools`, `--max-turns`, the system prompt, ...) without
    mocking `subprocess.run` itself."""
    path = os.environ.get("FAKE_CLAUDE_CC_ARGV_LOG")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(argv, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _connector_tool_names() -> "list[str]":
    """W4b connectors-bridge discovery: `FAKE_CLAUDE_CC_CONNECTOR_TOOLS`
    (comma-separated `mcp__claude_ai_<Name>__<tool>` wire names) -- merged
    into the `system/init` line's `tools` regardless of whether a real
    `--mcp-config` "rolo" bridge is also present, since a real discovery
    probe never sets one up at all (bare `-p --output-format stream-json`,
    no mcp-config)."""
    raw = os.environ.get("FAKE_CLAUDE_CC_CONNECTOR_TOOLS", "")
    return [t.strip() for t in raw.split(",") if t.strip()]


def _cmd_mcp_list() -> int:
    """W4b connectors-bridge tests: `claude mcp list` -- prints one
    `claude.ai <Name>: <url> - <status>` line per entry in the JSON array
    `FAKE_CLAUDE_CC_CONNECTORS` (`[{"name", "url", "status_text"}, ...]`),
    or nothing at all when unset (zero connectors configured)."""
    raw = os.environ.get("FAKE_CLAUDE_CC_CONNECTORS")
    if not raw:
        return 0
    try:
        rows = json.loads(raw)
    except ValueError:
        rows = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        name = row.get("name", "Connector")
        url = row.get("url", "https://example.invalid/mcp")
        status_text = row.get("status_text", "✔ Connected")
        print(f"claude.ai {name}: {url} - {status_text}")
    return 0


def _output_format(argv: "list[str]") -> str:
    for i, a in enumerate(argv):
        if a == "--output-format" and i + 1 < len(argv):
            return argv[i + 1]
    return "text"


def _one_shot_json(argv: "list[str]") -> int:
    """W4b connectors-bridge tests: `-p --output-format json <prompt>` (the
    connector bridge tool's own call shape -- ONE turn, no stream-json
    envelope) -- `FAKE_CLAUDE_CC_JSON_MODE` ("echo", the default: result is
    `"ECHO:<prompt>"`, so a test can see exactly what the bridge sent;
    "error": an `is_error: true` result) controls the reply."""
    prompt = argv[-1] if argv and not argv[-1].startswith("-") else ""
    if os.environ.get("FAKE_CLAUDE_CC_JSON_MODE") == "error":
        _write({"type": "result", "subtype": "error_during_execution", "is_error": True,
                 "result": "fake connector error", "session_id": "fake-json",
                 "total_cost_usd": 0.0, "duration_ms": 1, "usage": {}})
        return 0
    _write({"type": "result", "subtype": "success", "is_error": False, "result": f"ECHO:{prompt}",
             "session_id": "fake-json", "total_cost_usd": 0.0012, "duration_ms": 7,
             "usage": {"input_tokens": 3, "output_tokens": 4}})
    return 0


def _load_registry(path: str) -> set:
    try:
        return set(json.loads(open(path, encoding="utf-8").read()))
    except (OSError, ValueError):
        return set()


def _save_registry(path: str, ids: set) -> None:
    try:
        open(path, "w", encoding="utf-8").write(json.dumps(sorted(ids)))
    except OSError:
        pass


def _validate_session_id(opts: dict) -> "tuple[str, bool]":
    """`(session_id, ok)` -- finding 9's opt-in registry check. `ok=False`
    means "print the real failure text to stderr and exit 1 with NO
    stdout at all" (real claude's own shape for a bad --resume/--session-
    id, verified live)."""
    registry_path = os.environ.get("FAKE_CLAUDE_CC_REGISTRY")
    resume_id, fresh_id = opts.get("resume"), opts.get("session-id")
    if not registry_path:
        return resume_id or fresh_id or str(uuid.uuid4()), True
    ids = _load_registry(registry_path)
    if resume_id:
        if resume_id not in ids:
            print(f"No conversation found with session ID: {resume_id}", file=sys.stderr)
            return resume_id, False
        if opts.get("fork-session"):
            new_id = str(uuid.uuid4())
            ids.add(new_id)
            _save_registry(registry_path, ids)
            return new_id, True
        return resume_id, True
    if fresh_id:
        if fresh_id in ids:
            print(f"Session ID {fresh_id} is already in use.", file=sys.stderr)
            return fresh_id, False
        ids.add(fresh_id)
        _save_registry(registry_path, ids)
        return fresh_id, True
    return str(uuid.uuid4()), True


_TOOL_RE = re.compile(r"^TOOL:([^:]+):(.*)$", re.DOTALL)
_TOOL2_RE = re.compile(r"^TOOL2:(.*)$", re.DOTALL)
_WAITFOR_RE = re.compile(r"^WAITFOR:([^:]+):(.*)$", re.DOTALL)
_SLEEP_RE = re.compile(r"SLEEP:(\d+(?:\.\d+)?)")
_ERROR_RE = re.compile(r"^ERROR:(\w+)$")


def _extract_text(line: dict) -> str:
    msg = line.get("message") or {}
    content = msg.get("content") or []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            return block.get("text", "")
    return ""


def _echo(line: dict, session_id: str) -> None:
    """`--replay-user-messages` -- verbatim echo of what was sent, marked
    `isReplay: true` (live-verified against 2.1.284)."""
    _write({"type": "user", "message": line.get("message") or {"role": "user", "content": []},
             "session_id": session_id, "parent_tool_use_id": None, "uuid": str(uuid.uuid4()), "isReplay": True})


async def _call_tool(mcp_session, wire_name: str, arguments: dict):
    result = await mcp_session.call_tool(wire_name, arguments)
    parts = []
    for c in result.content or []:
        text = getattr(c, "text", None)
        if text is not None:
            parts.append(text)
            continue
        # finding 7 "MCP image content out": a REAL mcp.types.ImageContent
        # -- note its presence/mime type so a test can prove an image
        # block actually flowed through the bridge, never "[image block]".
        data = getattr(c, "data", None)
        if data is not None:
            mime = getattr(c, "mime_type", None) or "?"
            parts.append(f"[image:{mime}:{len(data)}b]")
    return "\n".join(parts), bool(result.is_error)


class _Cost:
    """Cumulative `total_cost_usd` for THIS fake process -- finding 28:
    the real binary's own cost is cumulative per process, never per turn."""
    total = 0.0


async def _run_one_call(mcp_session, session_id: str, msg_id: str, name: str, args: dict) -> str:
    wire_name = f"mcp__rolo__{name}"
    tool_use_id = f"toolu_fake_{uuid.uuid4().hex[:12]}"
    _write({"type": "assistant", "message": {"id": msg_id, "role": "assistant",
                                               "content": [{"type": "tool_use", "id": tool_use_id, "name": wire_name,
                                                             "input": args}]},
             "session_id": session_id})
    text, is_error = await _call_tool(mcp_session, name, args)
    _write({"type": "user",
             "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_use_id,
                                                         "content": [{"type": "text", "text": text}],
                                                         "is_error": is_error}]},
             "session_id": session_id})
    return text


def _write_result(session_id: str, final_text: str, *, is_error: bool = False, subtype: str = "success") -> None:
    _Cost.total += max(0.0002, len(final_text) * 0.00001)
    usage = {"input_tokens": 2, "output_tokens": max(1, len(final_text.split())),
              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    _write({
        "type": "result", "subtype": subtype, "is_error": is_error, "stop_reason": "end_turn",
        "session_id": session_id, "duration_api_ms": 5, "duration_ms": 6,
        "total_cost_usd": round(_Cost.total, 6), "usage": usage, "result": final_text,
        "modelUsage": {"fake-model": {"inputTokens": usage["input_tokens"], "outputTokens": usage["output_tokens"],
                                        "costUSD": round(_Cost.total, 6), "canonicalModel": "fake-model"}},
    })


async def _handle_compact(session_id: str, msg_id: str) -> None:
    """Brief item H3 -- the live-verified local-command shape: a
    "compacting" status line, then a terminal one carrying either
    `compact_result: "success"` + `compact_summary`, or `compact_result:
    "failed"` + `compact_error` (default: the EXACT live wording for a
    short conversation, "Not enough messages to compact."), then the
    ordinary local-command `assistant`+`result` pair -- never streamed
    deltas (the real binary doesn't stream a local command's own reply
    either)."""
    _write({"type": "system", "subtype": "status", "status": "compacting", "session_id": session_id})
    await asyncio.sleep(0.02)
    succeed = os.environ.get("FAKE_CLAUDE_CC_COMPACT_RESULT", "fail").strip().lower() == "success"
    if succeed:
        _write({"type": "system", "subtype": "status", "status": None, "compact_result": "success",
                 "compact_summary": "Summarized the earlier turns.", "session_id": session_id})
        text = "Compacted the conversation."
    else:
        _write({"type": "system", "subtype": "status", "status": None, "compact_result": "failed",
                 "compact_error": "Not enough messages to compact.", "session_id": session_id})
        text = "Not enough messages to compact."
    _write({"type": "assistant", "message": {"id": msg_id, "role": "assistant",
                                               "content": [{"type": "text", "text": text}]},
             "session_id": session_id, "local_command_run": {"command": "compact", "args": ""}})
    _write({"type": "result", "subtype": "success", "is_error": False, "session_id": session_id,
             "duration_api_ms": 0, "duration_ms": 1, "total_cost_usd": round(_Cost.total, 6), "usage": {},
             "result": text, "local_command": "compact", "num_turns": 0})


async def _run_round(mcp_session, session_id: str, lines: list, turn_index: int, line_queue,
                       control: "_ControlState | None" = None) -> None:
    """One claude-native "round": echoes every line in `lines` (`lines[0]`
    is what arrived when this round started; anything else in it was
    ALREADY queued behind it at that exact moment -- critical finding 1's
    "a batch of queued lines as one combined reply" shape, e.g. two
    steers sent while a plain SLEEP-shaped round was still running both
    land in the FOLLOW-UP round's own `lines` together), does the work
    `lines[0]`'s text asks for, and (ONLY for a TOOL2 multi-call round --
    see module docstring) ALSO checks between calls for a line that
    arrives WHILE this round is already running (arrives late enough
    that it MISSED the batch above), folding each one it finds into THIS
    same round's one final result (finding 1's OTHER shape: one steer
    between tool calls, absorbed into the turn already generating)."""
    msg_id = f"msg_fake_{turn_index}"
    first_line = lines[0]
    for ln in lines:
        _echo(ln, session_id)
    absorbed_notes = [f"(absorbed: {_extract_text(ln)[:40]})" for ln in lines[1:]]
    prompt_text = _extract_text(first_line)

    if prompt_text.startswith("/compact"):
        await _handle_compact(session_id, msg_id)
        return

    m = _ERROR_RE.match(prompt_text)
    if m:
        _write({"type": "assistant", "message": {"id": msg_id, "role": "assistant",
                                                    "content": [{"type": "text", "text": f"error: {m.group(1)}"}]},
                 "session_id": session_id})
        _write_result(session_id, f"error: {m.group(1)}", is_error=True, subtype=m.group(1))
        return

    if prompt_text == "ENVDUMP":
        # critical finding 2: report which sentinel-shaped keys THIS
        # process (standing in for the real claude subprocess) actually
        # sees -- a test asserts a sentinel value set on the PARENT rolo-
        # claude process never appears here. Goes through `_finish_round`
        # (streamed deltas), never a bare `_write_result`, so it round-
        # trips through the same text_delta path a normal reply would.
        keys = ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN",
                 "DATABRICKS_TOKEN", "CLAUDECODE", "CLAUDE_CODE_SESSION_ID")
        seen = {k: os.environ[k] for k in keys if k in os.environ}
        await _finish_round(session_id, msg_id, "ENV:" + json.dumps(seen, sort_keys=True))
        return

    if prompt_text == "REPORT_IMAGE":
        # finding 4/7 "stream-json image content in": did the message WE
        # were sent carry a real Anthropic image block?
        content = (first_line.get("message") or {}).get("content") or []
        images = [b for b in content if isinstance(b, dict) and b.get("type") == "image"]
        mime = (images[0].get("source") or {}).get("media_type", "") if images else None
        await _finish_round(session_id, msg_id, f"SAW_IMAGE:{mime}" if images else "NO_IMAGE")
        return

    sleep_m = _SLEEP_RE.search(prompt_text)
    if sleep_m:
        await asyncio.sleep(float(sleep_m.group(1)))

    wf = _WAITFOR_RE.match(prompt_text)
    if wf and mcp_session is not None:
        name, raw_args = wf.group(1).strip(), wf.group(2)
        args = json.loads(raw_args) if raw_args.strip() else {}
        changed = await _wait_for_list_changed(mcp_session, timeout=8.0)
        listed = await mcp_session.list_tools()
        present = any(t.name == name for t in listed.tools)
        text = await _run_one_call(mcp_session, session_id, msg_id, name, args)
        final_text = f"changed={changed} present={present} result={text}"
    else:
        results = []
        m1, m2 = _TOOL_RE.match(prompt_text), _TOOL2_RE.match(prompt_text)
        if m2:
            calls = []
            for part in m2.group(1).split("|"):
                name, _, raw_args = part.partition(":")
                calls.append((name.strip(), json.loads(raw_args) if raw_args.strip() else {}))
            _write({"type": "assistant", "message": {"id": msg_id, "role": "assistant",
                                                        "content": [{"type": "text", "text": "Calling tool(s)."}]},
                     "session_id": session_id})
            for i, (name, args) in enumerate(calls):
                results.append(await _run_one_call(mcp_session, session_id, msg_id, name, args))
                if i < len(calls) - 1:
                    # A real window for a steer sent right after this
                    # round started to actually land BEFORE the next call
                    # -- two real (fast) tool calls back to back leave no
                    # such window at all on their own. The window ends as
                    # soon as a line is waiting, or after
                    # FAKE_CLAUDE_CC_TOOL2_WINDOW_S (default 0.5 s): on a
                    # loaded Windows box the steer took longer than the
                    # old fixed half second to travel through the stream
                    # and became its own round, failing the absorption
                    # test only there.
                    window = float(os.environ.get("FAKE_CLAUDE_CC_TOOL2_WINDOW_S", "0.5") or 0.5)
                    waited = 0.0
                    while waited < window and line_queue.empty():
                        await asyncio.sleep(0.05)
                        waited += 0.05
                    absorbed_notes.extend(await _drain_absorbed(mcp_session, session_id, msg_id, line_queue))
        elif m1:
            name, raw_args = m1.group(1), m1.group(2)
            args = json.loads(raw_args) if raw_args.strip() else {}
            _write({"type": "assistant", "message": {"id": msg_id, "role": "assistant",
                                                        "content": [{"type": "text", "text": "Calling tool."}]},
                     "session_id": session_id})
            results.append(await _run_one_call(mcp_session, session_id, msg_id, name, args))
        elif "pong" in prompt_text.lower():
            results.append("pong")
        else:
            results.append("noted")
        final_text = " | ".join(results + absorbed_notes)

    await _finish_round(session_id, msg_id, final_text, control)


async def _finish_round(session_id: str, msg_id: str, final_text: str,
                          control: "_ControlState | None" = None) -> None:
    """Streamed text deltas (so `state.turn_had_deltas` is True on the
    parent side, the normal/common shape) + the closing `assistant`
    message + `result` -- shared by every non-error reply.

    Halo 2.0.5 round 1 (brief item H1 conformance: "the cut reply never
    reaches the transcript as a finished turn"): checked before EACH
    chunk -- a `control_request` `interrupt` that lands while this round
    is streaming (`_handle_control_request` sets `control.
    interrupt_event`, concurrently, via its own asyncio task) cuts it
    right there: whatever text already streamed stands, the rest is
    dropped, and the round's own `result` is a plain (`is_error=False`)
    success carrying ONLY that partial text -- never the full reply the
    interrupt cut short. The event is cleared here (not by the
    interrupter) so it can never also cut the NEXT, unrelated round."""
    emitted = ""
    for chunk in (final_text[:1] or " "), final_text[1:]:
        if control is not None and control.interrupt_event.is_set():
            break
        if chunk:
            _write({"type": "stream_event",
                     "event": {"type": "content_block_delta", "index": 0,
                               "delta": {"type": "text_delta", "text": chunk}},
                     "session_id": session_id})
            emitted += chunk
    if control is not None and control.interrupt_event.is_set():
        control.interrupt_event.clear()
        _write({"type": "assistant", "message": {"id": msg_id, "role": "assistant",
                                                    "content": [{"type": "text", "text": emitted}]},
                 "session_id": session_id})
        # Deliberately `is_error=True` -- the REAL binary's own exact
        # shape for an interrupted result is unverified (every probe
        # that could have reached a genuine in-flight interrupt needed
        # real auth, see docs/harness/CC-CONTROL-CHANNEL.md); this fake
        # exercises halo's WORST-CASE defense (`cc_runtime.py`'s
        # `expect_interrupted_result` suppression + "turn_is_error
        # reflects only the latest result" fix) deliberately, rather
        # than the easier shape that would never have caught either bug.
        _write_result(session_id, emitted, is_error=True, subtype="interrupted")
        return
    _write({"type": "assistant", "message": {"id": msg_id, "role": "assistant",
                                               "content": [{"type": "text", "text": final_text}]},
             "session_id": session_id})
    _write_result(session_id, final_text)


async def _drain_absorbed(mcp_session, session_id: str, msg_id: str, line_queue) -> list:
    """Non-blocking: everything ALREADY sitting on `line_queue` right now
    (sent while THIS round was running) -- echoed and folded into this
    same round (critical finding 1's "absorbed" shape); a `TOOL:` line
    among them is actually called too."""
    notes = []
    while True:
        try:
            line = line_queue.get_nowait()
        except asyncio.QueueEmpty:
            return notes
        if line is _EOF:
            continue
        _echo(line, session_id)
        text = _extract_text(line)
        m = _TOOL_RE.match(text)
        if m:
            name, raw_args = m.group(1), m.group(2)
            args = json.loads(raw_args) if raw_args.strip() else {}
            notes.append(await _run_one_call(mcp_session, session_id, msg_id, name, args))
        else:
            notes.append(f"(absorbed: {text[:40]})")


class _ListChanged:
    event: "asyncio.Event | None" = None


async def _wait_for_list_changed(mcp_session, *, timeout: float) -> bool:
    if _ListChanged.event is None:
        return False
    try:
        await asyncio.wait_for(_ListChanged.event.wait(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False


async def _serve_turns(mcp_session, session_id: str, tools_wire: list) -> None:
    control_on = _control_enabled()
    control = _ControlState()
    init_line = {"type": "system", "subtype": "init", "session_id": session_id, "tools": tools_wire,
                 "mcp_servers": ([{"name": "rolo", "status": "connected"}] if mcp_session is not None else []),
                 "model": "fake-model", "permissionMode": "bypassPermissions",
                 "claude_code_version": _fake_version()}
    if control_on:
        # Halo 2.0.5 round 1 (cc: route v2): live-verified field on the
        # REAL installed 2.1.291 -- see `_FAKE_CAPABILITIES`'s own
        # comment. Absent entirely when the switch is off, the correct
        # stand-in for an older claude that pre-dates this field.
        init_line["capabilities"] = _FAKE_CAPABILITIES
    _write(init_line)
    loop = asyncio.get_event_loop()
    line_queue: "asyncio.Queue" = asyncio.Queue()

    async def _reader() -> None:
        while True:
            raw_line = await loop.run_in_executor(None, sys.stdin.readline)
            if raw_line == "":
                await line_queue.put(_EOF)
                return
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                parsed = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed.get("type") == "control_request":
                if control_on:
                    # Answered concurrently, never blocking this reader
                    # (and never put on `line_queue` -- a control_request
                    # is not a "round" input) -- the real claude binary
                    # answers one mid-turn the same way.
                    asyncio.create_task(_handle_control_request(parsed, session_id, control))
                # Switch off: silently dropped, no response ever -- the
                # correct stand-in for an old claude that doesn't
                # understand `control_request` at all (halo's own
                # `cc_control.request_control` times out and caches
                # "unsupported", never hangs forever).
                continue
            await line_queue.put(parsed)

    reader_task = asyncio.create_task(_reader())
    turn_index = 0
    try:
        while True:
            first = await line_queue.get()
            if first is _EOF:
                return
            # critical finding 1 "a batch of queued lines as one combined
            # reply": everything ELSE already sitting on `line_queue` at
            # this exact moment (e.g. two steers sent while a slow prior
            # round was still running, both waiting by the time THIS
            # follow-up round starts) rides along in the SAME round.
            batch = [first]
            while True:
                try:
                    nxt = line_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if nxt is _EOF:
                    break
                batch.append(nxt)
            turn_index += 1
            await _run_round(mcp_session, session_id, batch, turn_index, line_queue, control)
    finally:
        reader_task.cancel()


async def _amain(argv: "list[str]") -> int:
    opts = _parse_argv(argv)
    session_id, ok = _validate_session_id(opts)
    if not ok:
        return 1
    mcp_config_raw = opts.get("mcp-config") or '{"mcpServers":{}}'
    try:
        mcp_config = json.loads(mcp_config_raw)
    except json.JSONDecodeError:
        mcp_config = {"mcpServers": {}}
    rolo_cfg = (mcp_config.get("mcpServers") or {}).get("rolo")

    if not rolo_cfg:
        await _serve_turns(None, session_id, _connector_tool_names())
        return 0

    from mcp import ClientSession
    import mcp.types as types
    from mcp.client.stdio import StdioServerParameters, stdio_client

    env = dict(os.environ)
    env.update({str(k): str(v) for k, v in (rolo_cfg.get("env") or {}).items()})
    params = StdioServerParameters(command=rolo_cfg["command"], args=rolo_cfg.get("args") or [], env=env)
    _ListChanged.event = asyncio.Event()

    async def _message_handler(message) -> None:
        if isinstance(message, types.ToolListChangedNotification):
            _ListChanged.event.set()

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, message_handler=_message_handler) as mcp_session:
            await mcp_session.initialize()
            listed = await mcp_session.list_tools()
            tools_wire = [f"mcp__rolo__{t.name}" for t in listed.tools] + _connector_tool_names()
            await _serve_turns(mcp_session, session_id, tools_wire)
    return 0


def main(argv=None) -> int:
    # W4b connectors-bridge tests: real claude.ai status text carries
    # "✔"/"✗" glyphs -- Windows' own default console codepage
    # (cp1252) can't encode them, which crashed this CHILD process's own
    # `print`/`sys.stdout.write` before a single byte ever reached the
    # parent (verified live). Real `claude`, a Node binary, defaults to
    # UTF-8 regardless of host locale; this fake, being Python, needs to
    # say so explicitly. Best-effort: a stream that refuses to reconfigure
    # (rare, e.g. already closed) just keeps its old behaviour.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    argv = sys.argv[1:] if argv is None else argv
    _log_argv(argv)
    if len(argv) >= 2 and argv[0] == "auth" and argv[1] == "status":
        _write(_auth_status_json())
        return 0
    if argv and argv[0] == "--version":
        # finding 23: doctor now reads THIS, never claude auth status's
        # own JSON (which has no version key at all, verified live).
        # Halo 2.0.5 round 1: `FAKE_CLAUDE_CC_VERSION` overrides this
        # (and `system.init`'s own `claude_code_version`, `_fake_
        # version()`) so a test can simulate a version below
        # `cc_tested.json`'s window.
        print(f"{_fake_version()} (Claude Code)")
        return 0
    if len(argv) >= 2 and argv[0] == "mcp" and argv[1] == "list":
        return _cmd_mcp_list()
    if not argv or argv[0] != "-p":
        # Any other invocation -- harmless no-op.
        return 0
    if _output_format(argv) == "json":
        return _one_shot_json(argv)
    return asyncio.run(_amain(argv))


if __name__ == "__main__":
    sys.exit(main())
