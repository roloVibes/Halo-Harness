"""tests.test_supervise_services -- a pack's services, run by the supervisor (Halo 3.3.13.0 R3; packs/manifest_services.py,
supervise/services.py, supervise/services_rows.py, docs/SUPERVISE.md "Pack services"), over the service-pack fixture
(tests/fixtures/packs/service-pack: a ticker that rewrites its health file):

1. the manifest: each bad value is one line naming the entry; a service needs the `services` grant;
2. a tick starts an enabled, granted pack's autostart service with the pack's environment (no provider key, its
   HALO_SERVICE / health / stop files), reads its health line, and the row says running;
3. Stop and Start (services-want.json), a crash started again after its wait, the grant taken back, the pack
   disabled, the supervisor's way out: each leaves the row saying why;
4. `halo pack enable` says where the service starts; `halo supervise services`; a pack command with `run:` runs the
   pack's program with no model call.
Run: python -m tests.test_supervise_services"""
from __future__ import annotations

import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.signal_rig import wait_for  # noqa: E402

test, TESTS = new_registry()


class Clock:
    def __init__(self) -> None:
        self.now = 1_900_000_000.0

    def __call__(self) -> float:
        return self.now


def _sup(h):
    from halo_harness.supervise import pulse
    from halo_harness.supervise.services import Services
    pulse.Pulse(h.home / ".halo").write("running")  # rows() reads a live pulse as "this supervisor runs"
    clock = Clock()
    return Services(h.home / ".halo", clock=clock, cwd=h.repo), clock


def _row(svc):
    return next((r for r in __import__("halo_harness.supervise.services_rows", fromlist=["rows_of"]).rows_of(svc.rec)
                 if r["key"] == "service-pack/ticker"), {})


@test
def test_the_manifest(ctx: Ctx):
    from halo_harness.packs.manifest_services import needs, service_lines
    bad = {"contributes": {"services": [
        {"name": "Bad Name", "run": ["${halo_python}", "../x.py"], "restart": "sometimes", "autostart": "yes"},
        {"name": "two", "run": "service/x.py", "health": {"file": "a.json", "url": "http://127.0.0.1:1/"}},
        {"name": "three", "run": "service/x.py", "health": {"url": "http://192.0.2.4:80/h"}, "log": "../out.log"},
        {"name": "two", "run": "service/x.py", "colour": 1}]}}
    lines = service_lines(bad)
    for needle in ("Bad Name", "outside the pack folder", "sometimes", "autostart: true or false", "exactly one of file",
                   "on this machine", "outside the pack's data folder", "used twice", "colour"):
        ctx.check(f"a line says {needle!r}", any(needle in ln for ln in lines))
    ctx.check("every service needs the services grant", needs(bad) and all(p == "services" for p, _ in needs(bad)))
    ctx.check("the fixture reads clean", PacksHome and not service_lines(
        __import__("halo_harness.agents_yaml", fromlist=["x"])._read_yaml_file(
            Path(__file__).resolve().parent / "fixtures" / "packs" / "service-pack" / "pack.yaml")))


@test
def test_a_tick_starts_the_service_with_the_packs_environment(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source("service-pack"), enable=True, grants=["services"])
        os.environ["OPENROUTER_API_KEY"] = "planted-not-a-key"
        svc, clock = _sup(h)
        try:
            svc.tick()
            row = _row(svc)
            ctx.check(f"started, got {row}", row.get("state") == "running" and row.get("pid"))
            health = h.home / ".halo" / "packs" / ".data" / "service-pack" / "ticker.json"
            ctx.check("it writes the health file the supervisor named", wait_for(lambda: health.exists(), 10.0))
            wait_for(lambda: "ticking" in health.read_text(encoding="utf-8"), 5.0)
            svc.tick()
            row = _row(svc)
            ctx.check(f"the row carries its line and health, got {row}", row.get("health") == "ok"
                      and "provider keys here: 0" in str(row.get("line")))
            ctx.check("HALO_SERVICE named it", json.loads(health.read_text(encoding="utf-8"))["service"] == "service-pack/ticker")
            from halo_harness.supervise.services_rows import rows, state_line
            ctx.check("another process reads it", [r["state"] for r in rows(h.home / ".halo")] == ["running"]
                      and state_line(rows(h.home / ".halo")[0]).startswith("running since "))
        finally:
            os.environ.pop("OPENROUTER_API_KEY", None)
            svc.stop_all()
        ctx.check("the supervisor's way out stops it", _row(svc).get("state") == "stopped")


