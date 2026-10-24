"""halo_harness.orchestra.merge -- the workers' pieces, one at a time.

Code decides the order (`merge_order`: the split's order, then the smaller
diff, `git diff --shortstat`), creates the finished branch
`orchestra/<run-id>` from the split's base in its own worktree
`<run>/wt/merge`, and merges each worker branch with `git merge --no-ff`.

On a conflict both versions stay in the file between git's markers; code
extracts the hunks and calls `judge(hunks, goal, file)` -- in the real
runner a FRESH agent that sees only the goal and the hunks -- applies its
text by code and runs the tests. Tests that pass (or, mid-sequence, fail no
test that was not already failing) keep the merge. Otherwise the merge is
undone and the piece goes back to its worker (`pieces_returned += 1`, lane
`waiting`, `respawn(lane, text)`), unless the lane is at `return_cap`: then
the run stops with the reason. A lane still marked `stale` (its upstream was
sent back and it is not re-based yet, orchestra/stale.py) is never merged.

`<run>/merge.json`:

    {"branch": "orchestra/<run>", "base": "<sha>", "order": [1, 2, 3],
     "merged": [1, 2], "finished": "<sha>" | null,
     "conflicts": [{"lane", "file", "attempt", "hunks", "judge_session", "fresh",
                    "messages_before", "resolution", "applied_by": "code",
                    "tests_ok", "tests_tail", "ts", "elapsed_s"}]}
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import gitops, jsonl
from halo_harness.orchestra.gate import run_tests, send_back
from halo_harness.orchestra.goal import repo_root_of
from halo_harness.orchestra.hunks import apply_resolution, extract_hunks, parse_resolution
from halo_harness.orchestra.split import StopRun
from halo_harness.outcomes.lane import with_evidence  # 3.1.8.0 R3: the judge reads the lanes' evidence


@dataclass
class MergeResult:
    branch: str
    order: list
    merged: list
    conflicts: list = field(default_factory=list)
    finished: Optional[str] = None


def merge_path(run_dir) -> Path:
    return Path(run_dir) / "merge.json"


def load_merge(run_dir) -> dict:
    data = jsonl.read_json(merge_path(run_dir), {})
    return data if isinstance(data, dict) else {}


def merge_order(run_dir, lanes: list, base: str) -> list:
    """Lane numbers in merge order: the hand-off layer (3.0.9.0), then the
    split's order, then the smaller diff. Undeclared lanes are all layer 0."""
    from halo_harness.orchestra.handoff_spec import layers
    repo = repo_root_of(run_dir)
    layer = layers({lane.job.id: lane.job.upstreams for lane in lanes})
    return [lane.n for lane in sorted(lanes, key=lambda l: (layer.get(l.job.id, 0), l.job.order,
                                                            gitops.shortstat(repo, base, l.branch), l.n))]


def merge_heads(run_dir, lane_n: int, heads: list) -> "tuple[Optional[str], str]":
    """The start of lane `lane_n` with two or more upstreams (3.0.9.0): a
    scratch branch `orchestra/<run>-base-<n>` at `heads[0]` in
    `<run>/wt/base-<n>`, each other head merged `--no-ff`. `(sha, "")`, or
    `(None, reason)` on a conflict (the merge is undone; no judge is asked:
    the lane waits with the reason)."""
    run_dir = Path(run_dir)
    repo = repo_root_of(run_dir)
    path = run_dir / "wt" / f"base-{int(lane_n)}"
    branch = f"{gitops.finished_branch(run_dir.name)}-base-{int(lane_n)}"
    gitops.worktree_remove(repo, path)
    gitops.check(["branch", "-f", branch, heads[0]], repo)
    gitops.worktree_add(repo, path, branch, heads[0])
    try:
        for sha in heads[1:]:
            got = gitops.merge_no_ff(path, sha, f"orchestra: the start of lane {lane_n} (merge {sha[:12]})")
            if got.returncode != 0:
                files = gitops.conflicted_files(path)
                gitops.merge_abort(path)
                why = f"conflict in {', '.join(files)}" if files else ((got.stderr or got.stdout or "").strip().splitlines() or ["no output"])[-1]
                return None, f"its upstreams' heads do not merge ({why})"
        return gitops.head(path), ""
    finally:
        gitops.worktree_remove(repo, path)


def _judge_answer(answer) -> dict:
    if isinstance(answer, dict):
        return {"text": str(answer.get("text") or ""), "session_id": answer.get("session_id"),
                "messages_before": int(answer.get("messages_before") or 0),
                "cost_usd": float(answer.get("cost_usd") or 0.0)}
    return {"text": str(answer or ""), "session_id": None, "messages_before": 0, "cost_usd": 0.0}


def merge_worktree(run_dir, base: str) -> Path:
    run_dir = Path(run_dir)
    path = run_dir / "wt" / "merge"
    gitops.worktree_add(repo_root_of(run_dir), path, gitops.finished_branch(run_dir.name), base)
    if gitops.merge_in_progress(path):
        gitops.merge_abort(path)
    return path


def _baseline(run_dir, goal, cwd: Path):
    """The tests at the merge worktree's HEAD before this merge, in a
    throwaway detached worktree."""
    repo = repo_root_of(run_dir)
    path = Path(run_dir) / "wt" / "baseline"
    gitops.worktree_remove(repo, path)
    gitops.check(["worktree", "add", "--detach", str(path), gitops.head(cwd)], repo)
    try:
        return run_tests(run_dir, goal, path)
    finally:
        gitops.worktree_remove(repo, path)


