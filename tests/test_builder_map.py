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


def _shop(rig) -> None:
    """3.6.0.5: a map of his named shop, the shipped auto.yaml's boxes and lines (the default is never edited)."""
    from halo_harness.crew import store
    raw = store.read(store.SHIPPED / "maps" / "auto.yaml")
    store.write_text(store.path_for("map", "shop", state_dir=rig.state), store.dump(
        {"format": raw["format"], "name": "shop", "main": raw.get("main") or {"agent": "main"}, "boxes": raw["boxes"],
         "lines": raw["lines"]}))


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
        _shop(rig)
        st, r = _ask(rig, "make me a reviewer agent and hand reviews to it", "m2", "shop")
        rows = r.get("changes") or []
        targets = [c["target"] for c in rows]
        ctx.check(f"one preview: the agent, its widening line, his map's box and line, got {targets}",
                  targets == ["agent:my-reviewer", "agent:my-reviewer", "map:shop", "map:shop"])
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
        st, r = _ask(rig, "use ship-it", "m4", "auto")
        ctx.check(f"in use already: no line, got {r['changes']}", r["changes"] == [])
        st, r = _ask(rig, "use starter", "m5", "auto")
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
        rows = _use_rows(rig, "mine")  # the map in use: the default (Auto, drawn)
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
        rows = _use_rows(rig, "auto")
        ctx.check(f"from mine to Auto: its agents and main's web / hand-offs widen, the mode does not rise, got "
                  f"{[r['summary'] for r in rows]}",
                  len(rows) == 1 and rows[0]["widen"] and "may do more than the map mine's" in rows[0]["summary"]
                  and "Hand work to agents" in rows[0]["summary"] and "mode" not in rows[0]["summary"])


@test
def test_map_use_base_mode_follows_project_trust(ctx: Ctx):
    """3.6.0.1 repair: the base mode the Builder compares from is the session's own, trust included. An UNTRUSTED
    project's settings `defaultMode` is dropped by a real session (headless.build_session), so a map whose main
    asks only before commands (acceptEdits) still RAISES its sessions from default: a widening row. Once the
    project is trusted, the settings already start sessions in acceptEdits IN THIS PROJECT -- but config `crew.map` is
    global (jf-mapuse), and a session in any other folder starts from default, so the same map still raises those: a
    widening row that says so ("outside this project")."""
    import json
    from pathlib import Path
    with CrewRig() as rig:
        from halo_harness.config.claude_json import is_trusted, load_claude_json
        from halo_harness.crew.map_session import configured_mode
        _boss_map(rig, "mine", "ask-commands", ("read",))
        d = Path(rig.proj) / ".claude"
        d.mkdir(parents=True, exist_ok=True)
        (d / "settings.json").write_text(json.dumps({"permissions": {"defaultMode": "acceptEdits"}}), encoding="utf-8")
        ctx.check("the project starts untrusted", not is_trusted(rig.proj, load_claude_json()))
        ctx.check(f"untrusted: the base mode is default (the session drops defaultMode), got {configured_mode(rig.proj)}",
                  configured_mode(rig.proj) == "default")
        rows = _use_rows(rig, "mine")
        ctx.check(f"untrusted: map_use mine raises default to acceptEdits -> a widening row, unticked, got "
                  f"{[(r['summary'], r['widen']) for r in rows]}",
                  len(rows) == 1 and rows[0]["widen"] and not rows[0]["ticked"] and "acceptEdits" in rows[0]["summary"])
        _trust(rig)
        ctx.check("the project is now trusted", is_trusted(rig.proj, load_claude_json()))
        ctx.check(f"trusted: the base mode is the settings' acceptEdits, got {configured_mode(rig.proj)}",
                  configured_mode(rig.proj) == "acceptEdits")
        ctx.check(f"outside any project the base stays default, got {configured_mode(rig.proj, project=False)}",
                  configured_mode(rig.proj, project=False) == "default")
        rows = _use_rows(rig, "mine")
        ctx.check(f"trusted: the mode does not rise HERE, but sessions in other folders rise default -> acceptEdits: a "
                  f"widening row, unticked, saying so, got {[(r['summary'], r['widen']) for r in rows]}",
                  len(rows) == 1 and rows[0]["widen"] and not rows[0]["ticked"]
                  and "new sessions outside this project start in acceptEdits mode" in rows[0]["summary"])


def _trust(rig) -> None:
    import json
    from halo_harness.config.paths import claude_json_path
    cj = claude_json_path()
    cj.parent.mkdir(parents=True, exist_ok=True)
    key = str(Path(rig.proj).absolute()).replace("\\", "/")
    cj.write_text(json.dumps({"projects": {key: {"hasTrustDialogAccepted": True}}}), encoding="utf-8")


