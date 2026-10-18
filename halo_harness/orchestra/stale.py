"""halo_harness.orchestra.stale -- a downstream lane is never merged stale
(Halo 3.1.2.0 R2, docs/ORCHESTRA.md "Stale lanes"; the 3.0.9.0 open item).

A lane that starts after another (`after` / a hand-off) starts from that
lane's head. When the gate sends the upstream's piece back (the tests fail
on the finished branch, or its merge failed the tests), the upstream is
written again and the downstream's start is out of date:

1. `sent_back(upstream)`: every lane whose `base` holds the upstream's head
   (it started from it, directly or through another lane) is marked
   `stale` in its lane file -- `{"upstreams": [n], "jobs": ["job-1"],
   "reason": "upstream job-1 was sent back", "ts"}` -- and moved to
   `waiting` with that reason; its worker step in workflow.json goes back
   to pending.
2. `rewritten(upstream, respawn)`: once every upstream it is stale on is
   written again, the lane is re-based: each upstream's branch is merged
   into its worktree and its tests run there (no worse than at the
   upstream's new head). Clean: the lane is `written` again with
   `rebased: {onto: [{lane, head}], head, tests_ok, ts}` and the `stale`
   flag cleared ("lane 2 re-based onto lane 1's new head <sha>"). A
   conflict (the markers stay in the files) or worse tests return the
   piece to the lane's own worker with the retry text (one more attempt,
   `return_cap` counts it); its next pass is the re-base.

`merge.merge_lanes` refuses a lane whose `stale` flag is still set. A run
with no lane after another never marks anything.
"""

from __future__ import annotations

import time
from typing import Callable

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import gitops, jsonl
from halo_harness.orchestra import workflow as wf
from halo_harness.orchestra.split import StopRun

WRITTEN = ("written", "in_review", "merged")


