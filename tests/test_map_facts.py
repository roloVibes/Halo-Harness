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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