@test
def test_stop_start_crash_grant_disable(ctx: Ctx):
    from halo_harness.supervise.services_rows import want
    with PacksHome() as h:
        h.install(h.source("service-pack"), enable=True, grants=["services"])
        svc, clock = _sup(h)
        try:
            svc.tick()
            want("service-pack/ticker", "stop", h.home / ".halo")
            svc.tick()
            ctx.check(f"Stop: stopped by you, got {_row(svc)}", _row(svc).get("state") == "stopped"
                      and _row(svc).get("line") == "stopped by you")
            svc.tick()
            ctx.check("and it stays stopped", _row(svc).get("state") == "stopped")
            want("service-pack/ticker", "start", h.home / ".halo")
            svc.tick()
            ctx.check("Start: running again", _row(svc).get("state") == "running")
            data = h.home / ".halo" / "packs" / ".data" / "service-pack"
            want("service-pack/ticker", "stop", h.home / ".halo")
            svc.tick()
            (data / "crash.flag").write_text("x", encoding="utf-8")
            want("service-pack/ticker", "start", h.home / ".halo")
            svc.tick()
            ctx.check("the crash is seen", wait_for(lambda: (svc.tick() or True) and _row(svc).get("state") == "failed", 10.0))
            ctx.check(f"with its exit and line, got {_row(svc)}", _row(svc).get("exit") == 3
                      and "crashed on purpose" in str(_row(svc).get("line")))
            svc.tick()
            ctx.check("not started again before its wait", _row(svc).get("state") == "failed")
            clock.now += 6
            svc.tick()
            ctx.check("started again after it", _row(svc).get("state") == "running")
            from halo_harness.packs.grants import disable, grant
            grant("service-pack", ["services"], on=False, cwd=h.repo, state_dir=h.home / ".halo")
            svc.tick()
            ctx.check(f"the grant taken back stops it, got {_row(svc)}", _row(svc).get("state") == "stopped"
                      and "services" in str(_row(svc).get("line")))
            disable("service-pack", state_dir=h.home / ".halo")
            svc.tick()
            ctx.check("a disabled pack's service leaves the list", _row(svc) == {})
        finally:
            svc.stop_all()


@test
def test_the_lines_and_the_command(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source("service-pack"))
        from halo_harness.packs.grants import enable_id
        ok, lines = enable_id("service-pack", grant=["services", "bash"], cwd=h.repo, state_dir=h.home / ".halo")  # bash: run:
        ctx.check(f"enable says where it starts, got {lines[-1:]}", ok and any(
            "service service-pack/ticker: starts with `halo supervise`" in ln and "running now: no" in ln for ln in lines))
        from halo_harness.supervise.cli import cmd_supervise
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cmd_supervise(["services"])
        ctx.check(f"halo supervise services before any tick, got {out.getvalue()!r}", rc == 0 and "no pack service" in out.getvalue())
        from halo_harness.commands.registry import Registry
        root = h.packs / "service-pack"
        cmd = Registry.discover(h.repo, home=h.home, plugin_roots=[root]).resolve("/service-pack")
        facade = type("F", (), {"cwd": h.repo, "session": None})()
        ctx.check("the entry command is a core command (no model call)", cmd is not None and cmd.kind == "core")
        ctx.check("it runs the pack's program with the words", "the pack's own program says: one two" in cmd.run("one two", facade))


class _Failing:
    """A service process that has already exited 1 (3.3.13.1, CORE-1)."""
    def __init__(self, *_a, **_k) -> None:
        self.pid = os.getpid()

    def poll(self):
        return 1

    def wait(self, *_a):
        return 1


@test
def test_two_thousand_failures_in_a_row_wait_300_s(ctx: Ctx):
    """REVIEW #15 (CORE-1): 5.0 * 2 ** 1024 raised OverflowError at the 1025th failure and every tick after it."""
    from halo_harness.supervise import services_rows as R
    from halo_harness.supervise.services import Services
    with PacksHome() as h:
        h.install(h.source("service-pack"), enable=True, grants=["services"])
        clock = Clock()
        svc = Services(h.home / ".halo", clock=clock, cwd=h.repo, popen=_Failing)
        svc.tick()
        svc.rec["service-pack/ticker"]["restarts"] = 2000
        clock.now += 1
        rows = svc.tick()
        r = svc.rec["service-pack/ticker"]
        ctx.check(f"one tick returns the rows, got {rows}", [x["key"] for x in rows] == ["service-pack/ticker"])
        ctx.check(f"the wait is 300 s, got {r['next_at'] - clock.now}", r["next_at"] - clock.now == 300.0)
        saved = R.read_json(R.state_path(h.home / ".halo"))["services"]["service-pack/ticker"]
        ctx.check(f"the state file is written, got {saved.get('restarts')}", saved.get("restarts") == 2001)


@test
def test_a_services_fault_never_skips_the_pulse(ctx: Ctx):
    from halo_harness.supervise import pulse
    from halo_harness.supervise.loop import Supervisor
    with PacksHome() as h:
        sup = Supervisor(h.home / ".halo")

        def boom():
            raise OverflowError("int too large to convert to float")
        sup.services.tick = boom
        sup.tick()
        ctx.check("the pulse is written after a services fault",
                  (pulse.read(h.home / ".halo") or {}).get("state") == "running")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
