"""tests.test_builder_session_parity -- Halo 3.6.0.0 R3: the builder's tools offered to main in a session ("In a
session": one tool module, crew/tools.py; the session's `Builder` tool wraps it, crew/session_tool.py + agent/loop.py).

1. the same request -- "make me a reviewer agent and hand reviews to it" -- through main's Builder tool in a real
   interactive Session (its approval card answered: the plain lines applied, the widening line ticked "Yes") and through
   `/api/builder` (the same lines ticked) writes byte-identical agent and map files;
2. the card: the plain lines in one question, each widening line its own question with "No" first; answering only
   "Apply them" leaves the widening line out; dismissing it writes nothing; with no one to answer (print mode) the tool
   previews and writes nothing; `studio_show` answers at once with no card.
Mock upstream / scripted fake model only. Run: python -m tests.test_builder_session_parity
"""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.crew_map_script import reviewer_calls  # noqa: E402
from tests.helpers.crew_rig import CrewRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MODEL = "or:mock/builder-session"
MAP = "parity-map"  # 3.6.0.2 R36: a new map named in the card (made by it, its use row ticked)


def _crew(state: Path) -> dict:
    return {str(p.relative_to(state)).replace("\\", "/"): p.read_bytes() for p in (state / "crew").rglob("*.yaml")} \
        if (state / "crew").is_dir() else {}


def _session(home: Path, mock):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.tools.builder_tool import BuilderTool
    from halo_harness.tools.registry import ToolRegistry, default_tools
    cwd = home / "proj"
    cwd.mkdir(exist_ok=True)
    from halo_harness.crew.map_session import prepare
    reg = ToolRegistry(default_tools() + [BuilderTool()])
    s = Session(cwd=cwd, model_ref=parse_model_ref(MODEL), model_profile=ModelProfile(), creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
                state_dir=home / "sess-state", model_label=MODEL, crew_map=prepare(None, cwd)[0],  # the default map, as a session gets it
                session_context=SessionContext(cwd=cwd, model_label=MODEL, tool_registry=reg), max_turns=6,
                permission_engine=PermissionEngine(mode="default", cwd=cwd))
    s.interactive = True
    return s


def through_main(answer_fn, calls=None) -> "tuple[dict, list, str]":
    """A real Session whose model calls Builder once; `answer_fn(questions)` answers the card (None: dismiss)."""
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, ScriptedTurns
    from tests.helpers.session_rig import text_step, tool_step
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_OPENROUTER_BASE_URL", "BRIDGE_STATE_DIR")}
    home = Path(tempfile.mkdtemp(prefix="builder-main-"))
    os.environ.pop("BRIDGE_STATE_DIR", None)
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    mock = MockUpstream().start()
    os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
    SCENARIOS["builder-session"] = ScriptedTurns([tool_step(("Builder", {"changes": calls or reviewer_calls(MAP)}, "call_b")),
                                                  text_step("Done.")])
    events: list = []
    try:
        s = _session(home, mock)
        done = threading.Event()

        def drive():
            try:
                events.extend(s.turn("make me a reviewer agent and hand reviews to it"))
            finally:
                done.set()
        threading.Thread(target=drive, daemon=True).start()
        end = time.monotonic() + 20
        while time.monotonic() < end and not done.is_set() and not any(e.kind == "question" for e in list(events)):
            time.sleep(0.02)
        q = next((e for e in list(events) if e.kind == "question"), None)
        qs = (q.data.get("input") or {}).get("questions") if q else []
        if q is not None:
            s.resolve_question(q.data["id"], answer_fn(qs))
        done.wait(20)
        result = next((n.get("content") for n in s.log.nodes() if n.get("type") == "tool_result"), "")
        from halo_harness.providers.config import default_state_dir
        return _crew(Path(default_state_dir())), qs, str(result)
    finally:
        mock.stop()
        SCENARIOS.pop("builder-session", None)
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        shutil.rmtree(home, ignore_errors=True)


def approve_all(qs: list):
    return {q["question"]: (q["options"][0]["label"] if q["question"].startswith("Apply") else q["options"][1]["label"]) for q in qs}


@test
def test_the_same_request_writes_the_same_files(ctx: Ctx):
    main_files, qs, result = through_main(approve_all)
    ctx.check(f"the card: one question for the plain lines (the agent, the new map, its box and line, the use row), one per "
              f"widening line with No first, got {[q['question'][:50] for q in qs]}",
              len(qs) == 2 and qs[0]["question"].startswith("Apply these 5 changes") and qs[1]["options"][0]["label"].startswith("No")
              and "Run commands" in qs[1]["question"] and f"New sessions run on {MAP}. " in qs[0]["question"])
    ctx.check(f"the tool result says what was written and the undo id, got {result[:200]!r}", "Applied 6 line(s)" in result and "Undo id" in result)
    with CrewRig() as rig:
        rig.studio()
        st, r = rig.api("POST", "builder/ask", {"tab": "map", "text": "make me a reviewer agent and hand reviews to it",
                                                "conversation_id": "p1", "selection": {"map": MAP}})
        st, a = rig.api("POST", "builder/apply", {"conversation_id": "p1", "change_ids": [c["id"] for c in r["changes"]]})
        studio_files = _crew(rig.state)
    ctx.check(f"byte-identical agent and map files, got {sorted(main_files)} vs {sorted(studio_files)}",
              main_files and main_files == studio_files and set(main_files) == {"crew/agents/my-reviewer.yaml", f"crew/maps/{MAP}.yaml"})


