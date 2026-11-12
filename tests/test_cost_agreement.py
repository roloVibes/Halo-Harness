"""tests.test_cost_agreement -- Halo 3.4.1.0 R5: one finished session with a sub-agent tells ONE number everywhere.

3.4.1.0 R2 fixed a replay counting a finished sub-agent's cost twice (the parent's rolled-up `usage` line AND the
sub-agent's own transcript); 3.4.0.1 made the harness's "today" and History read finished sessions from their
records (live/session_cost.py). The two read the same files differently, so this pins that they agree: the report
card, the compare row, the replay (Live's total), History's row, the harness's today (GET fleet's own entry) and the
fleet caps' harness figure, for a session started today with main's call ($0.004), a reviewer sub-agent ($0.008, its
own transcript plus the rollup line in main's) and a provider failure (a 429: a usage line with no price, which spent
nothing -- it must not make the total "unknown" in one place and whole in another).
Run: python -m tests.test_cost_agreement
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SID = "costagree0000000000000000000001"
TOTAL = 0.012


@contextlib.contextmanager
def _home():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    with tempfile.TemporaryDirectory(prefix="halo-cost-agree-") as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        try:
            from halo_harness.config.paths import bridge_home
            yield bridge_home()
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _lines(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def seed(state: Path, t0: float) -> Path:
    folder = state / "sessions" / "agree-proj"
    use = {"input_tokens": 1000, "output_tokens": 200}
    _lines(folder / f"{SID}.jsonl", [
        {"type": "meta", "ts": t0, "model": "or:mock/glm-5.3", "cwd": str(state.parent / "agree-proj"), "title": "agree"},
        {"type": "user", "ts": t0 + 1, "content": "Ship the basket fix"},
        {"type": "usage", "ts": t0 + 3, "usage": {}, "cost_usd": None, "model": "or:mock/glm-5.3", "status": "429", "retries": 1},
        {"type": "assistant", "ts": t0 + 5, "content": [{"type": "tool_use", "id": "a1", "name": "Agent", "input": {"subagent_type": "reviewer", "prompt": "review"}}]},
        {"type": "usage", "ts": t0 + 6, "usage": use, "cost_usd": 0.004, "model": "or:mock/glm-5.3", "status": "ok"},
        {"type": "usage", "ts": t0 + 40, "usage": {"input_tokens": 2000, "output_tokens": 400}, "cost_usd": 0.008, "agent_id": "rev1",
         "model": "or:mock/glm-5.3", "role": "reviewer", "ok": True},
        {"type": "tool_result", "ts": t0 + 40, "tool_use_id": "a1", "tool": "Agent", "content": "looks fine"},
        {"type": "assistant", "ts": t0 + 60, "content": [{"type": "text", "text": "Shipped."}]}])
    sub = folder / SID / "subagents"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "agent-rev1.meta.json").write_text(json.dumps({
        "agent_id": "rev1", "type": "reviewer", "role": "reviewer", "model": "or:mock/glm-5.3", "started": t0 + 6,
        "finished": t0 + 39, "status": "completed", "is_error": False, "description": "review"}), encoding="utf-8")
    _lines(sub / "agent-rev1.jsonl", [
        {"type": "user", "ts": t0 + 6, "content": "review"},
        {"type": "usage", "ts": t0 + 20, "usage": {"input_tokens": 2000, "output_tokens": 400}, "cost_usd": 0.008, "model": "or:mock/glm-5.3", "status": "ok"},
        {"type": "assistant", "ts": t0 + 38, "content": [{"type": "text", "text": "looks fine"}]}])
    return folder / f"{SID}.jsonl"


def _near(v, want=TOTAL) -> bool:
    return isinstance(v, (int, float)) and abs(float(v) - want) < 1e-9


@test
def test_one_finished_session_with_a_sub_agent_tells_one_number(ctx: Ctx):
    from halo_harness.live import caps, compare, history, replay_facts, report_card, session_cost
    from halo_harness.peers import local_view
    from halo_harness.studio import fleet_api
    with _home() as state:
        now = time.time()
        t0 = max(now - 600, session_cost._midnight(now) + 1)  # today, finished a while ago
        path = seed(state, t0)
        rec = session_cost.of_record(path)
        ctx.check(f"the record: main's call and the rollup, the 429 spent nothing: {rec}", _near(rec["usd"]) and rec["complete"])
        day = session_cost.today(state, now=now)
        ctx.check(f"the harness's today: one session, the same number, whole: {day}", _near(day["usd"]) and day["sessions"] == 1 and day["complete"])
        mine = local_view.today_fields(state)
        ctx.check(f"GET fleet's own entry: {mine}", _near(mine["cost_today"]) and mine["cost_today_complete"])
        live = history.read(path)
        ctx.check(f"the replay (Live's total): the sub-agent once: {live['cost_usd']}", _near(live["cost_usd"]))
        row = fleet_api.history(state, role="main")[0]
        ctx.check(f"History's row: {row['cost_usd']}", _near(row["cost_usd"]))
        facts = replay_facts.session_facts(path)
        ctx.check(f"the record's figures: {facts['cost_usd']} unknown {facts['cost_unknown']}", _near(facts["cost_usd"]) and facts["cost_unknown"] == [])
        p, from_file = report_card.resolve(state, f"session:{SID}")
        money = report_card.card(p, f"session:{SID}", from_file)["money"]
        ctx.check(f"the report card's money: {money['total']} known {money['known']}", _near(money["total"]) and money["known"])
        cmp = compare.compare(compare.resolve(state, f"session:{SID}"), compare.resolve(state, f"session:{SID}"))
        cost_row = next(r for r in cmp["rows"] if r["key"] == "cost")
        ctx.check(f"the compare row: {cost_row['a']}", _near(cost_row["a"]["value"]) and not cost_row["a"].get("unknown"))
        view = {"harnesses": [local_view.harness_entry([], state)]}
        spent = caps.spend(view, now)
        ctx.check(f"the caps' harness and fleet figures: {spent['harnesses']} {spent['fleet']}",
                  _near(spent["harnesses"][0]["usd"]) and _near(spent["fleet"]) and spent["complete"])


@test
def test_a_per_project_cap_counts_finished_sessions(ctx: Ctx):
    """3.4.0.1's hand-back (question 5): the per-project cap still counted only sessions still running. A harness's
    today now carries its records by project (`cost_today_projects`), and the cap reads it like the others."""
    from halo_harness.live import caps, session_cost
    from halo_harness.peers import local_view
    with _home() as state:
        now = time.time()
        seed(state, max(now - 600, session_cost._midnight(now) + 1))
        mine = local_view.harness_entry([], state)
        ctx.check(f"this harness's today by project (the session's folder), got {mine.get('cost_today_projects')}",
                  _near((mine.get("cost_today_projects") or {}).get("agree-proj", {}).get("usd")))
        member = {"id": "m", "name": "kali@kali", "cost_today": 0.02, "cost_today_projects": {"krepo": {"usd": 0.02, "sessions": 2}},
                  "sessions": [{"session_id": "live1", "started": now - 30, "cost_usd": 0.005, "project": {"repo": "krepo"}}]}
        spent = caps.spend({"harnesses": [mine, member]}, now)
        proj = {p["key"]: round(p["usd"], 6) for p in spent["projects"]}
        ctx.check(f"each project: the finished sessions' records (a live one already in them), got {proj}",
                  _near(proj.get("agree-proj")) and _near(proj.get("krepo"), 0.02))
        hit = caps.reached({"harnesses": [mine, member]}, {"per_project_usd_per_day": 0.015}, now)
        ctx.check(f"a per-project cap of $0.015 is reached by krepo only, got {[(r['scope'], r['key']) for r in hit]}",
                  [(r["scope"], r["key"]) for r in hit] == [("project", "krepo")])


@test
def test_lives_sentence_counts_a_members_session_once(ctx: Ctx):
    """Live re-check defect 33: on the hub's fleet scope a member's `halo -p` session box said $0.0075, its main agent
    $0.0075, and Live's sentence $0.015 (narrate.ts summed the session node AND its agent). The spend is the agents'."""
    import shutil
    import subprocess
    from tests.helpers.runner import SkipTest
    ui = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "agents" / "live"
    src = (ui / "narrate.ts").read_text(encoding="utf-8")
    ctx.check("the sentence's spend and its rows read liveSpend", "const spend = liveSpend(nodes)" in src and "liveSpend(ms)" in src)
    node = shutil.which("node")
    if not node:
        raise SkipTest("no node: the source is pinned above")
    nodes = [{"kind": "machine", "cost": 0.1419}, {"kind": "session", "cost": 0.0075}, {"cost": 0.0075}, {"kind": "part", "cost": 0.0075}]
    js = f"const m = await import({(ui / 'spend.ts').resolve().as_uri()!r}); console.log(JSON.stringify(m.liveSpend({json.dumps(nodes)})))"
    r = subprocess.run([node, "--experimental-strip-types", "--no-warnings", "--input-type=module", "-e", js],
                       capture_output=True, encoding="utf-8", errors="replace", timeout=60)
    if r.returncode != 0 and "strip-types" in (r.stderr or ""):
        raise SkipTest("this node cannot run a .ts module")
    got = json.loads((r.stdout or "null").strip().splitlines()[-1]) if r.returncode == 0 else r.stderr
    ctx.check(f"a machine, a session, its agent and a part: the agent's $0.0075 once, got {got}", _near(got, 0.0075))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="cost agreement tests"))
