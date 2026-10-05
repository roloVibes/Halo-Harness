"""tests.test_codex_stdin_delivery -- pass-B fix (review finding 4,
critical): the `cx:` turn prompt now ALWAYS rides on the subprocess's
stdin (`codex exec ... -`/`codex exec resume <id> ... -`), never on
argv -- a Windows npm `.cmd` shim used to hand a quoted `&`/`%VAR%` to
cmd.exe for a second, unwanted parse pass, and the practical argv length
ceiling capped every prompt at a few KB. Also pins the Windows launcher
fix: a resolved `.cmd`/`.CMD` shim with the real `codex.js` sitting
beside it (an npm global install's own layout) launches `node <that
.js>` directly instead.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all

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

# The exact trigger text from the brief's own pinning test: a quoted span
# containing `&` (cmd.exe's own command separator once a .cmd shim gets
# hold of it), a `%VAR%`-shaped token (cmd.exe expands this BEFORE the
# model ever sees it), and bulk beyond any practical argv ceiling.
_TRICKY_PROMPT = 'rename "foo & echo INJECTED-SECOND-COMMAND" now\n%USERPROFILE%\n' + ("q" * 40_000)


@test
def test_argv_ends_with_the_stdin_marker_never_the_prompt_text(ctx: Ctx):
    from halo_harness.agent.codex_process import build_cx_argv
    argv = build_cx_argv(model="astra", prompt=_TRICKY_PROMPT, resume_id=None, permission_mode="default",
                          mcp_override_args=[], prompt_via_stdin=True)
    ctx.check(f"argv ends with the bare '-' marker, got {argv[-1]!r}", argv[-1] == "-")
    ctx.check("the prompt text itself never appears anywhere in argv",
              all(_TRICKY_PROMPT not in a for a in argv))
    ctx.check(f"argv stays small regardless of prompt size, got {sum(len(a) for a in argv)} chars",
              sum(len(a) for a in argv) < 1000)


@test
def test_prompt_delivered_to_the_real_process_byte_for_byte_via_stdin(ctx: Ctx):
    """Drives the REAL `CodexExecProcess`/`build_cx_argv` (production
    code) against the fake codex -- the fake reads stdin to EOF and logs
    the exact text it received (FAKE_CODEX_STDIN_LOG), independent of
    Halo's own event pipeline, so this proves byte-for-byte delivery
    through the real pipe, not just that argv looks right."""
    from halo_harness.agent.codex_process import CodexExecProcess, build_cx_argv
    stdin_log = Path(tempfile.mkdtemp(prefix="cx-stdin-log-")) / "stdin.txt"
    env = dict(os.environ)
    env["HALO_CODEX_EXE"] = '"' + sys.executable + '" "' + str(FAKE_CODEX) + '"'
    env["FAKE_CODEX_STDIN_LOG"] = str(stdin_log)
    env.pop("BRIDGE_TEST_CODEX_LOGIN_STATUS", None)
    saved = os.environ.get("HALO_CODEX_EXE")
    os.environ["HALO_CODEX_EXE"] = env["HALO_CODEX_EXE"]
    try:
        argv = build_cx_argv(model="astra", prompt=_TRICKY_PROMPT, resume_id=None, permission_mode="default",
                              mcp_override_args=[], prompt_via_stdin=True)
        process = CodexExecProcess(argv, cwd=str(REPO_DIR), env=env)
        process.send_prompt(_TRICKY_PROMPT)
        events = []
        for _ in range(10_000):
            obj = process.read_event()
            if obj is None:
                break
            events.append(obj)
        process.wait(timeout=15)
        ctx.check(f"a normal turn.completed came back, got types={[e.get('type') for e in events]}",
                  any(e.get("type") == "turn.completed" for e in events))
        ctx.check(f"stdin log was written, got exists={stdin_log.exists()}", stdin_log.exists())
        got = stdin_log.read_text(encoding="utf-8")
        ctx.check(f"the quoted '&' span arrived unexpanded/unsplit, got {got[:60]!r}",
                  'rename "foo & echo INJECTED-SECOND-COMMAND" now' in got)
        ctx.check("the %VAR% token arrived LITERAL, never expanded by a shell", "%USERPROFILE%" in got)
        ctx.check(f"all 40,000 filler characters arrived, got {got.count('q')}", got.count("q") == 40_000)
        ctx.check("byte-for-byte identical to what was sent", got == _TRICKY_PROMPT)
    finally:
        if saved is None:
            os.environ.pop("HALO_CODEX_EXE", None)
        else:
            os.environ["HALO_CODEX_EXE"] = saved


# ---- Windows npm .cmd shim bypass ----------------------------------------

def _set_codex_exe(path: Path):
    saved = os.environ.get("HALO_CODEX_EXE")
    os.environ["HALO_CODEX_EXE"] = '"' + str(path) + '"'
    return saved


def _restore_codex_exe(saved):
    if saved is None:
        os.environ.pop("HALO_CODEX_EXE", None)
    else:
        os.environ["HALO_CODEX_EXE"] = saved


@test
def test_cmd_shim_with_real_script_beside_it_resolves_to_node_and_the_js(ctx: Ctx):
    if os.name != "nt":
        raise SkipTest("the .cmd shim bypass is Windows-only by design")
    from halo_harness.providers.codex_models import resolve_codex_launch_argv
    scratch = Path(tempfile.mkdtemp(prefix="cx-shim-"))
    shim = scratch / "codex.CMD"
    shim.write_text("@echo off\r\n", encoding="utf-8")
    script_dir = scratch / "node_modules" / "@openai" / "codex" / "bin"
    script_dir.mkdir(parents=True)
    script = script_dir / "codex.js"
    script.write_text("// fake codex entry point\n", encoding="utf-8")
    saved = _set_codex_exe(shim)
    try:
        argv = resolve_codex_launch_argv()
        ctx.check(f"resolves to node + the real .js, got {argv!r}",
                  len(argv) == 2 and argv[1] == str(script) and "node" in argv[0].lower())
    finally:
        _restore_codex_exe(saved)


@test
def test_cmd_shim_with_no_script_beside_it_falls_back_to_the_shim(ctx: Ctx):
    if os.name != "nt":
        raise SkipTest("the .cmd shim bypass is Windows-only by design")
    from halo_harness.providers.codex_models import resolve_codex_launch_argv
    scratch = Path(tempfile.mkdtemp(prefix="cx-shim-noscript-"))
    shim = scratch / "codex.cmd"
    shim.write_text("@echo off\r\n", encoding="utf-8")
    saved = _set_codex_exe(shim)
    try:
        argv = resolve_codex_launch_argv()
        ctx.check(f"falls back to the shim itself, got {argv!r}", argv == [str(shim)])
    finally:
        _restore_codex_exe(saved)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
