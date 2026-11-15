"""A small real owner for tests/test_closing.py (3.6.0.0 R10): it starts the way `halo` does (closing.install, the
SIGTERM/SIGHUP handlers of cli._main), starts ONE kind of child through Halo's own code, writes ready.json, and waits
to be ended -- by a `quit` file (a normal exit), Ctrl+C, SIGTERM, SIGHUP or a hard kill.

    python closing_owner.py <kind> <outdir>        (BRIDGE_TEST_HOME names the scratch home)

kinds: studio  -- studio/launch.launch_detached, the way `halo init` starts Studio
       tool    -- someone else's binary through subprocess_safe.Popen, in no ledger (a tool command, an MCP server)
       ledger  -- the same, recorded in children.json as this owner's (a schedule fire, a model server)
       kept    -- a spawn a person asked to keep (kept_kwargs, keep=True), like `halo --bg`
Windows cannot deliver Ctrl+C to another console group: CTRL_BREAK stands in for it (mapped to KeyboardInterrupt,
which is what Ctrl+C raises in a real halo).
"""
import json
import os
import signal
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _wait_file(path: Path, seconds: float) -> dict:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            time.sleep(0.05)
    raise SystemExit(f"no {path.name} within {seconds} s")


def main() -> int:
    kind, out = sys.argv[1], Path(sys.argv[2])
    from halo_harness import children, closing
    from halo_harness import subprocess_safe as subprocess
    closing.install()
    signal.signal(signal.SIGTERM, lambda *_a: sys.exit(143))
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, lambda *_a: sys.exit(129))
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    home = Path(os.environ["BRIDGE_TEST_HOME"]) / ".halo"
    home.mkdir(parents=True, exist_ok=True)
    sleeper = [sys.executable, str(Path(__file__).with_name("closing_sleeper.py"))]
    kids = []
    if kind == "studio":
        from halo_harness.studio import launch
        url = launch.launch_detached("setup", cwd=out, state_dir=home, open_browser=False, timeout=60)
        if not url:
            print("studio did not start: " + launch.failure_line(), file=sys.stderr)
            return 3
        info = launch.read_info(home)
        kids.append({"pid": info["pid"], "start": info.get("pstart"), "what": "studio", "studio_json": info})
    else:
        target = out / f"{kind}-child.json"
        kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if kind == "kept":
            kw = closing.kept_kwargs(kw)
        proc = subprocess.Popen(sleeper + [str(target)], **kw)
        got = _wait_file(target, 30)
        if kind == "ledger":
            children.register(proc.pid, "schedule", sleeper)
        elif kind == "kept":
            children.register(proc.pid, "bg", sleeper, keep=True)
        kids.append({"pid": proc.pid, "start": children.start_time(proc.pid), "what": kind, "marker": got["marker"]})
    (out / "ready.json").write_text(json.dumps({"owner": os.getpid(), "marker": os.environ.get("HALO_OWNER"),
                                                "kids": kids}), encoding="utf-8")
    try:
        while not (out / "quit").exists():
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("owner: interrupted", file=sys.stderr, flush=True)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
