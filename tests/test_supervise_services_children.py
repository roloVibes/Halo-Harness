"""tests.test_supervise_services_children -- a pack service's children end with it, and an ask is never lost (Halo
3.3.14.0 R2; supervise/procgroup.py, supervise/services.py, supervise/services_rows.py):

1. REVIEW #17 (CORE-3 / REMOTE-6 / PERMS-13 / PACKS-10): a slow service (it ignores its stop file) that started a
   child sleeper is stopped; the child's pid is gone after `_stop` (on Windows through the Job object, on POSIX
   through the service's own session);
2. REVIEW #25 (CORE-7 / PERMS-11 / PACKS-8): a Stop written between the tick's read of services-want.json and its
   clear survives to the next tick, which applies it.
Run: python -m tests.test_supervise_services_children"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.signal_rig import wait_for  # noqa: E402

test, TESTS = new_registry()
KEY = "service-pack/ticker"


class Clock:
    def __init__(self) -> None:
        self.now = 1_900_000_000.0

    def __call__(self) -> float:
        return self.now


@test
def test_stopping_a_slow_service_ends_its_child(ctx: Ctx):
    from halo_harness.bg_run import pid_alive
    from halo_harness.supervise import services as S
    with PacksHome() as h:
        h.install(h.source("service-pack"), enable=True, grants=["services"])
        data = h.home / ".halo" / "packs" / ".data" / "service-pack"
        data.mkdir(parents=True, exist_ok=True)
        (data / "slow.flag").write_text("x", encoding="utf-8")
        old = S.STOP_WAIT_S
        S.STOP_WAIT_S = 1.0
        svc = S.Services(h.home / ".halo", clock=Clock(), cwd=h.repo)
        child = 0
        try:
            svc.tick()
            ctx.check("the service runs", svc.rec[KEY].get("state") == "running")
            ctx.check("it started its child", wait_for(lambda: (data / "child.pid").exists(), 15.0))
            wait_for(lambda: (data / "child.pid").read_text(encoding="utf-8").strip().isdigit(), 2.0)
            child = int((data / "child.pid").read_text(encoding="utf-8").strip())
            ctx.check(f"the child {child} is alive before the stop", pid_alive(child))
            group = svc.groups.get(KEY)
            if os.name == "nt":
                ctx.check("the service is in a Job object", group is not None and group.job is not None)
            else:
                ctx.check("the service leads its own group", group is not None
                          and os.getpgid(svc.procs[KEY].pid) == svc.procs[KEY].pid)
            svc._stop(KEY, svc.rec[KEY], "stopped by you")
            ctx.check(f"the child {child} is gone after the stop", wait_for(lambda: not pid_alive(child), 10.0))
            ctx.check("the row says stopped", svc.rec[KEY].get("state") == "stopped")
        finally:
            S.STOP_WAIT_S = old
            svc.stop_all()
            if child and pid_alive(child):  # never leave a sleeper behind when the check failed
                try:
                    os.kill(child, 9)
                except OSError:
                    pass


class _Running:
    """A service process that keeps running (no real program, never signalled)."""
    def __init__(self, *_a, **_k) -> None:
        self.pid = os.getpid()

    def poll(self):
        return None

    def wait(self, *_a):
        return 0


@test
def test_an_ask_written_during_a_tick_waits_for_the_next(ctx: Ctx):
    from halo_harness.supervise import services_rows as R
    from halo_harness.supervise.services import Services
    with PacksHome() as h:
        h.install(h.source("service-pack"), enable=True, grants=["services"])
        state = h.home / ".halo"
        svc = Services(state, clock=Clock(), cwd=h.repo, popen=_Running)
        svc.tick()
        ctx.check("running", svc.rec[KEY].get("state") == "running")
        R.want("other-pack/svc", "start", state)
        real = R.declared

        def racing(*a, **k):  # the owner's Stop lands after the tick read the file, before it cleared it
            R.want(KEY, "stop", state)
            return real(*a, **k)
        R.declared = racing
        try:
            svc.tick()
        finally:
            R.declared = real
        left = R.read_json(R.want_path(state))
        ctx.check(f"the ask read is taken, the late one stays, got {left}", left == {KEY: "stop"})
        ctx.check("not applied yet", svc.rec[KEY].get("state") == "running")
        svc.tick()
        ctx.check(f"the next tick applies it, got {svc.rec[KEY]}", svc.rec[KEY].get("state") == "stopped"
                  and svc.rec[KEY].get("line") == "stopped by you")
        ctx.check("and the file is empty", R.read_json(R.want_path(state)) == {})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
