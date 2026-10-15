"""halo_harness.fleet.mission_merge -- a mission's repo parts merged one at a
time, and its other outputs checked (Halo 3.0.6.0 "Fleet Missions" round R7).

For each repo part that finished with changes, in the plan's `merge_order`:
its branch `mission/<id>/<part>` is in the hub's repo already (a part that
ran here) or is fetched from the bundle its harness pushed
(`parts/<n>/branch.bundle`); it is merged with `git merge --no-ff` into
`mission/<id>/merged` (made from the mission's base in its own worktree
`<repo>/.halo/missions/<id>/merged`). A conflict goes to a fresh judge the
way Orchestra's merge does (orchestra/hunks.py: the goal and the hunks only,
its answer applied by code); with a `test` command the tests run after each
judged merge and a failing one undoes it and fails the mission with the
reason. Files parts' outputs are already in `artifacts/<n>/`; a declared
output that is missing is listed.

    merge(home, doc, plan, judge) -> {ok, branch, order, merged: [ids], skipped: [{part, why}],
                                      conflicts: [{part, file, hunks, applied, tests_ok, judge_session, cost_usd}],
                                      finished: sha | null, missing_outputs: [paths], error: str | null}
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from halo_harness.fleet import mission_store as S
from halo_harness.orchestra import gitops
from halo_harness.orchestra.gate import run_tests
from halo_harness.orchestra.hunks import apply_resolution, extract_hunks, parse_resolution


class _Goal:
    def __init__(self, doc: dict) -> None:
        self.what = str(doc.get("goal") or "")
        self.done_when = str(doc.get("constraints") or "every part of the mission is merged")
        self.test = str(doc.get("test") or "")
        self.test_timeout_s = 600


def make_judge(cwd) -> Callable:
    from halo_harness.orchestra.adapters import fresh_judge
    return fresh_judge(None, "main", cwd=cwd)


def _answer(raw) -> dict:
    if isinstance(raw, dict):
        return {"text": str(raw.get("text") or ""), "session_id": raw.get("session_id"),
                "cost_usd": float(raw.get("cost_usd") or 0.0)}
    return {"text": str(raw or ""), "session_id": None, "cost_usd": 0.0}


def _fetch(repo: Path, folder: Path, pid: str, branch: str) -> Optional[str]:
    """None when the branch is here; else the reason it could not be fetched."""
    bundle = folder / "parts" / pid / "branch.bundle"
    if bundle.is_file():
        got = gitops.git(["fetch", "--force", str(bundle), f"{branch}:{branch}"], repo)
        return None if got.returncode == 0 else f"the bundle of part {pid} did not fetch: {(got.stderr or '').strip()[-200:]}"
    return None if gitops.branch_exists(repo, branch) else f"part {pid}'s branch {branch} is not here and no bundle came"


def _judge(cwd: Path, goal: _Goal, pid: str, judge: Callable, rows: list) -> bool:
    applied = True
    for rel in gitops.conflicted_files(cwd):
        path = cwd / rel
        text = path.read_text(encoding="utf-8")
        hunks = extract_hunks(text)
        ans = _answer(judge(hunks, goal, rel))
        texts = parse_resolution(ans["text"], len(hunks))
        rows.append({"part": pid, "file": rel, "hunks": len(hunks), "applied": texts is not None, "tests_ok": None,
                     "judge_session": ans["session_id"], "cost_usd": ans["cost_usd"]})
        if texts is None:
            applied = False
            continue
        path.write_text(apply_resolution(text, texts), encoding="utf-8", newline="")
        gitops.check(["add", "--", rel], cwd)
    return applied


def merge(home, doc: dict, plan: dict, judge: Optional[Callable] = None) -> dict:
    mid = doc["id"]
    folder = S.folder(home, mid)
    states = doc.get("parts") or {}
    by_id = {p["id"]: p for p in plan.get("parts") or []}
    out = {"ok": True, "branch": None, "order": list(plan.get("merge_order") or []), "merged": [], "skipped": [],
           "conflicts": [], "finished": None, "missing_outputs": [], "error": None}
    for p in by_id.values():
        if p.get("kind") != "repo":
            out["missing_outputs"] += [o for o in p.get("outputs") or [] if not (folder / o).is_file()]
    todo = [pid for pid in out["order"] if (states.get(pid) or {}).get("state") == "done" and by_id.get(pid)]
    for pid in [x for x in out["order"] if x not in todo]:
        out["skipped"].append({"part": pid, "why": f"part {pid} is {(states.get(pid) or {}).get('state')}"})
    repo_root = S.local(home, mid).get("repo_root")
    if not todo:
        return out
    if not repo_root or not doc.get("repo"):
        return {**out, "ok": False, "error": "the mission has repo parts but no repo on this hub"}
    repo, base = Path(repo_root), str(doc["repo"].get("base") or "")
    branch = out["branch"] = f"mission/{mid}/merged"
    cwd = gitops.worktree_add(repo, repo / ".halo" / "missions" / mid / "merged", branch, base)
    if gitops.merge_in_progress(cwd):
        gitops.merge_abort(cwd)
    goal = _Goal(doc)
    judge = judge or make_judge(folder)
    for pid in todo:
        part_branch = f"mission/{mid}/{pid}"
        if not (states.get(pid) or {}).get("files"):
            out["skipped"].append({"part": pid, "why": "it changed no file"})
            continue
        why = _fetch(repo, folder, pid, part_branch)
        if why:
            return {**out, "ok": False, "error": why}
        if gitops.is_ancestor(cwd, part_branch, "HEAD"):
            out["merged"].append(pid)
            continue
        got = gitops.merge_no_ff(cwd, part_branch, f"mission {mid}: merge part {pid} ({by_id[pid].get('title')})")
        if got.returncode != 0:
            if not gitops.conflicted_files(cwd):
                gitops.merge_abort(cwd)
                return {**out, "ok": False, "error": f"git could not merge part {pid}: {(got.stderr or got.stdout).strip()[-200:]}"}
            ok = _judge(cwd, goal, pid, judge, out["conflicts"])
            tests = run_tests(folder, goal, cwd) if ok else None
            for row in out["conflicts"]:
                if row["part"] == pid:
                    row["tests_ok"] = bool(tests and tests.ok)
            if not ok or not tests.ok:
                gitops.merge_abort(cwd)
                why = "the judge's answer did not fit the hunks" if not ok else f"the tests fail: {tests.tail.splitlines()[-1] if tests.tail else ''}"
                return {**out, "ok": False, "error": f"part {pid} conflicted and {why}"}
            gitops.commit_merge(cwd)
        out["merged"].append(pid)
        S.log(home, mid, "merged", part=pid, branch=branch)
    out["finished"] = gitops.head(cwd)
    gitops.worktree_remove(repo, cwd)
    return out
