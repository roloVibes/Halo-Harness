"""tests.test_host_refresh -- Halo 3.3.7.0 R4: the off-hours refresh (host/refresh_plan.py, host/refresh.py,
local_refresh_cli.py) with a fake clock (never a real sleep) on the R1 host rig (tests/helpers/host_rig.py: a real
halo host on 127.0.0.1:0 whose home holds a battery profile for qwen3.8:27b):

1. the plan: never probed, no speed card, older than host.refresh.max_age_days, drifted (the digest changed) first,
   each with its minutes; the window wraps midnight; "next: ..., tonight 22:00+";
2. a tick inside the window with an idle card runs one model (the battery, then the quick bench: the runner seams),
   stamps the profile and the speed card "verified by the host", writes refresh.jsonl; outside the window, during a
   session or with config off it runs nothing; a call that arrives mid-run stops it;
3. `halo host refresh status | off`, `halo local refresh --dry`, and the host's GET refresh;
4. with nothing left to measure, the roster review line.
No model is called, nothing leaves 127.0.0.1.
Run: python -m tests.test_host_refresh
"""
from __future__ import annotations

import contextlib
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_rig import BIG, CODER, HostRig, pc_host  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def at(hour: int, minute: int = 0, days: int = 0) -> float:
    """hour:minute on the first day it is still ahead of the real clock (+ `days`): a fake `now` must never lie BEFORE
    the rig's real-time stamps (its ledger line, its profile), or the card reads busy / the profile reads fresh and
    nothing runs -- both runners failed so at 23:21 UTC with today's 23:00 (3.3.8.0 candidate 44617414, runs
    41361746057 / 41361745675); 3.3.8.1: every fake hour here is this one (tests/test_flake_rules.py)."""
    t = time.localtime()
    s = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hour, minute, 0, 0, 0, -1))
    # at least two hours ahead: the tick needs the card idle `idle_min` (20 min) since the rig's real-time ledger line, so a
    # fake now a few minutes ahead reads "not idle yet" and nothing runs (local run at 22:49 with 23:00: two reds)
    return (s if s > time.time() + 7200 else s + 86400) + days * 86400


def tonight(hour: int) -> float:
    """The tick tests' name for `at(hour)`: the first such hour still ahead of the real clock."""
    return at(hour)


def cats(big_digest: str = "sha256:0b27") -> dict:
    from tests.helpers.steward_seed import rows
    r = rows()
    return {"pc": {"models": [{**r[BIG], "digest": big_digest}, {**r[CODER], "digest": "sha256:c0de"}]}}


class Fakes:
    """The runner seams: the battery writes a fresh profile, the bench a fresh speed card; `call` makes a call arrive."""

    def __init__(self, home, clock, call: bool = False):
        self.home, self.clock, self.call, self.ran = home, clock, call, []

    def battery(self, host, model, *, state_dir, on_status):
        from halo_harness.providers.ollama_capability import save_profile
        from tests.helpers.host_rig import profile
        self.ran.append(("battery", model))
        save_profile(state_dir, {**profile(model), "digest": "sha256:0b27" if model == BIG else "sha256:c0de",
                                 "probed_at": self.clock()})
        if self.call:
            from halo_harness.ollama_steward.ledger import append_lines
            from tests.helpers.steward_seed import line
            append_lines(state_dir, [line(model=CODER, ago=0, **{"from": "mac@lab"})])
        on_status({"step": 1})
        return {"ok": True}

    def bench(self, host, model, *, state_dir, on_line):
        from halo_harness.providers.local_bench_runs import save
        self.ran.append(("bench", model))
        save(state_dir, {"model": model, "host": "pc", "digest": "sha256:0b27" if model == BIG else "sha256:c0de",
                         "at": self.clock(), "windows": [], "cold_load_s": 20.0, "took_s": 60})
        on_line("done")
        return {"ok": True}

    def runners(self):
        return {"battery": self.battery, "bench": self.bench}


