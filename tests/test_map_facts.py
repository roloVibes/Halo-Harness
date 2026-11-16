"""tests.test_map_facts -- Halo 3.6.0.2 "Session map" R38: what a plain session sends the model.

1. (the golden, the package's FIRST commit, recorded GREEN on the 3.6.0.1 base b7ffce28) a real `Session` on the
   default map (`crew.map` unset: the starter, crew/map_control.py PlainMap) talks to a mock upstream for two turns --
   "Hello." then a Workflow call that runs a saved crew workflow `review` (coder, then reviewer) on the step runner --
   and every request body main sent is byte-equal to tests/fixtures/map_facts_plain_requests.json once the volatile
   parts are normalised (the scratch home and folder, today's date, the OS line). The map's frames, row tags, hops and
   the facts note never reach what a plain session sends: if a later change makes this red, the change is wrong. The
   fixture is never edited (as tests/test_crew_compile.py's RECORDED_* are never edited).

The tools are `default_tools(platform="linux")` so the one fixture holds on Windows, macOS and Linux (PowerShell is
win32-only). Mock upstream, a fake spawn for the steps' agents; no real model. Record (only on the base):
HALO_RECORD_MAP_FACTS=1 python -m tests.test_map_facts. Run: python -m tests.test_map_facts
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import tempfile
import threading
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MODEL = "or:mock/map-facts-plain"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "map_facts_plain_requests.json"
WORKFLOW = {"format": "workflow/1", "name": "review", "for": "Code a change, then review it.",
            "steps": [{"name": "Code", "agents": ["coder"]}, {"name": "Review", "agents": ["reviewer"]}]}
_ENV = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_OPENROUTER_BASE_URL", "BRIDGE_TEST_NO_BACKGROUND_NET",
        "OLLAMA_HOST", "HALO_NO_UPDATER", "HALO_SESSION_PARENT", "HALO_MODELS_ROSTER")


def _scenario(handler, body) -> None:
    """Turn 1: "Hello."; turn 2: a Workflow call, then "Done." once its result is back."""
    from tests.helpers.mock_openai import _finish
    from tests.helpers.session_rig import text_step, tool_step
    msgs = [m for m in (body or {}).get("messages") or [] if isinstance(m, dict)]
    if any(m.get("role") == "tool" for m in msgs):
        _finish(handler, text_step("Done."))
    elif not any(m.get("role") == "assistant" for m in msgs):
        _finish(handler, text_step("Hello."))
    else:
        _finish(handler, tool_step(("Workflow", {"name": "review", "task": "fix the retry"}, "call_w")))


def _spawn(*, runtime, tool_id, tool_input, tool_name, on_event=None, on_child=None):
    """A step's agent: its row in the session's tree, handed to on_child as run_agent_call does; it did its part."""
    from halo_harness.agent.agent_registry import tree_for
    from halo_harness.tools.base import ToolResult
    from tests.helpers.workflow_fakes import FakeChild
    who = str(tool_input.get("subagent_type") or "")
    child = FakeChild(f"step-{who}")
    tree_for(runtime.parent).add(child.agent_id, parent="main", name=who, state="running", kind="subagent")
    if on_child is not None:
        on_child(child)
    return [], ToolResult(f"<task_result>{who} did it</task_result>")


def _session(home: Path, cwd: Path, mock):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.crew.map_session import prepare
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.tools.registry import ToolRegistry, default_tools
    reg = ToolRegistry(default_tools(platform="linux"))
    crew_map = prepare(None, cwd)[0]
    s = Session(cwd=cwd, model_ref=parse_model_ref(MODEL), model_profile=ModelProfile(),
                creds=ProviderCreds(base_url=mock.base_url, api_key="k"), state_dir=home / "sess-state", model_label=MODEL,
                session_context=SessionContext(cwd=cwd, model_label=MODEL, tool_registry=reg), max_turns=6,
                permission_engine=PermissionEngine(mode="bypassPermissions", cwd=cwd), crew_map=crew_map)
    s.interactive = True
    return s


def _turn(s, text: str) -> None:
    done = threading.Event()

    def drive():
        try:
            list(s.turn(text))
        finally:
            done.set()
    t = threading.Thread(target=drive, daemon=True, name="map-facts-turn")
    t.start()
    done.wait(30)
    t.join(5)


def normalise(text: str, home: Path, cwd: Path) -> str:
    import datetime
    for p in sorted({str(cwd), str(home)}, key=len, reverse=True):
        for v in {p, p.replace("\\", "/"), json.dumps(p)[1:-1], json.dumps(p.replace("\\", "/"))[1:-1]}:
            text = text.replace(v, "<cwd>" if p == str(cwd) else "<home>")
    text = text.replace(datetime.date.today().isoformat(), "<date>")
    return text.replace(f"{platform.system()} {platform.release()}", "<os>")


def plain_requests() -> "tuple[list, dict]":
    """(main's request bodies, normalised JSON text each; facts about the run) for the two turns."""
    from halo_harness.crew import store
    from halo_harness.tools import workflow as W
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream
    saved = {k: os.environ.get(k) for k in _ENV}
    home = Path(tempfile.mkdtemp(prefix="map-facts-"))
    cwd = home / "proj"
    cwd.mkdir()
    for k in ("BRIDGE_STATE_DIR", "HALO_SESSION_PARENT"):
        os.environ.pop(k, None)
    os.environ.update({"BRIDGE_TEST_HOME": str(home), "BRIDGE_TEST_NO_BACKGROUND_NET": "1",
                       "OLLAMA_HOST": "http://127.0.0.1:9", "HALO_NO_UPDATER": "1",
                       "HALO_MODELS_ROSTER": "0"})  # the roster (a catalog, cached per process) off: pinned
    mock = MockUpstream().start()
    os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
    SCENARIOS["map-facts-plain"] = _scenario
    was = W.SPAWN
    W.SPAWN = _spawn
    s = None
    try:
        p = store.path_for("workflow", "review")
        p.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(p, store.dump(WORKFLOW))
        s = _session(home, cwd, mock)
        facts = {"map": getattr(getattr(s, "team_control", None), "map_name", None)}
        _turn(s, "Say hello.")
        _turn(s, "Run the review workflow on the retry fix.")
        facts["result"] = next((str(n.get("content")) for n in s.log.nodes() if n.get("type") == "tool_result"), "")
        bodies = [r["body"] for r in mock.requests if r.get("method") == "POST" and str(r.get("path")).endswith("/chat/completions")]
        return [normalise(json.dumps(b, ensure_ascii=False), home, cwd) for b in bodies], facts
    finally:
        W.SPAWN = was
        try:
            if s is not None:
                s.close_runtimes()
        except Exception:
            pass
        mock.stop()
        SCENARIOS.pop("map-facts-plain", None)
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        shutil.rmtree(home, ignore_errors=True)


@test
def test_plain_session_request_unchanged(ctx: Ctx):
    got, facts = plain_requests()
    if os.environ.get("HALO_RECORD_MAP_FACTS") == "1":
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(got, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ctx.check(f"the session runs on the default map (the starter), got {facts['map']!r}", facts["map"] == "starter")
    ctx.check(f"the Workflow call ran the crew workflow on the step runner, got {facts['result'][:160]!r}",
              "crew workflow review · ran on the step runner · done" in facts["result"])
    ctx.check(f"three requests: turn 1, turn 2's call, turn 2 after the result, got {len(got)}", len(got) == 3)
    want = json.loads(FIXTURE.read_text(encoding="utf-8")) if FIXTURE.is_file() else []
    first = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), None)
    where = ""
    if first is not None:
        a, b = got[first], want[first]
        at = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        where = f" request {first} differs at {at}: got {a[max(0, at - 80):at + 120]!r} want {b[max(0, at - 80):at + 120]!r}"
    ctx.check(f"every request body byte-equal to the recorded plain session's ({len(want)} recorded){where}",
              len(got) == len(want) and first is None)
    again, _f = plain_requests()
    ctx.check("the same both times (no time or ordering left in)", again == got)