@test
def test_the_widening_line_is_never_ticked_for_them(ctx: Ctx):
    files, qs, result = through_main(lambda qs: {qs[0]["question"]: "Apply them"})
    body = files.get("crew/agents/my-reviewer.yaml", b"").decode()
    ctx.check(f"only Apply: the agent reads only, got {body!r}", "- read" in body and "bash" not in body and "left 1" in result)
    files, _qs, result = through_main(lambda qs: None)
    ctx.check(f"dismissed: nothing written, got {sorted(files)} {result[-60:]!r}", files == {} and "nothing was written" in result)
    files, qs, result = through_main(lambda qs: None, calls=[{"tool": "studio_show", "args": {"what": "map", "name": "starter"}}])
    ctx.check(f"studio_show: no card, the answer at once, got {result[:80]!r}", qs == [] and "MAP Auto (the default)" in result and files == {})
    files, qs, result = through_main(lambda qs: None, calls=[{"tool": "map_box_add", "args": {"kind": "agent", "ref": "reviewer"}}])
    ctx.check(f"a nameless map change in a plain session: refused in the R36 sentence, no card, nothing written, got {result[:160]!r}",
              qs == [] and files == {} and "Name the map: this session runs on Auto (the default), where main chooses who "
              "works. Pass a new name in args.map to make a map that routes." in result)


@test
def test_both_doors_recheck_the_use_row_at_apply(ctx: Ctx):
    """R54 at Apply, one path for both doors: a `map_use` row whose map file changed since the preview and now lets
    agents do more, or whose recheck raises, is left out by the session's card (crew/session_tool.finish) AND by Studio's
    builder box (POST builder/apply), through the same function (crew/tools_map.apply_check); the rest is written."""
    from tests.test_builder_map import _S, _agent, _map_of, _uses
    with CrewRig() as rig:
        rig.studio()
        from halo_harness.crew import builder, session_tool, store, tools, tools_map
        from halo_harness.theme import get_config_value, set_config_value
        _agent(rig, "looker", ("read",), "ask-changes")
        _agent(rig, "runner", ("read", "bash"), "own")
        _map_of(rig, "shop", ("read",), ["looker"])
        set_config_value("crew.map", "shop")
        real = tools_map._use_words

        def widen(mp: str) -> None:
            path = store.path_for("map", mp, state_dir=rig.state)
            body = store.read(path)
            body["boxes"].append({"id": "runner", "agent": "runner"})
            body["lines"].append({"from": "main", "to": "runner", "when": "main-decides"})
            store.write_text(path, store.dump(body))

        def boom(*_a, **_k):
            raise RuntimeError("the check broke")
        for n, (door, case) in enumerate((("session", "widens"), ("session", "raises"), ("studio", "widens"),
                                          ("studio", "raises"))):
            mp = f"calm{n}"
            _map_of(rig, mp, ("read",))
            if door == "session":
                pv = session_tool.preview(_S(rig), {"tool": "map_use", "args": {"map": mp}})
                rows = pv["rows"]
            else:
                rows = tools.run("map_use", {"map": mp}, {"cwd": rig.proj, "state_dir": rig.state, "selection": {}})["rows"]
                with builder._LOCK:
                    builder.PENDING[(str(store.state_dir_of(rig.state)), f"r{n}")] = rows
            ctx.check(f"{door}/{case}: the use row came ticked, got {[(r['summary'], r['widen']) for r in rows]}",
                      len(_uses(rows)) == 1 and _uses(rows)[0]["ticked"])
            widen(mp)
            if case == "raises":
                tools_map._use_words = boom
            try:
                if door == "session":
                    out = session_tool.finish(pv, "Apply them", _S(rig))
                else:
                    st, a = rig.api("POST", "builder/apply", {"conversation_id": f"r{n}", "change_ids": [r["id"] for r in rows]})
                    out = f"{st} {a}"
            finally:
                tools_map._use_words = real
            ctx.check(f"{door}/{case}: crew.map stays shop and the result says it was left out, got "
                      f"{get_config_value('crew.map')} {out[-240:]!r}",
                      get_config_value("crew.map") == "shop" and "Left out: new sessions still run on shop: " in out
                      and ((f"{mp} changed after the card was shown" in out) if case == "widens"
                           else (f"whether {mp} lets agents do more could not be checked again" in out)))


@test
def test_print_mode_previews_and_writes_nothing(ctx: Ctx):
    from tests.helpers.config_seed import ConfigHome
    from halo_harness.tools.base import ToolContext
    from halo_harness.tools.builder_tool import BuilderTool
    with ConfigHome() as home:
        got = BuilderTool().run({"changes": reviewer_calls(MAP)}, ToolContext(cwd=home.home))
        ctx.check(f"previewed, not applied, said so, got {got.content[-160:]!r}", "Not applied" in got.content and _crew(home.state) == {})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
