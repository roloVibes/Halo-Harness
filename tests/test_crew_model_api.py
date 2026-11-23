"""tests.test_crew_model_api -- Halo 3.6.0.15 OP2 rule O2-2: GET crew/agent-model?session=&agent= says what a model
pick does for the helper a sheet opens at: {kind, name, model, first, line, can, now}, one of eight kinds (MAIN, MINE,
SHIPPED, ROUTED, BUILT-IN, MADE-UP, PACK, CLAUDE), the name a pick writes (never a built-in's) and the line letter for
letter, in its "now" form when the session's row says `use_now` (package UN) and its "later" form when not.

In-process Studio (tests/helpers/crew_rig.py, a scratch home), the live session rows stood in by replacing
`peers.local_view.sessions` (put back in a finally), as tests/test_crew_map_api.py's from-live tests do. Nothing calls
a model. Run: python -m tests.test_crew_model_api
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SID = "s-model-1"
RUN = "or:vendor/fast"
MAIN_MODEL = "or:vendor/main-model"
TASK = "Count the lines in basket.py\nthen stop"


def _helpers(state: str = "running") -> list:
    def h(aid, name, source=None, **more):
        spawn = {"step": "main#1", "description": "x", "lead": ""}
        if source is not None:
            spawn["source"] = source
        return {"agent_id": aid, "parent": "main", "name": name, "state": state, "model": RUN, "task": TASK,
                "spawn": {**spawn, **more.pop("spawn", {})}, **more}
    return [
        {"agent_id": "main", "name": "main", "state": "running", "model": MAIN_MODEL},
        h("a1", "sorter", "crew:yours"),
        h("a2", "planner", "crew:starter"),
        h("a3", "general-purpose", "built-in", spawn={"routed": {"word": "transcribe", "card": "media"}}),
        h("a4", "Judge", "built-in"),
        h("a5", "general-purpose", "built-in", crew={"map": "auto", "box": "main", "made_up": True}),
        h("a6", "doc-review--review-docs", "crew:pack"),
        h("a7", "helper-x", "user"),
        h("a8", "Coder", "built-in"),
    ]


def _row(rig, *, now: bool = True, state: str = "running", map_name: str = "auto") -> dict:
    return {"session_id": SID, "cwd": str(rig.proj), "map": map_name, "model": MAIN_MODEL, "use_now": now,
            "agents": _helpers(state)}


def _his(rig, name: str, model: str = "auto") -> None:
    folder = rig.state / "crew" / "agents"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.yaml").write_text(f"format: agent/1\nname: {name}\ndoes: Does {name} work.\nmodel: {model}\n"
                                         "uses:\n- read\ncareful: ask-changes\n", encoding="utf-8")


def _get(rig, aid: str, sid: str = SID):
    return rig.api("GET", "crew/agent-model?" + urlencode({"session": sid, "agent": aid}))


class _Rows:
    """`peers.local_view.sessions` answers `rows[0]` while inside; the real function is put back on exit."""

    def __init__(self, row: dict):
        self.rows = [row]

    def __enter__(self):
        from halo_harness.peers import local_view
        self._saved = local_view.sessions
        local_view.sessions = lambda list_live=None: list(self.rows)
        return self

    def __exit__(self, *exc):
        from halo_harness.peers import local_view
        local_view.sessions = self._saved


KEEPS = "\nThis helper keeps or:vendor/fast until it ends."
NOW_LINES = {
    "a1": ("MINE", "sorter", "", "Picking a model saves it in your agent sorter: its next start uses it, in this session "
                                 "too, unless main names a model itself." + KEEPS),
    "a2": ("SHIPPED", "planner", "", "planner ships with Halo and Auto picks its model per task. Picking a model saves your "
                                     "own planner on that model: its next start uses it, in this session too, unless main "
                                     "names a model itself." + KEEPS),
    "a3": ("ROUTED", "media-reader", "A general helper that Auto sent to its media card for the word \"transcribe\".",
           "Picking a model saves your own agent media-reader on that model: helpers Auto sends to its media card start "
           "as yours from their next start, in this session too, unless main names a model itself." + KEEPS),
    "a4": ("BUILT-IN", "judge", "", "Judge is built into Halo and has no file. Picking a model makes judge, an agent of "
                                    "yours built from Judge, on that model: main can start judge from now, in this session "
                                    "too, unless it names a model itself." + KEEPS),
    "a5": ("MADE-UP", "count-lines-basket", "", "Main made this helper up for its task. Picking a model makes "
                                                "count-lines-basket, an agent of yours built from it, on that model: main "
                                                "can start count-lines-basket from now, in this session too, unless it "
                                                "names a model itself." + KEEPS),
    "a6": ("PACK", "doc-review--review-docs", "",
           "doc-review--review-docs comes with the pack doc-review; Halo does not change it here."),
    "a7": ("CLAUDE", "helper-x", "", "helper-x is a Claude Code agent file; Halo reads it and does not change it."),
    "main": ("MAIN", "main", "", "Picking a model runs /model in this session."),
}
LATER_LINES = {
    "a1": "Picking a model saves it in your agent sorter: from your next session, unless main names a model itself." + KEEPS,
    "a2": "planner ships with Halo and Auto picks its model per task. Picking a model saves your own planner on that "
          "model: from your next session, unless main names a model itself." + KEEPS,
    "a3": "Picking a model saves your own agent media-reader on that model: helpers Auto sends to its media card start as "
          "yours from your next session, unless main names a model itself." + KEEPS,
    "a4": "Judge is built into Halo and has no file. Picking a model makes judge, an agent of yours built from Judge, on "
          "that model: main can start judge from your next session, unless it names a model itself." + KEEPS,
    "a5": "Main made this helper up for its task. Picking a model makes count-lines-basket, an agent of yours built from "
          "it, on that model: main can start count-lines-basket from your next session, unless it names a model itself."
          + KEEPS,
}


@test
def test_each_kind_reads_its_line_now_and_later(ctx: Ctx):
    from tests.helpers.crew_rig import CrewRig
    with CrewRig() as rig:
        rig.studio()
        _his(rig, "sorter")
        with _Rows(_row(rig)) as rows:
            for aid, (kind, name, first, line) in NOW_LINES.items():
                st, got = _get(rig, aid)
                ctx.check(f"{aid}: 200 {kind} {name}, got {st} {got.get('kind')} {got.get('name')}",
                          st == 200 and got.get("kind") == kind and got.get("name") == name)
                ctx.check(f"{aid}: first, letter for letter, got {got.get('first')!r}", got.get("first") == first)
                ctx.check(f"{aid}: the now line, letter for letter, got {got.get('line')!r}", got.get("line") == line)
                ctx.check(f"{aid}: can {kind not in ('PACK', 'CLAUDE')} and now True, got {got.get('can')} {got.get('now')}",
                          got.get("can") is (kind not in ("PACK", "CLAUDE")) and got.get("now") is True)
            ctx.check("main's picker shows the session's model", _get(rig, "main")[1].get("model") == MAIN_MODEL)
            ctx.check("his sorter on auto: the picker's Auto row (\"\")", _get(rig, "a1")[1].get("model") == "")
            _his(rig, "sorter", "or:vendor/slow")
            ctx.check("his sorter on a model: the picker shows it", _get(rig, "a1")[1].get("model") == "or:vendor/slow")
            rows.rows = [_row(rig, now=False)]
            for aid, line in LATER_LINES.items():
                st, got = _get(rig, aid)
                ctx.check(f"{aid}: the later line, letter for letter, got {got.get('line')!r}",
                          st == 200 and got.get("line") == line and got.get("now") is False)
            maps = rig.state / "crew" / "maps"
            maps.mkdir(parents=True, exist_ok=True)
            (maps / "shop.yaml").write_text("format: map/1\nname: shop\nboxes:\n- {id: sorter, agent: sorter}\n"
                                            "- {id: judge, agent: judge}\nlines:\n- {from: main, to: sorter}\n"
                                            "- {from: main, to: judge}\n", encoding="utf-8")
            got = _get(rig, "a1")[1].get("line")
            want = ("Picking a model saves it in your agent sorter: from your next session, unless main names a model "
                    "itself. Your map shop names sorter: it uses this model from its next session." + KEEPS)
            ctx.check(f"MINE named by his map, got {got!r}", got == want)
            got = _get(rig, "a4")[1].get("line")
            want = ("Judge is built into Halo and has no file. Picking a model makes judge, an agent of yours built from "
                    "Judge, on that model: main can start judge from your next session, unless it names a model itself. "
                    "Your map shop names judge: it uses yours from its next session." + KEEPS)
            ctx.check(f"a copy under a name his map uses, got {got!r}", got == want)
            rows.rows = [_row(rig, state="done")]
            got = _get(rig, "a2")[1].get("line")
            ctx.check(f"an ended helper: It ran on, got {got!r}", str(got).endswith("\nIt ran on or:vendor/fast."))


@test
def test_the_name_a_pick_writes(ctx: Ctx):
    from halo_harness.config.agents_md import BUILTIN_NAMES
    from tests.helpers.crew_rig import CrewRig
    with CrewRig() as rig:
        rig.studio()
        with _Rows(_row(rig)) as rows:
            names = {aid: _get(rig, aid)[1].get("name") for aid in ("a3", "a4", "a5", "a8")}
            ctx.check(f"ROUTED media -> media-reader, Judge -> judge, Coder -> coder (a shipped name is not his), got "
                      f"{names}", names == {"a3": "media-reader", "a4": "judge", "a5": "count-lines-basket", "a8": "coder"})
            st, live = rig.api("POST", "crew/from-live", {"session": SID, "agent_id": "a5"})
            ctx.check(f"MADE-UP: crew/from-live's own name, got {(live.get('agent') or {}).get('name')}",
                      st == 200 and (live.get("agent") or {}).get("name") == names["a5"])
            _his(rig, "judge")
            _his(rig, "coder")
            got = {aid: _get(rig, aid)[1] for aid in ("a4", "a8")}
            ctx.check(f"while his has it: judge-2, coder-2, still BUILT-IN, got {got}",
                      [(g.get("kind"), g.get("name")) for g in got.values()] == [("BUILT-IN", "judge-2"), ("BUILT-IN", "coder-2")])
            _his(rig, "planner")
            got = _get(rig, "a2")[1]
            ctx.check(f"a SHIPPED helper whose name a file of his has reads MINE, got {got.get('kind')} {got.get('name')}",
                      got.get("kind") == "MINE" and got.get("name") == "planner")
            _his(rig, "media-reader", "or:vendor/slow")
            got = _get(rig, "a3")[1]
            ctx.check(f"a routed helper whose card's agent is his reads MINE, got {got.get('kind')} {got.get('name')}",
                      got.get("kind") == "MINE" and got.get("name") == "media-reader" and got.get("model") == "or:vendor/slow")
            rows.rows = [_row(rig, map_name="shop")]
            got = _get(rig, "a3")[1]
            ctx.check(f"not on Auto, a general helper is MADE-UP, got {got.get('kind')}", got.get("kind") == "MADE-UP")
            every = [_get(rig, a["agent_id"])[1].get("name") for a in _helpers()]
            ctx.check(f"never a built-in's name, got {every}", not set(every) & set(BUILTIN_NAMES))


@test
def test_no_answer_says_starter(ctx: Ctx):
    from tests.helpers.crew_rig import CrewRig
    with CrewRig() as rig:
        rig.studio()
        _his(rig, "sorter")
        with _Rows(_row(rig)) as rows:
            said = []
            for now in (True, False):
                rows.rows = [_row(rig, now=now)]
                said += [_get(rig, a["agent_id"])[1] for a in _helpers()]
            text = json.dumps(said).lower()
            ctx.check(f"{len(said)} answers, each names its kind, none says starter",
                      len(said) == 18 and all(a.get("kind") and a.get("line") for a in said) and "starter" not in text)
            ctx.check("no answer carries a source or a scope", "source" not in text and "_scope" not in text)


@test
def test_a_missing_session_or_helper_is_404(ctx: Ctx):
    from tests.helpers.crew_rig import CrewRig
    with CrewRig() as rig:
        rig.studio()
        with _Rows(_row(rig)):
            st, got = _get(rig, "a1", sid="s-none")
            ctx.check(f"no session: 404 with its words, got {st} {got}",
                      st == 404 and got.get("error") == "no live session 's-none' on this harness")
            st, got = _get(rig, "zz")
            ctx.check(f"no helper: 404 with its words, got {st} {got}",
                      st == 404 and got.get("error") == f"no agent 'zz' in session '{SID}'")
            st, got = rig.api("GET", "crew/agent-model?session=" + SID)
            ctx.check(f"no helper named: 422, got {st} {got}",
                      st == 422 and got.get("error") == "name the session and the helper: {session, agent}")
            ctx.check("a read: no owner's proof needed", _get_plain(rig, "a1") == 200)


def _get_plain(rig, aid: str) -> int:
    return rig.api("GET", "crew/agent-model?" + urlencode({"session": SID, "agent": aid}), owner=False)[0]


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
