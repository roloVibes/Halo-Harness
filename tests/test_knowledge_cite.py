"""tests.test_knowledge_cite -- Halo 3.1.8.0 R4: an agent that reuses a finding
or a decision cites it (knowledge/cite.py, outcomes/evidence.py, the
Orchestra worker's brief), in the mock rig on the fake embedder:

1. the snapshot an agent receives lists each entry with its id, kind, who and
   when, and tells the agent to cite the id of any it reuses;
2. an Orchestra worker's brief carries the entries recall ranks for its job (two
   briefs built at once refresh the index together: one build at a time, neither
   loses its block -- on Windows the loser's replace of the index file was denied)
   (embeddings on, the store holding one), and nothing when embeddings are
   off, when `knowledge.brief: false`, or when the store is empty (no embed call);
3. the evidence gatherer records `cited: [<ids>]` when the agent's final text
   names an id this harness holds (an id it does not hold is not recorded),
   the evidence lines say `cited: <id>`, the outcome row carries the count,
   and `halo knowledge show <id>` lists the task under "reused by".
No model call. Run: python -m tests.test_knowledge_cite
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import knowledge_rig as K  # noqa: E402
from tests.helpers import outcomes_rig as R  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
GROUPS = [["add_item", "remove_item", "subtotal"], ["apply_discount", "total"]]


def _finding(state=None) -> dict:
    from halo_harness.knowledge.store import write
    return write("finding", "basket total rounds half up with decimal", evidence=["tests: `pytest -q` exit 0, 5 passed"],
                 by="gate", run="r0", repo="basket", state_dir=state)


def _citing(eid: str, other: str):
    """Lane 1's transcript: the fixture code lane, its final answer naming `eid` (and an id nobody holds)."""
    def rows(lane):
        nodes = R.nodes("code-lane")
        last = {"type": "assistant", "ts": 1760800009.0, "content": [
            {"type": "text", "text": f"Wrote add_item; total() rounds half up as ({eid}) found, unlike {other}."}]}
        return nodes + [last]
    return rows


def _run(plan: dict):
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo, workers=2, return_cap=2)
    worker = R.TranscriptWorker(F.FakeWorker(), plan)
    report = run(run_dir, model_calls=F.FakeLead(F.split_answer(GROUPS)), spawn=worker, judge=F.FakeJudge())
    return run_dir, worker, report


@test
def test_the_snapshot_tells_the_agent_to_cite(ctx: Ctx):
    from halo_harness.knowledge.cite import CITE_LINE, snapshot
    from halo_harness.knowledge.search import search
    with K.home() as state:
        f = _finding(state)
        text = snapshot(search("basket total", state_dir=state))
    ctx.check(f"one line per entry: id, kind, by, day, confidence, title, got {text!r}",
              f"- {f['id']} (finding, gate, {f['when'][:10]}, checked): {f['title']}" in text)
    ctx.check("and the line that tells it to cite the id", text.endswith(CITE_LINE) and "cite its id" in CITE_LINE)
    ctx.check("no hits: no block", snapshot([]) == "")


@test
def test_a_workers_brief_carries_the_ranked_entries(ctx: Ctx):
    from halo_harness.knowledge.cite import BRIEF_HEADER, CITE_LINE
    with K.home() as state:
        with K.embedder() as fake:
            _run_dir, worker, _report = _run({})
        ctx.check(f"an empty store: no block and no embed call, got {fake.calls}", fake.calls == 0
                  and all(BRIEF_HEADER not in p for ps in worker.prompts.values() for p in ps))
        f = _finding()
        with K.embedder():
            _run_dir, worker, _report = _run({})
        first = worker.prompts[1][0]
        ctx.check(f"embeddings on: the worker's brief lists it with the cite line, got {first[-400:]!r}",
                  BRIEF_HEADER in first and f"- {f['id']} (finding, gate, " in first and CITE_LINE in first)
        _run_dir, worker, _report = _run({})
        ctx.check("embeddings off: no block", BRIEF_HEADER not in worker.prompts[1][0])
        K.config(state, **{"knowledge.brief": False})
        with K.embedder():
            _run_dir, worker, _report = _run({})
        ctx.check("knowledge.brief false: no block", BRIEF_HEADER not in worker.prompts[1][0])


@test
def test_the_evidence_records_what_was_cited(ctx: Ctx):
    from halo_harness.knowledge.cli import cmd_knowledge
    from halo_harness.knowledge.cite import reused_by
    from halo_harness.outcomes.lane import load_lane, report_lines
    from halo_harness.outcomes.records import read
    with K.home():
        f = _finding()
        run_dir, _worker, report = _run({1: [_citing(f["id"], "f-20200101-0a0b0c")], 2: ["code-lane"]})
        ev1, ev2 = load_lane(run_dir, 1), load_lane(run_dir, 2)
        ctx.check(f"the run finished, got {report['status']}", report["status"] == "finished")
        ctx.check(f"lane 1's evidence cites the id it holds, not the other, got {ev1 and ev1.cited}",
                  ev1 is not None and ev1.cited == [f["id"]] and ev2 is not None and ev2.cited == [])
        ctx.check("its evidence lines say so", f"cited: {f['id']}" in report_lines(run_dir, 1))
        rows = {r["task"]: r for r in read()}
        ctx.check(f"the outcome row carries the count, got {[(t, r.get('cited')) for t, r in rows.items()]}",
                  rows["lane 1"].get("cited") == 1 and "cited" not in rows["lane 2"])
        reused = reused_by(f["id"])
        ctx.check(f"reused by lane 1 of the run, got {reused}", [(r["task"], r["run"]) for r in reused]
                  == [("lane 1", run_dir.name)] and reused[0]["outcome"] == "passed")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_knowledge(["show", f["id"]])
        ctx.check(f"halo knowledge show lists it, got {out.getvalue()[-200:]!r}",
                  f"reused by: lane 1 of {run_dir.name} (" in out.getvalue())


@test
def test_two_briefs_refresh_the_index_together(ctx: Ctx):
    """27956e6's Windows run: two workers' briefs refreshed the recall index at once; the loser's `os.replace`
    onto the file the other still read raised PermissionError, knowledge.search fell back to words and the
    brief dropped the block. recall.build_index runs one build at a time; the save tries a denied replace again."""
    import threading
    from halo_harness.recall import search as recall_search
    with K.home() as state:
        _finding(state)
        got, errors = [], []

        def one_brief():
            for _ in range(8):
                try:
                    got.append(bool(recall_search("basket total", state_dir=state, k=5)))
                except Exception as e:  # what the brief would have swallowed
                    errors.append(f"{type(e).__name__}: {e}"[:200])

        with K.embedder():
            threads = [threading.Thread(target=one_brief, name=f"brief-{i}") for i in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(60)
    ctx.check(f"no search raised, got {errors[:2]}", not errors)
    ctx.check(f"every search found the finding, got {got.count(False)} empty of {len(got)}", bool(got) and all(got))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
