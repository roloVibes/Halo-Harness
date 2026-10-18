"""tests.test_work_ledger -- Halo 3.1.2.0 R1: one ledger line and one report
row (halo_harness/work/ledger.py, report.py, docs/WORK.md).

1. every kind's real event file (an Orchestra run's events.jsonl, a mission's
   log.jsonl, a team run's events.jsonl, a flow run's events.jsonl) reads as
   LedgerLines of the shared kinds (state|claim|gate|change|handoff|note);
2. the `units` key each report now carries equals the engine's legacy rows
   field by field (lane == report.lanes, step == report.steps, part ==
   report.parts, stage == board.stages).
Run: python -m tests.test_work_ledger
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


@test
def test_every_kind_s_log_reads_as_ledger_lines(ctx: Ctx):
    from halo_harness.work import ledger
    from tests.helpers.coach_seed import flow_run, mission_folder, orchestra_run, team_run
    from tests.helpers import coach_seed as S
    root = Path(tempfile.mkdtemp(prefix="work-ledger-"))
    run_dir = orchestra_run(root, [S.lane(1), S.lane(2)],
                            events=[S.event(1010.0, "claim", "s1 claimed basket.py#f1", op="claim", holder="s1/main",
                                            key="basket.py#f1", lane=1),
                                    S.event(1020.0, "gate", "tests fail on orchestra/x", back=[1])])
    lines = ledger.read(run_dir, "lane")
    kinds = {x.kind for x in lines}
    ctx.check(f"orchestra lines are ledger kinds, got {kinds}", kinds <= set(ledger.KINDS) and "claim" in kinds and "gate" in kinds)
    claim = next(x for x in lines if x.kind == "claim")
    ctx.check(f"a claim line carries the unit, holder and key, got {claim.to_dict()}",
              claim.unit == "1" and claim.by == "s1/main" and claim.key == "basket.py#f1" and claim.native == "claim")
    for kind, folder in (("step", flow_run(root)), ("part", mission_folder(root)), ("stage", team_run(root))):
        got = ledger.read(folder, kind)
        ctx.check(f"{kind}: lines read, every kind allowed, got {sorted({x.kind for x in got})}",
                  all(x.kind in ledger.KINDS for x in got))
    team_lines = ledger.read(team_run(root), "stage")
    ctx.check("team: the refused write is a claim line, the gate a gate line",
              any(x.kind == "claim" and x.unit == "ship" for x in team_lines)
              and any(x.kind == "gate" and x.unit == "copy" for x in team_lines))


@test
def test_the_units_key_equals_the_legacy_rows(ctx: Ctx):
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("work-rows-")
    run_dir = F.make_run(repo)
    report = run(run_dir, model_calls=F.FakeLead(F.split_answer([[f] for f in F.FUNCS])), spawn=F.FakeWorker(),
                 judge=F.FakeJudge())
    units = {u["unit"]: u for u in report["units"]}
    ctx.check(f"one unit row per lane, got {sorted(units)}", sorted(units) == ["1", "2", "3", "4", "5"])
    for lane in report["lanes"]:
        u = units[str(lane["lane"])]
        ctx.check(f"lane {lane['lane']}: unit row matches the legacy row",
                  u["title"] == lane["title"] and u["native"] == lane["state"]
                  and abs(u["cost_usd"] - lane["cost_usd"]) < 1e-9 and u["attempts"] == lane["pieces_returned"])
        ctx.check(f"lane {lane['lane']}: the row is the shared shape",
                  u["kind"] == "lane" and set(u) == {"unit", "kind", "title", "owner", "state", "native", "cost_usd",
                                                     "attempts", "gate", "base", "gave", "error"})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="work ledger tests"))
