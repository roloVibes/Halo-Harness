"""tests.test_placement -- Halo 3.3.6.0 R1: the placement rules
(providers/placement.py, placement_apply.py) on profiles the battery made
against the scripted fake (tests/helpers/battery_rig.py):

1. every rule's verdict and fix per role (no tools, not interactive, a 32k
   window for compaction, the notes for a weak system role, thinking, fences,
   unverified ids); no profile: "expected";
2. Auto's pick never picks a no-tools model, and its reason says so;
3. the spawn gate: a tool-using child on a no-tools model does not start
   and the line names the fix; a child with no tools does start;
4. the system role hook: `system_role: weak` from the probe moves the
   instructions into the user turn (the wire), the line says so;
5. the reserve: a thinking model's steward profile `num_predict` raised (a
   reserve you set stays); the fence stripped before parsing;
6. the pivot schedule on a lineup (`lineup_pivots`, `halo teams show`, the
   Roles Problems finding); roles.py's warning; doctor --local's role check.
Run: python -m tests.test_placement
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.battery_rig import BatteryRig, gpu_card  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _all(rig):
    from halo_harness.studio import ollama_hosts_view as V
    with V._LOCK:
        V._CACHE[("card", rig.host.url)] = (1e18, gpu_card(24.0))
    return {n: rig.probe(n, card=gpu_card(24.0)) for n in rig.mock.scenarios if n.startswith("bt-")}


@test
def test_every_rule_its_verdict_and_fix(ctx: Ctx):
    from halo_harness.providers.placement import verdict
    with BatteryRig() as rig:
        p = _all(rig)
        v = verdict(p["bt-mute:24b"], "coder", state_dir=rig.state)
        ctx.check(f"no tools -> never a tool-using sub-agent, got {v}", v["ok"] is False and "no tool calling" in v["why"]
                  and "route this step to ol:bt-coder:30b@fake" in v["fix"] and "single-shot" in v["fix"])
        for role in ("compaction", "bulk", "small"):
            ctx.check(f"no tools: {role} stays open", verdict(p["bt-mute:24b"], role)["ok"] is True)
        v = verdict(p["bt-mute:24b"], "main")
        ctx.check(f"a no-tools model as main says it, got {v['why']}", v["ok"] is False)
        ctx.check("the coder holds every tool role", all(verdict(p["bt-coder:30b"], r)["ok"] for r in
                                                          ("main", "orchestrator", "coder", "reviewer", "researcher")))
        notes = verdict(p["bt-wrongid:8b"], "reviewer")["notes"]
        ctx.check(f"weak system role / thinking / ids: notes, got {notes}", any("user turn" in n for n in notes)
                  and any("reply reserve" in n for n in notes) and any("authoritative IDs" in n for n in notes))
        ctx.check("fenced JSON: a note", any("fence" in n for n in verdict(p["bt-fence:14b"], "coder")["notes"]))
        short = dict(p["bt-fence:14b"], window={**p["bt-fence:14b"]["window"], "usable": 32768})
        v = verdict(short, "compaction")
        ctx.check(f"a 32k window -> never compaction, got {v}", v["ok"] is False and "chunk inputs" in v["why"])
        ctx.check("no profile -> expected", verdict(None, "coder") == {"ok": None, "why": "not probed yet",
                                                                     "fix": "halo models probe <ref>", "notes": [],
                                                                     "source": "expected"})


@test
def test_auto_never_picks_a_no_tools_model(ctx: Ctx):
    from halo_harness.models_auto import pick
    rows = {"ol:bt-mute:24b@fake": {"facts": {"local": True, "tools": True, "modalities_out": ["text"]},
                                    "scores": {"bulk": 0.99, "fast": 0.99}},
            "ol:bt-coder:30b@fake": {"facts": {"local": True, "tools": True, "modalities_out": ["text"]},
                                     "scores": {"bulk": 0.2, "fast": 0.2}}}
    with BatteryRig(["bt-mute:24b", "bt-coder:30b"]) as rig:
        before = pick(rig.state, rows=rows, band="high", learn={"enabled": False})
        ctx.check(f"not probed: the fast one wins, got {before.ref}", before.ref == "ol:bt-mute:24b@fake")
        rig.probe("bt-mute:24b")
        got = pick(rig.state, rows=rows, band="high", learn={"enabled": False})
        ctx.check(f"probed with no tool calling: the coder, got {got.ref}", got.ref == "ol:bt-coder:30b@fake")
        ctx.check(f"the reason says why, got {got.reason!r}", "skipped ol:bt-mute:24b@fake: no tool calling" in got.reason)
        only = pick(rig.state, rows={k: v for k, v in rows.items() if "mute" in k}, band="high", main_ref="ol:main",
                    learn={"enabled": False})
        ctx.check(f"only it: main's, with the line, got {only.ref} {only.reason!r}", only.fallback and only.ref == "ol:main"
                  and "no tool calling" in only.reason)


def _parent(rig):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    cwd = rig.home.root / "cwd"
    cwd.mkdir(exist_ok=True)
    s = Session(cwd=cwd, model_ref=parse_model_ref("ol:bt-coder:30b@fake"), model_profile=ModelProfile(),
                creds=ProviderCreds(base_url=rig.mock.base_url, api_key=None), state_dir=rig.state,
                model_label="ol:bt-coder:30b@fake", session_context=SessionContext(cwd=cwd, model_label="x", bare=True),
                max_turns=4, permission_engine=PermissionEngine(mode="auto", cwd=cwd), agents={}, routes={})
    s.interactive = False
    return s


@test
def test_the_spawn_gate_and_its_fix(ctx: Ctx):
    from halo_harness.agent.subagent import AgentRuntime, _build_child_session
    from halo_harness.config.agents_md import AgentSpec
    from halo_harness.providers.placement import NoToolCalling
    with BatteryRig(["bt-mute:24b", "bt-coder:30b"]) as rig:
        rig.probe("bt-mute:24b")
        rig.probe("bt-coder:30b")
        runtime = AgentRuntime(parent=_parent(rig))
        spec = AgentSpec(name="worker", description="w", tools=None, body="You work.")
        try:
            _build_child_session(runtime=runtime, spec=spec, agent_id="bt-1", model_override="ol:bt-mute:24b@fake",
                                 parent_tool_use_id="t1")
            said = ""
        except NoToolCalling as e:
            said = str(e)
        ctx.check(f"a tool-using child on the no-tools model does not start, with the fix, got {said!r}",
                  "has no tool calling (probed" in said and "Route this step to ol:bt-coder:30b@fake" in said
                  and "single-shot step without tools" in said)
        child, _m = _build_child_session(runtime=runtime, spec=AgentSpec(name="bulk", description="b", tools=[], body="x"),
                                         agent_id="bt-2", model_override="ol:bt-mute:24b@fake", parent_tool_use_id="t2")
        ctx.check("a child with no tools starts on it", child.model_ref.raw == "ol:bt-mute:24b@fake")


@test
def test_a_weak_system_role_moves_the_instructions_and_says_so(ctx: Ctx):
    from halo_harness.agent.prompt_wire import shape
    with BatteryRig(["bt-wrongid:8b"]) as rig:
        rig.probe("bt-wrongid:8b")
        s = _parent(rig)
        from halo_harness.model import parse_model_ref
        s.model_ref = parse_model_ref("ol:bt-wrongid:8b@fake")
        system, messages, _t = shape(s, "You are Halo. Follow the rules.", [{"role": "user", "content": [
            {"type": "text", "text": "fix the bug"}]}], None)
        first = messages[0]["content"]
        ctx.check(f"the system message points at the user turn, got {system!r}", "first user message" in system)
        ctx.check(f"the instructions lead the user turn, before the words, got {first}",
                  first[0]["text"] == "You are Halo. Follow the rules." and first[-1]["text"] == "fix the bug")
        from halo_harness.agent.ollama_window import drain_markers
        ctx.check("the line says so", any("ignores the system role (probed" in m for m in drain_markers(s)))


@test
def test_the_reserve_raised_and_the_fence_stripped(ctx: Ctx):
    from halo_harness.ollama_steward.profiles import all_profiles, set_field
    from halo_harness.providers.battery_probes import strip_fences
    with BatteryRig(["bt-thinker:27b", "bt-wrongid:8b"]) as rig:
        p = rig.probe("bt-thinker:27b")
        got = all_profiles().get("fake|bt-thinker:27b") or {}
        ctx.check(f"a thinking model's reply reserve raised (>= 300, the class default), got {got} {p['applied']}",
                  got.get("num_predict", 0) >= 300 and got.get("by") == "steward" and p["applied"])
        set_field("fake|bt-wrongid:8b", "num_predict", 128, by="user")
        rig.probe("bt-wrongid:8b")
        ctx.check("a reserve you set stays", all_profiles()["fake|bt-wrongid:8b"]["num_predict"] == 128)
    ctx.check("a ```json fence is stripped", strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}')
    ctx.check("text without one stays", strip_fences('{"a": 1}') == '{"a": 1}')


@test
def test_a_lineup_that_is_a_pivot_schedule(ctx: Ctx):
    from halo_harness.doctor_local_roles import role_steps
    from halo_harness.providers.placement_apply import lineup_pivots
    from halo_harness.roles import resolve_all_roles
    with BatteryRig(["bt-mute:24b", "bt-coder:30b"]) as rig:
        _all(rig)
        table = {"coder": "ol:bt-coder:30b@fake", "small": "ol:bt-mute:24b@fake"}
        got = lineup_pivots(table, rig.state)
        ctx.check(f"the two cannot co-reside: a pivot schedule, got {got}", len(got) == 1
                  and "every switch is a 20-55 s pivot" in got[0]["line"])
        steps = role_steps(rig.state, role_table={"coder": "ol:bt-mute:24b@fake"}, main_ref="ol:bt-coder:30b@fake")
        ctx.check(f"doctor --local: the coder role on a no-tools model FAILs with the fix, got {steps}",
                  [s["ok"] for s in steps] == [True, False] and "fix: route this step" in steps[1]["reason"])
        from halo_harness.model import ModelProfile, parse_model_ref
        rows = resolve_all_roles(role_table={"coder": "ol:bt-mute:24b@fake"}, parent_ref=parse_model_ref("ol:bt-coder:30b@fake"),
                                 parent_profile=ModelProfile(), state_dir=rig.state)
        coder = next(r for r in rows if r["role"] == "coder")
        ctx.check(f"roles.py's resolution warns, got {coder.get('placement')!r}", "no tool calling" in (coder.get("placement") or ""))
        os.environ.pop("BRIDGE_TEST_HOME_UNUSED", None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
