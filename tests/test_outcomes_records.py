"""tests.test_outcomes_records -- `outcomes.jsonl`, one row per agent task
(Halo 3.1.8.0 R3, outcomes/records.py, outcomes/session.py):

1. an Orchestra run in the mock rig appends one row per lane when its report
   is written -- run, task, bio, model, kind, outcome (`returned` for the lane
   sent back, `passed` for the other), what checked it, returns, cost, tests,
   sources, the evidence file -- in the test's home, never the real one;
2. once per report: writing it again or the coach's `note_run` adds nothing,
   and runs.json gains `outcomes: n`; a stopped run's lanes read `failed`
   (the lane at the cap) and `stopped` (the others);
3. a session's sub-agents record the same at their end: a pool member whose
   acceptance holds is `passed` (check `acceptance`), one whose acceptance
   fails twice is `failed` with one return; its evidence.json sits beside
   its transcript;
4. `halo outcomes` prints the table, filters by bio / model / kind / since,
   and `--json` gives the rows.
No real model call (a mocked upstream). Run: python -m tests.test_outcomes_records
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import outcomes_rig as R  # noqa: E402

ensure_default_provider_credentials()
test, TESTS = new_registry()
GROUPS = [["add_item", "remove_item", "subtotal"], ["apply_discount", "total"]]
REAL = Path.home() / ".halo" / "coach" / "outcomes.jsonl"


def _real_size() -> int:
    try:
        return REAL.stat().st_size
    except OSError:
        return -1


def _orchestra(plan):
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo, workers=2)
    report = run(run_dir, model_calls=F.FakeLead(F.split_answer(GROUPS)), spawn=R.TranscriptWorker(F.FakeWorker(), plan),
                 judge=F.FakeJudge())
    return run_dir, report


@test
def test_an_orchestra_run_appends_one_row_per_lane(ctx: Ctx):
    from halo_harness.outcomes.records import path, read
    before = _real_size()
    with R.home() as state:
        run_dir, report = _orchestra({1: ["code-no-tests", "code-lane"], 2: ["code-lane"]})
        rows = read()
        where = path()
        ctx.check(f"the rows land in the test's home, got {where}", where == state / "coach" / "outcomes.jsonl" and where.is_file())
    ctx.check(f"two rows, one per lane, got {[r['task'] for r in rows]}", [r["task"] for r in rows] == ["lane 1", "lane 2"])
    one, two = rows
    ctx.check(f"lane 1 was sent back once and passed later: returned, got {one}",
              one["outcome"] == "returned" and one["returns"] == 1 and one["check"] == "gate" and one["source"] == "orchestra")
    ctx.check(f"lane 2: passed, got {two['outcome']}", two["outcome"] == "passed" and two["returns"] == 0)
    ctx.check("the row's facts", one["run"] == report["run_id"] and one["model"] == "or:mock/lane-coder"
              and one["kind"] == "code" and one["tests_passed"] == 9 and one["tests_failed"] == 1 and one["sources"] == 1
              and Path(one["evidence"]).name == "evidence.json" and one["cost_usd"] > 0 and one["run_dir"] == str(run_dir.resolve()))
    ctx.check("the real ~/.halo/coach/outcomes.jsonl is untouched", _real_size() == before)


@test
def test_once_per_report_the_coachs_count_and_a_stopped_run(ctx: Ctx):
    from halo_harness.orchestra import jsonl
    from halo_harness.orchestra.coach_record import note_run
    from halo_harness.orchestra.report import load_report
    from halo_harness.outcomes.records import lane_outcome, read_all, record_orchestra
    with R.home() as state:
        run_dir, _report = _orchestra({1: ["code-lane"], 2: ["code-lane"]})
        n = len(read_all())
        again = record_orchestra(run_dir, load_report(run_dir))
        note_run({"run": run_dir.name, "kind": "orchestra", "suggestions": []}, run_dir)
        runs = jsonl.read_json(state / "coach" / "runs.json", {})
        ctx.check(f"writing it again or the coach's read adds nothing, got {n} -> {len(read_all())}",
                  n == 2 and again == 2 and len(read_all()) == 2)
        ctx.check(f"runs.json gains outcomes: n, got {runs}", runs.get(str(run_dir.resolve()), {}).get("outcomes") == 2)
    stopped = {"status": "stopped", "stop_reason": "lane 2 reached the return cap (2) and the tests still fail"}
    got = [lane_outcome({"lane": n, "state": s, "pieces_returned": 2}, stopped) for n, s in ((1, "merged"), (2, "waiting"), (3, "failed"))]
    ctx.check(f"a stopped run: the capped and the failed lanes failed, the other stopped, got {got}",
              got == ["stopped", "failed", "failed"])


def _spawn_rows(ctx: Ctx):
    from tests import test_auto_spawn as A
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.outcomes.records import read
    from halo_harness.teams_yaml import save_team_template
    from halo_harness.theme import set_config_value
    mock = A._mock()
    try:
        with A._Env() as e:
            A._seed_index(e.state_dir, A.ROWS)
            session = A._session(e, mock)
            out = A._dispatch(session, "c1", "Summarize notes.md in two lines", description="summarize the notes")
            ok = "CHEAP DONE" in out
            save_agent_bio("strict-bio", {"description": "never satisfied", "kind": "writer",
                                          "models": {"preference": "or:mock/plain-worker"},
                                          "acceptance": {"expect": "NEVER-SAID"}}, state_dir=e.state_dir)
            saved, _p = save_team_template("strict", {"description": "an acceptance that fails",
                                                      "routing": {"draft": "drafter"},
                                                      "agents": [{"agent": "default-model", "role": "main"},
                                                                 {"agent": "strict-bio", "role": "subagent", "as": "drafter"}]},
                                           state_dir=e.state_dir)
            set_config_value("team", "strict")
            session2 = A._session(e, mock)
            out2 = A._dispatch(session2, "c2", "Draft the notes", description="draft the notes")
            return ok and saved and "PLAIN RAN" in out2, read(e.state_dir), session, session2
    finally:
        mock.stop()


@test
def test_a_sessions_sub_agents_record_at_their_end(ctx: Ctx):
    ok, rows, session, session2 = _spawn_rows(ctx)
    ctx.check(f"both sub-agents ran, got {ok}", ok)
    ctx.check(f"one row each, got {[(r['task'], r['outcome']) for r in rows]}", len(rows) == 2)
    good, bad = rows
    ctx.check(f"the pool writer's acceptance held: passed, got {good}",
              good["source"] == "session" and good["outcome"] == "passed" and good["check"] == "acceptance"
              and good["bio"] == "auto-writer" and good["model"] == "or:mock/auto-cheap" and good["kind"] == "writing"
              and good["run"] == session.log.session_id and good["task"].startswith("agent "))
    ctx.check(f"the strict bio failed its acceptance twice: failed, one return, got {bad}",
              bad["outcome"] == "failed" and bad["check"] == "acceptance" and bad["returns"] == 1
              and bad["bio"] == "strict-bio" and bad["model"] == "or:mock/plain-worker" and bad["run"] == session2.log.session_id)
    ev = Path(bad["evidence"])
    data = json.loads(ev.read_text(encoding="utf-8")) if ev.is_file() else {}
    ctx.check(f"its evidence sits beside its transcript, got {ev}",
              ev.parent.name == "subagents" and ev.name.endswith(".evidence.json")
              and (ev.parent / ev.name.replace(".evidence.json", ".jsonl")).is_file()
              and data.get("acceptance", {}).get("met") is False and data["acceptance"]["expect"] == "NEVER-SAID")


def _cli(argv) -> str:
    from halo_harness.outcomes.cli import cmd_outcomes
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_outcomes(argv)
    return buf.getvalue()


@test
def test_halo_outcomes_prints_the_table(ctx: Ctx):
    from halo_harness.outcomes.records import append, make_row
    with R.home():
        empty = _cli([])
        append([make_row(run="r1", task="lane 1", source="orchestra", bio="auto-coder", model="or:v/a", kind="code",
                         outcome="passed", check="gate", cost_usd=0.01, ts=1760000000.0),
                make_row(run="s1", task="agent ab", source="session", bio="auto-researcher", model="or:v/b",
                         kind="research", outcome="done", ts=1760000100.0)])
        table, coded = _cli([]), _cli(["--kind", "code"])
        rows = json.loads(_cli(["--json", "--model", "or:v/b"]))
        since = _cli(["--since", "1760000050"])
        bad = _cli(["--since", "soon"])
    ctx.check("nothing yet says so", "No outcomes recorded yet" in empty)
    ctx.check(f"the table: both rows, the check beside the outcome, got\n{table}",
              "auto-coder" in table and "passed (gate)" in table and "auto-researcher" in table and "2 task(s)" in table)
    ctx.check("--kind filters", "auto-coder" in coded and "auto-researcher" not in coded)
    ctx.check(f"--json --model, got {rows}", [r["task"] for r in rows] == ["agent ab"])
    ctx.check("--since filters, and a bad one says how to write it", "auto-coder" not in since and "auto-researcher" in since
              and "does not read" in bad)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
