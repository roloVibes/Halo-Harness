"""tests.test_studio_start_lines -- Halo 3.4.0.1 "Found live" (defect 1): `halo studio --no-open` with its output
redirected says where Studio is at once.

The live check: `halo studio --no-open > log 2>&1 &` left the log empty while Studio ran (Python buffers a pipe);
the three lines reached it only when Studio stopped. A `--no-open` user who captures the URL (a script, an SSH user)
needs it now. A child Studio on a scratch home, stdout a pipe, no PYTHONUNBUFFERED: the URL line arrives while it
runs; `halo studio --stop` stops it.
Run: python -m tests.test_studio_start_lines
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
PREFIXES = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_",
            "PYTHONUNBUFFERED")


def _env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(PREFIXES)}
    env.update(BRIDGE_TEST_HOME=str(home), BRIDGE_TEST_NO_BACKGROUND_NET="1", PYTHONPATH=str(REPO))
    return env


@test
def test_the_url_line_reaches_a_pipe_while_studio_runs(ctx: Ctx):
    home = Path(tempfile.mkdtemp(prefix="studio-lines-"))
    proj = home / "project"
    proj.mkdir()
    env = _env(home)
    child = subprocess.Popen([sys.executable, "-m", "halo_harness", "studio", "--no-open", "--port", "0", "--cwd", str(proj)],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                             cwd=str(proj), encoding="utf-8", errors="replace")
    lines: "queue.Queue[str]" = queue.Queue()
    threading.Thread(target=lambda: [lines.put(x) for x in child.stdout], daemon=True).start()
    first = []
    try:
        while True:
            line = lines.get(timeout=60)
            first.append(line.rstrip())
            if line.startswith("Halo Studio is at "):
                break
        running = child.poll() is None
        ctx.check(f"the URL line arrived while Studio runs, got {first[-1][:40]!r} running={running}",
                  running and first[-1].startswith("Halo Studio is at http://127.0.0.1:"))
        more = [lines.get(timeout=20).rstrip() for _ in range(2)]
        ctx.check(f"the SSH and Ctrl+C lines too, got {more}", more[0].startswith("Over SSH:") and more[1].startswith("Ctrl+C"))
    except queue.Empty:
        ctx.check(f"the start lines arrived within the wait, got {first}", False)
    finally:
        subprocess.run([sys.executable, "-m", "halo_harness", "studio", "--stop"], env=env, cwd=str(proj),
                       capture_output=True, timeout=60)
        try:
            child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=10)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio start lines tests"))