# ---- 3.6.0.2 P2 batch 3 (R40 R21 R24 R41 R46): the facts of a session's map, the status row ------------------------

class _Log:
    session_id = "s-facts"

    def __init__(self) -> None:
        self._nodes: list = []

    def _append(self, node: dict) -> dict:
        self._nodes.append(node)
        return node

    def nodes(self) -> list:
        return list(self._nodes)


class _Sess:
    """The parts of a Session the status row and map_facts read."""

    def __init__(self, tc=None) -> None:
        self.log = _Log()
        self.team_control = tc
        self.turn_count = 0
        self.busy = False

    def status_event(self):
        from types import SimpleNamespace
        return SimpleNamespace(data={"turn": self.turn_count})


def _default_control(cwd: Path):
    """The default map's control as a session gets it with `crew.map` unset (source "default": the starter)."""
    from halo_harness.crew.map_control import control_for
    from halo_harness.crew.map_session import prepare
    compiled = prepare(None, cwd)[0]
    return control_for(compiled, cwd=cwd)


def _config_path() -> Path:
    from halo_harness.theme import _config_path as p
    return p()


def _config() -> dict:
    return json.loads(_config_path().read_text(encoding="utf-8"))


def _status(sess, cwd: Path) -> dict:
    from halo_harness.remote.base import _BaseHandle
    return _BaseHandle(sess, cwd).status()