@test
def test_map_use_widening_seen_outside_a_project_that_shadows_main(ctx: Ctx):
    """jf-mapuse (case B): a trusted project ships its own `lead` (asks before changes), which hides your `lead`
    (works on its own) only inside that project. Your map `mine` (main: lead) raises nothing here, but every session in
    another folder would start in auto -- `crew.map` is global -- so map_use mine is a widening row."""
    with CrewRig() as rig:
        from halo_harness.crew import store
        from halo_harness.crew.compile import compile_map
        from halo_harness.crew.map_session import own_map
        store.write_text(store.path_for("agent", "lead", state_dir=rig.state), store.dump(
            {"format": "agent/1", "name": "lead", "does": "Runs the session.", "model": "auto", "uses": ["read"], "careful": "own"}))
        store.write_text(store.path_for("map", "mine", state_dir=rig.state), store.dump(
            {"format": "map/1", "name": "mine", "boxes": [], "lines": [], "main": {"agent": "lead"}}))
        d = Path(rig.proj) / ".halo" / "crew" / "agents"
        d.mkdir(parents=True, exist_ok=True)
        (d / "lead.yaml").write_text(store.dump({"format": "agent/1", "name": "lead", "does": "Runs the session.",
                                                 "model": "auto", "uses": ["read"], "careful": "ask-changes"}), encoding="utf-8")
        _trust(rig)
        here = compile_map("mine", cwd=rig.proj, state_dir=rig.state)
        out = compile_map("mine", cwd=None, state_dir=rig.state)
        ctx.check(f"the shape: inside the project main is the project's lead, outside it is yours (own), got "
                  f"{here.main.get('scope')} {out.main.get('careful')}",
                  here.main.get("scope") == "project" and not own_map(here) and own_map(out) and out.main.get("careful") == "own")
        rows = _use_rows(rig, "mine")
        ctx.check(f"map_use mine from the project: a widening row, unticked, naming auto outside this project, got "
                  f"{[(r['summary'], r['widen']) for r in rows]}",
                  len(rows) == 1 and rows[0]["widen"] and not rows[0]["ticked"]
                  and "new sessions outside this project start in auto mode" in rows[0]["summary"])
        # the agents' side too: the project's `helper` reads only; yours runs commands on its own
        from halo_harness.theme import set_config_value
        _agent(rig, "looker", ("read",), "ask-changes")
        _agent(rig, "helper", ("read", "bash"), "own")
        (d / "helper.yaml").write_text(store.dump({"format": "agent/1", "name": "helper", "does": "Helps.", "model": "auto",
                                                   "uses": ["read"], "careful": "ask-changes"}), encoding="utf-8")
        for mp, who in (("calm", "looker"), ("calm-helped", "helper")):
            store.write_text(store.path_for("map", mp, state_dir=rig.state), store.dump(
                {"format": "map/1", "name": mp, "main": {"agent": "mine-boss"}, "boxes": [{"id": who, "agent": who}],
                 "lines": [{"from": "main", "to": who, "when": "main-decides"}]}))
        _agent(rig, "mine-boss", ("read",), "ask-changes")
        set_config_value("crew.map", "calm")
        rows = _use_rows(rig, "calm-helped")
        ctx.check(f"from calm to calm-helped: helper does no more here, but yours does outside -> widening naming helper, "
                  f"got {[(r['summary'], r['widen']) for r in rows]}",
                  len(rows) == 1 and rows[0]["widen"] and "may do more than the map calm's (helper)" in rows[0]["summary"])


def _agent(rig, name: str, uses, careful: str) -> None:
    from halo_harness.crew import store
    store.write_text(store.path_for("agent", name, state_dir=rig.state), store.dump(
        {"format": "agent/1", "name": name, "does": "Does the work.", "model": "auto", "uses": list(uses), "careful": careful}))


