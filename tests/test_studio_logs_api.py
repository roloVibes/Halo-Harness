"""tests.test_studio_logs_api -- Halo 3.3.6.0 R3 deliverable 5, Local -> Logs's routes (studio/local_logs_api.py)
through studio/api.dispatch on a fixture home (tests/helpers/logs_rig.py: this machine's server.log under the home,
a remote host read through the fake ssh runner). Read-only, never a request to a server:

1. GET local/host/<n>/log: the bounded tail with each line's group, the kind filter, n bounded, a bad kind is 422;
2. GET local/host/<n>/log/status: the status line with the path and the tail command; a remote host over ssh;
3. GET local/host/<n>/log/models: per model the last load result, this session's truncations, the error lines,
   "crashed here" with the fingerprint's line; an unknown host is 404, a POST 405;
4. the Local door knows the page (`halo local logs`, `?page=logs`).
Run: python -m tests.test_studio_logs_api
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.logs_rig import GIN, LogsHome, T, crash_log  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BOX = {"name": "box", "url": "http://127.0.0.1:9"}
PC = {"name": "pc", "url": "http://192.0.2.10:11434", "ssh": "example@192.0.2.10"}
TRIM = 'time={t} level=WARN source=llama_server.go:334 msg="truncating input prompt" limit=2050 prompt=23536 keep=4 new=2050'


def _api(h, path, query=None, method="GET"):
    from halo_harness.studio.api import Request, dispatch
    return dispatch(Request(method=method, path=path, query=query or {}, body={}, cwd=h.root, state_dir=h.state, server=None))


def seed(h) -> None:
    """A log with a load, a cut prompt and a crash on `box`; a ledger session that called it."""
    from halo_harness.ollama_steward.server_log import scan
    from halo_harness.providers.ollama import resolve_ollama_hosts
    text = crash_log("qwen3.8:27b", 0.0) + TRIM.format(t=T(40)) + "\n" + GIN(41) + "\n"
    h.write_local(text)
    h.call(BOX, "qwen3.8:27b", time.time() - 115, session="s-1", num_ctx_sent=65536)
    scan(h.state, next(x for x in resolve_ollama_hosts() if x.name == "box"), from_start=True)


@test
def test_the_tail_and_its_filter(ctx: Ctx):
    with LogsHome(hosts=[BOX]) as h:
        seed(h)
        code, every = _api(h, "local/host/box/log", {"n": "500"})
        _c, cut = _api(h, "local/host/box/log", {"kind": "truncation"})
        _c, two = _api(h, "local/host/box/log", {"n": "2"})
        bad, why = _api(h, "local/host/box/log", {"kind": "loud"})
    groups = {r["group"] for r in every.get("lines") or []}
    ctx.check(f"every line with its group, got {code} {groups}", code == 200 and {"fit", "failure", "truncation"} <= groups
              and every["source"].endswith("server.log") and every["cli"] == "halo ollama log --host box -n 500")
    ctx.check(f"the kind filter keeps the cut line only, got {[r['text'][:40] for r in cut.get('lines') or []]}",
              len(cut["lines"]) == 1 and "truncating input prompt" in cut["lines"][0]["text"] and cut["lines"][0]["at"])
    ctx.check(f"n bounds the tail, got {len(two.get('lines') or [])}", len(two["lines"]) == 2)
    ctx.check(f"a bad kind is 422 with the kinds, got {bad} {why}", bad == 422 and "truncation" in why["error"])


@test
def test_the_status_route(ctx: Ctx):
    with LogsHome(hosts=[BOX, PC]) as h:
        seed(h)
        fake = h.remote("pc")
        fake.write("server.log", f'time={T(100)} level=INFO msg="a line"\n'.encode())
        _c, box = _api(h, "local/host/box/log/status")
        _c, pc = _api(h, "local/host/pc/log/status")
    ctx.check(f"the status line, the path, the tail command, got {box.get('line')!r}", box.get("state") in ("live", "stale")
              and box["path"].endswith("server.log") and box["tail_cli"] and box["debug_action"].startswith("set OLLAMA_DEBUG=1"))
    ctx.check(f"a remote host is read over ssh once, got {pc.get('line')!r}", "ssh example@192.0.2.10" in pc.get("path", "")
              and len(fake.calls) == 1 and pc.get("rung") == "ssh")


@test
def test_the_models_route(ctx: Ctx):
    with LogsHome(hosts=[BOX]) as h:
        seed(h)
        code, view = _api(h, "local/host/box/log/models")
        nf, _w = _api(h, "local/host/nowhere/log/models")
        post, _p = _api(h, "local/host/box/log", method="POST")
    row = next((m for m in view.get("models") or [] if m["model"] == "qwen3.8:27b"), {})
    ctx.check(f"the last load result, got {row.get('load')}", code == 200 and (row.get("load") or {}).get("state") == "spilled"
              and row["load"]["layers"] == [59, 66] and row["load"]["splits"] == 14)
    ctx.check(f"this session's truncations, got {row.get('truncations')}", len(row.get("truncations") or []) == 1
              and row["truncations"][0]["prompt"] == 23536 and view["session"]["id"] == "s-1")
    ctx.check(f"the error lines with times, got {[e['kind'] for e in row.get('errors') or []]}",
              any(e["kind"] == "gpu-memory" and e["at"] for e in row.get("errors") or []))
    ctx.check(f"crashed here with the fingerprint's line, got {row.get('crashed')}", (row.get("crashed") or {}).get("line", "")
              .startswith("crashed here on"))
    ctx.check(f"unknown host 404, POST 405, got {nf} {post}", nf == 404 and post == 405)


@test
def test_the_door_knows_the_page(ctx: Ctx):
    from halo_harness.studio.local_door import page_word
    ctx.check(f"`halo local logs` / ?page=logs, got {page_word('logs')}", page_word("logs") == ("logs", ""))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
