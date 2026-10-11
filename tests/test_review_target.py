"""tests.test_review_target -- Halo 2.0.10 round 1: `/review` target resolution
(halo_harness/review/target.py) against scratch git repos, plus the per-file
split and shards in target_model.py. The PR form runs against a fake `gh` on
PATH. Never touches this repo's own history.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.review_mock import fake_gh as _fake_gh

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return r.stdout


def _write(cwd: Path, name: str, text: str) -> None:
    p = cwd / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _repo() -> Path:
    """main with a.py; branch `feature` with a changed a.py and a new b.py committed."""
    d = Path(tempfile.mkdtemp(prefix="rv-target-"))
    _git(d, "init", "-q", "-b", "main")
    _git(d, "config", "user.email", "test@example.invalid")
    _git(d, "config", "user.name", "Test")
    _git(d, "config", "commit.gpgsign", "false")
    _write(d, "a.py", "def add(a, b):\n    return a + b\n")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "base")
    _git(d, "checkout", "-q", "-b", "feature")
    _write(d, "a.py", "def add(a, b):\n    return a - b\n")
    _write(d, "b.py", "VALUE = 1\n")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "feature work")
    return d


def _resolve(tokens, cwd):
    from halo_harness.review.target import resolve_target
    return resolve_target(tokens, cwd)


@test
def test_default_target_is_branch_against_merge_base(ctx: Ctx):
    d = _repo()
    t = _resolve([], d)
    ctx.check(f"kind branch, got {t.kind}", t.kind == "branch")
    ctx.check(f"label names both branches, got {t.label!r}", "feature vs main" in t.label)
    ctx.check(f"files are a.py and b.py, got {t.files}", sorted(t.files) == ["a.py", "b.py"])
    ctx.check("diff holds the changed line", "-    return a + b" in t.diff_text and "+    return a - b" in t.diff_text)
    ctx.check(f"head is the branch, got {t.head!r}", t.head == "feature")


@test
def test_default_target_adds_dirty_and_untracked_files(ctx: Ctx):
    d = _repo()
    _write(d, "b.py", "VALUE = 2\n")            # tracked edit, uncommitted
    _write(d, "c.py", "NEW = True\n")           # untracked
    t = _resolve([], d)
    ctx.check(f"all three files listed, got {t.files}", sorted(t.files) == ["a.py", "b.py", "c.py"])
    ctx.check("working-tree edit is in the diff", "+VALUE = 2" in t.diff_text)
    ctx.check("untracked file shows as a new file", "+++ b/c.py" in t.diff_text and "+NEW = True" in t.diff_text)


@test
def test_default_target_on_the_default_branch(ctx: Ctx):
    from halo_harness.review.target import TargetError
    d = _repo()
    _git(d, "checkout", "-q", "main")
    try:
        _resolve([], d)
        ctx.check("clean default branch raises", False)
    except TargetError as e:
        ctx.check(f"message says nothing to review, got {e}", "nothing to review" in str(e))
    _write(d, "a.py", "def add(a, b):\n    return b + a\n")
    t = _resolve([], d)
    ctx.check(f"dirty default branch reviews the working tree, got {t.kind}", t.kind == "worktree")
    ctx.check("diff holds the edit", "+    return b + a" in t.diff_text and t.files == ["a.py"])


@test
def test_range_form(ctx: Ctx):
    d = _repo()
    t = _resolve(["main..feature"], d)
    ctx.check(f"kind range, got {t.kind}", t.kind == "range")
    ctx.check(f"base/head parsed, got {t.base!r}/{t.head!r}", (t.base, t.head) == ("main", "feature"))
    ctx.check(f"files, got {t.files}", sorted(t.files) == ["a.py", "b.py"])
    t2 = _resolve(["HEAD~1..HEAD"], d)
    ctx.check("HEAD~1..HEAD works too", sorted(t2.files) == ["a.py", "b.py"])
    from halo_harness.review.target import TargetError
    try:
        _resolve(["main..nope"], d)
        ctx.check("unknown revision raises", False)
    except TargetError as e:
        ctx.check(f"error names the revision, got {e}", "nope" in str(e))


@test
def test_branch_name_form(ctx: Ctx):
    d = _repo()
    _git(d, "checkout", "-q", "main")
    t = _resolve(["feature"], d)
    ctx.check(f"kind branch, got {t.kind}", t.kind == "branch")
    ctx.check(f"label, got {t.label!r}", t.label.startswith("feature vs main"))
    ctx.check(f"files, got {t.files}", sorted(t.files) == ["a.py", "b.py"])
    ctx.check("main's own working tree is not part of it", "return a - b" in t.diff_text)


@test
def test_paths_and_globs_are_reviewed_as_they_are(ctx: Ctx):
    d = _repo()
    _write(d, "pkg/m.py", "x = 1\ny = 2\n")
    _write(d, "pkg/n.txt", "hello\n")
    t = _resolve(["pkg/m.py"], d)
    ctx.check(f"kind paths, got {t.kind}", t.kind == "paths")
    ctx.check(f"one file, got {t.files}", t.files == ["pkg/m.py"])
    ctx.check("lines are numbered, no diff markers", "    2| y = 2" in t.diff_text and "diff --git" not in t.diff_text)
    g = _resolve(["pkg/*.py"], d)
    ctx.check(f"glob matches the .py only, got {g.files}", g.files == ["pkg/m.py"])
    dd = _resolve(["pkg"], d)
    ctx.check(f"a directory expands to its files, got {dd.files}", dd.files == ["pkg/m.py", "pkg/n.txt"])
    many = _resolve(["pkg/m.py", "a.py"], d)
    ctx.check(f"several tokens are all paths, got {many.files}", many.files == ["pkg/m.py", "a.py"])
    ctx.check("per-file chunks", set(many.file_diffs()) == {"pkg/m.py", "a.py"})


@test
def test_paths_work_outside_a_git_repo(ctx: Ctx):
    d = Path(tempfile.mkdtemp(prefix="rv-nogit-"))
    _write(d, "script.sh", "echo hi\n")
    t = _resolve(["script.sh"], d)
    ctx.check(f"reviewed as-is, got {t.kind} {t.files}", t.kind == "paths" and t.files == ["script.sh"])
    from halo_harness.review.target import TargetError
    try:
        _resolve([], d)
        ctx.check("no target outside a repo raises", False)
    except TargetError as e:
        ctx.check(f"says it is not a repo, got {e}", "not inside a git repository" in str(e))


@test
def test_unknown_target_is_a_clean_error(ctx: Ctx):
    from halo_harness.review.target import TargetError
    d = _repo()
    try:
        _resolve(["no-such-thing"], d)
        ctx.check("raises", False)
    except TargetError as e:
        ctx.check(f"message names the token, got {e}", "no-such-thing" in str(e))


_PR_DIFF = ("diff --git a/lib/util.py b/lib/util.py\n--- a/lib/util.py\n+++ b/lib/util.py\n@@ -1,2 +1,2 @@\n"
            " def f():\n-    return 1\n+    return 2\n")
_PR_META = ('{"number": 7, "title": "Fix f", "headRefName": "fix-f", "baseRefName": "main", '
            '"files": [{"path": "lib/util.py", "additions": 1, "deletions": 1}], "url": "https://example.invalid/pr/7"}')


@test
def test_pr_form_uses_gh(ctx: Ctx):
    d = _repo()
    gh_dir = _fake_gh(_PR_DIFF, _PR_META)
    old = os.environ.get("PATH", "")
    os.environ["PATH"] = str(gh_dir) + os.pathsep + old
    try:
        for token in ("#7", "7"):
            t = _resolve([token], d)
            ctx.check(f"{token}: kind pr, got {t.kind}", t.kind == "pr")
            ctx.check(f"{token}: label has number and title, got {t.label!r}", t.label == "PR #7: Fix f")
            ctx.check(f"{token}: files from the JSON, got {t.files}", t.files == ["lib/util.py"])
            ctx.check(f"{token}: base/head, got {t.base!r}/{t.head!r}", (t.base, t.head) == ("main", "fix-f"))
            ctx.check(f"{token}: diff text from gh pr diff", "+    return 2" in t.diff_text)
        calls = (gh_dir / "calls.txt").read_text(encoding="utf-8")
        ctx.check(f"gh was asked for the diff and the view, got {calls!r}",
                  "pr diff 7" in calls and "pr view 7 --json" in calls)
    finally:
        os.environ["PATH"] = old


@test
def test_pr_form_without_gh_is_a_clean_error(ctx: Ctx):
    from halo_harness.review.target import TargetError
    d = _repo()
    empty = tempfile.mkdtemp(prefix="rv-nopath-")
    old = os.environ.get("PATH", "")
    os.environ["PATH"] = empty
    try:
        try:
            _resolve(["#9"], d)
            ctx.check("raises", False)
        except TargetError as e:
            ctx.check(f"names gh, got {e}", "gh" in str(e))
    finally:
        os.environ["PATH"] = old


@test
def test_diff_is_split_per_file_and_sharded(ctx: Ctx):
    from halo_harness.review.target_model import ReviewTarget
    parts = []
    for i in range(5):
        parts.append(f"diff --git a/f{i}.py b/f{i}.py\n--- a/f{i}.py\n+++ b/f{i}.py\n@@ -1 +1 @@\n-old{i}\n+new{i}\n"
                     + "".join(f"+pad{j}\n" for j in range(40)))
    t = ReviewTarget("range", "x", "".join(parts), [f"f{i}.py" for i in range(5)])
    per = t.file_diffs()
    ctx.check(f"five files, in order, got {list(per)}", list(per) == [f"f{i}.py" for i in range(5)])
    ctx.check("each slice holds only its own change", "new2" in per["f2.py"] and "new3" not in per["f2.py"])
    size = len(per["f0.py"])
    shards = t.shards(max_chars=size * 2 + 10)
    ctx.check(f"packed into 3 shards, got {[s.files for s in shards]}", [len(s.files) for s in shards] == [2, 2, 1])
    ctx.check("shards know their place", [(s.index, s.total) for s in shards] == [(1, 3), (2, 3), (3, 3)])
    capped = t.shards(max_chars=size + 10, max_shards=2)
    ctx.check(f"max_shards keeps 2, got {len(capped)}", len(capped) == 2)
    ctx.check(f"the rest is listed by name, got {capped[-1].omitted}", capped[-1].omitted == ["f2.py", "f3.py", "f4.py"])
    big = ReviewTarget("range", "x", "diff --git a/big.py b/big.py\n" + "+x\n" * 5000, ["big.py"])
    one = big.shards(max_chars=1000)
    ctx.check("one oversized file is truncated with a note",
              len(one) == 1 and len(one[0].text) < 1200 and "truncated" in one[0].text)
    ctx.check("excerpt is capped", len(big.excerpt_for("big.py", limit=200)) < 300)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
