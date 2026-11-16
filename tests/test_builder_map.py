"""tests.test_builder_map -- Halo 3.6.0.0 R3: the builder on the Map tab, through Studio's own routes with the scripted
fake model (tests/helpers/crew_rig.py, crew_map_script.py):

1. "send anything touching auth to my-reviewer after the code workflow" on ship-it -> ONE preview: the starter copied as
   yours, a box line, a line line with its When in words; each map row carries its ghost (the page draws it dashed);
   Apply writes the map; Undo puts the folder back byte for byte;
2. one request across agents and the map ("make me a reviewer agent and hand reviews to it"): one preview, the agent's
   widening line unticked, no map line widens;
3. a line that would make a circle is refused in one sentence (no change line); `map_use` on a map whose agents may do
   more than the map in use says so, amber, unticked; Apply of what came ticked writes no config;
4. "what is my map?" / "show me my workflows" / "why did reviewer run?" answer from studio_show with no change lines.
Run: python -m tests.test_builder_map
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.crew_rig import CrewRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _ask(rig, text: str, cid: str, mp: str = "ship-it"):
    return rig.api("POST", "builder/ask", {"tab": "map", "text": text, "conversation_id": cid, "selection": {"map": mp}})


def _files(rig) -> dict:
    out = {str(p.relative_to(rig.state)): p.read_bytes() for p in (rig.state / "crew").rglob("*.yaml")} if (rig.state / "crew").is_dir() else {}
    cfg = rig.state / "config.json"
    out["config.json"] = cfg.read_bytes() if cfg.is_file() else b""
    return out


def _save_reviewer(rig) -> None:
    from halo_harness.crew import store
    raw = {"format": "agent/1", "name": "my-reviewer", "does": "Reviews auth changes.", "model": "auto", "uses": ["read"],
           "careful": "ask-changes"}
    store.write_text(store.path_for("agent", "my-reviewer", state_dir=rig.state), store.dump(raw))


@test
def test_one_preview_ghosts_apply_undo(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        _save_reviewer(rig)
        before = _files(rig)
        st, r = _ask(rig, "send anything touching auth to my-reviewer after the code workflow", "m1")
        rows = r.get("changes") or []
        ctx.check(f"200 and three lines: the copy, the box, the line, got {st} {[c['summary'] for c in rows]}",
                  st == 200 and len(rows) == 3 and rows[0]["kind"] == "create" and "Copy the starter map ship-it" in rows[0]["summary"])
        ctx.check("the line line says its When in words", "code hands work to my-reviewer, when the task says auth" in rows[2]["summary"])
        ctx.check("every row draws as a ghost (the copy, the box, the line)",
                  rows[0]["ghost"]["op"] == "map_create" and rows[1]["ghost"]["op"] == "map_box_add" and
                  rows[2]["ghost"]["line"] == {"from": "code", "to": "my-reviewer", "when": {"says": ["auth"]}})
        ctx.check("no map line widens, all ticked", all(not c["widen"] and c["ticked"] for c in rows))
        st, a = rig.api("POST", "builder/apply", {"conversation_id": "m1", "change_ids": [c["id"] for c in rows]})
        from halo_harness.crew.compile import compile_map
        c = compile_map("ship-it", cwd=rig.proj)
        ctx.check(f"Apply wrote your ship-it, the chain code -> my-reviewer in it, got {st} {c.chains.get('code')}",
                  st == 200 and c.scope == "yours" and [e["name"] for e in c.chains.get("code") or []] == ["review", "my-reviewer"])
        st, u = rig.api("POST", "builder/undo", {"undo_id": a["undo_id"]})
        ctx.check(f"Undo puts the folder back byte for byte, got {st}", st == 200 and _files(rig) == before)


@test
def test_one_request_across_agents_and_the_map(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        st, r = _ask(rig, "make me a reviewer agent and hand reviews to it", "m2", "starter")
        rows = r.get("changes") or []
        targets = [c["target"] for c in rows]
        ctx.check(f"one preview: the agent, its widening line, the map's copy, box and line, got {targets}",
                  targets == ["agent:my-reviewer", "agent:my-reviewer", "map:starter", "map:starter", "map:starter"])
        wide = [c for c in rows if c["widen"]]
        ctx.check(f"only the agent's Run commands line widens, unticked, got {[c['summary'] for c in wide]}",
                  len(wide) == 1 and "Run commands" in wide[0]["summary"] and not wide[0]["ticked"])
        st, a = rig.api("POST", "builder/apply", {"conversation_id": "m2", "change_ids": [c["id"] for c in rows if c["ticked"]]})
        from halo_harness.crew import store
        got = store.load("agent", "my-reviewer", state_dir=rig.state) or {}
        ctx.check(f"Apply of what came ticked: the agent reads only, the map hands it reviews, got {got.get('uses')}",
                  st == 200 and got.get("uses") == ["read"] and "when the task says review" not in str(a))


@test
def test_a_circle_is_refused_and_map_use_says_more_power(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        st, r = _ask(rig, "loop it back", "m3")
        ctx.check(f"a circle: no change line, one sentence, got {r.get('reply')!r}",
                  st == 200 and r["changes"] == [] and "circle" in r["reply"])
        from halo_harness.theme import set_config_value
        set_config_value("crew.map", "ship-it")
        before = _files(rig)["config.json"]
        st, r = _ask(rig, "use ship-it", "m4", "starter")
        ctx.check(f"in use already: no line, got {r['changes']}", r["changes"] == [])
        st, r = _ask(rig, "use starter", "m5", "starter")
        rows = r["changes"]
        ctx.check(f"map_use: one line, amber and unticked, saying whose agents may do more, got {[c['summary'] for c in rows]}",
                  len(rows) == 1 and rows[0]["widen"] and not rows[0]["ticked"] and "may do more than the map ship-it's (researcher" in rows[0]["summary"])
        before = _files(rig)["config.json"]
        st, a = rig.api("POST", "builder/apply", {"conversation_id": "m5", "change_ids": []})
        ctx.check("Apply of nothing ticked writes no config", _files(rig)["config.json"] == before)


def _boss_map(rig, name: str, careful: str, uses=("read",)) -> None:
    """A map of yours whose main is an agent of yours (`<name>-boss`) with `careful` and `uses`: no boxes, no lines."""
    from halo_harness.crew import store
    boss = f"{name}-boss"
    store.write_text(store.path_for("agent", boss, state_dir=rig.state), store.dump(
        {"format": "agent/1", "name": boss, "does": "Runs the session.", "model": "auto", "uses": list(uses), "careful": careful}))
    store.write_text(store.path_for("map", name, state_dir=rig.state), store.dump(
        {"format": "map/1", "name": name, "boxes": [], "lines": [], "main": {"agent": boss}}))


def _use_rows(rig, name: str) -> list:
    from halo_harness.crew.tools_map import map_use
    return map_use({"map": name}, {"cwd": rig.proj, "state_dir": rig.state})["rows"]


@test
def test_map_use_compares_main_mode_and_tools(ctx: Ctx):
    """3.6.0.1: `map_use` compares MAIN too -- a map of yours whose main of yours is `careful: own` raises every next
    session to auto, so its row is a widening row (unticked, its own No-first question) that names the mode."""
    with CrewRig() as rig:
        from halo_harness.crew.compile import compile_map
        from halo_harness.crew.map_session import main_mode, own_map
        from halo_harness.crew.session_tool import NO, card, chosen
        from halo_harness.theme import set_config_value
        _boss_map(rig, "mine", "own", ("read", "edit", "bash"))
        _boss_map(rig, "mine-too", "own", ("read", "edit", "bash"))
        _boss_map(rig, "calm", "ask-changes")
        _boss_map(rig, "calm-cmds", "ask-changes", ("read", "bash"))
        c = compile_map("mine", cwd=rig.proj, state_dir=rig.state)
        ctx.check(f"the probe's shape: mine is yours, main yours, auto from default, got {c.problems} {own_map(c)}",
                  not c.problems and own_map(c) and main_mode(c, "default")[0] == "auto")
        rows = _use_rows(rig, "mine")  # the map in use: the default (starter, drawn)
        ctx.check(f"from the default map: map_use mine is ONE widening row, unticked, saying auto mode, got "
                  f"{[(r['summary'], r['widen']) for r in rows]}",
                  len(rows) == 1 and rows[0]["widen"] and not rows[0]["ticked"] and "start in auto mode" in rows[0]["summary"])
        qs = card(rows)["questions"]
        ctx.check(f"its question is its own, No first, naming the mode; Apply of the plain lines leaves it out, got {qs}",
                  len(qs) == 1 and qs[0]["options"][0]["label"] == NO and "start in auto mode" in qs[0]["question"]
                  and chosen(rows, "Apply them") == [])
        set_config_value("crew.map", "calm")
        rows = _use_rows(rig, "mine")
        ctx.check(f"from calm (main asks before changes, reads only): widening, the mode and main's tools named, got "
                  f"{[r['summary'] for r in rows]}",
                  len(rows) == 1 and rows[0]["widen"] and not rows[0]["ticked"] and "start in auto mode" in rows[0]["summary"]
                  and "Run commands" in rows[0]["summary"])
        rows = _use_rows(rig, "calm-cmds")
        ctx.check(f"from calm to calm-cmds: main may run commands -> widening, no mode words, got {[r['summary'] for r in rows]}",
                  len(rows) == 1 and rows[0]["widen"] and "Run commands" in rows[0]["summary"] and "mode" not in rows[0]["summary"])
        set_config_value("crew.map", "mine")
        for target in ("calm", "mine-too"):
            rows = _use_rows(rig, target)
            ctx.check(f"from mine to {target} (main as careful or more, no more tools): a plain row, ticked, got "
                      f"{[(r['summary'], r['widen']) for r in rows]}",
                      len(rows) == 1 and not rows[0]["widen"] and rows[0]["ticked"] and "mode" not in rows[0]["summary"])
        rows = _use_rows(rig, "starter")
        ctx.check(f"from mine to the starter: its agents and main's web / hand-offs widen, the mode does not rise, got "
                  f"{[r['summary'] for r in rows]}",
                  len(rows) == 1 and rows[0]["widen"] and "may do more than the map mine's" in rows[0]["summary"]
                  and "Hand work to agents" in rows[0]["summary"] and "mode" not in rows[0]["summary"])


@test
def test_questions_answer_from_studio_show_with_no_change(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        before = _files(rig)
        for text, want in (("what is my map?", "line main -> plan: always"), ("show me my workflows", "workflow review"),
                           ("why did reviewer run?", "No session has handed work on a map")):
            st, r = _ask(rig, text, "q" + str(abs(hash(text)) % 1000))
            ctx.check(f"{text!r}: no change lines, the answer from studio_show, got {r.get('reply')!r}",
                      st == 200 and r["changes"] == [] and want in r["reply"])
        ctx.check("nothing written", _files(rig) == before)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