@test
def test_a_line_from_main_on_the_map_in_use_widens_like_map_use(ctx: Ctx):
    """jf-mapuse: on the map IN USE, a line from main that gives main Agent / Task and an agent that may do more (or a
    line's When changed from `ask` so main hands work to it on its own) is a widening row, as map_use's is; on a map
    not in use, or a line to an agent that does no more, a plain row."""
    with CrewRig() as rig:
        from halo_harness.crew import store
        from halo_harness.crew.tools_map import map_box_add, map_line_add, map_line_change
        from halo_harness.theme import set_config_value
        _boss_map(rig, "mine", "ask-changes", ("read",))
        _boss_map(rig, "other", "ask-changes", ("read",))
        _agent(rig, "runner2", ("read", "edit", "bash"), "own")
        _agent(rig, "looker", ("read",), "ask-changes")
        set_config_value("crew.map", "mine")
        base = {"cwd": rig.proj, "state_dir": rig.state}

        def line_rows(mp: str, to: str, when=None):
            box = map_box_add({"map": mp, "kind": "agent", "ref": to}, base)["rows"]
            args = {"map": mp, "from": "main", "to": to} | ({"when": when} if when else {})
            return box, map_line_add(args, {**base, "made": box})["rows"]

        box, rows = line_rows("mine", "runner2")
        ctx.check(f"the box alone is plain, ticked, got {[(r['summary'], r['widen']) for r in box]}",
                  len(box) == 1 and not box[0]["widen"] and box[0]["ticked"])
        ctx.check(f"main -> runner2 on the map in use: a widening row, unticked, naming runner2 and Hand work to agents, "
                  f"got {[(r['summary'], r['widen']) for r in rows]}",
                  len(rows) == 1 and rows[0]["widen"] and not rows[0]["ticked"] and "runner2" in rows[0]["summary"]
                  and "Hand work to agents" in rows[0]["summary"])
        _b, rows = line_rows("other", "runner2")
        ctx.check(f"the same line on a map not in use: plain, got {[(r['summary'], r['widen']) for r in rows]}",
                  len(rows) == 1 and not rows[0]["widen"] and rows[0]["ticked"])
        # a map in use whose main already hands work to looker (reads only): a line to another reader adds no power
        store.write_text(store.path_for("map", "mine", state_dir=rig.state), store.dump(
            {"format": "map/1", "name": "mine", "main": {"agent": "mine-boss"},
             "boxes": [{"id": "looker", "agent": "looker"}, {"id": "runner2", "agent": "runner2"}],
             "lines": [{"from": "main", "to": "looker", "when": "main-decides"}, {"from": "main", "to": "runner2", "when": "ask"}]}))
        _agent(rig, "looker2", ("read",), "ask-changes")
        _b, rows = line_rows("mine", "looker2")
        ctx.check(f"a line to a reader when main hands to one already: plain, got {[(r['summary'], r['widen']) for r in rows]}",
                  len(rows) == 1 and not rows[0]["widen"] and rows[0]["ticked"])
        rows = map_line_change({"map": "mine", "from": "main", "to": "runner2", "when": "main-decides"}, base)["rows"]
        ctx.check(f"runner2's line from ask to main decides (main hands it work on its own): widening, got "
                  f"{[(r['summary'], r['widen']) for r in rows]}",
                  len(rows) == 1 and rows[0]["widen"] and not rows[0]["ticked"] and "runner2" in rows[0]["summary"])
        rows = map_line_change({"map": "mine", "from": "main", "to": "looker", "when": "ask"}, base)["rows"]
        ctx.check(f"a line narrowed to ask: plain, got {[(r['summary'], r['widen']) for r in rows]}",
                  len(rows) == 1 and not rows[0]["widen"] and rows[0]["ticked"])


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


# ---- 3.6.0.2 R36 R37 R54 R21: the Builder in a session (crew/session_tool.py over crew/tools_map.py) -------------------
NAME_IT = ("Name the map: this session runs on Auto (the default), where main chooses who works. Pass a new name in "
           "args.map to make a map that routes.")
NAME_NEW = ("Name the map: Auto (the default) stays as it is, where main chooses who works. Pass a new name in args.map to "
            "make a map that routes.")  # 3.6.0.5 RULINGS 3: no name typed and none to take
S13_RF = "This session keeps running on Auto (the default), as it started. Start a new session to run on review-flow."
TAIL = "In the terminal: quit, then run halo; /clear keeps Auto (the default)."
HANDOFF = "this session takes it at its next hand-off"


class _S:
    """The parts of a session the Builder reads: cwd, the team control (the default map, or `mp` as a picked map), the
    permission mode, a person to answer (interactive: the terminal, as no Studio handle names it)."""

    def __init__(self, rig, mp=None, mode: str = "default") -> None:
        from types import SimpleNamespace
        from halo_harness.crew.compile import compile_map
        from halo_harness.crew.map_control import control_for
        c = compile_map(mp or "auto", cwd=rig.proj, state_dir=rig.state)
        c.source = "flag" if mp else "default"
        self.cwd = rig.proj
        self.team_control = control_for(c, cwd=rig.proj, state_dir=rig.state)
        self.permission_engine = SimpleNamespace(mode=mode)
        self.interactive = True
        self.agent_depth = 0