@test
def test_the_plan_and_the_window(ctx: Ctx):
    from halo_harness.host.refresh_plan import in_window, plan, settings, start_words
    with HostRig() as rig:
        s = settings(rig.home)
        ctx.check(f"the defaults, got {s}", s == {"enabled": True, "window": "22:00-07:00", "idle_min": 20, "max_age_days": 14})
        p = plan(rig.home, [pc_host()], catalogs=cats(), now=at(12), settings_=s)
        got = {r["model"]: r for r in p["rows"]}
        ctx.check(f"never probed: the battery and the bench, got {got.get(CODER)}", got[CODER]["why"] == "unverified"
                  and got[CODER]["battery"] and got[CODER]["bench"] and got[CODER]["minutes"] >= 1)
        ctx.check(f"a fresh profile with no speed card: the bench only, got {got.get(BIG)}",
                  got[BIG]["why"] == "unverified" and not got[BIG]["battery"] and got[BIG]["bench"])
        old = plan(rig.home, [pc_host()], catalogs=cats(), now=time.time() + 20 * 86400, settings_=s)
        ctx.check("twenty days on: older", {r["model"]: r["why"] for r in old["rows"]}[BIG] == "older")
        drift = plan(rig.home, [pc_host()], catalogs=cats("sha256:9f1c"), now=at(12), settings_=s)
        ctx.check(f"a changed digest is drifted and first, got {drift['rows'][0]}", drift["rows"][0]["model"] == BIG
                  and drift["rows"][0]["why"] == "drifted" and "older build of this tag" in drift["rows"][0]["says"])
        ctx.check("the window wraps midnight", in_window("22:00-07:00", at(23)) and in_window("22:00-07:00", at(3))
                  and not in_window("22:00-07:00", at(12)) and not in_window("off", at(23)))
        ctx.check(f"the plan line, got {p['line']!r}", p["line"].startswith("next: ") and "tonight 22:00+" in p["line"]
                  and "idle 20 min" in p["line"] and start_words("22:00-07:00", at(23)).startswith("now"))


@test
def test_a_tick_runs_one_model_and_stamps_it(ctx: Ctx):
    from halo_harness.host import refresh as R
    with HostRig() as rig:
        R._STATE.update(running=None, checked=0.0)
        now = tonight(23)
        clock = iter([now + i for i in range(200)])
        f = Fakes(rig.home, lambda: next(clock))
        R._STATE["checked"] = 0.0
        out = R.tick(rig.home, [pc_host()], now=at(12), runners=f.runners(), start=lambda fn: fn(), clock=f.clock)
        ctx.check(f"outside the window: nothing, got {out!r}", out == "" and f.ran == [])
        R._STATE["checked"] = 0.0
        out = R.tick(rig.home, [pc_host()], now=now, runners=f.runners(), start=lambda fn: fn(), clock=f.clock)
        ctx.check(f"inside it, idle: one model, got {out!r} {f.ran}", out.startswith("refresh: ") and len({m for _k, m in f.ran}) == 1)
        st = R.status(rig.home, [pc_host()])
        ctx.check(f"stamped by the host, got {st['last_line']!r}", "verified by the host" in st["last_line"])
        from halo_harness.providers.ollama_capability import profile_for
        from halo_harness.providers.local_bench_runs import load
        m = f.ran[0][1]
        stamp = (profile_for(rig.home, m, "pc") or {}).get("verified_by"), (load(rig.home, "pc", m) or {}).get("verified_by")
        ctx.check(f"the profile and the speed card carry it, got {stamp}", stamp[1] == "the host"
                  and (stamp[0] == "the host" or ("battery", m) not in f.ran))
        kinds = [r["kind"] for r in R.log(rig.home)]
        ctx.check(f"refresh.jsonl has the start and the end, got {kinds}", kinds[:2] == ["start", "end"])


