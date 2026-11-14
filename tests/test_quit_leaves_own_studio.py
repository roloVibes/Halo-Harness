"""tests.test_quit_leaves_own_studio -- Halo 3.4.1.1 defect 48: a session's quit stops only what that session
started. A Studio the owner started on its own (`halo studio`) is in studio.json only, owned by no session, and
the last session's quit leaves it answering. A Studio a session
started for itself (studio/launch.launch_detached from inside a session) is that session's and ends with it; one a
shell command started (`halo replay open`, `halo init`) has no owner and stays.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from halo_harness import children as C

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
SCRUB = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_",
         "PACKS_TEST_")


def _env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB)}
    env.update(BRIDGE_TEST_HOME=str(home), BRIDGE_TEST_NO_BACKGROUND_NET="1", PYTHONPATH=str(REPO),
               PYTHONIOENCODING="utf-8")
    return env


def _read_lines(proc, lines: list) -> None:
    for line in proc.stdout:
        lines.append(line.rstrip("\n"))


def _wait_for(lines: list, prefix: str, proc, within: float = 90.0) -> str:
    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        hit = next((x for x in list(lines) if x.startswith(prefix)), None)
        if hit:
            return hit
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    raise TimeoutError(f"no {prefix!r} line; the child printed {lines!r}")


@test
def test_a_standalone_studio_outlives_another_sessions_quit(ctx: Ctx):
    """Two processes: `halo studio --no-open` started on its own, then a halo session of the same home that
    starts and quits. The Studio still answers; the quit line says it left the Studio."""
    import http.client
    home = Path(tempfile.mkdtemp(prefix="d48-home-"))
    lines: list = []
    studio = subprocess.Popen([sys.executable, "-u", "-m", "tests.helpers.standalone_studio", "studio"], cwd=str(REPO),
                              env=_env(home), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    threading.Thread(target=_read_lines, args=(studio, lines), daemon=True).start()
    try:
        url = _wait_for(lines, "Halo Studio is at ", studio).split("Halo Studio is at ", 1)[1].strip()
        port, token = int(re.search(r":(\d+)/", url).group(1)), url.split("#t=", 1)[1]
        info = next(home.rglob("studio.json"))
        ctx.check(f"studio.json names the standalone Studio, got {info.read_text(encoding='utf-8')!r}",
                  json.loads(info.read_text(encoding="utf-8")).get("pid") == studio.pid)
        quit_run = subprocess.run([sys.executable, "-m", "tests.helpers.standalone_studio", "quit"], cwd=str(REPO),
                                  env=_env(home), capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=120)
        said = next((x for x in quit_run.stdout.splitlines() if x.startswith("QUIT-LINE ")), "")
        ctx.check(f"the session quit (rc 0), got {quit_run.returncode} {quit_run.stderr[-600:]!r}",
                  quit_run.returncode == 0)
        ctx.check(f"its line leaves the Studio, got {said!r}",
                  said == "QUIT-LINE left running: Studio (started on its own; halo studio --stop)")
        ctx.check("the Studio process still runs", studio.poll() is None)
        ctx.check("studio.json is still there", info.exists())
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("GET", "/api/live", headers={"Authorization": "Bearer " + token})
        resp = conn.getresponse()
        body = json.loads(resp.read().decode("utf-8") or "{}")
        conn.close()
        ctx.check(f"Studio answers GET live, got {resp.status} {sorted(body)!r}",
                  resp.status == 200 and isinstance(body.get("harnesses"), list))
    finally:
        if studio.poll() is None:
            studio.terminate()
        try:
            studio.wait(timeout=15)
        except subprocess.TimeoutExpired:
            studio.kill()


def _sleeper() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@test
def test_a_shell_commands_studio_has_no_owner_and_a_sessions_is_its_own(ctx: Ctx):
    """launch_detached's owner: a plain process (a shell command) is no session, so its Studio has no owner and a
    quit leaves it; a process registered as a TUI session in run/sessions.json owns the Studio it starts."""
    from halo_harness.children_stop import quit_targets
    from halo_harness.remote import registry
    state = Path(tempfile.mkdtemp(prefix="d48-owner-"))
    reg = registry.registry_path()
    saved = reg.read_text(encoding="utf-8") if reg.exists() else None
    owner_env = os.environ.pop(C.OWNER_ENV, None)
    shell, mine = _sleeper(), _sleeper()
    try:
        ctx.check("a plain process is not a session", C.in_session() is False)
        C.register(shell.pid, "studio", ["halo", "studio"], state_dir=state, launched=not C.in_session())
        registry._write(reg, [{"session_id": "d48-me", "pid": os.getpid(), "kind": "tui", "endpoint": "", "cwd": "."}])
        ctx.check("a registered TUI session is one", C.in_session() is True)
        C.register(mine.pid, "studio", ["halo", "studio"], state_dir=state, launched=not C.in_session())
        rows = {r["pid"]: r for r in C.load(state)}
        ctx.check(f"the shell's Studio has no owner, the session's is this pid, got {rows}",
                  rows[shell.pid]["owner_pid"] is None and rows[mine.pid]["owner_pid"] == os.getpid())
        registry._write(reg, [])
        ctx.check(f"a quit stops the session's own Studio only, got {quit_targets(state)}",
                  [e["pid"] for e in quit_targets(state)] == [mine.pid])
    finally:
        if owner_env is not None:
            os.environ[C.OWNER_ENV] = owner_env
        if saved is None:
            reg.unlink(missing_ok=True)
        else:
            reg.write_text(saved, encoding="utf-8")
        for p in (shell, mine):
            p.kill()
            p.wait(timeout=10)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