def _map_of(rig, name: str, boss_uses=("read",), boxes=(), main=None) -> None:
    """A map of yours: main is `main` when given, else `<name>-boss` (asks before changes, `boss_uses`); each box an
    agent of `boxes`, connected from main (main decides)."""
    from halo_harness.crew import store
    if main is None:
        main = f"{name}-boss"
        _agent(rig, main, boss_uses, "ask-changes")
    store.write_text(store.path_for("map", name, state_dir=rig.state), store.dump(
        {"format": "map/1", "name": name, "main": {"agent": main}, "boxes": [{"id": b, "agent": b} for b in boxes],
         "lines": [{"from": "main", "to": b, "when": "main-decides"} for b in boxes]}))


def _box(mp, ref, kind="agent"):
    return {"tool": "map_box_add", "args": ({"map": mp} if mp else {}) | {"kind": kind, "ref": ref}}


def _line(mp, to, when="always"):
    return {"tool": "map_line_add", "args": ({"map": mp} if mp else {}) | {"from": "main", "to": to, "when": when}}


def _uses(rows) -> list:
    return [r for r in rows if r["target"] == "use:crew.map"]


@test
def test_plain_session_asks_for_a_map_name(ctx: Ctx):
    """R36: in a session on the default map a map tool with no `map` gets no rows, only the sentence; named, as before;
    3.6.0.5 A6: a map named `starter` (or `auto`) is refused with W16; Studio's builder box with no session and none
    set, and with Auto open, gets NAME_A_NEW_MAP: nothing written, no row (the default is never copied as his)."""
    with CrewRig() as rig:
        from halo_harness.crew import session_tool, tools
        _save_reviewer(rig)
        s = _S(rig)
        for call in (_box(None, "my-reviewer"), _line(None, "my-reviewer"),
                     {"tool": "map_box_remove", "args": {"box": "coder"}},
                     {"tool": "map_line_change", "args": {"from": "main", "to": "coder", "when": "always"}},
                     {"tool": "map_line_remove", "args": {"from": "main", "to": "coder"}}):
            pv = session_tool.preview(s, call)
            ctx.check(f"{call['tool']} with no map: no rows, no card, the sentence, got {pv['text']!r}",
                      pv["rows"] == [] and "card" not in pv and NAME_IT in pv["text"])
        pv = session_tool.preview(s, _box("starter", "my-reviewer"))
        ctx.check(f"named starter: W16, no rows, got {pv['text']!r} {[r['summary'] for r in pv['rows']]}",
                  pv["rows"] == [] and "card" not in pv
                  and "starter is a name of the default (Auto); give your map another name." in pv["text"])
        maps = rig.state / "crew" / "maps"
        for sel in ({}, {"map": "auto"}):  # outside a session with none set; Studio's builder box with Auto open
            got = tools.run("map_box_add", {"kind": "agent", "ref": "my-reviewer"},
                            {"cwd": rig.proj, "state_dir": rig.state, "selection": sel})
            ctx.check(f"no session, selection {sel}: NAME_A_NEW_MAP word for word, no row, no file, got {got}",
                      got.get("text") == NAME_NEW and got.get("rows") == [] and not (maps.is_dir() and list(maps.iterdir())))


@test
def test_session_edit_goes_to_the_running_map(ctx: Ctx):
    """R36: on a map of his, a nameless change goes to the map this session runs on (not config's), each row says the
    session takes it at its next hand-off, no use row; a box whose agent may do more than this session's main is
    its own question, No first."""
    with CrewRig() as rig:
        from halo_harness.crew import session_tool
        from halo_harness.theme import set_config_value
        _map_of(rig, "ship-it", ("read",))
        _map_of(rig, "shop", ("read",))
        set_config_value("crew.map", "shop")
        _save_reviewer(rig)
        _agent(rig, "runner", ("read", "bash"), "ask-changes")
        s = _S(rig, "ship-it")
        pv = session_tool.preview(s, {"changes": [_box(None, "my-reviewer"), _line(None, "my-reviewer")]})
        rows = pv["rows"]
        ctx.check(f"the rows go to ship-it, not shop, got {[r['target'] for r in rows]}",
                  [r["target"] for r in rows] == ["map:ship-it", "map:ship-it"])
        ctx.check(f"each row says the session takes it at its next hand-off, got {[r['summary'] for r in rows]}",
                  all(r["summary"].endswith(HANDOFF) for r in rows) and not any(r["widen"] for r in rows))
        ctx.check("no use row for the session's own map", _uses(rows) == [])
        pv = session_tool.preview(s, {"changes": [_box(None, "runner")]})
        qs = pv["card"]["questions"]
        ctx.check(f"a box whose agent runs commands main may not: its own question, No first, got {qs}",
                  len(pv["rows"]) == 1 and pv["rows"][0]["widen"] and not pv["rows"][0]["ticked"] and len(qs) == 1
                  and qs[0]["options"][0]["label"] == session_tool.NO and HANDOFF in qs[0]["question"])


