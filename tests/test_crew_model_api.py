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
                                         "uses:\n- read\ncareful: ask-changes\n", encoding="utf-8", newline="\n")


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
            # O2-8 (d), ruling B: `first` is "" for every kind but ROUTED: a routed helper whose card's agent is now one
            # of his reads MINE, with no routed state line
            _his(rig, "media-reader")
            try:
                st, got = _get(rig, "a3")
                ctx.check(f"a routed helper whose card's agent is his: MINE, first \"\", got {st} {got.get('kind')} {got.get('first')!r}",
                          st == 200 and got.get("kind") == "MINE" and got.get("name") == "media-reader" and got.get("first") == "")
            finally:
                (rig.state / "crew" / "agents" / "media-reader.yaml").unlink()


@test
def test_a_helper_whose_agent_is_gone_says_so(ctx: Ctx):
    """O2-8 (c): a helper whose row says its agent is HIS (`spawn.source` crew:yours or crew:project) but whose file is
    gone (deleted, or taken back by Undo, while it runs) is its own kind GONE: no picker, no button, its one line letter
    for letter (not the Claude Code file sentence); a pick for it is refused 409 with the same line, nothing written."""
    from tests.helpers.crew_rig import CrewRig
    line = "Your agent sorter is gone: it was deleted after this helper started."
    with CrewRig() as rig:
        rig.studio()
        for src in ("crew:yours", "crew:project"):
            row = _row(rig)
            row["agents"][1]["spawn"]["source"] = src
            with _Rows(row), _Push() as push:
                st, got = _get(rig, "a1")
                ctx.check(f"{src}, no file: 200 GONE sorter, can False, first \"\", its line, got {st} {got}",
                          st == 200 and got.get("kind") == "GONE" and got.get("name") == "sorter" and got.get("can") is False
                          and got.get("first") == "" and got.get("line") == line)
                before = _files(rig)
                st, got = _pick(rig, "a1")
                ctx.check(f"{src}: a pick is refused 409 with the same line, got {st} {got}",
                          st == 409 and got.get("line") == line and got.get("error") == line)
                ctx.check("nothing written, nobody asked", _files(rig) == before and push.calls == [])


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


# -- O2-3: POST crew/agent-model (a pick writes through the Agents form's own routes), main's door, Undo --------------

class _Push:
    """`studio.crew_push.put_live` answers `took` for the sheet's session (or `live` as given); put back on exit."""

    def __init__(self, took: bool = True, live: "list | None" = None):
        self.took, self.live, self.calls = took, live, []

    def __enter__(self):
        from halo_harness.studio import crew_push
        self._saved = crew_push.put_live

        def put_live(req, name, body, scope, text):
            self.calls.append((name, scope))
            return list(self.live) if self.live is not None else [{"session_id": SID, "took": self.took, "why": ""}]
        crew_push.put_live = put_live
        return self

    def __exit__(self, *exc):
        from halo_harness.studio import crew_push
        crew_push.put_live = self._saved


def _pick(rig, aid: str, model: str = RUN, owner: bool = True):
    return rig.api("POST", "crew/agent-model", {"session": SID, "agent": aid, "model": model}, owner=owner)


def _undo(rig, token, owner: bool = True):
    return rig.api("POST", "crew/agent-model/undo", {"undo": token}, owner=owner)


def _file(rig, name: str) -> Path:
    return rig.state / "crew" / "agents" / f"{name}.yaml"


def _files(rig) -> list:
    folder = rig.state / "crew" / "agents"
    return sorted(p.name for p in folder.glob("*.yaml")) if folder.is_dir() else []


def _body(name: str, scope: str = "yours") -> dict:
    from halo_harness.crew import store
    got = store.load("agent", name, scope=scope)
    return store.clean(got) if got else {}


