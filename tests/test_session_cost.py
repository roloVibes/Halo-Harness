"""tests.test_session_cost -- Halo 3.4.0.1 "Found live" (defects 10, 17, 26): a session's cost is read from its record
(live/session_cost.py), so "today" counts finished sessions too, on the hub's own machine and on a member, and the
fleet caps see them; a call Halo could not price stays unknown, never $0.

The live check: during a `halo -p` session GET fleet said `cost_today: 0.007372`; 20 s after it ended, `0.0`, and GET
fleet/costs `{fleet: 0.0}` after a mission and a goal run that day.
Run: python -m tests.test_session_cost
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.helpers import fleet_pack as _fleet_pack  # noqa: E402  (the fleet pack on, its modules by their old names)
_fleet_pack.on()

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _record(home: Path, sid: str, started: float, costs: list, project: str = "C--work-mrepo") -> Path:
    p = home / "sessions" / project / f"{sid}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [{"type": "meta", "ts": started, "session_id": sid}, {"type": "user", "content": "hi"}]
    lines += [{"type": "usage", "usage": {"input_tokens": 10}, "cost_usd": c, "model": m} for c, m in costs]
    p.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return p


def _home() -> Path:
    return Path(tempfile.mkdtemp(prefix="session-cost-"))


def _ago(s: float) -> float:
    """s seconds ago, never before today's midnight (a run just after midnight stays on one day)."""
    from halo_harness.live.session_cost import _midnight
    now = time.time()
    return max(_midnight(now) + 1, now - s)


@test
def test_today_counts_finished_sessions_from_their_records(ctx: Ctx):
    from halo_harness.live.session_cost import of_record, today
    from halo_harness.peers.local_view import harness_entry
    home, now = _home(), time.time()
    _record(home, "s-done", _ago(60), [(0.004, "or:a"), (0.003372, "or:a")])
    _record(home, "s-local", _ago(30), [(None, "ol:qwen3:8b@lan"), (0.0, "or:a")])
    old = _record(home, "s-yesterday", now - 3 * 86400, [(0.5, "or:a")])
    got = today(home)
    ctx.check(f"two sessions started today, the priced sum, the unpriced model named, got {got}",
              got["sessions"] == 2 and abs(got["usd"] - 0.007372) < 1e-9 and got["unknown"] == ["ol:qwen3:8b@lan"]
              and got["complete"] is False)
    ctx.check("a record started days ago is not today's", of_record(old)["usd"] == 0.5)
    entry = harness_entry([], home)  # no session runs any more
    ctx.check(f"this harness's cost_today after its sessions ended (defect 10), got {entry.get('cost_today')}",
              abs(entry["cost_today"] - 0.007372) < 1e-9 and entry["cost_today_complete"] is False
              and entry["cost_today_unknown"] == ["ol:qwen3:8b@lan"] and entry["sessions_today"] == 2)


@test
def test_the_caps_and_the_fleet_see_finished_spend(ctx: Ctx):
    from halo_harness.live.caps import spend
    view = {"harnesses": [{"id": "hub", "name": "kali@kali", "local": True, "cost_today": 0.0138, "sessions_today": 3,
                           "sessions": []},
                          {"id": "pc", "name": "rolo@roundBoy", "cost_today": 0.0434, "sessions_today": 1,
                           "cost_today_unknown": ["ol:x"],
                           "sessions": [{"session_id": "live", "cost_usd": 0.000431, "started": time.time()}]}]}
    got = spend(view)
    hs = {h["name"]: (h["usd"], h["sessions"]) for h in got["harnesses"]}
    ctx.check(f"each harness counts its finished sessions (defect 17), got {hs}",
              hs == {"kali@kali": (0.0138, 3), "rolo@roundBoy": (0.0434, 1)})
    ctx.check(f"the fleet total is theirs, and it says a price is unknown, got {got['fleet']} {got['complete']}",
              abs(got["fleet"] - 0.0572) < 1e-9 and got["complete"] is False)


@test
def test_a_member_says_its_own_today_and_the_hub_keeps_it(ctx: Ctx):
    from halo_harness.fleet.hub_links import Member
    m = Member({"id": "pc", "name": "rolo@roundBoy"}, None)
    m.note_costs([{"session_id": "live", "cost_usd": 0.000431, "started": time.time()}],
                 {"cost_today": 0.0434, "sessions_today": 2, "cost_today_unknown": []})
    v = m.view("3.4.0.1")
    ctx.check(f"the member's record-based today wins over the live rows the hub saw, got {v['cost_today']}",
              v["cost_today"] == 0.0434 and v["sessions_today"] == 2 and v["cost_today_complete"] is True)
    old = Member({"id": "old", "name": "old@box"}, None)
    old.note_costs([{"session_id": "s", "cost_usd": 0.02, "started": time.time()}])
    ctx.check("a member on an older Halo (no cost_today): what the hub saw", old.view("3.4.0.1")["cost_today"] == 0.02)


@test
def test_history_reads_the_same_record(ctx: Ctx):
    from halo_harness.studio.fleet_api import history
    home = _home()
    _record(home, "s-priced", _ago(60), [(0.0015, "or:a")])
    _record(home, "s-unpriced", _ago(30), [(None, "ol:x")])
    rows = {r["session_id"]: r["cost_usd"] for r in history(home, role="main")}
    ctx.check(f"History: the priced session's cost, the unpriced one unknown (None, never $0), got {rows}",
              rows == {"s-priced": 0.0015, "s-unpriced": None})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="session cost tests"))
