"""tests.test_remote_doctor -- `halo doctor`'s remote-control rows (halo_harness/remote/doctor_check.py; Halo 2.0.9
round 4, 3.3.13.0 R3: the Signal bridge's rows went with it to the signal pack): one line for the control sockets,
`remote.enabled` and the transports listening; one row per pack service the supervisor knows -- running is OK, an
autostart service that is not is a WARN with its line and the command; `--json` records like every other check;
doctor writes nothing."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Home:
    def __enter__(self):
        self.saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="remote-doctor-")
        from halo_harness.config.paths import bridge_home
        self.state = bridge_home()
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        return False


def _entries() -> dict:
    from halo_harness.remote.doctor_check import entries
    return dict(entries())


@test
def test_the_control_line_and_writes_nothing(ctx: Ctx):
    with _Home() as h:
        before = sorted(p.name for p in h.state.rglob("*")) if h.state.exists() else []
        rows = _entries()
        ctx.check(f"one quiet row with nothing in use, got {rows}", list(rows) == ["remote"])
        line = rows["remote"]
        ctx.check("it names the sockets, the switch and the transports", line.startswith("[OK] Remote control: control "
                  "sockets on") and "remote.enabled on" in line and "transports listening: none" in line)
        after = sorted(p.name for p in h.state.rglob("*")) if h.state.exists() else []
        ctx.check("doctor wrote nothing", before == after)
        from halo_harness.remote.notify import listen
        listen("signal")
        ctx.check("a transport that listens is named", "transports listening: signal" in _entries()["remote"])


@test
def test_a_row_per_pack_service(ctx: Ctx):
    with _Home() as h:
        from halo_harness.supervise import pulse
        from halo_harness.supervise.services_rows import state_path, write_json
        write_json(state_path(h.state), {"version": 1, "services": {
            "signal/bridge": {"pack": "signal", "name": "bridge", "state": "failed", "autostart": True,
                              "line": "signal-cli is not on PATH -- install it: brew install signal-cli"},
            "other/job": {"pack": "other", "name": "job", "state": "stopped", "autostart": False, "line": "not started"}}})
        p = pulse.Pulse(h.state)
        p.write("running")
        rows = _entries()
        ctx.check(f"the stopped autostart service is a WARN with its line, got {rows}",
                  rows.get("service_signal_bridge", "").startswith("[WARN] pack service signal/bridge: failed: signal-cli")
                  and "halo supervise services" in rows["service_signal_bridge"])
        ctx.check("one that does not autostart is OK", rows.get("service_other_job", "").startswith("[OK]"))
        from halo_harness.doctor import run_checks_structured
        checks, _ok = run_checks_structured()
        rec = next((c for c in checks if c["id"] == "service_signal_bridge"), None)
        ctx.check(f"doctor --json carries it as a warn record with its fix, got {json.dumps(rec)}",
                  rec is not None and rec["status"] == "warn" and "halo supervise services" in str(rec.get("fix")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
