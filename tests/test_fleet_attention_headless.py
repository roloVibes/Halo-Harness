"""tests.test_fleet_attention_headless -- Halo 3.3.11.0 R2: a session with no terminal parks its asks, and the
Fleet attention queue says so (fleet/attention.py `_parked`, studio/fleet_watch_sources.pages,
fleet/local_view.session_row's `parked`). Pure: no Studio, no session, no model.

1. a headless session's permission card is `parked`; with no Studio page open its line ends "waiting on you
   in Studio" and the detail names the Prompt panel;
2. with a page open the row is parked and reads as any card; a TUI session's card is never parked;
3. the fleet row carries the status's `parked` asks (None for a session that has none to say);
4. `pages` counts the feed's open pages, 0 without a feed.
Run: python -m tests.test_fleet_attention_headless
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
NOW = time.time() + 7200.0  # ahead of the real clock (flake rule 4)


def _view(kind: str) -> dict:
    s = {"session_id": "s-" + kind, "title": "work", "kind": kind, "cwd": "/w/shop",
         "pending": {"permission": ["perm-1"]}, "parked": [{"id": "perm-1", "kind": "permission", "since": NOW - 5}],
         "agents": [{"agent_id": "main", "parent": None, "name": "main", "state": "waiting"}]}
    return {"harnesses": [{"id": "h1", "name": "you@box", "local": True, "sessions": [s]}]}


def _asks(kind: str) -> dict:
    return {("h1", "s-" + kind, "perm-1"): {"kind": "permission", "agent_id": "main",
                                            "data": {"id": "perm-1", "name": "Write", "input": {"file_path": "a.txt"}}}}


@test
def test_a_parked_ask_with_no_page_says_waiting_on_you_in_studio(ctx: Ctx):
    from halo_harness.fleet import attention
    rows = [r for r in attention.build(_view("headless"), asks=_asks("headless"), now=NOW, pages=0) if r["kind"] == "permission"]
    ctx.check(f"one permission row, got {rows}", len(rows) == 1)
    r = rows[0] if rows else {}
    ctx.check(f"parked, the line says it, got {r.get('what')!r}",
              r.get("parked") is True and r.get("what", "").endswith("-- waiting on you in Studio")
              and r.get("what", "").startswith("Permission: Write"))
    ctx.check(f"the detail names the Prompt panel, got {r.get('detail')!r}", "Prompt panel" in str(r.get("detail")))
    ctx.check("its answer keys are a permission's", r.get("keys", {}).get("a") == "allow once")


@test
def test_with_a_page_open_and_for_a_tui_session(ctx: Ctx):
    from halo_harness.fleet import attention
    open_ = [r for r in attention.build(_view("headless"), asks=_asks("headless"), now=NOW, pages=1) if r["kind"] == "permission"]
    ctx.check(f"a page open: parked, the card's own line, got {open_}",
              len(open_) == 1 and open_[0].get("parked") is True and "waiting on you in Studio" not in open_[0]["what"])
    tui = [r for r in attention.build(_view("tui"), asks=_asks("tui"), now=NOW, pages=0) if r["kind"] == "permission"]
    ctx.check(f"a TUI session's card is never parked, got {tui}",
              len(tui) == 1 and "parked" not in tui[0] and "waiting on you in Studio" not in tui[0]["what"])


@test
def test_the_fleet_row_carries_the_parked_asks(ctx: Ctx):
    from halo_harness.fleet.local_view import session_row
    entry = {"session_id": "s1", "cwd": "/w", "kind": "headless", "pid": 1, "started": NOW}
    parked = [{"id": "perm-1", "kind": "permission", "since": NOW}]
    row = session_row(entry, {"pending": {"permission": ["perm-1"]}, "parked": parked, "busy": True}, [])
    ctx.check(f"parked and waiting, got {row.get('parked')} {row.get('status')}", row.get("parked") == parked and row.get("status") == "waiting")
    ctx.check("kind headless", row.get("kind") == "headless")
    plain = session_row({**entry, "kind": "tui"}, {"pending": {}}, [])
    ctx.check("no parked list from a session that says none", plain.get("parked") is None)


@test
def test_pages_counts_the_feed(ctx: Ctx):
    from halo_harness.studio.fleet_watch_sources import pages
    ctx.check("no feed: 0", pages(SimpleNamespace(events=None)) == 0)
    ctx.check("two pages", pages(SimpleNamespace(events=SimpleNamespace(listeners=lambda: 2))) == 2)
    ctx.check("a feed that fails: 0", pages(SimpleNamespace(events=SimpleNamespace(listeners=lambda: 1 / 0))) == 0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
