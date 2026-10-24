"""tests.test_outcomes_evidence -- the evidence an agent's task leaves behind,
read out of its transcript (Halo 3.1.8.0 R3, halo_harness/outcomes/):

1. code: every test run (a test-runner command, or the goal's own test) with
   its exit, passed count, failing names and tail; the files it wrote, with a
   `git diff --numstat` when the folder is a repo; the summary kept apart;
2. research: the sources -- WebSearch, WebFetch, Read, Grep -- and never a
   fetch that failed;
3. check (agent_transcript entries, not nodes): the reproductions with their
   exits (a non-zero `[exit code N]`, a timeout as unknown), a curl as a
   fetched source;
4. writing: the file written (not a denied one) and the bio's acceptance on
   the final text; the kinds' one mapping;
5. the file: a lane's evidence.json after a worker pass in the mock rig, and
   a sub-agent's `agent-<id>.evidence.json` beside its transcript; the lines.
Fixture transcripts only, no model call. Run: python -m tests.test_outcomes_evidence
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import outcomes_rig as R  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix="ev-repo-"))
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                 ["config", "core.autocrlf", "false"], ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    (repo / "basket.py").write_text("def add_item():\n    pass\n", encoding="utf-8", newline="\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True, capture_output=True)
    return repo


@test
def test_code_evidence_is_the_test_runs_and_the_diff(ctx: Ctx):
    from halo_harness.outcomes.evidence import gather
    repo = _repo()
    (repo / "basket.py").write_text("def add_item():\n    entry = 1\n    return entry\n", encoding="utf-8", newline="\n")
    ev = gather(R.nodes("code-lane"), None, cwd=repo, default_kind="code", model="or:v/coder", cost_usd=0.0123)
    ctx.check(f"a lane with no bio is code, got {ev.kind}", ev.kind == "code" and ev.transcript)
    first, second = (ev.tests + [{}, {}])[:2]
    ctx.check(f"the failing pytest run: exit 1, 4 passed, the failing name, got {first}",
              first.get("command") == "python -m pytest -q test_basket.py" and first.get("exit") == 1
              and first.get("passed") == 4 and first.get("failed") == ["test_basket.py::test_total"]
              and "1 failed, 4 passed" in first.get("tail", "") and "[exit code" not in first.get("tail", ""))
    ctx.check(f"the passing unittest run: exit 0, 5 passed, got {second}",
              second.get("exit") == 0 and second.get("passed") == 5 and second.get("failed") == [])
    ctx.check("`git status` is not a test run (and a code task keeps no reproductions)",
              len(ev.tests) == 2 and ev.reproduction == [])
    ctx.check(f"the diff: the edited file, +2 -1 from git, got {ev.diff}",
              ev.written == ["basket.py"] and ev.diff == {"files": ["basket.py"], "added": 2, "removed": 1})
    ctx.check("the final text is the summary, apart from the items", ev.summary == "Wrote add_item; the five tests pass.")
    ctx.check("the totals", ev.tests_passed == 9 and ev.tests_failed == 1 and ev.model == "or:v/coder" and ev.cost_usd == 0.0123)
    goal_test = '"C:/py/python.exe" -m custom_runner --all'
    nodes = R.nodes("code-no-tests") + R.test_run(goal_test, "all good")
    ev = gather(nodes, None, default_kind="code", test_command=goal_test)
    ctx.check(f"the goal's own test command counts whatever it looks like, got {ev.tests}",
              len(ev.tests) == 1 and ev.tests[0]["command"] == goal_test and ev.tests[0]["passed"] is None)


@test
def test_research_evidence_is_the_sources_it_read(ctx: Ctx):
    from halo_harness.outcomes.evidence import gather
    ev = gather(R.nodes("research"), {"name": "auto-researcher", "kind": "researcher"})
    kinds = [(s["kind"], s["target"]) for s in ev.sources]
    ctx.check(f"a researcher bio is research, got {ev.kind}", ev.kind == "research" and ev.bio == "auto-researcher")
    ctx.check(f"search, fetch, read and grep, in order, got {kinds}", kinds == [
        ("search", "python decimal ROUND_HALF_UP quantize"), ("fetch", "https://docs.python.org/3/library/decimal.html"),
        ("read", "docs/ROUNDING.md"), ("read", "grep quantize in basket.py")])
    ctx.check("the fetch that failed is not a source", all("example.invalid" not in t for _k, t in kinds))
    ctx.check("each source says when", all(isinstance(s["when"], float) for s in ev.sources))


@test
def test_check_evidence_from_entries_is_the_reproductions(ctx: Ctx):
    from halo_harness.outcomes.evidence import gather
    ev = gather(R.nodes("check-entries"), None, words="tester")
    rep = [(r["command"], r["exit"]) for r in ev.reproduction]
    ctx.check(f"a tester is a check, got {ev.kind}", ev.kind == "check")
    ctx.check(f"the reproductions and their exits (a timeout is unknown), got {rep}", rep == [
        ("curl -sI http://localhost:8080/health", 0), ("grep -c ERROR /var/log/svc.log", 1), ("sleep 900", None)])
    ctx.check("the curl's URL is a fetched source", [s["target"] for s in ev.sources] == ["http://localhost:8080/health"])
    ctx.check("the handback is the summary", ev.summary.startswith("The endpoint answers 200"))
    ev = gather(R.nodes("check-entries"), None, words="coder")
    ctx.check("another kind keeps no reproductions", ev.kind == "code" and ev.reproduction == [])


@test
def test_writing_evidence_is_the_file_and_its_acceptance_and_the_kinds_map(ctx: Ctx):
    from halo_harness.outcomes.evidence import gather
    from halo_harness.outcomes.kinds import is_test_command, kind_of
    bio = {"name": "auto-writer", "kind": "writer", "acceptance": {"expect": "NOTES.md"}}
    ev = gather(R.nodes("writing"), bio)
    ctx.check(f"the file written, not the denied one, got {ev.written}", ev.written == ["NOTES.md"])
    ctx.check(f"the acceptance on the final text, got {ev.acceptance}",
              ev.acceptance == {"expect": "NOTES.md", "met": True, "why": "acceptance 'NOTES.md' on the final text: met"})
    ev = gather(R.nodes("writing"), dict(bio, acceptance={"expect": "CHANGELOG"}))
    ctx.check("an unmet acceptance says so", ev.acceptance["met"] is False and "not met" in ev.acceptance["why"])
    ev = gather(R.nodes("writing"), bio, acceptance={"expect": "non-empty", "met": False, "why": "the caller's", "attempts": 2})
    ctx.check("the caller's verdict wins over the bio's check", ev.acceptance["why"] == "the caller's")
    mapping = {("coder", ""): "code", ("researcher", ""): "research", ("reviewer", ""): "review", ("judge", ""): "review",
               ("planner", ""): "plan", ("writer", ""): "writing", ("media", ""): "media", ("ops", ""): "check",
               ("subagent", "Explore"): "research", ("custom", "tester auto-x"): "check", (None, "Plan"): "plan",
               (None, "general-purpose"): "other"}
    got = {k: kind_of(*k) for k in mapping}
    ctx.check(f"the one mapping, got {got}", got == mapping and kind_of(None, "", default="code") == "code")
    ctx.check("test runners", all(is_test_command(c) for c in ("pytest -q", "python -m unittest", "npm test", "go test ./...",
                                                                "cargo test", "python tests/run_all.py --fast", "npx vitest run")))
    ctx.check("not test runners", not any(is_test_command(c) for c in ("git status", "ls tests", "cat test.txt", "npm install")))


@test
def test_the_files_written_at_the_end_and_their_lines(ctx: Ctx):
    from halo_harness.orchestra.run import run
    from halo_harness.outcomes.lane import evidence_path, load_lane
    from halo_harness.outcomes.lines import lines
    from halo_harness.outcomes.session import evidence_path_for, record_subagent
    from tests.helpers import orchestra_fixtures as F
    with R.home():
        repo = F.make_repo()
        run_dir = F.make_run(repo, workers=1)
        worker = R.TranscriptWorker(F.FakeWorker(), {1: ["code-lane"]})
        report = run(run_dir, model_calls=F.FakeLead(F.split_answer([list(F.FUNCS)])), spawn=worker, judge=F.FakeJudge())
        ev = load_lane(run_dir, 1)
        ctx.check(f"the lane's evidence.json is written after its pass, got {report['status']}",
                  evidence_path(run_dir, 1).is_file() and ev is not None and ev.transcript and len(ev.tests) == 2
                  and ev.model == "or:mock/lane-coder" and ev.sessions and ev.sessions[0].startswith("lane1-pass1"))
        ctx.check(f"the lines, got {lines(ev)}", lines(ev)[0].startswith("tests: `python -m pytest -q test_basket.py` exit 1")
                  and "Wrote add_item" not in " ".join(lines(ev)))

        class _Log:
            def __init__(self, path):
                self.path, self.session_id = path, "agent-abc12345"

            def nodes(self):
                return R.nodes("research")

        class _Child:
            cwd, state_dir = None, None
            model_ref = type("M", (), {"raw": "or:v/reader"})()
            cost_meter = type("C", (), {"total_usd": 0.02})()

        parent_dir = Path(tempfile.mkdtemp(prefix="ev-sess-")) / "sess-1" / "subagents"
        parent_dir.mkdir(parents=True)
        child = _Child()
        child.log = _Log(parent_dir / "agent-abc12345.jsonl")
        parent = type("P", (), {"log": type("L", (), {"session_id": "sess-1"})(), "state_dir": None})()
        row = record_subagent(parent, child, spec_name="Explore", agent_id="abc12345")
        where = evidence_path_for(child)
        data = json.loads(where.read_text(encoding="utf-8")) if where.is_file() else {}
        ctx.check(f"a sub-agent's evidence lands beside its transcript, got {where}",
                  where.name == "agent-abc12345.evidence.json" and data.get("kind") == "research" and len(data.get("sources") or []) == 4)
        ctx.check(f"and its row says what it was, got {row}", row and row["kind"] == "research" and row["sources"] == 4
                  and row["outcome"] == "done" and row["evidence"] == str(where))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