@test
def test_new_name_creates_and_offers_its_use_row_ticked(ctx: Ctx):
    """R36 + decision 6: a new name gives a create row; a map CREATED in the card comes with its use row "New sessions
    run on {B}. " + S13 (+ the terminal tail in a terminal), ticked."""
    with CrewRig() as rig:
        from halo_harness.crew import map_facts, session_tool
        _save_reviewer(rig)
        s = _S(rig)
        pv = session_tool.preview(s, {"changes": [_box("review-flow", "my-reviewer"), _line("review-flow", "my-reviewer")]})
        rows = pv["rows"]
        ctx.check(f"the create row, the box, the line, the use row, got {[r['summary'] for r in rows]}",
                  [r["summary"] for r in rows[:3]] == ["Make a new map review-flow (main, then the boxes below)",
                                                       "Add box my-reviewer (agent my-reviewer)",
                                                       "Add line main -> my-reviewer (When: always)"]
                  and rows[0]["op"]["op"] == "create" and len(rows) == 4)
        use = rows[-1]
        want = "New sessions run on review-flow. " + S13_RF + " " + TAIL
        ctx.check(f"the use row: ticked, its words S13 + the tail (literal and map_facts), got {use['summary']!r}",
                  use["target"] == "use:crew.map" and use["op"]["op"] == "use" and use["op"]["value"] == "review-flow"
                  and not use["widen"] and use["ticked"] and use["summary"] == want
                  and use["summary"] == "New sessions run on review-flow. " + map_facts.s13("Auto (the default)", "review-flow")
                  + " " + map_facts.terminal_tail("Auto (the default)"))
        qs = pv["card"]["questions"]
        ctx.check(f"one question, Apply these 4 changes, got {[q['question'][:40] for q in qs]}",
                  len(qs) == 1 and qs[0]["question"].startswith("Apply these 4 changes"))
        from types import SimpleNamespace
        from halo_harness.remote import runtime
        real = runtime.actives
        runtime.actives = lambda: [SimpleNamespace(handle=SimpleNamespace(session=s, kind="headless"))]
        try:
            pv = session_tool.preview(s, {"changes": [_box("review-flow", "my-reviewer")]})
        finally:
            runtime.actives = real
        ctx.check(f"a Studio session (headless): no terminal tail, got {_uses(pv['rows'])[0]['summary']!r}",
                  _uses(pv["rows"])[0]["summary"] == "New sessions run on review-flow. " + S13_RF)


@test
def test_workflow_card_first_row_ties_his_word(ctx: Ctx):
    """R37: "build me a review workflow: a coder then a reviewer" is ONE card: the agents, the workflow, a new map with a
    box running it and the line main -> it, the use row; its first line ties it to his word (no id, nothing written)."""
    with CrewRig() as rig:
        from halo_harness.crew import session_tool
        s = _S(rig)
        calls = [{"tool": "agent_make", "args": {"name": "coder", "does": "Writes the code."}},
                 {"tool": "agent_make", "args": {"name": "reviewer", "does": "Reviews the code."}},
                 {"tool": "workflow_make", "args": {"name": "review", "for": "code then review",
                                                    "steps": [{"name": "code", "agents": ["coder"]},
                                                              {"name": "review", "agents": ["reviewer"]}]}},
                 _box("review-flow", "review", "workflow"), _line("review-flow", "review")]
        pv = session_tool.preview(s, {"changes": calls})
        first = "Your review workflow: the workflow review (coder, then reviewer), run from a box on the new map review-flow."
        q = pv["card"]["questions"][0]["question"]
        ctx.check(f"the card's first line and the preview text's line 1, got {q.splitlines()[:2]} / {pv['text'].splitlines()[0]!r}",
                  q.splitlines()[1] == first and pv["text"].splitlines()[0] == first)
        said = [r["summary"] for r in pv["rows"]]
        want = ["Make the workflow review: 1 coder, 2 reviewer", "Make a new map review-flow (main, then the boxes below)",
                "Add box review (workflow review)", "Add line main -> review (When: always)"]
        at = [said.index(w) if w in said else -1 for w in want]
        ctx.check(f"the rows in section 4's words, in order, the use row last, got {said}",
                  -1 not in at and at == sorted(at) and pv["rows"][-1]["target"] == "use:crew.map" and pv["rows"][-1]["ticked"])
        ctx.check("the first line is no row", first not in said)