@test
def test_a_pick_saves_his_agent_through_the_forms_put(ctx: Ctx):
    from tests.helpers.crew_rig import CrewRig
    with CrewRig() as rig:
        rig.studio()
        _his(rig, "sorter")
        before = _body("sorter")
        with _Rows(_row(rig)), _Push() as push:
            st, got = _pick(rig, "a1")
            after = _body("sorter")
            ctx.check(f"200, his file's model is the pick and nothing else changed, got {st} {after}",
                      st == 200 and after == dict(before, model=RUN))
            ctx.check(f"through the form's PUT, its push asked once for sorter, got {push.calls}",
                      push.calls == [("sorter", "yours")])
            ctx.check(f"took: the now line, got {got.get('line')!r}", got.get("line") == (
                "Saved: sorter runs on or:vendor/fast from its next start, in this session too, unless main names a model "
                "itself."))
            ctx.check(f"an undo token with no path, got {got.get('undo')}",
                      isinstance(got.get("undo"), dict) and "path" not in got["undo"]
                      and got["undo"].get("name") == "sorter" and got["undo"].get("made") is False
                      and got["undo"].get("old") == before)
        later = "Saved: sorter runs on or:vendor/fast from your next session."
        for push in (_Push(took=False), _Push(live=[{"session_id": "s-other", "took": True, "why": ""}]), _Push(live=[])):
            with _Rows(_row(rig)), push:
                got = _pick(rig, "a1")[1]
                ctx.check(f"not took for the sheet's session: the later line, got {got.get('line')!r}", got.get("line") == later)
        with _Rows(_row(rig)):
            st, got = rig.api("POST", "crew/agent-model", {"session": SID, "agent": "a1", "model": " "})
            ctx.check(f"no model picked: 422, got {st}", st == 422)
            _file(rig, "sorter").write_text(_file(rig, "sorter").read_text(encoding="utf-8").replace(
                "careful: ask-changes", "careful: whenever"), encoding="utf-8")
            st, got = _pick(rig, "a1")
            ctx.check(f"the form refuses: its status and Not saved with its error, got {st} {got}",
                      st == 422 and got.get("error") and got.get("line") == f"Not saved: {got['error'].rstrip('.')}.")


@test
def test_a_pick_makes_an_agent_for_each_made_kind(ctx: Ctx):
    from halo_harness.config.agents_md import _builtin_specs
    from halo_harness.crew.spec import tools_of
    from tests.helpers.crew_rig import CrewRig
    made = "Made {n}, an agent of yours on or:vendor/fast: main can start it now, unless it names a model itself."
    with CrewRig() as rig:
        rig.studio()
        with _Rows(_row(rig)):
            built = {}
            for aid in ("a2", "a3", "a4", "a5"):
                st, live = rig.api("POST", "crew/from-live", {"session": SID, "agent_id": aid})
                built[aid] = live.get("agent") or {}
                m = built[aid].get("model")
                # O2-8 (b): a body on `auto` is written "Auto"; a model of his own as it is
                ctx.check(f"{aid}: from-live says what it built, got {live.get('line')!r}", live.get("line") == (
                    f"Built from {_helpers()[int(aid[1:])]['name']} on {'Auto' if m == 'auto' else m}, not saved yet: read it, "
                    "change what you like, then Save."))
            ctx.check(f"BUILT-IN Judge's body is on auto, so its line says Auto, got {built['a4'].get('model')!r}",
                      built["a4"].get("model") == "auto")
            src = (Path(__file__).resolve().parent.parent / "halo_harness/studio/ui/src/routes/crew/store.ts").read_text(encoding="utf-8")
            ctx.check("the form's note (store.ts fillFromLive) writes Auto for a body on auto, his model as it is",
                      '/^auto$/i.test(String(form.model || "")) ? "Auto" : form.model' in src)
            ctx.check("SHIPPED: from-live builds the shipped planner", built["a2"] == _body("planner", "starter"))
            ctx.check("ROUTED: from-live builds the shipped media-reader", built["a3"] == _body("media-reader", "starter"))
            judge = _builtin_specs()["Judge"]
            want = {"format": "agent/1", "name": "judge", "does": judge.description[:200], "instructions": judge.body,
                    "model": "auto", "uses": ["read", "bash", "web"], "careful": "ask-changes"}
            ctx.check(f"BUILT-IN: from the built-in, got {built['a4']}", built["a4"] == want)
            ctx.check("BUILT-IN: never Agent or Task", not {"Agent", "Task"} & set(tools_of(built["a4"])[0]))
            with _Push():
                for aid in ("a2", "a3", "a4", "a5"):
                    name = built[aid]["name"]
                    st, got = _pick(rig, aid)
                    want = {k: v for k, v in dict(built[aid], model=RUN).items() if k != "needs"}  # needs: only on auto
                    ctx.check(f"{aid}: 200, his {name} = the built body on the pick, got {st} {_body(name)}",
                              st == 200 and _body(name) == want)
                    ctx.check(f"{aid}: the made line, got {got.get('line')!r}", got.get("line") == made.format(n=name))
                    ctx.check(f"{aid}: undo made, no path", (got.get("undo") or {}).get("made") is True
                              and "path" not in (got.get("undo") or {}))
            for name in ("planner", "media-reader", "judge", built["a5"]["name"]):
                _file(rig, name).unlink()
            with _Push(took=False):
                got = _pick(rig, "a4")[1]
                ctx.check(f"not took: the later made line, got {got.get('line')!r}", got.get("line") == (
                    "Made judge, an agent of yours on or:vendor/fast: main can start it from your next session."))


