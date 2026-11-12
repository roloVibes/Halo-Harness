"""tests.test_skill_mode_cycle -- Halo 3.4.1.2 (ENGINE-3): a mode cycle (Shift+Tab, /permissions) answered an untrusted
skill's card "allow", and its asked commands then ran as "you said yes". Now an ask whose source is not the engine's
mode table (a pack's, an untrusted skill's, a hook's) is held for the person (agent/policy_gate.held_for_you), and only
the person's own allow on the card (Session.resolve_permission -> tools/skill_gate.confirm) lets the commands run once.
A scratch home and project; the span only writes a marker inside the scratch project.
Run: python -m tests.test_skill_mode_cycle
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home  # noqa: E402
from tests.test_skill_untrusted import _engine, _project, _run, _session  # noqa: E402

test, TESTS = new_registry()


class _Waiters:
    """The two Session methods under test only read `_permission_waiters` and `permission_engine`."""

    def __init__(self, engine):
        self.permission_engine = engine
        self._permission_waiters = {}

    def park(self, rid, decision, tool_input, tool):
        from halo_harness.agent import policy_gate as G
        self._permission_waiters[rid] = {"event": threading.Event(), "decision": None, "tool_name": "Skill",
                                         "tool_input": tool_input, "tool": tool,
                                         "policy_ask": G.held_for_you(decision), "engine": self.permission_engine}


@test
def test_engine3_a_mode_cycle_leaves_the_skill_card_for_you(ctx: Ctx):
    from halo_harness.agent.loop import Session
    from halo_harness.agent.policy_gate import decide
    from halo_harness.tools.skill import SkillTool
    with Home(hosts=()):
        os.environ.pop("CLAUDE_CODE_SANDBOXED", None)
        proj = _project()
        engine = _engine(proj)
        d = decide(_session(proj, engine), {}, "Skill", {"skill": "x"}, SkillTool())
        ctx.check(f"the card: ask, source skill, got {d.action} {d.source}", d.action == "ask" and d.source == "skill")
        w = _Waiters(engine)
        w.park("r1", d, {"skill": "x"}, SkillTool())
        engine.mode = "acceptEdits"
        got = Session.reevaluate_pending_permission(w, "r1")
        ctx.check(f"Shift+Tab to acceptEdits does not answer it, got {got!r}", got is None
                  and not w._permission_waiters["r1"]["event"].is_set())
        engine.mode = "auto"
        ctx.check("nor auto", Session.reevaluate_pending_permission(w, "r1") is None)
        engine.mode = "default"
        r = _run(proj, engine)
        ctx.check(f"without the person's answer the span does not run, got {r.content!r}",
                  r.is_error and not (proj / "marker.txt").exists())
        d = decide(_session(proj, engine), {}, "Skill", {"skill": "x"}, SkillTool())
        w.park("r2", d, {"skill": "x"}, SkillTool())
        from halo_harness.permissions import Decision
        ok = Session.resolve_permission(w, "r2", Decision("allow", "you said yes"))
        r = _run(proj, engine)
        ctx.check(f"the person's allow runs it once, got {r.content!r}",
                  ok and not r.is_error and (proj / "marker.txt").exists())


@test
def test_engine3_a_hook_ask_is_held_too(ctx: Ctx):
    from halo_harness.agent.policy_gate import held_for_you
    from halo_harness.permissions import Decision
    ctx.check("a hook's ask is held", held_for_you(Decision("ask", "h", source="hook")))
    ctx.check("a pack's ask is held", held_for_you(Decision("ask", "p", source="pack:x")))
    ctx.check("the mode table's ask is not", not held_for_you(Decision("ask", "m", source="mode")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