@test
def test_edit_of_another_map_offers_unticked_use_row(ctx: Ctx):
    """R36: editing a map new sessions do not use asks, unticked, No first, in section 4's words; Apply alone leaves
    crew.map; Yes switches it."""
    with CrewRig() as rig:
        from halo_harness.crew import session_tool
        from halo_harness.crew.compile import compile_map
        from halo_harness.theme import get_config_value, set_config_value
        _agent(rig, "looker", ("read",), "ask-changes")
        _map_of(rig, "shop", ("read",), ["looker"])
        _map_of(rig, "ship-it", ("read",))
        set_config_value("crew.map", "shop")
        _save_reviewer(rig)
        s = _S(rig)
        for yes in (False, True):
            pv = session_tool.preview(s, {"changes": [_box("ship-it", "my-reviewer" if not yes else "looker")]})
            qs = pv["card"]["questions"]
            ask = [q for q in qs if q["question"].endswith(
                "New sessions do not run on ship-it; they run on shop. Run new sessions on it instead?")]
            ctx.check(f"its own question, exactly, No first, got {[q['question'] for q in qs]}",
                      len(qs) == 2 and len(ask) == 1 and ask[0]["question"] == "2. New sessions do not run on ship-it; they "
                      "run on shop. Run new sessions on it instead?" and ask[0]["options"][0]["label"] == session_tool.NO
                      and not _uses(pv["rows"])[0]["ticked"])
            answer = {qs[0]["question"]: session_tool.APPLY} | ({ask[0]["question"]: session_tool.YES} if yes else {})
            session_tool.finish(pv, answer, s)
            boxes = set(compile_map("ship-it", cwd=rig.proj, state_dir=rig.state).boxes)
            ctx.check(f"yes={yes}: the box written, crew.map {'ship-it' if yes else 'shop'}, got {boxes} "
                      f"{get_config_value('crew.map')}", ("looker" if yes else "my-reviewer") in boxes
                      and get_config_value("crew.map") == ("ship-it" if yes else "shop"))


@test
def test_map_use_row_not_appended_for_own_map(ctx: Ctx):
    with CrewRig() as rig:
        from halo_harness.crew import session_tool
        from halo_harness.theme import set_config_value
        _map_of(rig, "ship-it", ("read",))
        _map_of(rig, "shop", ("read",))
        set_config_value("crew.map", "shop")
        _save_reviewer(rig)
        s = _S(rig, "ship-it")
        for mp in ("ship-it", None):
            pv = session_tool.preview(s, {"changes": [_box(mp, "my-reviewer")]})
            ctx.check(f"map={mp}: the box row, no use row, one question, got {[r['summary'] for r in pv['rows']]}",
                      len(pv["rows"]) == 1 and _uses(pv["rows"]) == [] and len(pv["card"]["questions"]) == 1)


@test
def test_use_row_checks_the_final_card_body(ctx: Ctx):
    """R54: the use row is checked on the map as the card leaves it -- an agent made in the same card included: one that
    may run commands, where the map new sessions use reads only, makes the row its own question, unticked."""
    with CrewRig() as rig:
        from halo_harness.crew import session_tool
        from halo_harness.theme import set_config_value
        _agent(rig, "looker", ("read",), "ask-changes")
        _map_of(rig, "calm", boxes=["looker"], main="main")
        set_config_value("crew.map", "calm")
        s = _S(rig)
        for who, uses, wide in (("runner", ["read", "bash"], True), ("reader", ["read"], False)):
            mp = f"fast-{who}"
            pv = session_tool.preview(s, {"changes": [
                {"tool": "agent_make", "args": {"name": who, "does": "Does the work.", "uses": uses}},
                _box(mp, who), _line(mp, who)]})
            use = _uses(pv["rows"])
            q = [x for x in pv["card"]["questions"] if "New sessions run on " + mp in x["question"]]
            ctx.check(f"{who}: the use row widen={wide}, got {[(u['summary'], u['widen']) for u in use]}",
                      len(use) == 1 and use[0]["widen"] == wide and use[0]["ticked"] == (not wide)
                      and (not wide or (len(q) == 1 and q[0]["options"][0]["label"] == session_tool.NO)))


