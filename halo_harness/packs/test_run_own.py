"""halo_harness.packs.test_run_own -- `halo pack test` runs the pack's own test modules (Halo 3.3.13.0 R3;
docs/PACK-AUTHORING.md "Testing"). Each `tests/test_*.py` in the pack folder runs as `python -m tests.<name>` from
the pack's folder, in the scratch home `halo pack test` made (BRIDGE_TEST_HOME, offline, no provider key), one check
per module: exit 0 passes; any other exit fails with its last lines. `tests/pack_test.py` is not one of them (it
runs `halo pack test` itself). A module that takes longer than OWN_TIMEOUT_S is stopped and fails.
"""

from __future__ import annotations

import os
import subprocess
import sys

OWN_TIMEOUT_S = 300.0


def own_tests(r) -> None:
    from halo_harness.packs.interpreter import pack_env
    folder = r.folder / "tests"
    mods = sorted(p for p in folder.glob("test_*.py") if p.is_file()) if folder.is_dir() else []
    if not r.wants("tests") or not mods:
        return
    env = pack_env(r.folder, dict(os.environ))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for p in mods:
        try:
            run = subprocess.run([sys.executable, "-m", f"tests.{p.stem}"], cwd=str(r.folder), env=env,
                                 capture_output=True, text=True, encoding="utf-8", errors="replace",
                                 timeout=max(OWN_TIMEOUT_S, r.timeout), stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            r.add("tests", f"tests/{p.name}", f"the pack's own test module {p.stem}", False,
                  f"it ran past {int(OWN_TIMEOUT_S)} s: a test that waits on something that never comes")
            continue
        tail = [ln for ln in (run.stdout + "\n" + run.stderr).splitlines() if ln.strip()][-6:]
        r.add("tests", f"tests/{p.name}", f"the pack's own test module {p.stem} ({tail[-1] if tail else 'no output'})",
              run.returncode == 0, " | ".join(tail) or f"exit {run.returncode}")