@test
def test_facts_running_next_since(ctx: Ctx):
    import time
    from tests.helpers.config_seed import ConfigHome
    with ConfigHome() as env:
        from halo_harness.crew import map_events
        from halo_harness.crew import map_facts
        from halo_harness.theme import set_config_value, unset_config_value
        s = _Sess(_default_control(env.repo))
        map_events.started(s, s.team_control)
        logged = next((n["data"] for n in s.log.nodes() if n.get("event") == "map_start"), {})
        set_config_value("crew.map", "review-flow")
        f = map_facts.facts(s)
        ctx.check(f"running map starter, its words 'starter (the default)', plain, got {f}",
                  f["map"] == "starter" and f["words"] == "starter (the default)" and f["plain"] is True)
        ctx.check(f"F1: the start time is map_start's t ({logged.get('t')}), got {f['since']}",
                  f["since"] is not None and f["since"] == logged.get("t"))
        ctx.check(f"F4: next review-flow since about now, got {f['next']} {f['next_since']}",
                  f["next"] == "review-flow" and isinstance(f["next_since"], float)
                  and abs(f["next_since"] - time.time()) < 5)
        unset_config_value("crew.map")
        f = map_facts.facts(s)
        ctx.check(f"crew.map unset: next None (new sessions draw the default), got {f['next']} {f['next_words']}",
                  f["next"] is None and f["next_words"] == "starter (the default)")


@test
def test_s13_golden(ctx: Ctx):
    import re
    import time
    from halo_harness.crew import map_facts
    got = map_facts.s13("starter (the default)", "review-flow")
    ctx.check(f"S13 letter for letter, got {got!r}", got == "This session keeps running on starter (the default), as it "
              "started. Start a new session to run on review-flow.")
    tail = map_facts.terminal_tail("starter (the default)")
    ctx.check(f"the terminal tail, got {tail!r}",
              tail == "In the terminal: quit and run halo again; /clear keeps starter (the default).")
    ctx.check("the words of the default and of a named map",
              map_facts.words_of("starter", True) == "starter (the default)"
              and map_facts.words_of("review-flow") == "review-flow" and map_facts.words_of(None) == "starter (the default)")
    ctx.check(f"%H:%M by pattern, got {map_facts.hhmm(time.time())!r}",
              re.fullmatch(r"\d{2}:\d{2}", map_facts.hhmm(time.time())) is not None)


