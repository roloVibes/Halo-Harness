"""A small real owner for tests/test_closing.py (3.6.0.0 R10): it starts the way `halo` does (closing.install, the
SIGTERM/SIGHUP handlers of cli._main), starts ONE kind of child through Halo's own code, writes ready.json, and waits
to be ended -- by a `quit` file (a normal exit), Ctrl+C, SIGTERM, SIGHUP or a hard kill.

    python closing_owner.py <kind> <outdir>        (BRIDGE_TEST_HOME names the scratch home)

kinds: studio  -- studio/launch.launch_detached, the way `halo init` starts Studio
       tool    -- someone else's binary through subprocess_safe.Popen, in no ledger (a tool command, an MCP server)
       ledger  -- the same, recorded in children.json as this owner's (a schedule fire, a model server)
       kept    -- a spawn a person asked to keep (kept_kwargs, keep=True), like `halo --bg`
       grandchild -- a tool command that starts its own child with the plain standard library
       mcp     -- an MCP stdio server through mcp/stdio.connect (the MCP SDK's own spawn)
       sub     -- its own child AND a sub-agent: a second owner (kind tool) it starts itself, which installs the
                  closing procedure and starts its own child (an orchestra worker, a nested `halo -p`)
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
    if kind == "mcp":
        return _mcp(out, home)
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
        extra = [str(out / "grandchild.json")] if kind == "grandchild" else []
        proc = subprocess.Popen(sleeper + [str(target)] + extra, **kw)
        got = _wait_file(target, 30)
        if kind == "grandchild":
            g = _wait_file(out / "grandchild.json", 30)
            kids.append({"pid": g["pid"], "start": children.start_time(g["pid"]), "what": "grandchild",
                         "marker": g["marker"]})
        if kind == "sub":
            sub_out = out / "sub"
            sub_out.mkdir(exist_ok=True)
            sub_proc = subprocess.Popen([sys.executable, str(Path(__file__)), "tool", str(sub_out)],
                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sub_ready = _wait_file(sub_out / "ready.json", 60)
            sub_ready["start"] = children.start_time(sub_proc.pid)
        if kind == "ledger":
            children.register(proc.pid, "schedule", sleeper)
        elif kind == "kept":
            children.register(proc.pid, "bg", sleeper, keep=True)
        kids.insert(0, {"pid": proc.pid, "start": children.start_time(proc.pid), "what": kind, "marker": got["marker"]})
    reaper = closing._STATE.get("reaper")
    ready = {"owner": os.getpid(), "marker": os.environ.get("HALO_OWNER"), "kids": kids,
             "reaper": {"pid": reaper.pid, "start": children.start_time(reaper.pid)} if reaper else None}
    if kind == "sub":
        ready["sub"] = sub_ready
    (out / "ready.json").write_text(json.dumps(ready), encoding="utf-8")
    try:
        while not (out / "quit").exists():
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("owner: interrupted", file=sys.stderr, flush=True)
        return 130
    return 0


def _mcp(out: Path, home: Path) -> int:
    import asyncio
    from halo_harness import children
    from halo_harness.mcp.stdio import connect
    pidfile = out / "mcp.json"
    env = dict(os.environ, R10_MCP_PIDFILE=str(pidfile), PYTHONPATH=str(REPO))
    server = str(Path(__file__).with_name("closing_mcp_server.py"))

    async def run() -> int:
        stack, _session = await connect(command=sys.executable, args=[server], env=env, cwd=str(out),
                                        errlog=sys.stderr, connect_timeout=60)
        try:
            got = _wait_file(pidfile, 30)
            kids = [{"pid": got["pid"], "start": children.start_time(got["pid"]), "what": "mcp", "marker": got["marker"]}]
            (out / "ready.json").write_text(json.dumps({"owner": os.getpid(), "marker": os.environ.get("HALO_OWNER"),
                                                        "kids": kids, "reaper": None}), encoding="utf-8")
            while not (out / "quit").exists():
                await asyncio.sleep(0.1)
        finally:
            await stack.aclose()
        return 0
    try:
        return asyncio.run(run())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