@test
def test_use_row_rechecked_at_apply_when_file_changed(ctx: Ctx):
    """R54: at Apply, a use row whose map file changed since the card was shown is checked again; now widening, it is
    left out (crew.map unchanged), the other rows are written, and the result says so."""
    with CrewRig() as rig:
        from halo_harness.crew import session_tool, store
        from halo_harness.crew.compile import compile_map
        from halo_harness.theme import get_config_value, set_config_value
        _agent(rig, "looker", ("read",), "ask-changes")
        _agent(rig, "looker2", ("read",), "ask-changes")
        _agent(rig, "runner", ("read", "bash"), "own")
        _map_of(rig, "shop", ("read",), ["looker"])
        _map_of(rig, "calm", ("read",))
        set_config_value("crew.map", "shop")
        s = _S(rig)
        pv = session_tool.preview(s, {"changes": [_box("calm", "looker2"), {"tool": "map_use", "args": {"map": "calm"}}]})
        use = _uses(pv["rows"])
        ctx.check(f"the use row came ticked (calm reads only), got {[(u['summary'], u['widen']) for u in use]}",
                  len(use) == 1 and use[0]["ticked"] and len(pv["card"]["questions"]) == 1)
        path = store.path_for("map", "calm", state_dir=rig.state)
        body = store.read(path)
        body["boxes"].append({"id": "runner", "agent": "runner"})
        body["lines"].append({"from": "main", "to": "runner", "when": "main-decides"})
        store.write_text(path, store.dump(body))
        out = session_tool.finish(pv, "Apply them", s)
        boxes = set(compile_map("calm", cwd=rig.proj, state_dir=rig.state).boxes)
        ctx.check(f"crew.map stays shop, the box is written, got {get_config_value('crew.map')} {boxes}",
                  get_config_value("crew.map") == "shop" and {"looker2", "runner"} <= boxes)
        ctx.check(f"the result says the use row was left because calm changed, got {out[-300:]!r}",
                  "calm changed after the card was shown and now lets agents do more" in out)


@test
def test_apply_recheck_fails_closed(ctx: Ctx):
    """R54 at Apply fails CLOSED: when the recheck cannot decide -- the check raises, or the map's file cannot be read --
    the use row is left out (crew.map unchanged), the rest of the card is written, and the result says in one line that
    new sessions were not switched and why. A map the agent wrote grants nothing the person did not tick."""
    with CrewRig() as rig:
        from halo_harness.crew import session_tool, store, tools_map
        from halo_harness.crew.compile import compile_map
        from halo_harness.theme import get_config_value, set_config_value
        _agent(rig, "looker", ("read",), "ask-changes")
        _map_of(rig, "shop", ("read",), ["looker"])
        _map_of(rig, "calm", ("read",))
        set_config_value("crew.map", "shop")
        s = _S(rig)
        real = tools_map._use_words
        for who, case in (("looker2", "raises"), ("looker3", "unreadable")):
            _agent(rig, who, ("read",), "ask-changes")
            pv = session_tool.preview(s, {"changes": [_box("calm", who), {"tool": "map_use", "args": {"map": "calm"}}]})
            use = _uses(pv["rows"])
            ctx.check(f"{case}: the use row came ticked, got {[(u['summary'], u['widen']) for u in use]}",
                      len(use) == 1 and use[0]["ticked"])
            if case == "raises":  # the file changed since the card (a box with no line: no more power), the check raises
                path = store.path_for("map", "calm", state_dir=rig.state)
                body = store.read(path)
                body["boxes"].append({"id": "looker", "agent": "looker"})
                store.write_text(path, store.dump(body))

                def boom(*_a, **_k):
                    raise RuntimeError("the check broke")
                tools_map._use_words = boom
            else:
                use[0]["op"]["file"] = str(Path(rig.root) / "no-such-dir" / "calm.yaml")
            try:
                out = session_tool.finish(pv, "Apply them", s)
            finally:
                tools_map._use_words = real
            boxes = set(compile_map("calm", cwd=rig.proj, state_dir=rig.state).boxes)
            ctx.check(f"{case}: crew.map stays shop, the box is written, got {get_config_value('crew.map')} {boxes}",
                      get_config_value("crew.map") == "shop" and who in boxes)
            ctx.check(f"{case}: one line says new sessions still run on shop and why, got {out[-260:]!r}",
                      "Left out: new sessions still run on shop: whether calm lets agents do more could not be checked "
                      "again" in out and "Applied 1 line(s), left 1" in out)


