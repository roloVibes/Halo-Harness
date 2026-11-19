"""tests.test_ready_lines -- Halo 3.6.0.5, the true lines (package t: C18 to C22): after a Builder card is applied in a
session on Auto, the result ends with what is ready in this session now and what waits for the next session, computed
from what the session really has (crew/ready_now.py); the `builder_done` frame and its log receipt carry the same
answer; nothing about the session changes, and a map of his or an undo gets no line.

Real Sessions on the default map; the turns run against the mock upstream (nothing calls a real model). Every test sets
BRIDGE_TEST_HOME to a fresh scratch folder and restores it and removes the folder in a finally.
Run: python -m tests.test_ready_lines
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
import time
import types
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
ROOT = Path(__file__).resolve().parent.parent
SCENARIO = "ready-lines"
MODEL = f"or:mock/{SCENARIO}"
DEAD = "http://127.0.0.1:9"
ENV = ("BRIDGE_TEST_HOME", "BRIDGE_OPENROUTER_BASE_URL", "BRIDGE_STATE_DIR")
CHECKER = {"format": "agent/1", "name": "checker", "does": "Checks a change.",
           "instructions": "You check the change you are given and say what is wrong with it.", "model": "auto",
           "careful": "ask-changes",
           "uses": ["read"]}
REVIEW = {"format": "workflow/1", "name": "review", "for": "review a change",
          "steps": [{"name": "code", "agents": ["coder"]}, {"name": "check", "agents": ["checker"]}]}
CARD = [{"tool": "agent_make", "args": {"name": "checker", "does": "Checks a change.", "uses": ["read"]}},
        {"tool": "workflow_make", "args": {"name": "review", "for": "review a change",
                                           "steps": [{"name": "code", "agents": ["coder"]},
                                                     {"name": "check", "agents": ["checker"]}]}}]
P1_REVIEW = "Ready in this session now: the workflow review."
P2_STEP = ("Saved for your next session: the agent checker (this session's list of agents was fixed when it started; "
           "as a step of the workflow review it can run now).")
P2_AG1 = "Saved for your next session: the agent checker (this session's list of agents was fixed when it started)."
P2_AG2 = "Saved for your next session: the agent checker (this session keeps the checker it started with)."
P2_WF = ("Saved for your next session: the workflow review (this session started with no workflow, so it has no "
         "Workflow tool).")
P3_REVIEW = ("Not run under its name: the workflow review (this project has its own workflow review, which runs "
             "first).")


# -- a scratch home ------------------------------------------------------------------------------------------------

def _scoped(fn):
    """Run `fn(home)` with BRIDGE_TEST_HOME a fresh folder (its project at home/proj); restore and remove it after."""
    saved = {k: os.environ.get(k) for k in ENV}
    home = Path(tempfile.mkdtemp(prefix="ready-lines-"))
    os.environ.pop("BRIDGE_STATE_DIR", None)
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    (home / "proj").mkdir()
    try:
        return fn(home)
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        shutil.rmtree(home, ignore_errors=True)


def _fresh(home: Path) -> None:
    """The same home path, empty again (a second run whose paths equal the first's)."""
    shutil.rmtree(home, ignore_errors=True)
    home.mkdir()
    (home / "proj").mkdir()


def _state() -> Path:
    from halo_harness.providers.config import default_state_dir
    return Path(default_state_dir())


def _write(kind: str, body: dict, *, proj: "Path | None" = None) -> Path:
    """A crew file written as the card writes it: yours, or (proj) the project's own."""
    from halo_harness.crew import store
    if proj is not None:
        path = proj / ".halo" / "crew" / store.KINDS[kind] / f"{body['name']}.yaml"
    else:
        path = store.path_for(kind, body["name"])
    path.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(path, store.dump(body))
    return path


def _shop() -> None:
    """His map `shop`: the shipped auto.yaml's boxes and lines under yours, its `name:` line changed."""
    from halo_harness.crew import store
    raw = store.read(store.SHIPPED / "maps" / "auto.yaml")
    mine = _state() / "crew" / "maps" / "shop.yaml"
    mine.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(mine, store.dump({"format": raw["format"], "name": "shop", "main": raw.get("main") or {"agent": "main"},
                                       "boxes": raw["boxes"], "lines": raw["lines"]}))


def _auto_session(home: Path, *, workflow_tool: bool = True, agents=None, base_url: str = DEAD, crew_map=None):
    """A real, never-turned Session on the default map (as tests/test_builder_session_parity.py builds one), with
    `agents` its start agents and, when `workflow_tool` is False, the Workflow tool taken out before it is made (the
    call workflows/offer.py makes). `crew_map`: another map (his) instead of the default."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.crew.map_session import prepare
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.tools.builder_tool import BuilderTool
    from halo_harness.tools.registry import ToolRegistry, default_tools
    cwd = home / "proj"
    cwd.mkdir(exist_ok=True)
    reg = ToolRegistry(default_tools() + [BuilderTool()])
    if not workflow_tool:
        reg.remove_tool("Workflow")
    s = Session(cwd=cwd, model_ref=parse_model_ref(MODEL), model_profile=ModelProfile(),
                creds=ProviderCreds(base_url=base_url, api_key="k"), state_dir=home / "sess-state", model_label=MODEL,
                crew_map=crew_map if crew_map is not None else prepare(None, cwd)[0],
                session_context=SessionContext(cwd=cwd, model_label=MODEL, tool_registry=reg), max_turns=6,
                permission_engine=PermissionEngine(mode="default", cwd=cwd), agents=agents)
    s.interactive = True
    return s


def _apply(s, calls=None, at: "float | None" = None):
    """The card applied straight through crew/session_tool.py (preview, then finish with Apply)."""
    from halo_harness.crew import session_tool
    s._map_started_at = time.time() if at is None else at
    pv = session_tool.preview(s, {"changes": calls or CARD})
    return pv, session_tool.finish(pv, "Apply them", s)


def _apply_all(qs: list):
    return {q["question"]: (q["options"][0]["label"] if q["question"].startswith("Apply") else q["options"][1]["label"])
            for q in qs}


def _drive(calls, answer_fn, *, home: Path, workflow_tool: bool = True, crew_map_flags=None, agents_fn=None,
           before=None, started_at=None, go_on: bool = False, inspect=None) -> dict:
    """A REAL interactive Session turn against the mock upstream: the model calls Builder once with `calls`, the card is
    answered by `answer_fn(questions)`, then it says `Done.`; with `go_on`, a second turn ("go on") answered `ok.`.
    BRIDGE_TEST_HOME must name `home` (the caller's `_scoped`). Returns the yielded events, the `builder_done` frames,
    the log's receipts, the result, the session and the mock's requests."""
    from halo_harness.agent.agent_registry import tree_for
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, ScriptedTurns
    from tests.helpers.session_rig import text_step, tool_step
    saved = os.environ.get("BRIDGE_OPENROUTER_BASE_URL")
    mock = MockUpstream().start()
    os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
    steps = [tool_step(("Builder", {"changes": calls}, "call_b")), text_step("Done.")] + ([text_step("ok.")] if go_on else [])
    SCENARIOS[SCENARIO] = ScriptedTurns(steps)
    out: dict = {"frames": [], "error": None, "events": []}
    try:
        if before:
            before(home)
        crew_map = None
        if crew_map_flags is not None:
            from halo_harness.crew.map_session import prepare
            crew_map = prepare(crew_map_flags, home / "proj")[0]
        agents = agents_fn(home / "proj") if agents_fn else None
        s = _auto_session(home, workflow_tool=workflow_tool, agents=agents, base_url=mock.base_url, crew_map=crew_map)
        s._map_started_at = time.time() if started_at is None else started_at
        out["names_before"] = list(s.tool_registry.names())
        out["agents_before"] = dict(s.agent_runtime.agents)
        tree_for(s).add_listener(lambda kind, aid, data: out["frames"].append(json.loads(json.dumps(data, default=str)))
                                 if kind == "builder_done" else None)
        done = threading.Event()

        def drive():
            try:
                out["events"].extend(s.turn("make me a checker and a review workflow"))
                if go_on:
                    out["events"].extend(s.turn("go on"))
            except Exception as e:
                out["error"] = e
            finally:
                done.set()
        threading.Thread(target=drive, daemon=True).start()
        end = time.monotonic() + 30
        while time.monotonic() < end and not done.is_set() and not any(e.kind == "question" for e in list(out["events"])):
            time.sleep(0.02)
        q = next((e for e in list(out["events"]) if e.kind == "question"), None)
        if q is not None:
            s.resolve_question(q.data["id"], answer_fn((q.data.get("input") or {}).get("questions") or []))
        out["ended"] = done.wait(30)
        out["result"] = str(next((n.get("content") for n in s.log.nodes() if n.get("type") == "tool_result"), ""))
        out["receipts"] = [n for n in s.log.nodes() if n.get("type") == "receipt" and n.get("event") == "builder_done"]
        out["built"] = getattr(s, "_builder_built", None)
        out["session"] = s
        out["requests"] = [r for r in mock.requests if r.get("method") == "POST" and str(r.get("path", "")).endswith(
            "/chat/completions")]
        out["inspect"] = inspect(s) if inspect else None
        return out
    finally:
        mock.stop()
        SCENARIOS.pop(SCENARIO, None)
        os.environ.pop("BRIDGE_OPENROUTER_BASE_URL", None) if saved is None else \
            os.environ.__setitem__("BRIDGE_OPENROUTER_BASE_URL", saved)


def _keys(d) -> dict:
    return {k: (d or {})[k] for k in ("ready", "later", "p3") if k in (d or {})}


def _p_of(text: str) -> list:
    from halo_harness.crew import ready_now
    return [ln for ln in str(text).split("\n") if ln.startswith(ready_now.FIRST_WORDS)]


# -- entry 1: ready_and_later and p_lines ---------------------------------------------------------------------------

@test
def test_workflow_ready_now_when_the_session_has_the_workflow_tool(ctx: Ctx):
    def body(home):
        from halo_harness.crew import ready_now
        review, checker = _write("workflow", REVIEW), _write("agent", CHECKER)
        s = _auto_session(home)
        ans = ready_now.ready_and_later(s, [str(review), str(checker)])
        lines = ready_now.p_lines(ans)
        ctx.check(f"review is ready, no P3, the first line is P1, got {ans} {lines}",
                  ans is not None and ans["ready"] == ["review"] and ans["p3"] == [] and lines[:1] == [P1_REVIEW])
        tidy = _write("workflow", {**REVIEW, "name": "tidy"})
        two = ready_now.p_lines(ready_now.ready_and_later(s, [str(review), str(tidy)]))
        ctx.check(f"two workflows on one line, in written order, got {two}",
                  two == ["Ready in this session now: the workflow review, the workflow tidy."])
    _scoped(body)


@test
def test_workflow_waits_when_the_tool_was_dropped_at_start(ctx: Ctx):
    def body(home):
        from halo_harness.crew import ready_now
        review = _write("workflow", REVIEW)
        ans = ready_now.ready_and_later(_auto_session(home, workflow_tool=False), [str(review)])
        ctx.check(f"WF, got {ans}", ans == {"ready": [], "later": [{"kind": "workflow", "name": "review", "why": "WF"}],
                                            "p3": []})
        ctx.check(f"the WF line, got {ready_now.p_lines(ans)}", ready_now.p_lines(ans) == [P2_WF])
    _scoped(body)


@test
def test_project_workflow_of_the_same_name_gets_p3(ctx: Ctx):
    def body(home):
        from halo_harness.crew import ready_now
        from tests.helpers.trust_dir import trust
        trust(home / "proj")
        _write("workflow", REVIEW, proj=home / "proj")
        review = _write("workflow", REVIEW)
        ans = ready_now.ready_and_later(_auto_session(home), [str(review)])
        ctx.check(f"P3, in neither ready nor later, got {ans}",
                  ans is not None and ans["p3"] == ["review"] and ans["ready"] == [] and ans["later"] == [])
        ctx.check(f"the P3 line, got {ready_now.p_lines(ans)}", ready_now.p_lines(ans) == [P3_REVIEW])
    _scoped(body)


@test
def test_new_agent_waits_list_fixed_at_start(ctx: Ctx):
    def body(home):
        from halo_harness.crew import ready_now
        checker = _write("agent", CHECKER)
        ans = ready_now.ready_and_later(_auto_session(home), [str(checker)])
        ctx.check(f"AG1 with no step, got {ans}",
                  ans == {"ready": [], "later": [{"kind": "agent", "name": "checker", "why": "AG1"}], "p3": []})
        ctx.check(f"the AG1 line, got {ready_now.p_lines(ans)}", ready_now.p_lines(ans) == [P2_AG1])
    _scoped(body)


@test
def test_known_agent_keeps_its_start_spec(ctx: Ctx):
    def body(home):
        from halo_harness.config.agents_md import discover_agents
        from halo_harness.crew import ready_now
        _write("agent", CHECKER)
        start = discover_agents(home / "proj")
        ctx.check("checker is known at start", "checker" in start)
        s = _auto_session(home, agents=start)
        checker = _write("agent", {**CHECKER, "does": "Checks a change twice."})
        ans = ready_now.ready_and_later(s, [str(checker)])
        ctx.check(f"AG2, got {ans}", ans is not None and ans["later"] == [{"kind": "agent", "name": "checker", "why": "AG2"}])
        ctx.check(f"the AG2 line, got {ready_now.p_lines(ans)}", ready_now.p_lines(ans) == [P2_AG2])
    _scoped(body)


@test
def test_step_agent_of_a_ready_workflow_gets_the_step_clause(ctx: Ctx):
    def body(home):
        from halo_harness.crew import ready_now
        review, checker = _write("workflow", REVIEW), _write("agent", CHECKER)
        s = _auto_session(home)
        ans = ready_now.ready_and_later(s, [str(review), str(checker)])
        ctx.check(f"the step clause, got {ready_now.p_lines(ans)}", ready_now.p_lines(ans) == [P1_REVIEW, P2_STEP])
        from tests.helpers.trust_dir import trust
        trust(home / "proj")
        _write("agent", CHECKER, proj=home / "proj")  # the step runner now reads the project's checker, not the card's
        ans = ready_now.ready_and_later(s, [str(review), str(checker)])
        ctx.check(f"no clause when the step would run another file, got {ready_now.p_lines(ans)}",
                  ready_now.p_lines(ans) == [P1_REVIEW, P2_AG1])
    _scoped(body)


@test
def test_only_auto_and_only_what_the_card_wrote(ctx: Ctx):
    def body(home):
        from halo_harness.crew import ready_now
        from halo_harness.crew.compile import compile_map
        from halo_harness.crew.map_control import control_for
        review, checker = _write("workflow", REVIEW), _write("agent", CHECKER)
        s = _auto_session(home)
        auto_tc = s.team_control
        s.team_control = None
        ctx.check("no control: None", ready_now.ready_and_later(s, [str(review), str(checker)]) is None)
        _shop()
        s.team_control = control_for(compile_map("shop", cwd=home / "proj", state_dir=_state()), cwd=home / "proj",
                                     state_dir=_state())
        ctx.check(f"his map shop: None, got {ready_now.ready_and_later(s, [str(review)])}",
                  ready_now.ready_and_later(s, [str(review), str(checker)]) is None)
        s.team_control = auto_tc
        other = _write("agent", {**CHECKER, "name": "other"})
        ans = ready_now.ready_and_later(s, [str(_state() / "crew" / "maps" / "shop.yaml"), str(_state() / "config.json")])
        ctx.check(f"a map path and a config path name nothing, got {ans}", ans == {"ready": [], "later": [], "p3": []})
        ans = ready_now.ready_and_later(s, [str(checker)])
        ctx.check(f"an agent on disk not in wrote is not named, got {ans}",
                  other.is_file() and [i["name"] for i in ans["later"]] == ["checker"])
        bare = types.SimpleNamespace(cwd=home / "proj", team_control=auto_tc)
        ans = ready_now.ready_and_later(bare, [str(review), str(checker)])
        ctx.check(f"a bare session object: WF and AG1, never None, got {ans}",
                  ans == {"ready": [], "later": [{"kind": "workflow", "name": "review", "why": "WF"},
                                                 {"kind": "agent", "name": "checker", "why": "AG1"}], "p3": []})
    _scoped(body)


# -- entry 2: the Builder's result ends with the lines ---------------------------------------------------------------

@test
def test_auto_card_result_ends_with_p_lines(ctx: Ctx):
    def body(home):
        pv, out = _apply(_auto_session(home))
        ctx.check(f"the result ends with P1 and the step-clause P2, got {out[-300:]!r}",
                  out.endswith("\n" + P1_REVIEW + "\n" + P2_STEP))
        o = pv["outcome"]
        ctx.check(f"the outcome carries ready and later, no p3, got {_keys(o)}",
                  o.get("ready") == ["review"] and "p3" not in o
                  and o.get("later") == [{"kind": "agent", "name": "checker", "why": "AG1", "step": "review"}])
    _scoped(body)


@test
def test_p_lines_follow_the_3602_tail_letter_for_letter(ctx: Ctx):
    def body(home):
        from halo_harness.crew import ready_now
        at = time.time()
        pv1, out1 = _apply(_auto_session(home), at=at)
        _fresh(home)
        real = ready_now.ready_and_later
        ready_now.ready_and_later = lambda session, wrote: None
        try:
            pv2, out2 = _apply(_auto_session(home), at=at)
        finally:
            ready_now.ready_and_later = real
        m1 = out1.replace(pv1["outcome"]["undo"], "U")
        m2 = out2.replace(pv2["outcome"]["undo"], "U")
        ctx.check(f"with the lines: the result without them plus exactly the two lines, got {m1[-400:]!r} vs {m2[-300:]!r}",
                  m1 == m2 + "\n" + P1_REVIEW + "\n" + P2_STEP and not _p_of(m2))
    _scoped(body)


@test
def test_left_and_undo_cards_compute_nothing(ctx: Ctx):
    def body(home):
        from halo_harness.crew import ready_now, session_tool
        s = _auto_session(home)
        s._map_started_at = time.time()
        calls: list = []
        real = ready_now.ready_and_later
        ready_now.ready_and_later = lambda session, wrote: calls.append(wrote) or real(session, wrote)
        try:
            pv = session_tool.preview(s, {"changes": CARD})
            out = session_tool.finish(pv, "Leave them", s)
            ctx.check(f"left: no line, no key, not called, got {out[-200:]!r} {pv['outcome']}",
                      not _p_of(out) and not _keys(pv["outcome"]) and pv["outcome"]["outcome"] == "left" and not calls)
        finally:
            ready_now.ready_and_later = real
        pv, out = _apply(s)
        ctx.check("the applied card has its lines", len(_p_of(out)) == 2)
        ready_now.ready_and_later = lambda session, wrote: calls.append(wrote) or real(session, wrote)
        try:
            un = {"undo": pv["outcome"]["undo"], "rows": [], "text": ""}
            out = session_tool.finish(un, {"Undo it?": "Yes"}, s)
            ctx.check(f"undo: applied, no line, no key, not called, got {out!r} {un['outcome']}",
                      un["outcome"]["outcome"] == "applied" and not _p_of(out) and not _keys(un["outcome"]) and not calls)
        finally:
            ready_now.ready_and_later = real
    _scoped(body)


# -- entry 3: the builder_done frame and its receipt carry the answer ------------------------------------------------

@test
def test_builder_done_carries_ready_and_later(ctx: Ctx):
    want = {"ready": ["review"], "later": [{"kind": "agent", "name": "checker", "why": "AG1", "step": "review"}]}

    def auto(home):
        out = _drive(CARD, _apply_all, home=home)
        ctx.check(f"the turn ended without an error, got {out['error']!r}", out["ended"] and out["error"] is None)
        ctx.check(f"one frame with ready and later, no p3, got {[_keys(f) for f in out['frames']]}",
                  len(out["frames"]) == 1 and _keys(out["frames"][0]) == want)
        r = out["receipts"]
        ctx.check(f"one receipt with the same facts and no maps, got {[_keys(x.get('data') or x) for x in r]}",
                  len(r) == 1 and _keys(r[0].get("data") or r[0]) == want and "maps" not in (r[0].get("data") or r[0]))
        ctx.check(f"the session's built carries them, got {_keys(out['built'])}", _keys(out["built"]) == want)

    def shop(home):
        out = _drive(CARD, _apply_all, home=home, crew_map_flags={"map": "shop"}, before=lambda h: _shop())
        ctx.check(f"his map: the card was applied, got {out['frames'][:1]}",
                  len(out["frames"]) == 1 and out["frames"][0].get("outcome") == "applied")
        ctx.check("his map: no key in the frame, the receipt or built",
                  not _keys(out["frames"][0]) and not any(_keys(x.get("data") or x) for x in out["receipts"])
                  and not _keys(out["built"]))

    def project(home):
        from tests.helpers.trust_dir import trust

        def before(h):
            trust(h / "proj")
            _write("workflow", REVIEW, proj=h / "proj")
        out = _drive(CARD, _apply_all, home=home, before=before)
        ctx.check(f"the project's own review: p3, got {[_keys(f) for f in out['frames']]}",
                  len(out["frames"]) == 1 and out["frames"][0].get("p3") == ["review"])
    _scoped(auto)
    _scoped(shop)
    _scoped(project)


# -- entry 4: guards -------------------------------------------------------------------------------------------------

def _masked_messages(req: dict, undo: str) -> list:
    text = json.dumps((req.get("body") or {}).get("messages") or [])
    text = text.replace(undo, "U") if undo else text
    text = re.sub(r"Today's date: [^\\\"]*", "Today's date: D", text)
    return json.loads(text)


@test
def test_ready_lines_add_nothing_to_the_session(ctx: Ctx):
    src = (ROOT / "halo_harness" / "crew" / "ready_now.py").read_text(encoding="utf-8")
    bad = [w for w in ("import threading", "from threading", "Timer(", "import socket", "urllib", "import requests",
                       "time.sleep(") if w in src]
    ctx.check(f"ready_now.py starts no thread, timer or network call, got {bad}", not bad)

    def body(home):
        from halo_harness.crew import ready_now
        from halo_harness.crew.store import path_for
        at = time.time()
        counted: list = []

        def inspect(s):
            real_start = threading.Thread.start
            threading.Thread.start = lambda self, *a, **k: (counted.append(self), real_start(self, *a, **k))[1]
            try:
                ready_now.ready_and_later(s, [str(path_for("workflow", "review")), str(path_for("agent", "checker"))])
            finally:
                threading.Thread.start = real_start
            return None
        one = _drive(CARD, _apply_all, home=home, started_at=at, go_on=True, inspect=inspect)
        _fresh(home)
        real = ready_now.ready_and_later
        ready_now.ready_and_later = lambda session, wrote: None
        try:
            two = _drive(CARD, _apply_all, home=home, started_at=at, go_on=True)
        finally:
            ready_now.ready_and_later = real
        s1, s2 = one["session"], two["session"]
        ctx.check(f"both turns ended, got {one['error']!r} {two['error']!r}",
                  one["ended"] and two["ended"] and one["error"] is None and two["error"] is None)
        ctx.check("the run with the lines has them, the other none", len(_p_of(one["result"])) == 2 and not _p_of(two["result"]))
        ctx.check(f"the session holds the same attributes, got {set(vars(s1)) ^ set(vars(s2))}", set(vars(s1)) == set(vars(s2)))
        ctx.check("its tools are what they were before the card", list(s1.tool_registry.names()) == one["names_before"])
        ctx.check("its agents are the very same objects",
                  set(s1.agent_runtime.agents) == set(one["agents_before"])
                  and all(s1.agent_runtime.agents[k] is v for k, v in one["agents_before"].items()))
        ctx.check(f"computing the answer starts no thread, got {len(counted)}", counted == [])
        r1, r2 = one["requests"][-1]["body"], two["requests"][-1]["body"]
        ctx.check("the next request's tools are byte-equal", json.dumps(r1.get("tools")) == json.dumps(r2.get("tools")))
        m1 = _masked_messages(one["requests"][-1], (one["built"] or {}).get("undo"))
        m2 = _masked_messages(two["requests"][-1], (two["built"] or {}).get("undo"))
        ctx.check("the next request's system message is byte-equal",
                  json.dumps(m1[:1]) == json.dumps(m2[:1]) and m1[:1] and m1[0].get("role") == "system")
        tool1 = [i for i, m in enumerate(m1) if m.get("role") == "tool"]
        tool2 = [i for i, m in enumerate(m2) if m.get("role") == "tool"]
        same_rest = len(m1) == len(m2) and tool1 == tool2 and all(
            json.dumps(a) == json.dumps(b) for i, (a, b) in enumerate(zip(m1, m2)) if i not in tool1)
        ctx.check("every other message is equal", same_rest)
        c1 = [str(m1[i].get("content")) for i in tool1]
        c2 = [str(m2[i].get("content")) for i in tool2]
        ctx.check(f"the Builder's tool result differs only by the lines at its end, got {c1[-1:]!r} vs {c2[-1:]!r}",
                  len(c1) == 1 and c1[0] == c2[0] + "\n" + P1_REVIEW + "\n" + P2_STEP)
    _scoped(body)


@test
def test_map_of_his_and_undo_get_no_p_lines(ctx: Ctx):
    def shop(home):
        out = _drive(CARD, _apply_all, home=home, crew_map_flags={"map": "shop"}, before=lambda h: _shop())
        ctx.check(f"his map: no line in the result, got {out['result'][-200:]!r}",
                  "Applied" in out["result"] and not _p_of(out["result"]))
        ctx.check("his map: no key in the frame or the receipt",
                  out["frames"] and not any(_keys(f) for f in out["frames"])
                  and not any(_keys(x.get("data") or x) for x in out["receipts"]))

    def undo(home):
        from halo_harness.crew import map_events, session_tool
        s = _auto_session(home)
        pv, _out = _apply(s)
        un = {"undo": pv["outcome"]["undo"], "rows": [], "text": ""}
        out = session_tool.finish(un, {"Undo it?": "Yes"}, s)
        data = map_events.builder_done(s, "undo-1", un["outcome"])
        ctx.check(f"an applied undo: no line, no key on the outcome or the frame, got {out!r} {_keys(data)}",
                  un["outcome"]["outcome"] == "applied" and not _p_of(out) and not _keys(un["outcome"])
                  and data and not _keys(data))
    _scoped(shop)
    _scoped(undo)


@test
def test_ready_lines_match_what_runs(ctx: Ctx):
    def with_tool(home):
        from halo_harness.crew import map_events, ready_now, store
        from halo_harness.crew.flow_door import named
        from halo_harness.crew.session_tool import _same_path
        s = _auto_session(home)
        pv, out = _apply(s)
        o = pv["outcome"]
        for w in o.get("ready") or []:
            ctx.check(f"{w} runs by name through the Workflow tool: its file is the card's",
                      _same_path(named(w, s.cwd)["_path"]) == _same_path(store.path_for("workflow", w))
                      and s.tool_registry.get("Workflow") is not None)
        for it in o.get("later") or []:
            if it["kind"] == "agent" and it["why"] == "AG1":
                ctx.check(f"the Agent tool does not know {it['name']}", s.agent_runtime.agents.get(it["name"]) is None)
            if it.get("step"):
                ctx.check(f"the step runner reads the card's {it['name']}",
                          _same_path(store.load("agent", it["name"], cwd=s.cwd)["_path"])
                          == _same_path(store.path_for("agent", it["name"])))
        ctx.check(f"the answer had ready and a step clause, got {_keys(o)}",
                  o.get("ready") and any(it.get("step") for it in o.get("later") or []))
        data = map_events.builder_done(s, "card-1", o)
        ctx.check(f"the result's lines, the frame's keys and p_lines of them are one list, got {_p_of(out)}",
                  _p_of(out) == ready_now.p_lines(_keys(data)) == ready_now.p_lines(_keys(o)) and len(_p_of(out)) == 2)

    def known(home):
        from halo_harness.config.agents_md import discover_agents
        _write("agent", CHECKER)
        start = discover_agents(home / "proj")
        s = _auto_session(home, agents=start)
        spec = s.agent_runtime.agents["checker"]
        new = "Checks a change and names each fault."
        pv, out = _apply(s, [{"tool": "agent_change", "args": {"name": "checker", "fields": {"does": new}}}])
        ctx.check(f"AG2, got {pv['outcome']} {out[-300:]!r}",
                  pv["outcome"].get("later") == [{"kind": "agent", "name": "checker", "why": "AG2"}])
        ctx.check("the Agent tool runs the spec the session started with, not the card's new text",
                  s.agent_runtime.agents["checker"] is spec and new not in repr(spec))

    def no_tool(home):
        s = _auto_session(home, workflow_tool=False)
        pv, out = _apply(s)
        wf = [it for it in pv["outcome"].get("later") or [] if it["why"] == "WF"]
        ctx.check(f"WF lines only where the session has no Workflow tool, got {wf}",
                  wf == [{"kind": "workflow", "name": "review", "why": "WF"}] and s.tool_registry.get("Workflow") is None
                  and P2_WF in _p_of(out))
    _scoped(with_tool)
    _scoped(known)
    _scoped(no_tool)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