@test
def test_since_written_with_crew_map_in_one_write(ctx: Ctx):
    import time
    from tests.helpers.config_seed import ConfigHome
    with ConfigHome():
        from halo_harness import privateio
        from halo_harness import theme
        from halo_harness.crew.changes_map import config_text
        p = _config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        rest = {"theme": "dark", "improve": {"model": "or:x/y"}, "crew": {"keep": 1}}
        p.write_text(json.dumps(rest), encoding="utf-8")
        real, writes = privateio.write_private_atomic, []

        def counting(path, text, *a, **k):
            writes.append(str(path))
            return real(path, text, *a, **k)
        privateio.write_private_atomic = counting
        try:
            theme.set_config_value("crew.map", "shop")
        finally:
            privateio.write_private_atomic = real
        data = _config()
        since = data.get("crew", {}).get("map_since") or {}
        ctx.check(f"one write, got {len(writes)}", len(writes) == 1)
        ctx.check(f"crew.map shop and map_since {{map shop, at now}}, got {data.get('crew')}",
                  data["crew"].get("map") == "shop" and since.get("map") == "shop"
                  and isinstance(since.get("at"), float) and abs(since["at"] - time.time()) < 5)
        others = {k: v for k, v in data.items() if k != "crew"}
        ctx.check(f"every other key untouched, got {others}",
                  others == {k: v for k, v in rest.items() if k != "crew"} and data["crew"].get("keep") == 1)
        crew = json.loads(config_text("review-flow"))["crew"]
        ctx.check(f"config_text writes map_since with the map, got {crew}",
                  crew.get("map") == "review-flow" and (crew.get("map_since") or {}).get("map") == "review-flow")
        crew = json.loads(config_text(None))["crew"]
        ctx.check(f"config_text(None): map out, map_since names none, got {crew}",
                  "map" not in crew and (crew.get("map_since") or {}).get("map", "x") is None
                  and isinstance(crew["map_since"].get("at"), float))
        theme.set_config_value("crew.map", None)  # as agent/main_model_check.py takes it out
        crew = _config()["crew"]
        ctx.check(f"set_config_value('crew.map', None): map_since names none, got {crew}",
                  crew.get("map_since", {}).get("map", "x") is None and isinstance(crew["map_since"].get("at"), float))
        theme.set_config_value("crew.map", "shop")
        theme.unset_config_value("crew.map")  # `halo config unset crew.map`
        crew = _config().get("crew") or {}
        ctx.check(f"unset_config_value('crew.map'): map_since names none, got {crew}",
                  "map" not in crew and (crew.get("map_since") or {}).get("map", "x") is None)
        theme.set_config_value("theme", "light")
        ctx.check("another key leaves map_since alone", _config()["crew"].get("map_since") == crew.get("map_since"))


@test
def test_since_dropped_when_config_set_elsewhere(ctx: Ctx):
    from tests.helpers.config_seed import ConfigHome
    with ConfigHome() as env:
        from halo_harness import theme
        from halo_harness.crew import map_facts
        theme.set_config_value("crew.map", "shop")
        data = _config()
        first = data["crew"]["map_since"]
        data["crew"]["map"] = "other"  # by hand: map_since still names shop
        _config_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
        f = map_facts.facts(_Sess(None))
        ctx.check(f"a hand edit: next other, since not known (T11), got {f['next']} {f['next_since']}",
                  f["next"] == "other" and f["next_since"] is None)
        theme.set_config_value("crew.map", "other")
        f = map_facts.facts(_Sess(None))
        ctx.check(f"switched through Halo: valid again, got {f['next']} {f['next_since']}",
                  f["next"] == "other" and isinstance(f["next_since"], float))
        at = _config()["crew"]["map_since"]["at"]
        theme.set_config_value("crew.map", "other")
        ctx.check(f"choosing the map in use again is no switch: the time stays ({first['map']} -> other at {at})",
                  _config()["crew"]["map_since"] == {"map": "other", "at": at} and map_facts.next_map() == ("other", at))


