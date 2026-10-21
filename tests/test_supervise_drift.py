"""tests.test_supervise_drift -- Halo 3.1.8.0 R2: when a supervised run drifts
(supervise/drift.py). Each drift kind and its number on the fixture run folder
tests/fixtures/supervise/drift-run (a merged lane, a lane sent back twice, a
lane waiting on a hand-off, a writing lane gone quiet, a writing lane refused a
claim), the thresholds read from config.json's `supervise` section, the queue
cap, and the replan's gate (mode, replan_max, the cooldown). No model is called.

Run: python -m tests.test_supervise_drift
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
FIXTURE = REPO / "tests" / "fixtures" / "supervise" / "drift-run"
T0 = 1760000000.0


def _run() -> Path:
    dst = Path(tempfile.mkdtemp(prefix="drift-")) / "drift-run"
    shutil.copytree(FIXTURE, dst)
    return dst


def _cfg(**over) -> dict:
    from halo_harness.supervise.settings import DEFAULTS
    return dict(DEFAULTS, **over)


def _by(drifts, kind):
    return [d for d in drifts if d.kind == kind]


@test
def test_each_drift_kind_with_its_number(ctx: Ctx):
    from halo_harness.supervise.drift import drift
    out = drift(_run(), _cfg(), now=T0 + 1000)
    kinds = sorted(d.kind for d in out)
    ctx.check(f"forecast, returns, two blocked, stalled; got {kinds}", kinds == ["blocked", "blocked", "forecast", "returns", "stalled"])
    f = _by(out, "forecast")[0]
    ctx.check(f"forecast: $0.65 spent + $0.85 left = $1.50 over 1.25 x $1.00, got {f.value} / {f.limit}: {f.text}",
              abs(f.value - 1.5) < 1e-6 and abs(f.limit - 1.25) < 1e-6 and "1.50x the goal's cap" in f.text)
    r = _by(out, "returns")[0]
    ctx.check(f"returns: lane 2 sent back 2 times, got {r.to_dict()}", r.lane == 2 and r.value == 2 and r.limit == 2)
    blocked = {d.lane: d for d in _by(out, "blocked")}
    ctx.check(f"blocked: lane 3 on a hand-off for 900s, got {blocked.get(3)}",
              3 in blocked and blocked[3].value == 900.0 and "hand-off from job-1" in blocked[3].text)
    ctx.check(f"blocked: lane 5 on a claim for 800s, got {blocked.get(5)}",
              5 in blocked and blocked[5].value == 800.0 and "basket.py#total" in blocked[5].text)
    s = _by(out, "stalled")[0]
    ctx.check(f"stalled: lane 4 quiet for 950s, got {s.to_dict()}", s.lane == 4 and s.value == 950.0)
    ctx.check("a merged lane never drifts (lane 1 was sent back 3 times)", all(d.lane != 1 for d in out))
    ctx.check("every line names its kind first", all(d.line.startswith(d.kind + ": ") for d in out))


@test
def test_the_thresholds_come_from_the_config(ctx: Ctx):
    from halo_harness.supervise.drift import drift
    from halo_harness.supervise.settings import settings
    sd = Path(tempfile.mkdtemp(prefix="drift-cfg-"))
    (sd / "config.json").write_text(json.dumps({"supervise": {
        "replan": "review", "replan_forecast": 1.6, "replan_returns": 3, "replan_block_s": 1000, "replan_stall_s": 1000,
        "replan_cooldown_s": 60, "replan_max": 1}}), encoding="utf-8")
    cfg = settings(sd)
    ctx.check(f"the section is read, got {cfg}", cfg["replan"] == "review" and cfg["replan_forecast"] == 1.6
              and cfg["replan_returns"] == 3 and cfg["replan_block_s"] == 1000.0 and cfg["replan_max"] == 1)
    ctx.check("nothing drifts under the raised thresholds", drift(_run(), cfg, now=T0 + 1000) == [])
    later = drift(_run(), cfg, now=T0 + 1300)
    ctx.check(f"past them, time drifts again (blocked, stalled), got {[d.kind for d in later]}",
              sorted(d.kind for d in later) == ["blocked", "blocked", "stalled"])
    (sd / "config.json").write_text(json.dumps({"supervise": {"replan": "sometimes", "replan_forecast": 0.5,
                                                              "replan_returns": "x", "replan_max": -1}}), encoding="utf-8")
    bad = settings(sd)
    ctx.check(f"values it does not understand take the defaults, got {bad}", bad["replan"] == "none"
              and bad["replan_forecast"] == 1.25 and bad["replan_returns"] == 2 and bad["replan_max"] == 2)


@test
def test_the_queue_cap_is_a_forecast_drift_too(ctx: Ctx):
    from halo_harness.supervise.drift import drift
    run = _run()
    goal = json.loads((run / "goal.json").read_text(encoding="utf-8"))
    goal.pop("budget_usd")
    (run / "goal.json").write_text(json.dumps(goal), encoding="utf-8")
    ctx.check("no cap at all: no forecast drift", not _by(drift(run, _cfg(), now=T0 + 1000), "forecast"))
    out = _by(drift(run, _cfg(budget_usd=1.2), now=T0 + 1000, others_usd=0.5), "forecast")
    ctx.check(f"the other goals' $0.50 + this run's $1.50 passes 1.25 x the queue's $1.20, got {[d.text for d in out]}",
              len(out) == 1 and abs(out[0].value - 2.0) < 1e-6 and "the queue's cap" in out[0].text)


@test
def test_no_lane_left_no_drift(ctx: Ctx):
    from halo_harness.supervise.drift import drift
    run = _run()
    for p in (run / "lanes").glob("*.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        data["state"] = "merged"
        p.write_text(json.dumps(data), encoding="utf-8")
    ctx.check("every lane merged: nothing drifts", drift(run, _cfg(), now=T0 + 5000) == [])
    lane = json.loads((run / "lanes" / "2.json").read_text(encoding="utf-8"))
    lane.update(state="written", replaced={"revision": 1, "by": ["job-2a", "job-2b"]})
    (run / "lanes" / "2.json").write_text(json.dumps(lane), encoding="utf-8")
    ctx.check("a lane a replan replaced never drifts", drift(run, _cfg(), now=T0 + 5000) == [])


@test
def test_the_replan_gate_mode_max_and_cooldown(ctx: Ctx):
    from halo_harness.supervise.replan import allowed, mode
    cfg = _cfg(replan="auto", replan_max=2, replan_cooldown_s=300)
    ctx.check("supervise.replan none: no replan", mode({}, _cfg()) == "none" and allowed({}, _cfg(), T0))
    ctx.check("auto from the config", mode({}, cfg) == "auto" and allowed({}, cfg, T0) == "")
    ctx.check("a goal's own --replan wins", mode({"replan": "review"}, cfg) == "review" and mode({"replan": "none"}, cfg) == "none")
    ctx.check("a plan: review goal always reviews", mode({"plan": "review"}, cfg) == "review")
    one = {"replans": [{"n": 1, "at": T0, "state": "applied", "settled": T0 + 10}]}
    ctx.check("within the cooldown of the last replan: not yet", "cooldown" in allowed(one, cfg, T0 + 200))
    ctx.check("past the cooldown: allowed", allowed(one, cfg, T0 + 400) == "")
    two = {"replans": one["replans"] + [{"n": 2, "at": T0 + 500, "state": "rejected", "settled": T0 + 600}]}
    ctx.check("at supervise.replan_max: no more", "replan_max" in allowed(two, cfg, T0 + 5000))
    dropped = {"replans": one["replans"] + [{"n": 2, "at": T0 + 500, "state": "dropped"}]}
    ctx.check("a pause the run outran does not count against the max", allowed(dropped, cfg, T0 + 5000) == "")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
