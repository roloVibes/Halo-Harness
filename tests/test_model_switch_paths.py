"""tests.test_model_switch_paths -- Halo 3.3.5.0 R0: the switch step's other
callers, through the loop rig (tests/helpers/model_switch_rig.py; a fake
Ollama on 127.0.0.1:0, no model call):

1. a child on another model than its parent's (the Auto lineup's per-task
   pick): its first request fits -- the prompt cut to the child's window with
   the one line at the cut, the switch line first, a `model_switch` node;
2. the compaction model's own window, checked before the summary call: a
   conversation larger than it is summarised from a transcript cut to fit;
3. a steward profile that lowers the window below the live prompt: the line,
   then the compaction (trigger "switch") before the call;
4. a session resumed on another model than it last ran on: the step at start;
5. the steward: a call to another model with no fit step is flagged
   (`switch-without-fit`); the history conversion on the Anthropic dialect;
   the lineup-apply answer is one line.
Run: python -m tests.test_model_switch_paths
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="m0-paths-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.model_switch_rig import Rig, fill, markers  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_a_child_on_another_model_fits_its_first_request(ctx: Ctx):
    from halo_harness.agent.subagent import _run_child_to_completion
    with Rig() as rig:
        child = rig.session("ol:small:9b@lan")
        child._parent_model_raw = "ol:big:30b@lan"
        prompt = "Summarise these notes. " + ("a long pasted log line\n" * 7000)
        evs = _run_child_to_completion(child, prompt, agent_id="a1", parent_tool_use_id="t1")
        first = evs[0]
        ctx.check(f"the child's first event is the switch line, got {first.kind} {first.data.get('text')!r}",
                  first.kind == "turn_marker" and first.data.get("state") == "switch" and first.data["text"].startswith(
                      "the task runs on ol:small:9b@lan: window 32,768 (learned cap); the task is ") and "-> cut to fit" in first.data["text"])
        body = rig.chats("small:9b")[0]
        wire = json.dumps(body["messages"])
        ctx.check("the prompt reached the child cut, with the line at the cut",
                  "tokens of this task's text were cut to fit ol:small:9b@lan's window (32,768 tokens)" in wire
                  and wire.count("a long pasted log line") < 7000)
        ctx.check(f"the first call fits the window, got {body.get('options')}", (body.get("options") or {}).get("num_ctx", 0) <= 32768)
        node = next((n for n in child.log._nodes if n.get("type") == "model_switch"), {})
        ctx.check("the child's transcript has the switch report", (node.get("report") or {}).get("why") == "auto")
        same = rig.session("ol:small:9b@lan")
        same._parent_model_raw = "ol:small:9b@lan"
        evs = _run_child_to_completion(same, "hi", agent_id="a2", parent_tool_use_id="t2")
        ctx.check("a child on its parent's model has no switch step", not markers(evs))


@test
def test_the_compaction_models_own_window(ctx: Ctx):
    from halo_harness.agent.compact import CompactionKnobs
    with Rig() as rig:
        s = rig.session("ol:big:30b@lan")
        fill(s, 45)
        s._compaction_knobs = CompactionKnobs(compaction_model="ol:small:9b@lan")
        evs = list(s._run_compaction(1, trigger="manual"))
        cut = [t for t in markers(evs, "resend") if "is larger than ol:small:9b@lan's window (32,768)" in t]
        ctx.check(f"the summariser's window is checked first, got {markers(evs, 'resend')}", len(cut) == 1)
        done = [e for e in evs if e.kind == "compaction" and e.data.get("phase") == "done"]
        ctx.check("the compaction still completes", len(done) == 1)
        body = rig.chats("small:9b")[0]
        ctx.check(f"the summary call to the small model holds a flattened transcript and no tools, got {len(body['messages'])} messages",
                  not body.get("tools") and len(json.dumps(body["messages"])) < 4 * 32768)
        ctx.check("the session is back on its own model", s.model_ref.raw == "ol:big:30b@lan")


@test
def test_a_profile_that_lowers_the_window(ctx: Ctx):
    from halo_harness import events
    from halo_harness.ollama_steward.profiles import key_for, set_field
    with Rig() as rig:
        set_field(key_for("lan", "mid:14b"), "num_ctx", 65536, by="user")
        s = rig.session("ol:mid:14b@lan")
        fill(s, 30)
        evs = rig.run(s, [events.Command("user_input", {"text": "first"})])
        ctx.check(f"the first call fits the profile's window, got {markers(evs)}", not markers(evs))
        set_field(key_for("lan", "mid:14b"), "num_ctx", 32768, by="steward", note="lowered for the test")
        rig.mock.clear()
        evs = rig.run(s, [events.Command("user_input", {"text": "second"})])
        lines = markers(evs)
        ctx.check(f"the line names the lowered window, got {lines}", lines and lines[0].startswith(
            "the steward profile lowered ol:mid:14b@lan's window: window 32,768 (steward profile); this conversation is ")
                  and "-> compacting to fit" in lines[0])
        trig = [e.data.get("trigger") for e in evs if e.kind == "compaction" and e.data.get("phase") == "done"]
        ctx.check(f"the compaction before the call says switch, got {trig}", trig == ["switch"])
        from tests.helpers.model_switch_rig import COMPACTION_MARKER
        sent = [b for b in rig.chats("mid:14b") if COMPACTION_MARKER not in json.dumps(b.get("messages"))]
        last = sent[-1] if sent else {}
        ctx.check(f"the call after it fits the lowered window, got {last.get('options')}",
                  0 < (last.get("options") or {}).get("num_ctx", 0) <= 32768)


@test
def test_a_session_resumed_on_another_model(ctx: Ctx):
    from halo_harness.agent.log import SessionLog
    with Rig() as rig:
        s = rig.session("ol:big:30b@lan")
        fill(s, 3)
        log = SessionLog(rig.fh["proj"], session_id=s.log.session_id)
        log._nodes = log.read_all()
        r = rig.session("ol:small:9b@lan", session_log=log)
        node = next((n for n in r.log._nodes if n.get("type") == "model_switch"), {})
        rep = node.get("report") or {}
        ctx.check(f"the step ran at start, got {rep.get('line')!r}", rep.get("why") == "resume"
                  and rep.get("from") == "ol:big:30b@lan" and str(rep.get("line", "")).startswith("resumed on ol:small:9b@lan: window 32,768"))
        ctx.check("its line waits for the first step", r._switch_lines and r._switch_lines[0] == rep.get("line"))


@test
def test_the_steward_flags_a_switch_without_fit(ctx: Ctx):
    from halo_harness.ollama_steward.rules_window import switch_without_fit
    lines = [{"at": "2026-10-27T10:00:00+00:00", "model": "small:9b", "kind": "turn", "switched_from": "big:30b", "fitted": False},
             {"at": "2026-10-27T10:01:00+00:00", "model": "small:9b", "kind": "turn", "switched_from": "big:30b", "fitted": True},
             {"at": "2026-10-27T10:02:00+00:00", "model": "small:9b", "kind": "small", "switched_from": "x", "fitted": False}]
    g = {"host": "lan", "model": "small:9b", "key": "lan|small:9b", "lines": lines}
    found = switch_without_fit(g, {})
    ctx.check(f"one finding for the one unfitted turn, got {found}", len(found) == 1 and found[0]["rule"] == "switch-without-fit"
              and found[0]["evidence"]["calls"] == ["2026-10-27T10:00:00+00:00"] and "big:30b" in found[0]["finding"])
    ctx.check("no finding when every switch was fitted", switch_without_fit(dict(g, lines=lines[1:]), {}) == [])
    from halo_harness.ollama_steward.explain import explain
    ctx.check("halo ollama explain knows it", explain("switch-without-fit")[1])
    from halo_harness.ollama_steward.ledger import FIELDS, blank_line
    ctx.check("the ledger line carries the two fields", {"switched_from", "fitted"} <= set(FIELDS) and blank_line()["fitted"] is False)


@test
def test_history_on_the_anthropic_dialect_and_the_lineup_answer(ctx: Ctx):
    from halo_harness.agent.model_switch_history import convert
    msgs = [{"role": "user", "content": [{"type": "text", "text": "go"}]},
            {"role": "assistant", "content": [{"type": "thinking", "thinking": "from another model"},
                                              {"type": "tool_use", "id": "functions.Read:0", "name": "Read", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "functions.Read:0", "content": "x"}]}]
    out, counts = convert(msgs, {"vision": True, "thinking": True, "tools": True, "dialect": "anthropic-passthrough"})
    ids = (out[1]["content"][0]["id"], out[2]["content"][0]["tool_use_id"])
    ctx.check(f"a call id another provider wrote is re-shaped the same in the call and its result, got {ids}",
              ids == ("functions_Read_0", "functions_Read_0") and counts.get("ids") == 2)
    ctx.check("an unsigned thinking block is dropped on the Anthropic dialect", counts["thinking"] == 1)
    only_tools = [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "x"}]}]
    out, _ = convert(only_tools, {"vision": True, "thinking": True, "tools": False, "dialect": "ollama"})
    ctx.check("a flattened history always holds a user turn with text", any(m["role"] == "user" for m in out)
              and "[result of a tool: x]" in json.dumps(out))
    from halo_harness.teams_apply_answer import apply_answer
    notes = [f"{r}: agent '{r}-bio' has no models.preference/fallback of its own -- left out of the role table "
             f"(falls through to the session model)" for r in ("main", "small", "researcher", "judge")]
    line, details = apply_answer("local-first", notes)
    ctx.check(f"the lineup answer is one line, got {line!r}", line == "lineup 'local-first' applied; main, small, researcher "
              "and judge run on the session model (their agents name none)" and details == notes)
    from halo_harness.commands.builtins import _cmd_teams  # noqa: F401  (the /teams apply path prints the same line)


@test
def test_every_model_list_says_how_many(ctx: Ctx):
    """3.3.5.0 R0 (f): `halo models` prints every row and a count line; the TUI's /model picker's hint says
    how many it lists (never a silent cut)."""
    import contextlib
    import io
    from types import SimpleNamespace
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "OPENROUTER_API_KEY")}
    home = Path(tempfile.mkdtemp(prefix="m0-count-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-count-test"
    try:
        from halo_harness.config.paths import bridge_home
        state = Path(bridge_home())
        state.mkdir(parents=True, exist_ok=True)
        (state / "models.json").write_text(json.dumps({f"mock/m{i:03d}": {"context_length": 8192} for i in range(312)}), encoding="utf-8")
        from halo_harness.catalog_cli import cmd_models
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_models([])
        out = buf.getvalue()
        ctx.check(f"halo models: every row and the count line, got rc {rc}", rc == 0 and "\n312 models\n" in out
                  and out.count("mock/m") == 312)
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    from halo_harness.tui.dialogs.model_picker import ModelPicker
    pool = [{"ref": f"or:m{i}"} for i in range(312)]
    fake = SimpleNamespace(initial_hint="", hints=[], _source="models", _filtered=pool[:12], _effective_models=lambda: pool)
    ctx.check(f"the picker's hint, filtered, got {ModelPicker._hint_text(fake)!r}", ModelPicker._hint_text(fake) == "12 of 312 models")
    fake._filtered = pool
    ctx.check("and unfiltered", ModelPicker._hint_text(fake) == "312 models")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