@test
def test_it_never_runs_during_a_session_and_stops_on_a_call(ctx: Ctx):
    from halo_harness.host import refresh as R
    from halo_harness.ollama_steward import idle
    with HostRig() as rig:
        now = tonight(23)
        f = Fakes(rig.home, lambda: now, call=True)
        saved = idle.idle_since
        idle.idle_since = lambda home, host, **kw: {**saved(home, host, sessions=lambda: [], **kw)}
        try:
            R._STATE.update(running=None, checked=0.0)
            R.tick(rig.home, [pc_host()], now=now, runners=f.runners(), start=lambda fn: fn(), clock=lambda: now)
        finally:
            idle.idle_since = saved
        end = [r for r in R.log(rig.home) if r["kind"] == "end"][-1]
        ctx.check(f"a call that arrives stops it, got {end}", end["stopped"].startswith("a call arrived")
                  and end["ok"] is False and "mac@lab" in end["stopped"])
        f2 = Fakes(rig.home, lambda: now)
        idle.idle_since = lambda home, host, **kw: {**saved(home, host, sessions=lambda: [
            {"session_id": "s-1", "model": f"ol:{BIG}@pc", "pid": -1}], **kw)}
        try:
            R._STATE.update(running=None, checked=0.0)
            out = R.tick(rig.home, [pc_host()], now=now + 7200, runners=f2.runners(), start=lambda fn: fn(),
                         clock=lambda: now + 7200)
        finally:
            idle.idle_since = saved
        ctx.check(f"a session on the card: nothing runs, got {out!r} {f2.ran}", out == "" and f2.ran == [])
        rig.set_peer()
        from halo_harness.fleet import identity
        from halo_harness.theme import set_config_value
        import os
        os.environ["BRIDGE_STATE_DIR"] = str(rig.home)
        try:
            set_config_value("host.refresh.enabled", False)
            identity.forget_cache()
            R._STATE.update(running=None, checked=0.0)
            out = R.tick(rig.home, [pc_host()], now=now + 9000, runners=f2.runners(), start=lambda fn: fn(),
                         clock=lambda: now + 9000)
        finally:
            os.environ.pop("BRIDGE_STATE_DIR", None)
            identity.forget_cache()
        ctx.check(f"config off: nothing, got {out!r}", out == "" and f2.ran == [])


@test
def test_the_commands_and_the_host_route(ctx: Ctx):
    from halo_harness.local_refresh_cli import cmd_host_refresh, cmd_refresh
    with HostRig(host_home=None) as rig:
        rig.set_peer(**{"ollama.hosts": [{"name": "pc", "url": "http://127.0.0.1:9"}]})
        from halo_harness.studio import ollama_hosts_view as V
        V.READERS["catalog"] = lambda h: cats()["pc"]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_refresh(["--dry", "--host", "pc"])
            rc2 = cmd_host_refresh(["status"])
            rc3 = cmd_host_refresh(["off"])
        text = out.getvalue()
        ctx.check(f"local refresh --dry says the plan and runs nothing, got {text[:400]!r}", rc == 0
                  and "next: " in text and "would: " in text)
        ctx.check("host refresh status: the settings line, the plan, the last run", rc2 == 0 and "window 22:00-07:00" in text
                  and "last refresh: none yet" in text)
        from halo_harness.theme import get_config_value
        ctx.check("host refresh off writes host.refresh.enabled", rc3 == 0 and get_config_value("host.refresh.enabled") is False
                  and "the off-hours refresh is off" in text)
        rig.start()
        rig.pair()
        got = rig.client().get("refresh")
        ctx.check(f"GET refresh answers the line, got {str(got)[:200]}", "line" in got and "last_line" in got)


@test
def test_nothing_left_is_a_roster_review(ctx: Ctx):
    from halo_harness.host import refresh as R
    with HostRig() as rig:
        from halo_harness.host.refresh_plan import settings
        import halo_harness.host.refresh_plan as RP
        saved = RP.plan
        RP.plan = lambda *a, **k: {"rows": [], "total_min": 0, "line": "nothing to refresh"}
        try:
            R._STATE.update(running=None, checked=0.0)
            out = R.tick(rig.home, [pc_host()], now=at(23), start=lambda fn: fn())
        finally:
            RP.plan = saved
        rows = [r for r in R.log(rig.home) if r.get("kind") == "roster-review"]
        ctx.check(f"the roster review line, got {out!r} {rows[-1:]}", out.startswith("roster review: ") and rows
                  and rows[-1]["lines"][0].startswith("roster: ") and settings(rig.home)["enabled"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
