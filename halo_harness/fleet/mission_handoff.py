"""halo_harness.fleet.mission_handoff -- what a mission part hands on and
where a sequenced part starts (Halo 3.0.9.0 round R1).

Hand-off vocabulary. A part's `outputs` are what it hands on: a part that
depends on it reads, from the mission folder, exactly those outputs plus
the dependency's `parts/<d>/handback.md`; a part with `take: all` reads the
dependency's whole `artifacts/<d>/**` instead (mission_files.readable).

The base rule. A repo part with `depends_on` (declared, or added by
mission_plan_check.sequence) starts from its repo dependencies' finished
work, not the mission's base: one dependency that changed files = its
branch head (the hub fetches it from `parts/<d>/branch.bundle` when it ran
on a member); two or more = their merge, made by the hub in
`<repo>/.halo/missions/<id>/<n>-base` on branch `mission/<id>/<n>-base`, a
conflict going to a fresh judge as the mission's merge does (its answer
applied by code, the mission's tests after it); a failure fails the part
with the reason. A member gets that commit as `parts/<n>/base.bundle`. The
part's `base` lands in its state, its result.json and the report.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from halo_harness.fleet import mission_store as S
from halo_harness.orchestra import gitops

TAKES = ("outputs", "all")


def take_of(part: dict) -> str:
    return "all" if str((part or {}).get("take") or "").strip().lower() == "all" else "outputs"


def dep_paths(plan: dict, part: dict) -> list:
    """The mission-folder paths (and globs) `part` reads from its dependencies."""
    by_id = {p["id"]: p for p in (plan or {}).get("parts") or []}
    out = []
    for d in part.get("depends_on") or []:
        dep = by_id.get(d) or {}
        out.append(f"parts/{d}/handback.md")
        if take_of(part) == "all":
            out.append(f"artifacts/{d}/**")
        else:
            out += [o for o in dep.get("outputs") or [] if o.startswith(f"artifacts/{d}/")]
    return list(dict.fromkeys(out))


def edge_label(plan: dict, part: dict, dep: str) -> str:
    """What the edge dep -> part carries: `all`, the dependency's outputs, or its hand-back."""
    if take_of(part) == "all":
        return "all"
    d = next((p for p in (plan or {}).get("parts") or [] if p["id"] == dep), {})
    names = [o.split("/")[-1] for o in d.get("outputs") or []]
    return ", ".join(names) if names else "hand-back"


def _goal(doc: dict):
    from halo_harness.fleet.mission_merge import _Goal
    return _Goal(doc)


def merge_into(cwd: Path, folder: Path, doc: dict, pid: str, heads: list, judge: Optional[Callable]) -> str:
    """Merge `heads[1:]` into the worktree `cwd` (at heads[0]); "" or the reason it failed."""
    from halo_harness.fleet.mission_merge import _judge, make_judge
    from halo_harness.orchestra.gate import run_tests
    goal, rows, mid = _goal(doc), [], doc["id"]
    for sha in heads[1:]:
        got = gitops.merge_no_ff(cwd, sha, f"mission {mid}: the start of part {pid} (merge {sha[:12]})")
        if got.returncode == 0:
            continue
        if not gitops.conflicted_files(cwd):
            gitops.merge_abort(cwd)
            return f"git could not merge its dependencies: {(got.stderr or got.stdout).strip()[-200:]}"
        judge = judge or make_judge(folder)
        ok = _judge(cwd, goal, pid, judge, rows)
        tests = run_tests(folder, goal, cwd) if ok else None
        if not ok or not tests.ok:
            gitops.merge_abort(cwd)
            why = "the judge's answer did not fit the hunks" if not ok else f"the tests fail: {tests.tail.splitlines()[-1] if tests.tail else ''}"
            return f"part {pid}'s dependencies conflicted and {why}"
        gitops.commit_merge(cwd)
    return ""


def start_base(home, doc: dict, plan: dict, part: dict, judge: Optional[Callable] = None) -> "tuple[Optional[str], str]":
    """`(base, "")` the commit a repo part starts from, or `(None, reason)`."""
    from halo_harness.fleet.mission_merge import _fetch
    mid, repo_doc = doc["id"], doc.get("repo") or {}
    mission_base = repo_doc.get("base")
    if part.get("kind") != "repo":
        return None, ""
    by_id = {p["id"]: p for p in plan.get("parts") or []}
    states = doc.get("parts") or {}
    deps = [d for d in part.get("depends_on") or [] if (by_id.get(d) or {}).get("kind") == "repo"
            and (states.get(d) or {}).get("state") == "done" and (states.get(d) or {}).get("files")]
    root = S.local(home, mid).get("repo_root")
    if not deps or not root:
        return mission_base, ""
    repo, folder = Path(root), S.folder(home, mid)
    for d in deps:
        why = _fetch(repo, folder, d, f"mission/{mid}/{d}")
        if why:
            return None, why
    heads = []
    for d in sorted(deps, key=lambda x: -float((states.get(x) or {}).get("ended") or 0)):  # the last finished first
        sha = gitops.head(repo, f"mission/{mid}/{d}")
        if sha not in heads:
            heads.append(sha)
    heads = [h for h in heads if not any(o != h and gitops.is_ancestor(repo, h, o) for o in heads)]
    branch = f"mission/{mid}/{part['id']}-base"
    if len(heads) == 1:
        gitops.check(["branch", "-f", branch, heads[0]], repo)
        return heads[0], ""
    cwd = repo / ".halo" / "missions" / mid / f"{part['id']}-base"
    gitops.worktree_remove(repo, cwd)
    gitops.check(["branch", "-f", branch, heads[0]], repo)
    gitops.worktree_add(repo, cwd, branch, heads[0])
    try:
        why = merge_into(cwd, folder, doc, part["id"], heads, judge)
        return (None, why) if why else (gitops.head(cwd), "")
    finally:
        gitops.worktree_remove(repo, cwd)


def base_bundle(home, doc: dict, part: dict, base: str) -> bool:
    """`parts/<n>/base.bundle` for a member: the commits from the mission's base to the part's start."""
    mid = doc["id"]
    root = S.local(home, mid).get("repo_root")
    mission_base = (doc.get("repo") or {}).get("base")
    if not root or not base or base == mission_base:
        return False
    target = S.folder(home, mid) / "parts" / str(part["id"]) / "base.bundle"
    target.parent.mkdir(parents=True, exist_ok=True)
    span = f"{mission_base}..mission/{mid}/{part['id']}-base" if mission_base else f"mission/{mid}/{part['id']}-base"
    return gitops.git(["bundle", "create", str(target), span], Path(root)).returncode == 0


def fetch_base(checkout: Path, folder: Path, mid: str, pid: str) -> bool:
    """The member's side: the base commit from `parts/<n>/base.bundle` into its checkout."""
    bundle = Path(folder) / "parts" / str(pid) / "base.bundle"
    if not bundle.is_file():
        return False
    ref = f"mission/{mid}/{pid}-base"
    return gitops.git(["fetch", "--force", str(bundle), f"{ref}:{ref}"], checkout).returncode == 0
