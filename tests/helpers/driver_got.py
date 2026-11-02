"""tests.helpers.driver_got -- the one `_got` every Chrome test module reads its driver through (Halo 3.3.8.1, in place of
each module's private copy): the driver subprocess runs once per module (the result cached), its last stdout line is
the JSON it saw, and a run the driver retried once (tests/helpers/driver_retry.py) says so on the runner's [PASS] line.

    got(ctx, module, *, why, cache, key="r", args=(), timeout=480, tail=800, stdin=True, what="the driver", env=None)
        -> info   (`env`: variables put back over driver_env's scrub, e.g. HALO_STUDIO_SLOW_MS)
        SkipTest without Chrome ("no Chrome found (<why>)") or when the driver says `skip`; one `ctx.check` that the
        driver ran (exit 0, no `failed`); `ctx.retried` = the first failure line when the driver retried once, which
        tests/helpers/runner.run_all appends to each [PASS] line: " (driver retried once: <first failure>)"
    run(module, args=(), timeout=480, stdin=True, env=None) -> (CompletedProcess, info)   the subprocess alone
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def run(module: str, args=(), timeout: int = 480, stdin: bool = True, env=None) -> tuple:
    from tests.helpers.chrome_driver import driver_env
    from tests.helpers.driver_retry import TIMEOUT_S
    kw = {"stdin": subprocess.DEVNULL} if stdin else {}
    r = subprocess.run([sys.executable, "-m", module, *args], capture_output=True, encoding="utf-8", errors="replace",
                       timeout=timeout + TIMEOUT_S + 30, env={**driver_env(REPO), **(env or {})}, cwd=str(REPO), **kw)  # + a retry
    try:
        info = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        info = {}
    return r, info if isinstance(info, dict) else {}


def got(ctx, module: str, *, why: str, cache: dict, key: str = "r", args=(), timeout: int = 480, tail: int = 800,
        stdin: bool = True, what: str = "the driver", env=None) -> dict:
    from tests.helpers.chrome_driver import find_chrome
    from tests.helpers.runner import SkipTest
    if not find_chrome():
        raise SkipTest(f"no Chrome found ({why})")
    if key not in cache:
        cache[key] = run(module, args, timeout, stdin, env)
    r, info = cache[key]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    if info.get("retried"):
        ctx.retried = str(info["retried"])[:300]
    ctx.check(f"{what} ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-tail:]!r}", r.returncode == 0
              and "failed" not in info)
    return info
