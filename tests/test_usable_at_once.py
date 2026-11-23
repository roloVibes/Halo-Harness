"""tests.test_usable_at_once -- Halo 3.6.0.15 UN: an agent saved while a session runs is usable in that session at
once. U3: after a 200 of Studio's POST, PUT or DELETE crew/agent/<name>, the save reaches each live top session whose
folder sees its scope (studio/crew_push.py over the control socket's agent_put / agent_gone), skips a row marked
`unreachable_since`, and the answer gains `live`; a refused save asks nobody.

Real Sessions on the default map with real control sockets and a real Studio server (tests/helpers/crew_rig.py), a mock
upstream: nothing calls a model. Every session, socket and patch is closed or put back in a finally.
Run: python -m tests.test_usable_at_once
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MODEL = "or:mock/usable-at-once"


def _agent(name: str, does: str = "Sorts the files it is given by kind.") -> dict:
    return {"format": "agent/1", "name": name, "does": does, "uses": ["read"], "careful": "ask-changes", "model": "auto"}


def _trust(folder: Path) -> None:
    from halo_harness.config.paths import claude_json_path
    cj = claude_json_path()
    cj.parent.mkdir(parents=True, exist_ok=True)
    key = str(folder.absolute()).replace("\\", "/")
    cj.write_text(json.dumps({"projects": {key: {"hasTrustDialogAccepted": True}}}), encoding="utf-8")


def _session(rig, cwd: Path):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.crew.map_session import prepare
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.tools.registry import ToolRegistry, default_tools
    return Session(cwd=cwd, model_ref=parse_model_ref(MODEL), model_profile=ModelProfile(),
                   creds=ProviderCreds(base_url=rig.mock.base_url, api_key="k"),
                   state_dir=Path(tempfile.mkdtemp(prefix="sess-", dir=str(rig.root))), model_label=MODEL,
                   crew_map=prepare(None, cwd)[0], openrouter_base_url=rig.mock.base_url, max_turns=4,
                   session_context=SessionContext(cwd=cwd, model_label=MODEL, tool_registry=ToolRegistry(default_tools())),
                   permission_engine=PermissionEngine(mode="default", cwd=cwd))


def _asked(session) -> list:
    """(cmd, name) of every agent_put / agent_gone this session's socket ran (main's transcript records each)."""
    return [(n["control"]["cmd"], n["control"].get("name")) for n in session.log.nodes()
            if n.get("type") == "meta" and isinstance(n.get("control"), dict)
            and n["control"].get("cmd") in ("agent_put", "agent_gone")]


@test
def test_a_save_reaches_the_sessions_that_see_it_two_projects_one_reached(ctx: Ctx):
    from halo_harness.agent.helpers_words import on_auto
    from halo_harness.controller import Controller
    from halo_harness.remote import agent_control, registry, runtime
    from halo_harness.remote.base import HandleError
    from tests.helpers.crew_rig import CrewRig
    from tests.helpers.fake_remote_session import FakeRegistry
    controllers: list = []
    real_run, real_live = agent_control.run, registry.list_live
    with CrewRig() as rig:
        try:
            other = rig.root / "other"
            other.mkdir()
            _trust(rig.proj)
            proj_agent = rig.proj / ".halo" / "crew" / "agents" / "sorter.yaml"
            proj_agent.parent.mkdir(parents=True, exist_ok=True)
            from halo_harness.crew import store
            store.write_text(proj_agent, store.dump(_agent("sorter")))
            names = ("a", "b", "old", "far")
            sessions = {k: _session(rig, rig.proj if k != "b" else other) for k in names}
            ctx.check("every session is on Auto", all(on_auto(s) for s in sessions.values()))
            ids = {}
            for k, s in sessions.items():
                c = Controller(session=s, cwd=s.cwd, registry=FakeRegistry()).start()
                controllers.append(c)
                act = runtime.start_for_controller(c)
                ctx.check(f"session {k}: its socket opened", act is not None)
                ids[k] = act.session_id if act is not None else None
            old_session = sessions["old"]

            def older(handle, req, conn=None):  # a session of a release before agent_put: its socket refuses
                if handle.session is old_session and req.get("cmd") in ("agent_put", "agent_gone"):
                    raise HandleError(f"unknown agent cmd {req.get('cmd')!r}")
                return real_run(handle, req, conn)

            def live():  # the row of `far` is marked as a failing probe marks it
                rows = real_live()
                return [dict(r, unreachable_since=1.0) if r.get("session_id") == ids["far"] else r for r in rows]
            agent_control.run, registry.list_live = older, live
            rig.studio()

            def by_sid(items) -> dict:
                return {next(k for k, v in ids.items() if v == it["session_id"]): {x: y for x, y in it.items()
                                                                                   if x != "session_id"}
                        for it in items}

            status, got = rig.api("PUT", "crew/agent/sorter", {"agent": _agent("sorter", "Sorts by kind and size.")})
            ctx.check(f"PUT of the project's sorter: 200 and only this project's sessions, got {status} {got.get('live')}",
                      status == 200 and by_sid(got.get("live") or []) == {
                          "a": {"took": True, "why": ""}, "old": {"took": False, "why": "unreached"}})
            status, got = rig.api("POST", "crew/agent/tidy", {"agent": _agent("tidy", "Tidies a folder.")})
            ctx.check(f"POST of yours: every reachable top session, got {status} {got.get('live')}",
                      status == 200 and by_sid(got.get("live") or []) == {
                          "a": {"took": True, "why": ""}, "b": {"took": True, "why": ""},
                          "old": {"took": False, "why": "unreached"}})
            before = {k: len(_asked(s)) for k, s in sessions.items()}
            status, got = rig.api("POST", "crew/agent/tidy", {"agent": _agent("tidy")})
            ctx.check(f"a 409 has no `live`, got {status} {sorted(got)}", status == 409 and "live" not in got)
            status, got = rig.api("PUT", "crew/agent/bad", {"agent": {"name": "bad", "does": "x"}})
            ctx.check(f"a 422 has no `live`, got {status} {sorted(got)}", status == 422 and "live" not in got)
            ctx.check("a refused save asks no session", {k: len(_asked(s)) for k, s in sessions.items()} == before)
            status, got = rig.api("DELETE", "crew/agent/tidy")
            ctx.check(f"DELETE of yours: queued in each, got {status} {got.get('live')}",
                      status == 200 and by_sid(got.get("live") or []) == {
                          "a": {"queued": True}, "b": {"queued": True}, "old": {"queued": False}})
            ctx.check(f"session a ran each command once, got {_asked(sessions['a'])}", _asked(sessions["a"]) == [
                ("agent_put", "sorter"), ("agent_put", "tidy"), ("agent_gone", "tidy")])
            ctx.check(f"session b was never asked about the project's sorter, got {_asked(sessions['b'])}",
                      _asked(sessions["b"]) == [("agent_put", "tidy"), ("agent_gone", "tidy")])
            ctx.check(f"the unreachable row's socket saw no request, got {_asked(sessions['far'])}",
                      _asked(sessions["far"]) == [])
        finally:
            agent_control.run, registry.list_live = real_run, real_live
            runtime.stop()
            for c in controllers:
                try:
                    c.quit()
                except Exception:
                    pass
            runtime._private_flag = None
            runtime._reopeners[:] = []


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