@test
def test_copy_of_running_project_map_is_checked_like_map_use(ctx: Ctx):
    """R36 + R54: a session runs on a project's map that new sessions use too; a nameless change copies it as yours, and
    that copy is what new sessions read where no project shadows it -- a switch. When the copy would let main hand work
    to an agent that may do more, the copy row is its own question, unticked, No first, and a box whose agent may do
    more than the session's main is too; answering only Apply writes no copy and leaves crew.map."""
    with CrewRig() as rig:
        from halo_harness.crew import session_tool, store
        from halo_harness.theme import get_config_value, set_config_value
        _agent(rig, "proj-boss", ("read",), "ask-changes")
        _agent(rig, "runner", ("read", "bash"), "own")
        d = Path(rig.proj) / ".halo" / "crew" / "maps"
        d.mkdir(parents=True, exist_ok=True)
        (d / "proj-flow.yaml").write_text(store.dump({"format": "map/1", "name": "proj-flow", "main": {"agent": "proj-boss"},
                                                      "boxes": [], "lines": []}), encoding="utf-8")
        _trust(rig)
        set_config_value("crew.map", "proj-flow")
        s = _S(rig, "proj-flow")
        ctx.check(f"the session runs on the project's map, got {getattr(s.team_control.map, 'scope', '')}",
                  getattr(s.team_control.map, "scope", "") == "project")
        pv = session_tool.preview(s, {"changes": [_box(None, "runner"), _line(None, "runner")]})
        rows = pv["rows"]
        copy = [r for r in rows if r["op"].get("op") == "copy"]
        box = [r for r in rows if r["op"].get("op") == "map_box_add"]
        ctx.check(f"the copy row widens, unticked, got {[(r['summary'], r['widen'], r['ticked']) for r in rows]}",
                  len(copy) == 1 and copy[0]["widen"] and not copy[0]["ticked"] and "runner" in copy[0]["summary"])
        ctx.check(f"the box row (runner runs commands, main reads only) widens too, got {[(r['summary'], r['widen']) for r in box]}",
                  len(box) == 1 and box[0]["widen"] and not box[0]["ticked"])
        qs = pv["card"]["questions"]
        ask = [q for q in qs if "Copy the project map proj-flow as yours" in q["question"]]
        ctx.check(f"the copy is its own question, No first, got {[q['question'][:70] for q in qs]}",
                  len(ask) == 1 and ask[0]["options"][0]["label"] == session_tool.NO)
        session_tool.finish(pv, {q["question"]: session_tool.APPLY for q in qs if q["question"].startswith("Apply")}, s)
        ctx.check("only Apply: no copy of yours written, crew.map unchanged",
                  not store.path_for("map", "proj-flow", state_dir=rig.state).is_file()
                  and get_config_value("crew.map") == "proj-flow")


@test
def test_card_row_and_tail_say_s13_golden(ctx: Ctx):
    """R21 + section 4: the use row and the result tail say S13 (+ the terminal tail); the result keeps Applied and the
    undo id, and no longer says "Studio follows the files."; an agent-only card ends with T1. 3.6.0.5: the card is
    APPLIED, so the session runs on a map of his (shop), never on the default."""
    import re
    import time
    s13_rf = "This session keeps running on shop, as it started. Start a new session to run on review-flow."
    tail = "In the terminal: quit, then run halo; /clear keeps shop."
    with CrewRig() as rig:
        from halo_harness.crew import session_tool
        from halo_harness.theme import set_config_value
        _map_of(rig, "shop", ("read",))
        s = _S(rig, "shop")
        s._map_started_at = time.time()
        pv = session_tool.preview(s, {"changes": [
            {"tool": "agent_make", "args": {"name": "my-reviewer", "does": "Reviews.", "uses": ["read"]}},
            _box("review-flow", "my-reviewer"), _line("review-flow", "my-reviewer")]})
        use = _uses(pv["rows"])
        ctx.check(f"the use row's words, got {[u['summary'] for u in use]}",
                  len(use) == 1 and use[0]["summary"] == "New sessions run on review-flow. " + s13_rf + " " + tail)
        out = session_tool.finish(pv, "Apply them", s)
        u = pv["outcome"]["undo"]
        ctx.check(f"Applied, the undo id, the tail (Written, Undo, word for word S13 + tail), got {out[-420:]!r}",
                  "Applied 5 line(s)" in out and f"Undo id {u}" in out and "Studio follows the files." not in out
                  and out.endswith(f"Written: the map review-flow (new); the agent my-reviewer (new). Undo: {u}. "
                                   f"Tell the person, word for word: {s13_rf} {tail}"))
        set_config_value("crew.map", "shop")
        pv = session_tool.preview(s, {"tool": "agent_make", "args": {"name": "quiet", "does": "Reads."}})
        out = session_tool.finish(pv, "Apply them", s)
        ctx.check(f"an agent only: the tail is T1, got {out[-200:]!r}",
                  re.search(r"Written: the agent quiet \(new\)\. Undo: [\w-]+\. Tell the person, word for word: This session "
                            r"runs on shop, as it started at \d{2}:\d{2}\. New sessions will too\.$", out))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
