"""tests.test_studio_logs -- Halo 3.3.6.0 R3 deliverable 5, Local -> Logs in headless Chrome through
tests/helpers/studio_logs.py (skipped without one), over R1's seeded home (`box` a fake Ollama on 127.0.0.1:0, its log
this home's server.log) with a fixture log read into events; no provider request, no model call, never a real ssh:

1. the page opens from its door with box picked; the status line names the state and the path; the debug window is a
   stated action; every block has its "?" help; nothing opens over the page;
2. the per-model row: the last load (spilled, 59/66 layers), the cut prompt, the error lines, "crashed here";
3. the tail's lines carry their groups; the truncation filter keeps the cut line only; Copy says it on its row;
4. Live on: a line appended to the log arrives within a poll.
Run: python -m tests.test_studio_logs
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.driver_got import got as driver_got  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    info = driver_got(ctx, "tests.helpers.studio_logs", why="the Logs page checks need headless Chrome", cache=_RUN,
                      timeout=480)
    return info


@test
def test_the_status_line_and_the_page(ctx: Ctx):
    got = _got(ctx)
    state, text = (got.get("status") or ["", ""])[:2]
    ctx.check(f"box picked, its status with the path, got {got.get('host')} {state} {text!r}", got.get("host") == "box"
              and state in ("live", "stale", "quiet") and "server.log" in text)
    ctx.check(f"the debug window is a stated action, got {got.get('debug')!r}", "set OLLAMA_DEBUG=1 and restart Ollama on box"
              in str(got.get("debug")))
    ctx.check(f"a ? help per block, got {got.get('helps')}", {"local-logs-status-help", "local-logs-models-help",
                                                              "local-logs-tail-help"} <= set(got.get("helps") or []))
    ctx.check(f"nothing opens over the page, got {got.get('dialogs')}", got.get("dialogs") == 0)


@test
def test_the_per_model_row(ctx: Ctx):
    got = _got(ctx)
    load, line = (got.get("row") or ["", ""])[:2]
    ctx.check(f"the last load: spilled, 59/66 layers, got {load} {line!r}", load == "spilled" and "59/66 layers" in line)
    ctx.check(f"the cut prompt, got {got.get('truncations')}", any("cut at 2,050 of 23,536 tokens" in x for x in got.get("truncations") or []))
    ctx.check(f"the error lines, got {got.get('errors')}", "gpu-memory" in (got.get("errors") or []))
    ctx.check(f"crashed here with the fingerprint's line, got {got.get('crashed')!r}", str(got.get("crashed")).startswith("crashed here on"))


@test
def test_the_tail_its_filter_and_live(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the lines carry their groups, got {got.get('groups')}", {"fit", "failure", "truncation"} <= set(got.get("groups") or []))
    ctx.check(f"the truncation filter keeps the cut line only, got {got.get('filtered')}", len(got.get("filtered") or []) == 1
              and "truncating input prompt" in got["filtered"][0])
    ctx.check(f"Copy says it on its row, got {got.get('copied')!r}", "Get-Content" in str(got.get("copied"))
              or "tail -f" in str(got.get("copied")))
    ctx.check(f"Live: an appended line arrives, got {got.get('live')}", got.get("live") == "arrived")


@test
def test_a_local_server_beside_the_hosts(ctx: Ctx):
    """3.3.8.0 R2: the picker lists a llama-server Halo started; its status line, its runtime, its per-model row."""
    got = _got(ctx)
    state, runtime, text = (got.get("server_status") or ["", "", ""])[:3]
    ctx.check(f"its status line with its runtime and its log's path, got {state} {runtime} {text!r}",
              runtime == "llama-server" and f"{got.get('server_name')}.log" in text and state in ("live", "stale", "quiet"))
    load, facts = (got.get("server_row") or ["", ""])[:2]
    ctx.check(f"its row: spilled, 30/37 layers, the window per slot, got {load} {facts!r}", load == "spilled"
              and "30/37 layers" in facts and "window 8,192" in facts)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