@test
def test_status_row_reads_config_through_stat_cache(ctx: Ctx):
    import time
    from tests.helpers.config_seed import ConfigHome
    with ConfigHome() as env:
        from halo_harness import theme
        p = _config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"crew": {"map": "aa"}}), encoding="utf-8")
        now = time.time()
        os.utime(p, (now - 10, now - 10))

        class _Counting:
            n = 0

            def loads(self, *a, **k):
                _Counting.n += 1
                return json.loads(*a, **k)

            def __getattr__(self, k):
                return getattr(json, k)
        was = theme.json
        theme.json = _Counting()
        try:
            s = _Sess(_default_control(env.repo))
            a, b = _status(s, env.repo), _status(s, env.repo)
            ctx.check(f"two polls parse config at most once, got {_Counting.n}", _Counting.n <= 1)
            ctx.check(f"both say map_next aa, got {a.get('map_next')} {b.get('map_next')}",
                      a.get("map_next") == "aa" and b.get("map_next") == "aa")
            p.write_text(json.dumps({"crew": {"map": "bb"}}), encoding="utf-8")  # same size, by hand
            os.utime(p, (now - 9, now - 9))
            c = _status(s, env.repo)
        finally:
            theme.json = was
        ctx.check(f"a hand edit is read: map_next bb, map_next_since None (T11), got {c.get('map_next')} "
                  f"{c.get('map_next_since')!r}", c.get("map_next") == "bb" and "map_next_since" in c
                  and c["map_next_since"] is None)


@test
def test_status_row_carries_built(ctx: Ctx):
    from tests.helpers.config_seed import ConfigHome
    with ConfigHome() as env:
        from halo_harness.crew import map_events
        from halo_harness.peers.local_view import session_row
        from halo_harness.theme import set_config_value
        s = _Sess(_default_control(env.repo))
        map_events.started(s, s.team_control)
        set_config_value("crew.map", "review-flow")
        st = _status(s, env.repo)
        ctx.check(f"asked False before the first turn, built None, got {st.get('asked')!r} {st.get('built')!r}",
                  st.get("asked") is False and "built" in st and st["built"] is None)
        built = {"id": "r1", "outcome": "applied", "wrote": [{"kind": "map", "name": "review-flow", "added": True}],
                 "undo": "u1", "next": "review-flow", "this_session": "starter", "t": 1.5}
        s._builder_built = {**built, "maps": {"review-flow": {"boxes": []}}}
        s.turn_count = 1
        st = _status(s, env.repo)
        ctx.check(f"built is the last outcome without maps, got {st.get('built')}", st.get("built") == built)
        ctx.check(f"asked True after a turn, got {st.get('asked')!r}", st.get("asked") is True)
        s.turn_count, s._map_asked = 0, True  # /clear starts the count again; the session has still been asked
        ctx.check("asked stays True after /clear", _status(s, env.repo).get("asked") is True)
        row = session_row({"session_id": "s-facts", "cwd": str(env.repo)}, st, [])
        want = {"map_since": float, "map_plain": bool, "map_next": str, "map_next_since": float, "built": dict,
                "asked": bool}
        got = {k: row.get(k) for k in want}
        ctx.check(f"session_row forwards all six fields, typed, got {got}",
                  all(isinstance(row.get(k), t) for k, t in want.items()) and row["built"] == built
                  and row["map_plain"] is True and row["map_next"] == "review-flow")
        bad = session_row({"session_id": "s-x"}, {"map_since": "x", "map_plain": 1, "map_next": 3, "map_next_since": True,
                                                  "built": [], "asked": "yes"}, [])
        ctx.check(f"a wrong type is dropped, got {[bad.get(k) for k in want]}",
                  [bad.get(k) for k in want] == [None, False, None, None, None, False])


@test
def test_status_row_has_no_switch_field(ctx: Ctx):
    """R46 GUARD (green on the base too: no switch field exists; it must stay so)."""
    from tests.helpers.config_seed import ConfigHome
    with ConfigHome() as env:
        from halo_harness.peers.local_view import session_row
        from halo_harness.theme import set_config_value
        s = _Sess(_default_control(env.repo))
        set_config_value("crew.map", "review-flow")  # a switch would be offered here if it existed
        st = _status(s, env.repo)
        row = session_row({"session_id": "s-facts", "cwd": str(env.repo)}, st, [])
        ctx.check("no 'switch' in the status or the row", "switch" not in st and "switch" not in row)
        ctx.check("no set_map / map_switch either",
                  not any(k in st or k in row for k in ("set_map", "map_switch")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