@test
def test_pack_and_claude_are_refused_409(ctx: Ctx):
    from tests.helpers.crew_rig import CrewRig
    with CrewRig() as rig:
        rig.studio()
        with _Rows(_row(rig)), _Push() as push:
            before = _files(rig)
            for aid in ("a6", "a7"):
                st, got = _pick(rig, aid)
                line = NOW_LINES[aid][3]
                ctx.check(f"{aid}: 409 with the kind's line, got {st} {got}",
                          st == 409 and got.get("line") == line and got.get("error") == line)
            ctx.check("nothing written, nobody asked", _files(rig) == before and push.calls == [])


@test
def test_undo_puts_back_or_deletes_while_the_sha_holds(ctx: Ctx):
    from tests.helpers.crew_rig import CrewRig
    with CrewRig() as rig:
        rig.studio()
        _his(rig, "sorter")
        with _Rows(_row(rig)):
            raw = _file(rig, "sorter").read_bytes()
            token = _pick(rig, "a1")[1].get("undo")
            st, got = _undo(rig, token)
            ctx.check(f"MINE: Put back, got {st} {got}", st == 200 and got.get("line") == "Put back: sorter runs on auto again.")
            ctx.check("his file byte-equal to before", _file(rig, "sorter").read_bytes() == raw)
            token = _pick(rig, "a4")[1].get("undo")
            st, got = _undo(rig, token)
            ctx.check(f"made: Taken back, got {st} {got}", st == 200 and got.get("line") == "Taken back: judge is gone.")
            ctx.check("the made file is gone", not _file(rig, "judge").exists())
            token = _pick(rig, "a1")[1].get("undo")
            edited = _file(rig, "sorter").read_bytes() + b"# a hand edit\n"
            _file(rig, "sorter").write_bytes(edited)
            st, got = _undo(rig, token)
            ctx.check(f"changed since: 409, nothing written, got {st} {got}", st == 409
                      and got.get("line") == "Not undone: sorter was changed since."
                      and _file(rig, "sorter").read_bytes() == edited)
            token = _pick(rig, "a1")[1].get("undo")
            _file(rig, "sorter").unlink()
            st, got = _undo(rig, token)
            ctx.check(f"gone before Undo: Not undone, got {st} {got}",
                      st == 409 and got.get("line") == "Not undone: sorter was changed since." and not _file(rig, "sorter").exists())
            token = _pick(rig, "a4")[1].get("undo")
            maps = rig.state / "crew" / "maps"
            maps.mkdir(parents=True, exist_ok=True)
            (maps / "shop.yaml").write_text("format: map/1\nname: shop\nboxes:\n- {id: judge, agent: judge}\nlines:\n"
                                            "- {from: main, to: judge}\n", encoding="utf-8")
            st, got = _undo(rig, token)
            ctx.check(f"a made judge his map names: 409 and the route's own words, got {st} {got}",
                      st == 409 and got.get("line") == "judge is used by map shop: take it out there first"
                      and _file(rig, "judge").exists())


@test
def test_undo_reads_no_path_it_is_sent(ctx: Ctx):
    import hashlib
    from halo_harness.crew import store
    from tests.helpers.crew_rig import CrewRig
    with CrewRig() as rig:
        rig.studio()
        _his(rig, "sorter")
        decoy = rig.root / "decoy.yaml"
        decoy.write_text("format: agent/1\nname: sorter\n", encoding="utf-8")
        with _Rows(_row(rig)):
            token = _pick(rig, "a1")[1].get("undo")
            sha = hashlib.sha256(decoy.read_bytes()).hexdigest()
            st, got = _undo(rig, dict(token, path=str(decoy), sha256=sha))
            ctx.check(f"the decoy's sha with its path: the route hashes HIS file, Not undone, got {st} {got}",
                      st == 409 and got.get("line") == "Not undone: sorter was changed since.")
            st, got = _undo(rig, dict(token, path=str(decoy)))
            ctx.check(f"an added path is answered as without it, got {st} {got}",
                      st == 200 and got.get("line") == "Put back: sorter runs on auto again.")
            asked: list = []
            saved = store.find
            store.find = lambda *a, **k: asked.append((a, k)) or saved(*a, **k)
            try:
                for bad in ({"name": "../x"}, {"name": "\\\\gpu-box\\share\\a"}, {"name": "A b"}, {"name": ""},
                            {"scope": "starter"}, {"scope": "pack"}, {"scope": "../yours"}, {"sha256": None}):
                    st, got = _undo(rig, dict(token, **bad))
                    ctx.check(f"{bad}: 422, got {st} {got}", st == 422 and got.get("error") == "not an undo this route made")
                st, got = _undo(rig, "sorter")
                ctx.check(f"no token mapping: 422, got {st}", st == 422)
            finally:
                store.find = saved
            ctx.check(f"nothing was looked up for a refused token, got {len(asked)}", asked == [])


