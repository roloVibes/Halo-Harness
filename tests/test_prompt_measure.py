"""tests.test_prompt_measure -- Halo 3.3.16.1 "the local prompt diet": what a first turn costs before it is
sent (agent/prompt_measure.py) and everywhere it is shown. In-process, a fake home of its own (its MEMORY.md
and topic files), never a server or a model call:

1. `first_turn`: the composition, the reply's room, the window it goes out at, a row per tool (offered or
   left out and why);
2. `halo local prompt <ref> --window N` prints the line and the rows; `--json` the measure;
3. `/status` gains "Halo's own first turn: N tokens of W (P %)" on a local model (not on a cloud one);
   `halo doctor`'s default-model row the same note;
4. Studio's model card: a row "Halo's first turn: N tokens (P % of the window)" in its `how` list;
5. the steward: `prompt-heavy` past half the window, with one next step (the lean profile on, a bigger
   window, the core tools); the fit plan's floor is the measured first turn.
Run: python -m tests.test_prompt_measure
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="pb_measure-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")
os.environ.setdefault("OLLAMA_HOST", "http://127.0.0.1:9")

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_HOME: dict = {}


class _In:
    """The working directory for one block (the CLI and Studio's card measure the process's cwd), put back after."""

    def __init__(self, path):
        self.path, self.was = path, None

    def __enter__(self):
        self.was = os.getcwd()
        os.chdir(self.path)

    def __exit__(self, *exc):
        os.chdir(self.was)


def _proj() -> Path:
    if "fh" not in _HOME:
        from tests.helpers.fake_home import build_fake_home
        _HOME["fh"] = build_fake_home()
        os.environ["BRIDGE_TEST_HOME"] = str(_HOME["fh"]["home"])
    return _HOME["fh"]["proj"]


@test
def test_first_turn_says_what_it_is_made_of(ctx: Ctx):
    from halo_harness.agent.prompt_measure import first_turn, first_turn_line
    m = first_turn("ol:qwen3-coder:30b@lan", window=32768, platform="win32", cwd=_proj())
    rows = {r["name"]: r for r in m["tools"]}
    ctx.check(f"the parts add up to the prompt, got {m['line']}", m["line"].startswith(f"prompt {m['prompt']:,}: system "))
    ctx.check(f"the room and the window, got {m['reply_room']} {m['sent_window']}", (m["reply_room"], m["sent_window"]) == (8192, 32768))
    ctx.check("Task: the same tool as Agent", not rows["Task"]["offered"] and "the same tool as Agent" in rows["Task"]["why"])
    ctx.check("PowerShell or Bash: the other shell, reachable", any(not rows[s]["offered"] and "ToolSearch" in rows[s]["why"]
                                                                    for s in ("PowerShell", "Bash")))
    ctx.check(f"the core tools offered as core, got {rows['Read']}", rows["Read"]["offered"] and rows["Read"]["why"] == "core")
    ctx.check(f"the line, got {first_turn_line(m)!r}", first_turn_line(m) ==
              f"Halo's own first turn: {m['prompt']:,} tokens of 32,768 ({m['share']:.0f} %)")


@test
def test_the_measure_is_the_session_a_person_really_gets(ctx: Ctx):
    """3.6.0.19 LM: `halo local prompt` (and /status, Studio's card, halo doctor) measures the session a person really
    gets: a top session someone answers has the Builder (tools/builder_tool.wanted, the one rule headless.build_session
    applies), a one-shot (print mode) has none, and /status measures the session's own registry."""
    from halo_harness.agent.prompt_measure import first_turn, for_session, new_session
    from halo_harness.tools.builder_tool import wanted
    cwd = _proj()
    ref = "ol:qwen3-coder:30b@lan"
    m = first_turn(ref, window=32768, platform="linux", cwd=cwd)
    real = first_turn(ref, window=32768, platform="linux", cwd=cwd, builder=True)
    rows = {r["name"]: r for r in m["tools"]}
    ctx.check(f"a Builder row, offered, got {rows.get('Builder')}", rows.get("Builder", {}).get("offered") is True)
    ctx.check(f"the prompt is the real session's, got {m['prompt']:,} vs {real['prompt']:,}", m["prompt"] == real["prompt"])
    one = first_turn(ref, window=32768, platform="linux", cwd=cwd, one_shot=True)
    ctx.check("a one-shot (print mode) has no Builder", "Builder" not in [r["name"] for r in one["tools"]])
    ctx.check("the one rule: a session someone answers", wanted() is True and wanted(tools="default") is True)
    ctx.check("bare, print mode, --disallowedTools Builder, --tools without it: none",
              not any((wanted(bare=True), wanted(print_mode=True), wanted(disallow=["Builder"]), wanted(tools="Read,Bash"))))
    from halo_harness.agent.prompt_measure import _first_request
    for has in (False, True):  # 3.6.0.20 P: /status reads the session's own log (here a new session's, before a request)
        s = _first_request(ref, window=32768, cwd=cwd, builder=has)[0]
        s.cwd = cwd
        got = for_session(s)
        names = [r["name"] for r in (got or {}).get("tools") or []]
        ctx.check(f"/status measures the session's own registry (Builder {has}), got {'Builder' in names}",
                  got is not None and ("Builder" in names) == has)


def _start_mode(cwd) -> str:
    """The mode a new session with no flag starts in, in `cwd`, on the map in use now (crew/map_session's one rule)."""
    from halo_harness.crew.map_session import configured_mode, start
    return start(None, cwd=cwd, resolved=configured_mode(cwd))[0]


def _turn_start_lines(ref, cwd, mode):
    """(the mode line, the reminder) a new session's first turn logs, through the loop's own functions."""
    from halo_harness.agent.helpers_words import remind
    from halo_harness.agent.mode_notice import mode_line
    from halo_harness.agent.prompt_measure import new_session
    return mode_line(mode), remind(new_session(ref, window=32768, platform="linux", cwd=cwd))


@test
def test_first_turn_counts_the_mode_line_and_the_reminder(ctx: Ctx):
    """3.6.0.15 F9: `halo local prompt` weighs what a first request really sends: the permission mode line always, the
    reminder for a local main on Auto, each its own named row, the total holding them."""
    from halo_harness.agent.prompt_composition import tokens_of
    from halo_harness.agent.prompt_measure import _first_request, first_turn
    from halo_harness.providers.ollama_wire_estimate import wire_estimate
    from halo_harness.theme import get_config_value, set_config_value, unset_config_value
    cwd = _proj()
    for ref, local in (("ol:qwen3-coder:30b@lan", True), ("ant:claude-opus-5-5", False)):
        mode = _start_mode(cwd)
        m = first_turn(ref, window=32768, platform="linux", cwd=cwd)
        _s, _full, system_text, messages, sent = _first_request(ref, window=32768, platform="linux", cwd=cwd, mode=mode)
        real = wire_estimate(system_text, messages, sent) - 1024
        ctx.check(f"{ref}: the prompt is the request built with the turn's start lines, got {m['prompt']} vs {real}",
                  m["prompt"] == real and m["total"] == m["prompt"] + m["reply_room"])
        line, reminder = _turn_start_lines(ref, cwd, mode)
        want = [{"name": "mode line", "tokens": tokens_of(line), "text": line}]
        if local:
            ctx.check(f"a local main on Auto has a reminder, got {reminder!r}", bool(reminder))
            want.append({"name": "reminder", "tokens": tokens_of(reminder), "text": reminder})
        else:
            ctx.check(f"a cloud main has none, got {reminder!r}", reminder == "")
        ctx.check(f"{ref}: the rows, got {m.get('turn_start')!r}", m.get("turn_start") == want
                  and all(r["tokens"] > 0 for r in want))
    was = get_config_value("permission_mode", default=None)
    try:
        set_config_value("permission_mode", "acceptEdits")
        m = first_turn("ol:qwen3-coder:30b@lan", window=32768, platform="linux", cwd=cwd)
        from halo_harness.agent.mode_notice import mode_line
        got = (m.get("turn_start") or [{}])[0]
        ctx.check(f"config acceptEdits: the mode line row says that mode, got {got!r}",
                  got.get("text") == mode_line(_start_mode(cwd)) and "acceptEdits" in got.get("text", ""))
    finally:
        if was is None:
            unset_config_value("permission_mode")
        else:
            set_config_value("permission_mode", was)


@test
def test_halo_local_prompt_prints_the_line_and_the_rows(ctx: Ctx):
    from halo_harness.local_cli import cmd_local
    out = io.StringIO()
    with _In(_proj()), redirect_stdout(out):
        rc = cmd_local(["prompt", "ol:qwen3-coder:30b@lan", "--window", "49152", "--platform", "linux"])
    text = out.getvalue()
    ctx.check(f"exit 0 and the first-turn line, got {rc} {text[:300]!r}", rc == 0 and "Halo's own first turn:" in text
              and "of 49,152" in text and "reply's room 12,288" in text)
    ctx.check("a row per tool, offered or left out", "  Read " in text and "offered" in text and "left out" in text)
    # 3.6.0.15 F9: the turn's start lines, each its own row, ending with the line letter for letter
    line, reminder = _turn_start_lines("ol:qwen3-coder:30b@lan", _proj(), _start_mode(_proj()))
    rows = text.splitlines()
    ctx.check(f"the mode line row, got {[r for r in rows if 'mode line' in r]!r}",
              any(r.startswith("  mode line ") and r.endswith(line) and " sent " in r for r in rows))
    ctx.check(f"the reminder row, got {[r for r in rows if r.startswith('  reminder')]!r}",
              bool(reminder) and any(r.startswith("  reminder ") and r.endswith(reminder) for r in rows))
    out = io.StringIO()
    with _In(_proj()), redirect_stdout(out):
        rc = cmd_local(["prompt", "ol:qwen3-coder:30b@lan", "--window", "16384", "--json"])
    got = json.loads(out.getvalue())
    ctx.check(f"--json: the measure, got {sorted(got)[:6]}", rc == 0 and got["sent_window"] == 16384 and got["tools"])
    ctx.check(f"--json: the turn's start rows, got {got.get('turn_start')!r}",
              [r.get("name") for r in got.get("turn_start") or []] == ["mode line", "reminder"])


@test
def test_status_and_doctor_say_the_first_turn_on_a_local_model(ctx: Ctx):
    from halo_harness.agent.prompt_measure import composition_text, doctor_note
    from halo_harness.model import parse_model_ref
    comp = {"system": {"tokens": 1, "parts": {"harness": 1, "claude_md": 0, "memory": 0, "topic_index": 0, "tools_schema": 0}},
            "history": {"tokens": 0, "turns": 0}, "user": {"tokens": 1, "parts": {"text": 1, "memory": 0, "topic_index": 0,
                                                                                   "attachments": 0}}, "total": 2}
    from halo_harness.agent.prompt_measure import _first_request  # 3.6.0.20 P: /status reads the session's own log
    local = _first_request("ol:qwen3-coder:30b@lan", window=49152, cwd=_proj())[0]
    local._prompt_composition, local.cwd = comp, _proj()
    text = composition_text(local, first=True)
    ctx.check(f"/status on a local model: the composition, then the first turn, got {text!r}",
              text.startswith("prompt 2:") and "\nHalo's own first turn: " in text and "of 49,152" in text)
    cloud = SimpleNamespace(model_ref=parse_model_ref("ant:claude-opus-5-5"), _prompt_composition=comp, cwd=_proj())
    ctx.check("a cloud model: the composition only", "first turn" not in composition_text(cloud, first=True))
    ctx.check("/cost: the composition only", "first turn" not in composition_text(local))
    note = doctor_note(parse_model_ref("ol:qwen3-coder:30b@lan"), _proj())
    ctx.check(f"halo doctor's default-model row on a local model, got {note!r}", note.startswith(" · Halo's own first turn: "))
    ctx.check("and nothing on a cloud model", doctor_note(parse_model_ref("ant:claude-opus-5-5"), _proj()) == "")


def _children() -> int:
    try:
        import psutil
        return len(psutil.Process().children(recursive=True))
    except Exception:
        return 0


def _cached_tools(server: str, n: int) -> list:
    from halo_harness.mcp.tools_cache import tool_from_dict
    return [tool_from_dict({"name": f"page_action_{i:02d}", "description": f"{server}: action {i} on a page.",
                            "input_schema": {"type": "object", "properties": {"page": {"type": "string"}}}})
            for i in range(n)]


@test
def test_halo_local_prompt_counts_the_other_tool_servers_from_halos_cache(ctx: Ctx):
    """3.6.0.20 P entry 2: `halo local prompt` weighs what a session in this folder sends: the other tool servers'
    lines and their tools from Halo's own cache of their tool lists (mcp/tools_cache.py), nothing started (no thread,
    no process); a lean model gets the lines with their counts, a model that is not lean the block of names; a server
    with no usable cache (none, or one made for other settings) is named as not counted."""
    import threading
    from halo_harness.agent.catalog import deferred_reminder
    from halo_harness.agent.prompt_composition import tokens_of
    from halo_harness.agent.prompt_measure import _first_request, first_turn
    from halo_harness.config.claude_json import load_claude_json
    from halo_harness.local_cli import cmd_local
    from halo_harness.mcp import tools_cache
    from halo_harness.mcp_setup import server_configs
    from tests.helpers.fake_home import build_fake_home
    was = os.environ.get("BRIDGE_TEST_HOME")
    fh = build_fake_home()
    stand_ins = {n: {"type": "stdio", "command": "python", "args": ["-c", "pass"]} for n in ("gpu-box-tools", "kb", "notes")}
    (fh["home"] / ".claude.json").write_text(json.dumps({"mcpServers": stand_ins}), encoding="utf-8")
    os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
    try:
        proj, ref = fh["proj"], "ol:example-model:30b"
        configs = server_configs(cwd=proj, claude_json=load_claude_json())[0]
        for name in ("kb", "notes"):
            tools_cache.write_cache(name, key=tools_cache.config_cache_key(configs[name]), tools=_cached_tools(name, 60),
                                    instructions=f"Keeps {name} pages. Reads them back.")
        tools_cache.write_cache("gpu-box-tools", key="made-for-other-settings", tools=_cached_tools("gpu", 60),
                                instructions="A stale cache.")
        before = first_turn(ref, window=16384, platform="linux", cwd=proj)
        threads, kids = threading.active_count(), _children()
        m = first_turn(ref, window=16384, platform="linux", cwd=proj, servers=True)
        ctx.check(f"no thread and no process made, got {threading.active_count()} {_children()} (was {threads} {kids})",
                  (threading.active_count(), _children()) == (threads, kids))
        ctx.check(f"the facts, got {m.get('other_servers')!r}",
                  m.get("other_servers") == {"servers": 2, "tools": 120, "not_counted": ["gpu-box-tools"]})
        _s, _f, lean, msgs, _t = _first_request(ref, window=16384, platform="linux", cwd=proj, servers=True)
        ctx.check(f"lean: the lines with their counts, got {lean[lean.find('- MCP servers'):][:300]!r}",
                  "  - `kb` (60 tools): Keeps kb pages." in lean and "  - `notes` (60 tools): Keeps notes pages." in lean
                  and "gpu-box-tools" not in lean and "page_action_" not in json.dumps(msgs))
        ctx.check(f"lean: the prompt grows by the lines, got {before['prompt']:,} -> {m['prompt']:,}",
                  0 < m["prompt"] - before["prompt"] <= 600)
        cloud = "ant:claude-opus-5-5"
        _s, _f, _sys, msgs, _t = _first_request(cloud, window=200000, platform="linux", cwd=proj, servers=True)
        names = sorted(f"mcp__{s}__page_action_{i:02d}" for s in ("kb", "notes") for i in range(60))
        block = deferred_reminder(names)
        ctx.check("not lean: the block of the 120 names, as a session logs it",
                  any(b.get("text") == block for msg in msgs for b in msg.get("content") or [] if isinstance(b, dict)))
        a = first_turn(cloud, window=200000, platform="linux", cwd=proj)
        b = first_turn(cloud, window=200000, platform="linux", cwd=proj, servers=True)
        ctx.check(f"not lean: the prompt grows by the block and the lines, got {a['prompt']:,} -> {b['prompt']:,}",
                  b["prompt"] - a["prompt"] >= tokens_of(block))
        ctx.check(f"the composition names the block as its own part, got {b['line']!r}",
                  f"other servers' tools {tokens_of(block):,}" in b["line"])
        out = io.StringIO()
        with _In(proj), redirect_stdout(out):
            rc = cmd_local(["prompt", ref, "--window", "16384", "--platform", "linux"])
        text = out.getvalue()
        ctx.check(f"the two lines word for word, got {text[:600]!r}", rc == 0 and
                  "other tool servers: 2, 120 tools (from Halo's cache of their tool lists; none was started)" in text
                  and "not counted: the tools of 1 other tool server (gpu-box-tools); a session's /status counts them"
                  in text)
        out = io.StringIO()
        with _In(proj), redirect_stdout(out):
            rc = cmd_local(["prompt", ref, "--window", "16384", "--json"])
        got = json.loads(out.getvalue())
        ctx.check(f"--json carries the same facts, got {got.get('other_servers')!r}",
                  got.get("other_servers") == {"servers": 2, "tools": 120, "not_counted": ["gpu-box-tools"]})
    finally:
        if was is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = was


def _figure(text: str) -> int:
    import re
    m = re.search(r"Halo's own first turn: ([\d,]+) tokens", text or "")
    return int(m.group(1).replace(",", "")) if m else -1


@test
def test_status_says_the_sessions_own_first_request(ctx: Ctx):
    """3.6.0.20 P entry 3: `/status` in a live session says the session's OWN first request: before any request the
    preview of its own log, registry and snapshots (here: `--tools` left four tools, 16 stand-in servers' block); kept
    when the conversation's first main request is shaped, not moved by a later one; after `/clear` or a compaction the
    NEW conversation's first request; on a model switch (a request at the new model or not) and in a resumed session,
    the preview of the conversation's FIRST request (its log up to its first answer), never the whole conversation."""
    from halo_harness.agent.catalog import deferred_reminder
    from halo_harness.agent.derive import derive_request
    from halo_harness.agent.prompt_composition import compose, known_texts
    from halo_harness.agent.prompt_measure import _Nodes, composition_text, first_turn, new_session
    from halo_harness.agent.prompt_wire import placement_for, shape
    from halo_harness.model import parse_model_ref
    from halo_harness.providers.ollama_wire_estimate import wire_estimate
    ref, cwd = "ol:example-model:30b", _proj()
    s = new_session(ref, window=16384, platform="linux", cwd=cwd)
    s.cwd = cwd
    s.tool_registry = s.tool_registry.filtered(["Read", "Grep", "Bash", "ToolSearch"])
    names = sorted(f"mcp__srv{n:02d}-craft__tool_action_{t:02d}" for n in range(16) for t in range(60))

    def _start(log, words="hi"):
        log.add(type="meta", model=ref, tools=s.tool_registry.definitions())
        log.add(type="system", text=s.session_context.system_prompt)
        log.add(type="snapshot", kind="environment", content=[{"type": "text", "text": "Platform: linux"}])
        log.add(type="snapshot", kind="deferred_tools", content=[{"type": "text", "text": deferred_reminder(names)}])
        log.add(type="user", content=[{"type": "text", "text": words}])

    def _own(purpose="measure", upto=None):  # the request shaped as the loop shapes it, weighed by the measure's rule
        out = shape(s, *derive_request(s.log, upto=upto), purpose=purpose)
        total = compose(s, out[1], out[2], out[0], placement=placement_for(s), known=known_texts(s))["total"]
        weighed = wire_estimate(*out) - 1024
        ctx.check(f"the measure's rule is the composition's within 3 %, got {weighed} vs {total}",
                  abs(weighed - total) <= 0.03 * total)
        return weighed

    _start(s.log)
    want = _own()
    default = first_turn(ref, window=16384, platform="linux", cwd=cwd)["prompt"]
    got = _figure(composition_text(s, first=True))
    ctx.check(f"before any request: the session's own preview, got {got:,} want {want:,} (a new default session's "
              f"{default:,})", got == want and abs(default - want) > 0.05 * want)
    first = _own("turn")
    s.log.add(type="assistant", content=[{"type": "text", "text": "ok"}])
    s.log.add(type="user", content=[{"type": "text", "text": "and now a long ask " * 600}])
    _own("turn")
    got = _figure(composition_text(s, first=True))
    ctx.check(f"a later request does not move it, got {got:,} want {first:,}", got == first)
    s.log = _Nodes()  # /clear: a new log (agent/loop.py's clear)
    _start(s.log, "a new conversation " * 300)
    fresh = _own("turn")
    got = _figure(composition_text(s, first=True))
    ctx.check(f"after /clear: the new conversation's first request, got {got:,} want {fresh:,}",
              got == fresh and abs(fresh - first) > 0.05 * first)
    s.log.add(type="assistant", content=[{"type": "text", "text": "ok"}])
    s.log.add(type="compacted", trigger="manual")
    s.log.add(type="user", content=[{"type": "text", "text": "<compacted-summary>short</compacted-summary>"}])
    s.log.add(type="snapshot", kind="deferred_tools", content=[{"type": "text", "text": deferred_reminder(names)}])
    after = _own("turn")
    got = _figure(composition_text(s, first=True))
    ctx.check(f"after a compaction: the new conversation's first request, got {got:,} want {after:,}",
              got == after and abs(after - fresh) > 0.05 * fresh)
    at_first = len(s.log.nodes())  # the conversation's first request was made of these nodes
    for i in range(4):  # a longer conversation at the same model
        s.log.add(type="assistant", content=[{"type": "text", "text": "ok " * 200}])
        s.log.add(type="user", content=[{"type": "text", "text": f"ask {i} " * 400}])
        _own("turn")
    s.model_ref = parse_model_ref("ol:other-model:8b")
    want = _own(upto=at_first)
    got = _figure(composition_text(s, first=True))
    ctx.check(f"a model switch with no request yet: the conversation's first request at the new model, got {got:,} "
              f"want {want:,} (the whole conversation: {_own():,})", got == want and _own() > 2 * want)
    sent = _own("turn")
    got = _figure(composition_text(s, first=True))
    ctx.check(f"a request at the new model does not make it the whole conversation, got {got:,} want {want:,} "
              f"(sent {sent:,})", got == want)
    s.model_ref = parse_model_ref(ref)
    got = _figure(composition_text(s, first=True))
    ctx.check(f"back at the first model: its kept first request, got {got:,} want {after:,}", got == after)
    resumed = new_session(ref, window=16384, platform="linux", cwd=cwd)  # a resumed session: its log, no request yet
    resumed.cwd, resumed.tool_registry, resumed.log = cwd, s.tool_registry, s.log
    s = resumed
    want = _own(upto=at_first)
    got = _figure(composition_text(s, first=True))
    ctx.check(f"a resumed session before its first request: the conversation's first request, got {got:,} "
              f"want {want:,}", got == want and _own() > 2 * want)


@test
def test_the_model_card_has_the_row(ctx: Ctx):
    from halo_harness.agent.prompt_measure import card_line
    from halo_harness.studio.model_card_api import view
    with _In(_proj()):
        line = card_line("ol:qwen3-coder:30b@lan", 49152)
        card = {"ref": "ol:qwen3-coder:30b@lan", "how": ["calls it with tools"], "window": {"tokens": 49152, "source": "trained"}}
        how = view(card, None)["card"]["how"]
    ctx.check(f"the row, got {line!r}", bool(line) and line.startswith("Halo's first turn: ") and line.endswith("% of the window)"))
    ctx.check(f"a row of its own after the card's own, got {how}", how[0] == "calls it with tools" and how[1] == line)
    ctx.check("a cloud model's card: no row", card_line("ant:claude-opus-5-5", 200000) is None)


def _group(own: int, window: int, cap=None, profile=None) -> dict:
    line = {"at": "2026-11-10T12:00:00Z", "num_ctx_sent": window, "dialect": "ollama", "status": 200,
            "composition": {"system": own // 2, "memory": own // 4, "topic_index": 0, "tools_schema": own - own // 2 - own // 4,
                            "history": 10, "user": 5, "total": own + 15}}
    return {"host": "lan", "model": "qwen3-coder:30b", "key": "lan|qwen3-coder:30b", "cap": cap,
            "profile": profile or {}, "stats": {"native": [line]}}


@test
def test_the_steward_says_prompt_heavy_with_one_next_step(ctx: Ctx):
    from halo_harness.ollama_steward.rules_prompt import prompt_heavy
    from halo_harness.theme import set_config_value, unset_config_value
    ctx.check("under half: nothing", prompt_heavy(_group(6000, 16384), {}) == [])
    f = prompt_heavy(_group(9000, 16384, cap=65536), {})
    ctx.check(f"over half with room to grow: a bigger window, got {f}", len(f) == 1 and f[0]["rule"] == "prompt-heavy"
              and f[0]["proposal"]["field"] == "num_ctx" and f[0]["proposal"]["to"] == 32768)
    f = prompt_heavy(_group(9000, 16384, cap=16384), {})
    ctx.check(f"at the cap: the core tools, got {f[0]['proposal']}", f[0]["proposal"]["field"] == "tools_max")
    set_config_value("prompt.lean", "off")
    try:
        f = prompt_heavy(_group(9000, 16384, cap=65536), {})
    finally:
        unset_config_value("prompt.lean")
    ctx.check(f"the lean profile off: turn it on, got {f[0]['server_hint']}", f[0]["proposal"] is None
              and "prompt.lean auto" in f[0]["server_hint"]["line"])


@test
def test_the_fit_plan_floor_is_the_measured_first_turn(ctx: Ctx):
    from halo_harness.agent.prompt_measure import first_turn, first_turn_floor
    from halo_harness.ollama_steward.fit import FLOOR, floor_window
    with _In(_proj()):
        lean = first_turn("ol:model", window=16384)["prompt"]
        got, planner = first_turn_floor(), floor_window()
    ctx.check(f"Halo's leanest first turn ({lean}) plus a reply, in steps of 4,096, never under 8,192, got {got}",
              got % 4096 == 0 and got >= max(FLOOR, lean + 4096) and got - 4096 < max(FLOOR, lean + 4096))
    ctx.check("the planner reads it", planner == got)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
