"""tests.test_supervise_pulse -- Halo 3.1.8.0 R1: the supervisor's pulse and
stop file (supervise/pulse.py), the generalized service-file writer
(remote/daemon_units.py) behind `halo supervise --service`, and `halo
supervise status|stop`. No daemon is ever started against the real home.

Run: python -m tests.test_supervise_pulse
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="supervise-pulse-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        self.state_dir = d / ".halo"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@test
def test_pulse_live_only_for_the_writing_process(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise import pulse
        ctx.check("no pulse reads off", pulse.read(e.state_dir)["state"] == "off" and not pulse.live(e.state_dir))
        p = pulse.Pulse(e.state_dir)
        p.write("running", {"queued": 2, "running": 1, "done": 0, "parked": 0})
        got = pulse.read(e.state_dir)
        ctx.check("this process's pulse is live and running", got["running"] and got["state"] == "running"
                  and got["goals"]["queued"] == 2)
        # a pulse written by a dead pid reads stopped (pid reuse guard)
        row = pulse.read_row(e.state_dir)
        row["pid"] = 2  # a pid that is not this process and not alive as a halo
        row["pstart"] = "nope"
        from halo_harness.privateio import write_private_atomic
        write_private_atomic(pulse.pulse_path(e.state_dir), json.dumps(row, sort_keys=True))
        ctx.check("a foreign pulse reads stopped", pulse.read(e.state_dir)["state"] == "stopped")


@test
def test_stop_file(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise import pulse
        ctx.check("no stop at first", not pulse.stop_requested(e.state_dir))
        pulse.request_stop(e.state_dir)
        ctx.check("stop requested now", pulse.stop_requested(e.state_dir))
        pulse.clear_stop(e.state_dir)
        ctx.check("cleared", not pulse.stop_requested(e.state_dir))


@test
def test_status_and_stop_cli(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise.cli import cmd_supervise
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cmd_supervise(["status"])
        ctx.check(f"status with no supervisor says so, got {out.getvalue()!r}", rc == 0 and "not running" in out.getvalue())
        j = io.StringIO()
        with redirect_stdout(j):
            cmd_supervise(["status", "--json"])
        row = json.loads(j.getvalue())
        ctx.check("status --json carries the goal counts", row["ok"] and "goals" in row and row["running"] is False)
        stop = io.StringIO()
        with redirect_stdout(stop):
            rc = cmd_supervise(["stop"])
        ctx.check("stop with none running says so and exits 0", rc == 0 and "no supervisor" in stop.getvalue())


@test
def test_service_file_written_under_the_state_dir_and_never_enabled(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise.cli import cmd_supervise
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cmd_supervise(["--service", "--os", "linux", "--json"])
        row = json.loads(out.getvalue())
        unit = Path(row["unit"])
        text = unit.read_text(encoding="utf-8")
        ctx.check("a systemd unit under supervise/ with the supervise ExecStart",
                  rc == 0 and unit.name == "halo-supervise.service" and unit.parent.name == "supervise"
                  and "supervise" in text and "WantedBy=default.target" in text)
        ctx.check("the enable command links and enables, nothing more",
                  row["enable"].startswith("systemctl --user link ") and "enable --now" in row["enable"])
        ctx.check("the file is not under the remote dir", "remote" not in unit.parts)


@test
def test_service_file_windows_and_macos(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise.cli import cmd_supervise
        for os_n, name, needle in (("windows", "halo-supervise-task.xml", "Halo Supervise"),
                                   ("macos", "dev.halo.supervise.plist", "dev.halo.supervise")):
            out = io.StringIO()
            with redirect_stdout(out):
                cmd_supervise(["--service", "--os", os_n, "--json"])
            row = json.loads(out.getvalue())
            unit = Path(row["unit"])
            text = unit.read_bytes().decode("utf-16") if os_n == "windows" else unit.read_text(encoding="utf-8")
            ctx.check(f"{os_n}: the right file and label, got {unit.name}", unit.name == name and needle in (text + row["enable"]))


@test
def test_the_signal_bridge_unit_is_unchanged(ctx: Ctx):
    """The generalized writer keeps the Signal bridge's own files and names."""
    with _Env() as e:
        from halo_harness.remote import daemon_units as du
        path, cmd = du.write_unit("linux", ["/usr/bin/halo", "remote", "signal", "run"], {})
        ctx.check("the bridge still writes halo-remote.service with its description",
                  path.name == "halo-remote.service" and "Halo remote control (Signal bridge)" in path.read_text(encoding="utf-8"))
        ctx.check("the bridge's enable command is unchanged", cmd.startswith("systemctl --user link "))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
