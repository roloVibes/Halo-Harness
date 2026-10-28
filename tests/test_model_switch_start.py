"""tests.test_model_switch_start -- Halo 3.3.5.0 R1 (R0b's open item): a session that STARTS on a model whose card
says it cannot take what it would be sent gets the switch step's fit at its first call
(agent/model_switch_paths.start_check, `why: "start"`), through the loop rig (a real Session over a fake Ollama on
127.0.0.1:0; tests/helpers/model_switch_rig.py). No real server, no model call:

1. a session launched on `notools:7b` (completion only): the line in the transcript ("this session runs on
   ol:notools:7b@lan: window 32,768 (...)" and "... no tools (answers only); reply reserve 4,096") before the first
   call, no tool catalog on the wire, the reserve set, a `model_switch` node with why "start", the first call's
   ledger line `fitted` with body_flags tools false -- so the steward's `called-wrong` has nothing to flag;
2. a session launched on `big:30b` (tools, vision): no start line, its tools sent as before;
3. images in the history of a session that starts on a model without vision: the step runs and they go as captions.
Run: python -m tests.test_model_switch_start
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="l1-start-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.model_switch_rig import Rig, ledger_lines, markers, png_file  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _ask(rig, s, text: str = "hello there"):
    from halo_harness import events
    return rig.run(s, [events.Command("user_input", {"text": text})])


@test
def test_a_session_that_starts_on_a_no_tools_model(ctx: Ctx):
    with Rig() as rig:
        s = rig.session("ol:notools:7b@lan")
        evs = _ask(rig, s)
        lines = markers(evs)
        ctx.check(f"the start line, then what was fitted, got {lines}", len(lines) == 2
                  and lines[0].startswith("this session runs on ol:notools:7b@lan: window ")
                  and "no tools (answers only)" in lines[1] and "reply reserve" in lines[1])
        kinds = [e.kind for e in evs]
        first_text = kinds.index("text_chunk") if "text_chunk" in kinds else len(kinds)
        first_marker = next(i for i, e in enumerate(evs) if e.kind == "turn_marker" and e.data.get("state") == "switch")
        ctx.check("the line comes before the reply", first_marker < first_text)
        bodies = rig.chats("notools:7b")
        ctx.check(f"no tool catalog on the wire, got {[bool(b.get('tools')) for b in bodies]}", bodies and not any(b.get("tools") for b in bodies))
        node = next((n for n in s.log._nodes if n.get("type") == "model_switch"), None)
        rep = (node or {}).get("report") or {}
        ctx.check(f"a model_switch node with why start, no tools, a reserve, got {rep.get('why')} {rep.get('tools_max')} {rep.get('reserve')}",
                  rep.get("why") == "start" and rep.get("tools_max") == 0 and isinstance(rep.get("reserve"), int))
        led = [x for x in ledger_lines(rig.state_dir) if x.get("model") == "notools:7b"]
        ctx.check(f"the first call's ledger line: fitted, no tool catalog, got {[(x.get('fitted'), x.get('body_flags')) for x in led]}",
                  led and led[0].get("fitted") is True and (led[0].get("body_flags") or {}).get("tools") is False)
        from halo_harness.ollama_steward.rules_card import called_wrong
        from halo_harness.providers.ollama import get_catalog, resolve_ollama_host
        from halo_harness.providers.ollama_hw import catalog_row
        row = catalog_row(get_catalog(resolve_ollama_host("lan")), "notools:7b")
        found = called_wrong({"host": "lan", "model": "notools:7b", "lines": led},
                             {"catalogs": {"lan": {"notools:7b": row}}, "state_dir": rig.state_dir})
        ctx.check(f"called-wrong has nothing to flag on those calls, got {[f.get('finding') for f in found]}", found == [])
        again = _ask(rig, s, "and again")
        ctx.check(f"once per session: no second start line, got {markers(again)}", markers(again) == [])


@test
def test_a_session_that_starts_on_a_model_with_tools(ctx: Ctx):
    with Rig() as rig:
        s = rig.session("ol:big:30b@lan")
        evs = _ask(rig, s)
        ctx.check(f"no start line, got {markers(evs)}", markers(evs) == [])
        bodies = rig.chats("big:30b")
        ctx.check("its tools go as before", bodies and bodies[0].get("tools"))
        ctx.check("no model_switch node", not any(n.get("type") == "model_switch" for n in s.log._nodes))


@test
def test_images_in_the_history_of_a_session_without_vision(ctx: Ctx):
    with Rig() as rig:
        s = rig.session("ol:small:9b@lan")
        s.log.append_user([{"type": "text", "text": "look"}, {"type": "image", "source": {"type": "path", "path": png_file(),
                                                                                           "media_type": "image/png"}}])
        s.log.append_assistant(content=[{"type": "text", "text": "seen"}], stop_reason="end_turn")
        evs = _ask(rig, s)
        lines = markers(evs)
        ctx.check(f"the start step runs and converts the image, got {lines}", len(lines) == 2 and "images to captions" in lines[1])
        body = rig.chats("small:9b")[0]
        ctx.check("no image went to the model without vision", not any(m.get("images") for m in body.get("messages") or []))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
