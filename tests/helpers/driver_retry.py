"""tests.helpers.driver_retry -- a Chrome driver retries once, in the open (Halo 3.3.8.1, docs/DEVELOPMENT.md "Flake
rules"). `chrome_driver.Driver.main` calls `after(out, own_home=...)` once its run has ended:

    after(out, *, own_home, real_chrome=True) -> out      unchanged unless the run ended `failed` on a TimeoutError in a
                                                          step (not an assertion, not a setup error) and no retry is off:
                                                          then the whole session runs once more in a fresh process with a
                                                          fresh home, and its result comes back with `retried: "<the first
                                                          failure line>"`
    first_failure(out) -> "" | the line a retry names     why(out) -> "" | why a run is retried

HALO_DRIVER_NO_RETRY=1 turns it off (a local red stays red); HALO_DRIVER_RETRY_OF marks the second run, which never
retries. A second timeout fails as the first would have, with `retried` still naming the first. The test modules read
the second result through tests/helpers/driver_got.py, which hands `retried` to the runner's [PASS] line.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

TIMEOUT_S = 600
OFF, MARK = "HALO_DRIVER_NO_RETRY", "HALO_DRIVER_RETRY_OF"


def first_failure(out: dict) -> str:
    return str((out or {}).get("failed") or "")


def why(out: dict, *, real_chrome: bool = True) -> str:
    f = first_failure(out)
    if not f or f.startswith("setup:") or ": TimeoutError: " not in f or not real_chrome:
        return ""
    if os.environ.get(OFF) == "1" or os.environ.get(MARK):
        return ""
    return f


def _argv() -> list:
    spec = getattr(sys.modules.get("__main__"), "__spec__", None)
    head = ["-m", spec.name] if spec is not None and spec.name else [sys.argv[0]]
    return [sys.executable, *head, *sys.argv[1:]]


def _drop(path) -> None:
    if path:
        import shutil
        shutil.rmtree(path, ignore_errors=True)


def after(out: dict, *, own_home: bool, real_chrome: bool = True) -> dict:
    first = why(out, real_chrome=real_chrome)
    if not first:
        return out
    env = dict(os.environ)
    env[MARK] = first[:300]
    fresh = None
    if own_home:  # the second run gets a fresh scratch home of its own, set BEFORE its first import: popping the
        # variables instead let the retried process resolve the real ~/.halo until scope_home ran (the Linux shard-0
        # run 41393796146 ended with the real-state guard: ~/.halo did not exist before and does now)
        import tempfile
        fresh = tempfile.mkdtemp(prefix="driver-retry-home-")
        env["BRIDGE_TEST_HOME"] = fresh
        env.pop("BRIDGE_STATE_DIR", None)
    print(f"[driver] retried once after: {first}", file=sys.stderr)
    try:
        r = subprocess.run(_argv(), capture_output=True, encoding="utf-8", errors="replace", timeout=TIMEOUT_S, env=env,
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        _drop(fresh)
        return {**out, "retried": first, "failed": f"{first} (and the retry ran past {TIMEOUT_S} s)"}
    _drop(fresh)
    sys.stderr.write(r.stderr or "")
    lines = (r.stdout or "").strip().splitlines()
    for line in lines[:-1]:
        print(line)
    try:
        second = json.loads(lines[-1]) if lines else {}
    except ValueError:
        second = {}
    if not isinstance(second, dict) or not second:
        second = {"failed": f"{first} (the retry printed no result, exit {r.returncode})"}
    return {**second, "retried": first}
