"""tests.test_review3_d1b -- pins for the 3.0.2.0 review fix pass, round D1
(remote control core), part two:

  * review items 30, 97, 99 (the Signal bridge): the signal pack's tests/test_transport_pins.py,
                    test_bridge_pins.py and test_pairing.py since 3.3.13.0 R3
  * review item 98  the .ctl sweep keeps a sibling's young or owned socket
  * review item 100 the launchd agent restarts on failure only (logon_units.py since 3.3.13.0 R3)
"""
from __future__ import annotations

import json
import os
import plistlib
import socket
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


# ---- item 98 -------------------------------------------------------------------

@test
def test_item98_sweep_keeps_young_and_owned_sockets(ctx: Ctx):
    from halo_harness.remote import registry
    d = Path(tempfile.mkdtemp(prefix="d1-run-"))
    young, owned, dead = d / "young.ctl", d / "owned.ctl", d / "dead.ctl"
    for f in (young, owned, dead):
        f.write_text("", encoding="utf-8")
    old = time.time() - 3600
    for f in (owned, dead):
        os.utime(f, (old, old))
    (d / registry.FILENAME).write_text(json.dumps({"version": 1, "sessions": [
        {"session_id": "owned", "pid": os.getpid(), "endpoint": "unix:x"}]}), encoding="utf-8")
    registry.sweep_stale_ctl(d)
    ctx.check("a just-created socket file is kept", young.exists())
    ctx.check("one whose session has a live pid is kept", owned.exists())
    ctx.check("an old unowned one with no listener is removed", not dead.exists())
    if os.name == "nt" or not hasattr(socket, "AF_UNIX"):
        return
    path = d / "binding.ctl"
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.bind(str(path))  # bound, not yet listening: a connect probe is refused
        registry.sweep_stale_ctl(d)
        ctx.check("a sibling's bound-but-not-listening socket survives the sweep", path.exists())
    finally:
        s.close()



# ---- item 100 ------------------------------------------------------------------

@test
def test_item100_launchd_restarts_on_failure_only(ctx: Ctx):
    from halo_harness.logon_units import render_launchd
    plist = plistlib.loads(render_launchd(["/usr/local/bin/halo", "supervise"]).encode("utf-8"))
    ctx.check("KeepAlive restarts only after a non-zero exit", plist.get("KeepAlive") == {"SuccessfulExit": False})
    ctx.check("RunAtLoad still starts it at login", plist.get("RunAtLoad") is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
