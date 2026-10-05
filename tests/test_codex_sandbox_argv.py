"""tests.test_codex_sandbox_argv -- pass-B fix (review finding 3,
critical): `build_cx_argv` never emits `-s <mode>` after `exec resume
<id>` (the real `codex exec resume` has no `-s/--sandbox` option at all)
-- the sandbox rides on `-c sandbox_mode=<mode>` instead, on a fresh
`exec` AND a `resume` alike, since both subcommands accept it. The fake
codex (tests/helpers/fake_codex.py) now rejects an unexpected `-s` after
`resume` the exact way clap does, so this class of bug fails the suite
instead of passing silently.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

REPO_DIR = Path(__file__).resolve().parent.parent
FAKE_CODEX = REPO_DIR / "tests" / "helpers" / "fake_codex.py"


def _argv(*, resume_id=None):
    from halo_harness.agent.codex_process import build_cx_argv
    return build_cx_argv(model="astra", prompt="hi", resume_id=resume_id, permission_mode="default",
                          mcp_override_args=[], prompt_via_stdin=True)


@test
def test_fresh_exec_never_uses_bare_dash_s(ctx: Ctx):
    argv = _argv()
    ctx.check(f"no bare -s token anywhere in a fresh exec argv, got {argv!r}", "-s" not in argv)
    ctx.check(f"sandbox passed as -c sandbox_mode=..., got {argv!r}", "sandbox_mode=workspace-write" in argv)
    ctx.check("approval policy still its own -c entry", "approval_policy=on-request" in argv)


@test
def test_resume_never_uses_bare_dash_s_either(ctx: Ctx):
    argv = _argv(resume_id="thread-123")
    ctx.check(f"resume+exec present, got {argv!r}", "resume" in argv and "thread-123" in argv)
    ctx.check(f"no bare -s token anywhere in a resume argv, got {argv!r}", "-s" not in argv)
    ctx.check(f"sandbox STILL passed as -c sandbox_mode=... on resume, got {argv!r}",
              "sandbox_mode=workspace-write" in argv)


@test
def test_every_permission_mode_avoids_bare_dash_s_on_resume(ctx: Ctx):
    from halo_harness.agent.codex_process import build_cx_argv
    for mode in ("bypass", "auto", "default", "manual"):
        argv = build_cx_argv(model="astra", prompt="hi", resume_id="t1", permission_mode=mode,
                              mcp_override_args=[], prompt_via_stdin=True)
        ctx.check(f"{mode}: no bare -s on resume, got {argv!r}", "-s" not in argv)
        ctx.check(f"{mode}: a -c sandbox_mode entry exists, got {argv!r}",
                  any(a.startswith("sandbox_mode=") for a in argv))


@test
def test_fake_codex_rejects_dash_s_after_resume_like_clap(ctx: Ctx):
    """Pins the test fixture itself: without this, the fake would have
    silently accepted the pre-fix argv shape and this whole bug class
    could ship again with every test still green."""
    proc = subprocess.run(
        [sys.executable, str(FAKE_CODEX), "exec", "resume", "thread-1", "-s", "read-only",
         "--json", "--skip-git-repo-check", "-"],
        input="hi", capture_output=True, text=True, timeout=15,
    )
    ctx.check(f"exit code 2 (clap's own code), got {proc.returncode}", proc.returncode == 2)
    ctx.check(f"the real clap wording, got {proc.stderr!r}",
              "unexpected argument '-s' found" in proc.stderr)


@test
def test_fake_codex_still_accepts_dash_s_on_a_fresh_exec(ctx: Ctx):
    """The real `codex exec` (never `resume`) DOES take `-s` -- the fake
    must keep accepting it there so a test exercising the OLD, still-
    valid fresh-exec shape never breaks."""
    proc = subprocess.run(
        [sys.executable, str(FAKE_CODEX), "exec", "-s", "workspace-write",
         "--json", "--skip-git-repo-check", "reply with the single word pong"],
        capture_output=True, text=True, timeout=15,
    )
    ctx.check(f"exit 0, got {proc.returncode} stderr={proc.stderr!r}", proc.returncode == 0)
    ctx.check(f"a normal turn.completed came back, got {proc.stdout!r}", "turn.completed" in proc.stdout)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
