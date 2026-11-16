"""A small real owner for tests/test_studio_launch_door.py: starts Studio the way `halo init` does
(studio/launch.launch_detached) with Halo's python behind a launcher (tests/helpers/fake_venv_launcher.py, what an
installed Halo's python.exe is on Windows), then runs THE closing procedure and writes what it saw to <out>/probe.json.

    python studio_door_probe.py <out>      (BRIDGE_TEST_HOME names the scratch home)
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def main() -> int:
    out = Path(sys.argv[1])
    from halo_harness import children, closing, selfexec
    from halo_harness.studio import launch
    closing.install()
    home = Path(os.environ["BRIDGE_TEST_HOME"]) / ".halo"
    home.mkdir(parents=True, exist_ok=True)
    real = selfexec.python_argv
    launcher = str(Path(__file__).with_name("fake_venv_launcher.py"))
    selfexec.python_argv = lambda *a, **k: [sys.executable, launcher, *real(*a, **k)]
    url = launch.launch_detached("setup", cwd=out, state_dir=home, open_browser=False, timeout=90)
    got: dict = {"url": bool(url), "why": launch.failure_line()}
    if url:
        info = launch.read_info(home) or {}
        got["studio_pid"] = info.get("pid")
        got["ledger"] = [{"pid": e.get("pid"), "launcher_pid": e.get("launcher_pid")}
                         for e in children.load(home) if e.get("what") == "studio"]
        from halo_harness import ps_cli
        got["ps_studio_rows"] = len([r for r in ps_cli.rows(home) if r.get("kind") == "studio"])
        t0 = time.monotonic()
        closing.close(state_dir=home)
        got["close_s"] = round(time.monotonic() - t0, 2)
        got["port_answers_after"] = launch.port_answers(info["port"]) if info.get("port") else None
        got["studio_json_after"] = (home / "studio.json").exists()
    (out / "probe.json").write_text(json.dumps(got), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
