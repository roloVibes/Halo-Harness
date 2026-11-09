"""tests.test_service_ctl -- the service the supervisor runs and the /signal verbs (3.3.13.0 R3): the service says
what it needs in its health file and ends 3 (no signal-cli, no account) or 0 (off, offline), runs the bridge until its
stop file appears and says goodbye to a phone it was talking to; the one-time move of ~/.halo/remote/; `/signal`,
`/signal pair`, `/signal phones`, `/signal sign on 1`, `/signal home 1 <folder>`, `/signal url`, a verb that is not
one; Setup's checks under offline mode. Every program runs as `bin/signal.py` in a scratch home.
Run: python -m tests.test_service_ctl"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from tests.support import ACI_A, PACK_ROOT, StubTransport, main, registry, wait_for

test, TESTS = registry()
BIN = PACK_ROOT / "bin" / "signal.py"


def _home() -> str:
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="signal-svc-")
    return os.environ["BRIDGE_TEST_HOME"]


def run(*args, env=None) -> "subprocess.CompletedProcess":
    e = {**os.environ, **(env or {})}
    e["PYTHONPATH"] = os.pathsep.join([str(Path(__import__("halo_harness").__file__).resolve().parent.parent),
                                       e.get("PYTHONPATH", "")])
    return subprocess.run([sys.executable, str(BIN), *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=e, timeout=60, stdin=subprocess.DEVNULL)


@test
def test_the_service_says_what_it_needs(ctx):
    _home()
    r = run("service", env={"PATH": "", "HALO_OFFLINE": "0"})
    from halo_signal import health
    h = health.read()
    ctx.check(f"no signal-cli: exit 3 with the install line, got {r.returncode} {r.stdout!r}",
              r.returncode == 3 and "install it" in h.get("line", "") and h.get("state") == "stopped")
    r = run("service", env={"HALO_OFFLINE": "1"})
    ctx.check("offline mode: off, exit 0", r.returncode == 0 and "offline" in health.read().get("line", ""))


@test
def test_the_service_runs_the_bridge_until_stopped(ctx):
    home = _home()
    from halo_signal import files, health, service, settings
    settings.save_signal(account="+15550199", binary=[sys.executable, "-c", "print('signal-cli 0.14.9')"])
    os.environ["HALO_SERVICE_STOP"] = str(Path(home) / "svc.stop")
    offline = os.environ.get("HALO_OFFLINE")
    os.environ["HALO_OFFLINE"] = "0"  # halo pack test runs offline; this bridge's transport is a stub
    tr = StubTransport()
    done = {}
    t = threading.Thread(target=lambda: done.setdefault("code", service.main([], transport_factory=lambda cfg: tr)),
                         daemon=True)
    try:
        t.start()
        ctx.check("the bridge started and says so in its health file",
                  wait_for(lambda: health.read().get("state") in ("starting", "connected"), 10.0))
        Path(os.environ["HALO_SERVICE_STOP"]).write_text("stop", encoding="utf-8")
        t.join(10)
        ctx.check("the stop file ends it with 0", done.get("code") == 0 and health.read().get("state") == "stopped")
        ctx.check("the data folder is the pack's", files.home().parent.name == ".data")
    finally:
        os.environ.pop("HALO_SERVICE_STOP", None)
        if offline is None:
            os.environ.pop("HALO_OFFLINE", None)
        else:
            os.environ["HALO_OFFLINE"] = offline


@test
def test_the_one_time_move(ctx):
    home = _home()
    from halo_signal import files
    old = Path(home) / ".halo" / "remote"
    if not files.home().parents[2].name == ".halo":
        old = files.home().parents[2] / "remote"
    old.mkdir(parents=True, exist_ok=True)
    (old / "peers.json").write_text(json.dumps({"version": 1, "peers": {ACI_A: {"aci": ACI_A, "signed": True}}}))
    (old / "signal.json").write_text(json.dumps({"account": "+15550199", "data_dir": str(old / "signal-cli")}))
    (old / "bridge.json").write_text("{}")
    lines = files.migrate()
    ctx.check(f"one line says what moved, got {lines}", len(lines) == 1 and "peers.json" in lines[0])
    ctx.check("the files are in the data folder", files.path("peers.json").exists()
              and files.read_json(files.path("signal.json")).get("data_dir") == "")
    ctx.check("the old pulse is gone and the move happens once", not (old / "bridge.json").exists() and files.migrate() == [])


@test
def test_the_signal_verbs(ctx):
    _home()
    r = run("ctl")
    ctx.check(f"/signal shows the state and the verbs, got {r.stdout[:200]!r}", r.returncode == 0 and "/signal" in r.stdout
              and "pair" in r.stdout)
    r = run("ctl", "pair")
    ctx.check("pair prints six words and a QR code", r.returncode == 0 and "Pairing phrase" in r.stdout
              and "█" in r.stdout)
    r = run("ctl", "pair")
    ctx.check("again while open: its state, not a second phrase", "waiting for a text" in r.stdout)
    from halo_signal.pairing import Pairing
    p = Pairing(trust_needed=False)
    p.redeem(ACI_A, p.invite()["phrase"], "+15550100")
    r = run("ctl", "phones")
    ctx.check("phones lists it, masked and unsigned", "0100" in r.stdout and "unsigned" in r.stdout)
    r = run("ctl", "sign", "on", "1")
    ctx.check("sign on shows the secret once with its link", "halo-remote://pair?" in r.stdout
              and Pairing().peer(ACI_A)["signed"] is True)
    folder = tempfile.mkdtemp(prefix="signal-home-dir-")
    r = run("ctl", "home", "1", folder)
    ctx.check("home sets the phone's folder", "new sessions start in" in r.stdout)
    r = run("ctl", "nonsense")
    ctx.check("a verb that is not one: exit 2 and the list", r.returncode == 2 and "pair | phones" in r.stdout)


@test
def test_setup_checks_offline(ctx):
    _home()
    for block in ("link", "test", "service"):
        r = run("setup", block, env={"HALO_OFFLINE": "1"})
        ctx.check(f"setup {block} under offline mode is green and says why, got {r.returncode} {r.stdout!r}",
                  r.returncode == 0 and "offline mode" in r.stdout)
    r = run("setup", "box", env={"PATH": ""})
    ctx.check("setup box without signal-cli is red with the install line", r.returncode == 1 and "install it" in r.stdout)
    r = run("setup", "pair")
    ctx.check("setup pair makes a phrase", r.returncode == 0 and "Pairing phrase" in r.stdout)


if __name__ == "__main__":
    raise SystemExit(main(TESTS))