def _resolve(run_dir, goal, lane, cwd: Path, judge: Callable, attempt: int, state: dict) -> bool:
    """Judge every conflicted file of the merge in progress; True when the
    applied answers keep the tests whole. Each file is one `conflicts` row."""
    rows, applied = [], True
    for rel in gitops.conflicted_files(cwd):
        path = cwd / rel
        text = path.read_text(encoding="utf-8")
        hunks = extract_hunks(text)
        answer = _judge_answer(judge(hunks, with_evidence(goal, run_dir, lane.n, rel), rel))  # 3.1.8.0 R3
        texts = parse_resolution(answer["text"], len(hunks))
        row = {"lane": lane.n, "file": rel, "attempt": attempt, "hunks": hunks,
               "judge_session": answer["session_id"] or f"judge-{lane.n}-{attempt}-{len(state['conflicts']) + 1}",
               "fresh": answer["messages_before"] == 0, "messages_before": answer["messages_before"],
               "resolution": answer["text"], "applied_by": "code", "applied": texts is not None,
               "tests_ok": False, "tests_tail": "", "cost_usd": answer["cost_usd"]}
        if texts is None:
            applied = False
            row["tests_tail"] = f"the judge's answer did not give one replacement per hunk ({len(hunks)})"
        else:
            path.write_text(apply_resolution(text, texts), encoding="utf-8", newline="")
            gitops.check(["add", "--", rel], cwd)
        rows.append(row)
    ok = applied and bool(rows)
    if ok:
        after = run_tests(run_dir, goal, cwd)
        ok = after.ok or after.no_worse_than(_baseline(run_dir, goal, cwd))
        for row in rows:
            row["tests_ok"], row["tests_tail"] = ok, after.tail
        if ok:  # 3.1.8.0 R4: a conflict resolved with evidence is a finding (knowledge/writers.py)
            from halo_harness.knowledge.writers import judge_resolved
            judge_resolved(run_dir, lane.n, rows, after)
    for row in rows:
        ts = time.time()
        row.update(ts=round(ts, 3), elapsed_s=jsonl.elapsed(run_dir, ts))
        state["conflicts"].append(row)
    return ok


def merge_lanes(run_dir, goal, lanes: list, *, judge: Callable, base: str,
                respawn: Optional[Callable] = None, on_return: Optional[Callable] = None,
                on_merged: Optional[Callable] = None, clock: Callable = time.time) -> MergeResult:
    """Merge every lane not yet merged, in code's order. Raises StopRun."""
    run_dir = Path(run_dir)
    branch = gitops.finished_branch(run_dir.name)
    cwd = merge_worktree(run_dir, base)
    state = load_merge(run_dir)
    by_n = {lane.n: lane for lane in lanes}
    order = [n for n in (state.get("order") or []) if n in by_n] or merge_order(run_dir, lanes, base)
    state.update(branch=branch, base=base, order=order, finished=None)
    state.setdefault("merged", [])
    state.setdefault("conflicts", [])

    def save() -> None:
        jsonl.write_json(merge_path(run_dir), state)

    save()
    for n in order:
        lane = by_n[n]
        if lane.data().get("stale"):  # 3.1.2.0 R2 (orchestra/stale.py): never merged stale
            raise StopRun(f"lane {n} is stale ({lane.data()['stale'].get('reason')}): it is re-based before it merges")
        if lane.state == "merged" and n in state["merged"] and gitops.is_ancestor(cwd, lane.branch, "HEAD"):
            continue
        attempt = 0
        while True:
            attempt += 1
            lane.set_state("in_review", f"merging {lane.branch}", clock=clock)
            result = gitops.merge_no_ff(cwd, lane.branch, f"orchestra: merge worker {n} ({lane.job.title})")
            if result.returncode == 0:
                break
            if not gitops.conflicted_files(cwd):
                gitops.merge_abort(cwd)
                why = (result.stderr or result.stdout or "").strip().splitlines()
                raise StopRun(f"git could not merge lane {n}: {why[-1] if why else 'no output'}")
            run_events.log(run_dir, "merge", f"lane {n}: conflict, asking a fresh judge", lane=n,
                           files=gitops.conflicted_files(cwd))
            ok = _resolve(run_dir, goal, lane, cwd, judge, attempt, state)
            save()
            if ok:
                gitops.commit_merge(cwd)
                run_events.log(run_dir, "merge", f"lane {n}: the judge's answer applied by code, tests ok", lane=n)
                break
            gitops.merge_abort(cwd)
            tail = state["conflicts"][-1]["tests_tail"] if state["conflicts"] else ""
            run_events.log(run_dir, "merge", f"lane {n}: the judge's answer failed the tests", lane=n)
            if respawn is None or lane.pieces_returned >= goal.return_cap:
                lane.set_state("failed", "merge failed at the return cap", clock=clock)
                raise StopRun(f"lane {n}'s piece failed the tests after the merge and reached the return cap "
                              f"({goal.return_cap}): {tail.splitlines()[-1] if tail else 'no output'}")
            send_back(lane, lambda k: f"piece sent back ({k}/{goal.return_cap})", clock=clock)
            if on_return is not None:
                on_return(lane)
            respawn(lane, f"Merging your branch into {branch} conflicted and the resolution failed the tests:\n"
                          f"{tail}\nMerge {branch} into your worktree, keep both changes, and make the tests pass.")
            if lane.state == "failed":
                raise StopRun(f"lane {n}'s worker failed after its piece was sent back: {lane.data().get('error')}")
        if n not in state["merged"]:
            state["merged"].append(n)
        save()
        lane.set_state("merged", f"merged into {branch}", clock=clock)
        run_events.log(run_dir, "merge", f"lane {n} merged into {branch}", lane=n, branch=branch)
        if on_merged is not None:
            on_merged(lane)
    state["finished"] = gitops.head(cwd)
    save()
    return MergeResult(branch, order, list(state["merged"]), list(state["conflicts"]), state["finished"])

