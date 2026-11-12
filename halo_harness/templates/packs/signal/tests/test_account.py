"""tests.test_account -- the account verbs over the one-shot fake signal-cli (tests/fake_signal_admin.py): `/signal
register` asks for the captcha, then the code, verifies, saves the account and a registration-lock PIN set over
stdin; `/signal link` shows the link's QR code at once while a helper waits for the scan, and the account is linked
(Note to Self) with its own ACI. Every program runs as `bin/signal.py` in a scratch home. Run: python -m tests.test_account"""

from __future__ import annotations

import json
import os
from halo_harness.ext import subprocess_safe as subprocess
import sys
import tempfile
from pathlib import Path

from tests.support import PACK_ROOT, main, registry, wait_for

test, TESTS = registry()
ADMIN = Path(__file__).resolve().parent / "fake_signal_admin.py"


def _setup(mode: str = "ok") -> dict:
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="signal-acct-")
    from halo_signal import settings
    settings.save_signal(binary=[sys.executable, str(ADMIN)])
    log = Path(os.environ["BRIDGE_TEST_HOME"]) / "admin.log"
    return {"FAKE_SIGNAL_MODE": mode, "FAKE_SIGNAL_LOG": str(log)}


def ctl(*args, env=None) -> "subprocess.CompletedProcess":
    e = {**os.environ, **(env or {})}
    e["PYTHONPATH"] = os.pathsep.join([str(Path(__import__("halo_harness").__file__).resolve().parent.parent),
                                       e.get("PYTHONPATH", "")])
    return subprocess.run([sys.executable, str(PACK_ROOT / "bin" / "signal.py"), "ctl", *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=e, timeout=60, stdin=subprocess.DEVNULL)


@test
def test_register_a_number(ctx):
    env = _setup("captcha")
    r = ctl("register", "+15550199", env=env)
    ctx.check(f"a captcha first, with the page, got {r.stdout!r}", r.returncode == 1 and "signalcaptchas.org" in r.stdout)
    r = ctl("register", "+15550199", "--captcha", "signalcaptcha://x", env=env)
    ctx.check("then the SMS code is asked for", r.returncode == 0 and "--code" in r.stdout)
    r = ctl("register", "+15550199", "--code", "000000", env=env)
    ctx.check("a wrong code fails with its line", r.returncode == 1 and "Verification failed" in r.stdout)
    r = ctl("register", "+15550199", "--code", "123-456", env=env)
    from halo_signal import files, settings
    ctx.check(f"the right one registers, got {r.stdout!r}", r.returncode == 0 and settings.load_signal()["account"] == "+15550199"
              and settings.load_signal()["identity_model"] == "dedicated")
    pin = files.path("registration-pin")
    log = Path(env["FAKE_SIGNAL_LOG"]).read_text(encoding="utf-8")
    ctx.check("a registration-lock PIN was set over stdin and kept", pin.exists()
              and pin.read_text().strip() not in "".join(line for line in log.splitlines() if line.startswith("[")))
    r = ctl("register", "15550199", env=env)
    ctx.check("a number not in international form is the usage line", r.returncode == 2)


@test
def test_link_this_computer(ctx):
    env = _setup("ok")
    os.environ.update(env)
    try:
        r = ctl("link", env=env)
        ctx.check(f"the QR code and the link at once, got {r.stdout[-200:]!r}", r.returncode == 0
                  and "sgnl://linkdevice?" in r.stdout and "█" in r.stdout)
        from halo_signal import files, settings
        ctx.check("the helper finishes the link in the background",
                  wait_for(lambda: files.read_json(files.path("link.json")).get("state") == "linked", 20.0))
        cfg = settings.load_signal()
        ctx.check("the account is linked with its own ACI", cfg.get("identity_model") == "linked"
                  and cfg.get("own_aci", "").endswith("aa"))
        r = ctl("link", env=env)
        ctx.check("again: it says it is linked", "Linked as +15550199" in r.stdout)
    finally:
        for k in env:
            os.environ.pop(k, None)


if __name__ == "__main__":
    raise SystemExit(main(TESTS))
