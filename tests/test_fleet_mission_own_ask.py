"""tests.test_fleet_mission_own_ask -- Halo 3.4.1.2 (ENGINE-6): a mission part's own-folder rule (fleet
mission_guard.py) turned ANY ask inside `artifacts/<n>/` into an allow, including one from the owner's own `ask:`
path rule. Now it lifts only the mode's ask (`decision.matched_rule is None`); an ask rule of yours stays an ask, and a
deny stays a deny.
Run: python -m tests.test_fleet_mission_own_ask
"""
from __future__ import annotations
from tests.helpers import fleet_pack as _fleet_pack  # noqa: E402  (the fleet pack on, its modules by their old names)
_fleet_pack.on()

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
MID = "m-20261112-e6e6"


def _engine(m: Path, *, ask=(), deny=()):
    from halo_harness.fleet.mission_guard import MissionClaimGuard, install
    from halo_harness import permissions as P
    engine = P.PermissionEngine(mode="default", cwd=m, print_mode=False,
                                ask_rules=[P.parse_rule(r, source="user", base_dir=m, action="ask") for r in ask],
                                deny_rules=[P.parse_rule(r, source="user", base_dir=m, action="deny") for r in deny])
    install(engine, MissionClaimGuard(m, ["artifacts/1/**"], mission=MID, part="1", own=m))
    return engine


@test
def test_engine6_your_ask_rule_survives_the_own_folder_rule(ctx: Ctx):
    m = Path(tempfile.mkdtemp(prefix="mission-e6-")) / MID
    (m / "artifacts" / "1").mkdir(parents=True)
    write = {"file_path": str(m / "artifacts" / "1" / "x.html"), "content": "x"}
    d = _engine(m).decide("Write", write)
    ctx.check(f"no rule: the mode's ask is lifted (its own outputs folder), got {d.action}", d.action == "allow")
    d = _engine(m, ask=("Edit(**/*.html)",)).decide("Write", write)
    ctx.check(f"your ask rule Edit(**/*.html): still an ask, got {d.action} {d.reason!r}", d.action == "ask"
              and "matched ask rule" in d.reason)
    d = _engine(m, deny=("Edit(**/*.html)",)).decide("Write", write)
    ctx.check(f"a deny stays a deny, got {d.action}", d.action == "deny")
    d = _engine(m, ask=("Edit(**/*.html)",)).decide("Write", {"file_path": str(m / "artifacts" / "1" / "x.txt"),
                                                                     "content": "x"})
    ctx.check(f"a file your rule does not name: lifted as before, got {d.action}", d.action == "allow")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
