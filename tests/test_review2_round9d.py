"""tests.test_review2_round9d -- pins for the vibes/review.md fix pass, round 9,
the print-mode session flags:

  * f76  `-p -c` / bare `-r` with no earlier session started a new one and
        exited 0; a `-r <path>.jsonl` from another project resumed empty
  * f82  `--fork-session --no-session-persistence` left the fork on disk
  * f83  `-w` created the worktree before validating the other flags
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

if "BRIDGE_TEST_HOME" not in os.environ:
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="r9d-home-")


# ---- f76 / f82 / f83: session flags in print mode -----------------------------------

def _git_project(fh) -> Path:
    proj = Path(fh["proj"])
    for cmd in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
        subprocess.run(["git"] + cmd, cwd=str(proj), check=True)
    (proj / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(proj), check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(proj), check=True)
    return proj


def _run_print(fh, mock, args: list):
    env = {k: v for k, v in os.environ.items() if not k.startswith("HALO_") and k != "BRIDGE_STATE_DIR"}
    env.update({"BRIDGE_TEST_HOME": str(fh["home"]), "BRIDGE_OPENROUTER_BASE_URL": mock.base_url,
                "OPENROUTER_API_KEY": "test-key", "PYTHONPATH": str(REPO_DIR)})
    return subprocess.run([sys.executable, "-m", "halo_harness", "-p"] + args + ["--model", "or:mock/model",
                          "--cwd", str(fh["proj"])], env=env, cwd=str(REPO_DIR), capture_output=True,
                          text=True, timeout=90)


def _worktrees(proj: Path) -> int:
    out = subprocess.run(["git", "worktree", "list"], cwd=str(proj), capture_output=True, text=True).stdout
    return len([l for l in out.splitlines() if l.strip()])


def _session_files(fh) -> list:
    saved = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
    try:
        from halo_harness.agent import sessions
        return sorted(p.name for p in sessions.sessions_dir(fh["proj"]).glob("*.jsonl"))
    finally:
        if saved is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved


@test
def test_f76_continue_or_bare_resume_without_a_session_is_an_error(ctx: Ctx):
    from tests.helpers.fake_home import build_fake_home
    from tests.helpers.mock_openai import MockUpstream
    fh, mock = build_fake_home(), MockUpstream().start()
    try:
        for flag in (["-c"], ["--resume"]):
            r = _run_print(fh, mock, ["hi"] + flag)
            ctx.check(f"{flag}: exit 2, got {r.returncode} stderr={r.stderr[-200:]!r}", r.returncode == 2)
            ctx.check(f"{flag}: the error names the flag", flag[0].lstrip("-")[:3] in r.stderr)
        ctx.check("no session was started", _session_files(fh) == [])
        ctx.check("the model was never called", not mock.requests)
    finally:
        mock.stop()


@test
def test_f76_resume_of_a_transcript_outside_the_project_imports_it(ctx: Ctx):
    from tests.helpers.fake_home import build_fake_home
    fh = build_fake_home()
    saved = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
    try:
        from halo_harness.agent import sessions
        elsewhere = Path(tempfile.mkdtemp(prefix="r9d-elsewhere-")) / "0123456789abcdef0123456789abcdef.jsonl"
        elsewhere.write_text('{"type": "user", "content": []}' + chr(10), encoding="utf-8")
        sid, err = sessions.resolve_resume(fh["proj"], str(elsewhere))
        ctx.check(f"it resolves, got {sid!r} {err!r}", sid == elsewhere.stem and err is None)
        landed = sessions.sessions_dir(fh["proj"]) / elsewhere.name
        ctx.check("the history now exists under this project, so the resume is not empty", landed.is_file())
        ctx.check("the original is untouched", elsewhere.is_file())
    finally:
        if saved is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved


@test
def test_f83_a_bad_flag_creates_no_worktree(ctx: Ctx):
    from tests.helpers.fake_home import build_fake_home
    from tests.helpers.mock_openai import MockUpstream
    fh, mock = build_fake_home(), MockUpstream().start()
    try:
        proj = _git_project(fh)
        for extra in (["--session-id", "not-a-uuid"], ["-c"]):
            r = _run_print(fh, mock, ["hi", "-w"] + extra)
            ctx.check(f"{extra}: exit 2, got {r.returncode} stderr={r.stderr[-160:]!r}", r.returncode == 2)
            ctx.check(f"{extra}: still one worktree, got {_worktrees(proj)}", _worktrees(proj) == 1)
    finally:
        mock.stop()


@test
def test_f82_fork_with_no_session_persistence_leaves_nothing_behind(ctx: Ctx):
    from tests.helpers.fake_home import build_fake_home
    from tests.helpers.mock_openai import MockUpstream
    fh, mock = build_fake_home(), MockUpstream().start()
    try:
        sid = "0123456789abcdef0123456789abcdef"
        r = _run_print(fh, mock, ["pong", "--session-id", sid])
        ctx.check(f"seed run ok, got {r.returncode} {r.stderr[-160:]!r}", r.returncode == 0)
        before = _session_files(fh)
        ctx.check(f"one seeded session, got {before}", before == [sid + ".jsonl"])
        r2 = _run_print(fh, mock, ["pong2", "-r", sid, "--fork-session", "--no-session-persistence"])
        ctx.check(f"fork run ok, got {r2.returncode} {r2.stderr[-160:]!r}", r2.returncode == 0)
        ctx.check(f"the fork was removed, only the original remains, got {_session_files(fh)}",
                  _session_files(fh) == before)
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