class StaleLanes:
    """The run's stale lanes; `lanes_of()` answers the run's lanes as they are now."""

    def __init__(self, run_dir, goal, lanes_of: Callable[[], list], flow, clock: Callable = time.time):
        self.run_dir, self.goal, self.lanes_of, self.flow, self.clock = run_dir, goal, lanes_of, flow, clock

    def _repo(self):
        from halo_harness.orchestra.goal import repo_root_of
        return repo_root_of(self.run_dir)

    def _step_back(self, n: int, text: str) -> None:
        with self.flow.lock:
            jsonl.write_json(self.flow.path, wf.loop_back(self.flow.graph(), n))
            run_events.log(self.run_dir, "state", text, lane=n, step=wf.worker_id(n), state="pending")
            self.flow.pump()

    def sent_back(self, upstream) -> list:
        """Mark every lane that started from `upstream`'s head stale; the lanes marked."""
        head = str(upstream.data().get("head") or "")
        if not head:
            return []
        repo, marked = self._repo(), []
        for lane in self.lanes_of() or []:
            base = str(lane.data().get("base") or "")
            if lane.n == upstream.n or not base or lane.state in ("", "pending", "failed"):
                continue
            if not gitops.is_ancestor(repo, head, base):
                continue
            old = lane.data().get("stale") or {}
            ups = list(dict.fromkeys(list(old.get("upstreams") or []) + [upstream.n]))
            jobs = list(dict.fromkeys(list(old.get("jobs") or []) + [upstream.job.id]))
            reason = f"upstream {' and '.join(jobs)} was sent back"
            lane.update(stale={"upstreams": ups, "jobs": jobs, "reason": reason, "ts": round(self.clock(), 3)})
            lane.set_state("waiting", f"stale: {reason}; it is re-based once {'they are' if len(jobs) > 1 else 'it is'} "
                                      "written again", clock=self.clock)
            self._step_back(lane.n, f"lane {lane.n} is stale: {reason}")
            marked.append(lane)
        return marked

    def rewritten(self, upstream, respawn: Callable) -> None:
        """`upstream` was written again: re-base every stale lane whose upstreams are all written now."""
        if upstream.state not in WRITTEN:
            return
        by_n = {lane.n: lane for lane in self.lanes_of() or []}
        for lane in list(by_n.values()):
            stale = lane.data().get("stale") or {}
            ups = [by_n[u] for u in stale.get("upstreams") or [] if u in by_n]
            if not stale or upstream.n not in (stale.get("upstreams") or []):
                continue
            if any(u.state not in WRITTEN for u in ups):
                continue  # another upstream it is stale on is still out
            self.rebase(lane, ups, respawn)

    def _return(self, lane, ups: list, text: str, respawn: Callable, record: dict) -> None:
        from halo_harness.orchestra.gate import send_back
        cap = int(getattr(self.goal, "return_cap", 2))
        if lane.pieces_returned >= cap:
            if gitops.merge_in_progress(lane.worktree):
                gitops.merge_abort(lane.worktree)
            lane.update(ended=self.clock(), error=f"the re-base failed at the return cap ({cap})")
            lane.set_state("failed", f"re-base failed at the return cap ({cap})", clock=self.clock)
            raise StopRun(f"lane {lane.n} could not be re-based onto {self._onto(ups)} and reached the return cap ({cap})")
        send_back(lane, lambda k: f"re-base sent back to its worker ({k}/{cap})", clock=self.clock)
        lane.update(stale=None, rebased=record)
        respawn(lane, text)
        if lane.state == "failed":
            raise StopRun(f"lane {lane.n}'s worker failed after its re-base was sent back: {lane.data().get('error')}")

    @staticmethod
    def _onto(ups: list) -> str:
        return " and ".join(f"lane {u.n}'s new head" for u in ups)

    def rebase(self, lane, ups: list, respawn: Callable) -> None:
        from halo_harness.orchestra.gate import run_tests
        onto = [{"lane": u.n, "job": u.job.id, "head": str(u.data().get("head") or "")} for u in ups]
        lane.set_state("writing", f"re-basing onto {self._onto(ups)}", clock=self.clock)
        self.flow.set(wf.worker_id(lane.n), "running", f"re-basing onto {self._onto(ups)}")
        for u in ups:
            got = gitops.merge_no_ff(lane.worktree, u.branch, f"orchestra: re-base lane {lane.n} onto lane {u.n}'s new head")
            if got.returncode == 0:
                continue
            files = gitops.conflicted_files(lane.worktree)
            if not files:
                gitops.merge_abort(lane.worktree)
            why = f"conflict in {', '.join(files)}" if files else ((got.stderr or got.stdout or "").strip().splitlines() or ["git said nothing"])[-1]
            run_events.log(self.run_dir, "state", f"lane {lane.n}: re-base onto lane {u.n}'s new head: {why}; the piece goes "
                           "back to its worker", lane=lane.n, step=wf.worker_id(lane.n), rebase="conflict", files=files)
            text = (f"Lane {u.n} ({u.job.id}) was sent back and written again, and your lane started from its old head. "
                    + (f"Merging its new head into your worktree conflicted in {', '.join(files)}: the conflict markers "
                       "are in those files. Resolve them keeping both changes; the run commits the merge when you finish."
                       if files else f"Merging its branch {u.branch} into your worktree failed ({why}): merge it, keep "
                       "both changes, and finish your job."))
            return self._return(lane, ups, text, respawn, {"onto": onto, "conflict": files, "ts": round(self.clock(), 3)})
        head = gitops.head(lane.worktree)
        tests = run_tests(self.run_dir, self.goal, lane.worktree)
        ok = tests.ok or tests.no_worse_than(self._baseline(onto[-1]["head"]))
        record = {"onto": onto, "head": head, "tests_ok": ok, "ts": round(self.clock(), 3)}
        if not ok:
            text = (f"Your lane was re-based onto {self._onto(ups)} and its tests got worse there:\n{tests.tail}\n"
                    "Fix your piece so the tests pass with the new upstream.")
            return self._return(lane, ups, text, respawn, record)
        lane.update(head=head, stale=None, rebased=record)
        line = f"re-based onto {self._onto(ups)} {onto[-1]['head'][:12]}; tests {'ok' if tests.ok else 'no worse'}"
        lane.set_state("written", line, clock=self.clock)
        run_events.log(self.run_dir, "state", f"lane {lane.n} {line}", lane=lane.n, step=wf.worker_id(lane.n),
                       rebase="ok", rebased=record)
        self.flow.set(wf.worker_id(lane.n), "done", "re-based")

    def _baseline(self, sha: str):
        """The tests at the upstream's new head, in a throwaway detached worktree."""
        from halo_harness.orchestra.gate import run_tests
        repo = self._repo()
        path = self.run_dir / "wt" / "rebase-baseline"
        gitops.worktree_remove(repo, path)
        gitops.check(["worktree", "add", "--detach", str(path), sha], repo)
        try:
            return run_tests(self.run_dir, self.goal, path)
        finally:
            gitops.worktree_remove(repo, path)