class _Door:
    """`studio.live_agents_api.forward` stood in: a session whose model moves when the door or `model` switches it."""

    def __init__(self, *, terminal: bool, refuse: str = "", busy: bool = False):
        self.terminal, self.refuse, self.busy, self.model, self.cmds = terminal, refuse, busy, MAIN_MODEL, []

    def __call__(self, sid, cmd, fields):
        self.cmds.append(cmd)
        if cmd == "status":
            return 200, {"busy": self.busy, "model": self.model}
        if cmd == "slash":
            ref = fields["line"].split(" ", 1)[1]
            if not self.terminal:
                return 200, {"output": f"Current model: {self.model}", "ran": True}
            if self.refuse:
                return 200, {"output": self.refuse + "\nmore", "ran": True, "terminal": True}
            self.model = ref
            return 200, {"output": f"Model set to {ref}", "ran": True, "terminal": True}
        if cmd == "model":
            if self.refuse:
                return 502, {"error": self.refuse}
            self.model = fields["ref"]
            return 200, {"model": fields["ref"], "queued": True}
        return 422, {"error": "no"}

    def __enter__(self):
        from halo_harness.studio import live_agents_api
        self._saved = live_agents_api.forward
        live_agents_api.forward = self
        return self

    def __exit__(self, *exc):
        from halo_harness.studio import live_agents_api
        live_agents_api.forward = self._saved


@test
def test_mains_pick_runs_the_door(ctx: Ctx):
    from tests.helpers.crew_rig import CrewRig
    with CrewRig() as rig:
        rig.studio()
        with _Rows(_row(rig)):
            with _Door(terminal=True) as door:
                st, got = _pick(rig, "main")
                ctx.check(f"a terminal ran /model: Switched now, saved, got {st} {got}", st == 200 and got == {
                    "line": "Switched main to or:vendor/fast now, as /model in its terminal, and saved for your next launch.",
                    "undo": None, "terminal": True, "model": RUN})
                ctx.check(f"status, the door, status, got {door.cmds}", door.cmds == ["status", "slash", "status"])
            with _Door(terminal=False) as door:
                st, got = _pick(rig, "main")
                ctx.check(f"no terminal: the socket's model, this session only, got {st} {got}", st == 200 and got == {
                    "line": "Switched main to or:vendor/fast for this session; not saved for your next launch.",
                    "undo": None, "terminal": False, "model": RUN})
                ctx.check(f"the model command was sent, got {door.cmds}", door.cmds[:3] == ["status", "slash", "model"])
            with _Door(terminal=True, refuse="unknown model: or:vendor/none") as door:
                st, got = _pick(rig, "main", "or:vendor/none")
                ctx.check(f"a refused ref: Not switched with the door's first line, got {st} {got}",
                          got.get("line") == "Not switched: unknown model: or:vendor/none." and got.get("terminal") is True
                          and got.get("model") == MAIN_MODEL and st != 200)
            with _Door(terminal=False, refuse="unknown model: or:vendor/none") as door:
                got = _pick(rig, "main", "or:vendor/none")[1]
                ctx.check(f"no terminal, the model command refused: its error, got {got}",
                          got.get("line") == "Not switched: unknown model: or:vendor/none." and got.get("terminal") is False)
            with _Door(terminal=True, busy=True) as door:
                st, got = _pick(rig, "main")
                ctx.check(f"main in a turn: 409 before the door, got {st} {got}", st == 409 and got == {
                    "line": "Not switched: main is in a turn: pick again when it ends.", "undo": None, "terminal": None,
                    "model": MAIN_MODEL})
                ctx.check(f"nothing sent but the status, got {door.cmds}", door.cmds == ["status"])


@test
def test_the_two_routes_are_owner_only(ctx: Ctx):
    from tests.helpers.crew_rig import CrewRig
    with CrewRig() as rig:
        rig.studio()
        _his(rig, "sorter")
        with _Rows(_row(rig)), _Push():
            raw = _file(rig, "sorter").read_bytes()
            ctx.check("POST crew/agent-model without the owner's proof: 403", _pick(rig, "a1", owner=False)[0] == 403)
            ctx.check("nothing written", _file(rig, "sorter").read_bytes() == raw)
            token = _pick(rig, "a1")[1].get("undo")
            ctx.check("POST crew/agent-model/undo without the owner's proof: 403", _undo(rig, token, owner=False)[0] == 403)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
