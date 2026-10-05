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
# `build_cx_argv` resolves the real launcher, so on a machine without a
# `codex` install (the Kali VM run of the 2.0.3 release suites) every
# argv-only test here raised CodexNotFoundError. Point Halo at the fake for
# the whole module unless the caller already chose a launcher.
import os
if not os.environ.get("HALO_CODEX_EXE"):
    os.environ["HALO_CODEX_EXE"] = '"' + sys.executable + '" "' + str(FAKE_CODEX) + '"'


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
    # Pass-B finding 11: every REAL `PermissionEngine.mode` value (plus
    # the legacy "bypass"/"manual" strings, still accepted) goes through
    # `build_cx_argv` cleanly -- "test every CLI choice through it".
    for mode in ("bypass", "auto", "default", "manual", "acceptEdits", "plan", "dontAsk", "bypassPermissions"):
        argv = build_cx_argv(model="astra", prompt="hi", resume_id="t1", permission_mode=mode,
                              mcp_override_args=[], prompt_via_stdin=True)
        ctx.check(f"{mode}: no bare -s on resume, got {argv!r}", "-s" not in argv)
        ctx.check(f"{mode}: a -c sandbox_mode entry exists, got {argv!r}",
                  any(a.startswith("sandbox_mode=") for a in argv))
        ctx.check(f"{mode}: a -c approval_policy entry exists, got {argv!r}",
                  any(a.startswith("approval_policy=") for a in argv))


@test
def test_codex_approval_and_sandbox_matches_every_real_engine_mode(ctx: Ctx):
    """Pass-B finding 11 (major): the table used to be keyed on `bypass`/
    `auto`/`default`/`manual` -- Halo's six REAL `PermissionEngine.mode`
    values are `default|acceptEdits|plan|auto|dontAsk|bypassPermissions`
    (its own docstring), and `normalize_permission_mode` only ever maps
    `manual` to `default` before a mode reaches this table, so every mode
    but `auto` used to fall through to the `default` row, including
    `bypassPermissions`/`dontAsk`/`acceptEdits`/`plan`. Pinned against
    docs/MODELS.md's own "Execution, one subprocess per turn" table."""
    from halo_harness.agent.codex_process import codex_approval_and_sandbox
    expected = {
        "auto": ("never", "danger-full-access"),
        "bypassPermissions": ("never", "danger-full-access"),
        "default": ("on-request", "workspace-write"),
        "acceptEdits": ("on-request", "workspace-write"),
        "dontAsk": ("never", "workspace-write"),
        "plan": ("never", "read-only"),
    }
    for mode, want in expected.items():
        got = codex_approval_and_sandbox(mode)
        ctx.check(f"{mode}: expected {want}, got {got}", got == want)
    # Every mode avoids the ONE combination the research doc flags as
    # unanswerable in non-interactive `codex exec` (an approval request
    # paired with a sandbox that can't just silently fail the attempt
    # instead) -- `plan`'s read-only sandbox means a blocked write has
    # nothing to approve, and every approval_policy actually used here is
    # "never" or "on-request", never "on-failure"/"untrusted".
    for mode in expected:
        approval, _sandbox = codex_approval_and_sandbox(mode)
        ctx.check(f"{mode}: approval_policy is never/on-request only, got {approval!r}",
                  approval in ("never", "on-request"))


@test
def test_codex_approval_and_sandbox_legacy_bypass_alias_and_fallback(ctx: Ctx):
    """The literal string "bypass" (never produced by `normalize_
    permission_mode` any more, but still the hardcoded value `codex_
    runtime.one_shot_cx_call` passes -- a different, unassigned finding)
    keeps resolving to the same full-access row; a totally unrecognized
    string falls back to the `default` row rather than raising."""
    from halo_harness.agent.codex_process import codex_approval_and_sandbox
    ctx.check('legacy "bypass" still full access', codex_approval_and_sandbox("bypass") == ("never", "danger-full-access"))
    ctx.check("an unrecognized mode falls back to the default row",
              codex_approval_and_sandbox("some-made-up-mode") == ("on-request", "workspace-write"))


@test
def test_effort_reaches_argv_as_model_reasoning_effort(ctx: Ctx):
    """Pass-B finding 13 (major): `--effort`/`/effort` used to never reach
    `codex exec` at all (`cc:` already forwards it, `cx:` didn't) -- now
    rides as its own `-c model_reasoning_effort=<value>` on both a fresh
    exec and a resume, mapped from Halo's harness-wide effort levels
    (which happen to share five of Codex's own six names outright)."""
    from halo_harness.agent.codex_process import build_cx_argv
    for level in ("low", "medium", "high", "xhigh", "max"):
        argv = build_cx_argv(model="astra", prompt="hi", resume_id=None, permission_mode="default",
                              mcp_override_args=[], prompt_via_stdin=True, effort=level)
        ctx.check(f"{level}: carried on a fresh exec, got {argv!r}",
                  f"model_reasoning_effort={level}" in argv)
        argv_resume = build_cx_argv(model="astra", prompt="hi", resume_id="t1", permission_mode="default",
                                     mcp_override_args=[], prompt_via_stdin=True, effort=level)
        ctx.check(f"{level}: carried on a resume too, got {argv_resume!r}",
                  f"model_reasoning_effort={level}" in argv_resume)


@test
def test_no_effort_omits_the_flag_entirely(ctx: Ctx):
    from halo_harness.agent.codex_process import build_cx_argv
    argv_unset = build_cx_argv(model="astra", prompt="hi", resume_id=None, permission_mode="default",
                                mcp_override_args=[], prompt_via_stdin=True)
    ctx.check(f"no effort given at all -> no flag, got {argv_unset!r}",
              not any("model_reasoning_effort=" in a for a in argv_unset))
    argv_empty = build_cx_argv(model="astra", prompt="hi", resume_id=None, permission_mode="default",
                                mcp_override_args=[], prompt_via_stdin=True, effort="")
    ctx.check(f"empty string -> no flag, got {argv_empty!r}",
              not any("model_reasoning_effort=" in a for a in argv_empty))
    argv_unknown = build_cx_argv(model="astra", prompt="hi", resume_id=None, permission_mode="default",
                                  mcp_override_args=[], prompt_via_stdin=True, effort="not-a-real-level")
    ctx.check(f"a value Codex has never heard of -> no flag, got {argv_unknown!r}",
              not any("model_reasoning_effort=" in a for a in argv_unknown))


@test
def test_codex_reasoning_effort_mapping_function(ctx: Ctx):
    from halo_harness.agent.codex_process import codex_reasoning_effort
    for level in ("low", "medium", "high", "xhigh", "max", "ultra"):
        ctx.check(f"{level} passes through unchanged", codex_reasoning_effort(level) == level)
    ctx.check("None stays None", codex_reasoning_effort(None) is None)
    ctx.check("empty string becomes None", codex_reasoning_effort("") is None)
    ctx.check("an unrecognized value becomes None", codex_reasoning_effort("none") is None)


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
