"""tests.test_check_cli -- Halo 3.2.2.0 R2: `halo check` and the TUI's `/check`
(halo_harness/check_cli.py over start/checks.py), every check stubbed.

1. no flag runs the default-on checks (doctor, catalog, hello), each with its
   title, its what / cost / time line and its result lines; exit 0
2. `--all` runs the five in order; named flags run those; `--models` feeds
   the gym
3. `--explain` prints the five rows and runs nothing; exit 0
4. exit 1 when one failed (named on the last line); exit 2 on a bad flag
5. `halo check` is a verb of the CLI; `/check` is a built-in (its `--start`
   points at /start)
Run: python -m tests.test_check_cli
"""
from __future__ import annotations

import io
import sys
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


@contextmanager
def _stubbed(fail=()):
    """Every check's run replaced by a recorder; the keys in `fail` raise CheckFailed."""
    from halo_harness.start import checks as C
    saved = {c["key"]: c["run"] for c in C.CHECKS}
    ran: list = []

    def make(key):
        def run(ctx):
            ran.append((key, list(ctx.gym_models) if ctx.gym_models is not None else None))
            if key in fail:
                raise C.CheckFailed([f"{key} went wrong"])
            return [f"{key} result line"]
        return run
    try:
        for c in C.CHECKS:
            c["run"] = make(c["key"])
        yield ran
    finally:
        for c in C.CHECKS:
            c["run"] = saved[c["key"]]


def _check(*argv):
    from halo_harness.check_cli import run
    from halo_harness.start.checks import CheckCtx
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = run(list(argv), stream=out, ctx=CheckCtx(cwd=Path.cwd(), model="or:v/m"))
    return rc, out.getvalue(), err.getvalue()


@test
def test_no_flag_runs_the_default_set(ctx: Ctx):
    with _stubbed() as ran:
        rc, text, _ = _check()
    ctx.check(f"exit 0, got {rc} {text[-300:]!r}", rc == 0)
    ctx.check(f"doctor, catalog, hello in order, got {ran}", [k for k, _ in ran] == ["doctor", "catalog", "hello"])
    ctx.check("each: its title, its what / cost / time line, its result lines", "Doctor (doctor)\n  checks your config" in text
              and "Cost: free. Time: seconds." in text and "  doctor result line\n  [ok]" in text)
    ctx.check("the last line counts them", text.rstrip().endswith("halo check: 3 of 3 passed"))
    ctx.check("the paid ones did not run", "Model gym" not in text and "guided first run (start)" not in text)


@test
def test_all_named_flags_and_models(ctx: Ctx):
    with _stubbed() as ran:
        rc, _text, _ = _check("--all")
    ctx.check(f"--all: the five in order, got {ran}", rc == 0 and [k for k, _ in ran] == ["doctor", "catalog", "hello", "gym", "start"])
    with _stubbed() as ran:
        rc, _text, _ = _check("--gym", "--doctor", "--models", "ol:a, ol:b")
    ctx.check(f"named: those, in the list's order; --models feeds the gym, got {ran}", rc == 0
              and ran == [("doctor", ["ol:a", "ol:b"]), ("gym", ["ol:a", "ol:b"])])


@test
def test_explain_runs_nothing(ctx: Ctx):
    with _stubbed() as ran:
        rc, text, _ = _check("--explain")
    lines = text.splitlines()
    ctx.check(f"exit 0, nothing ran, got {rc} {ran}", rc == 0 and ran == [])
    ctx.check(f"the five rows, the defaults ticked, got {lines[::2]}", len(lines) == 10 and lines[0] == "[x] Doctor (doctor)"
              and lines[6] == "[ ] Model gym, quick (gym)" and lines[8] == "[ ] The guided first run (start)")
    ctx.check("hello's cost names the default model", "or:v/m" in lines[5])
    with _stubbed():
        _rc, text, _ = _check("--explain", "--all")
    ctx.check("--explain --all ticks every row", text.count("[x]") == 5)


@test
def test_exit_codes(ctx: Ctx):
    with _stubbed(fail=("catalog",)) as ran:
        rc, text, _ = _check()
    ctx.check(f"one failed: exit 1, the rest still ran, got {rc} {ran}", rc == 1 and len(ran) == 3)
    ctx.check("its lines and the mark, named last", "  catalog went wrong\n  [failed]" in text
              and text.rstrip().endswith("halo check: 2 of 3 passed; failed: catalog"))
    with _stubbed():
        rc, _text, err = _check("--nope")
    ctx.check(f"a bad flag: exit 2, got {rc} {err[-120:]!r}", rc == 2 and "--nope" in err)


@test
def test_the_cli_verb_and_the_builtin(ctx: Ctx):
    from halo_harness.cli import main
    out = io.StringIO()
    with redirect_stdout(out):
        rc = main(["check", "--explain"])
    ctx.check(f"`halo check --explain` through the CLI, got {rc} {out.getvalue()[:80]!r}", rc == 0
              and out.getvalue().startswith("[x] Doctor (doctor)"))
    from halo_harness.commands.builtins import _BUILTIN_SPECS
    ctx.check("/check is a built-in", "check" in _BUILTIN_SPECS)
    run = _BUILTIN_SPECS["check"][3]
    with _stubbed() as ran:
        text = run("--doctor --start", None)
    ctx.check(f"/check --doctor --start: doctor runs, the start points at /start, got {ran} {text[-160:]!r}",
              [k for k, _ in ran] == ["doctor"] and "doctor result line" in text and "/start" in text)
    with _stubbed() as ran:
        text = run("--all", None)
    ctx.check(f"/check --all: the four that run in a transcript, got {ran}", [k for k, _ in ran] == ["doctor", "catalog", "hello", "gym"]
              and "/start" in text)
    from halo_harness.completion_cli import SUBCOMMANDS
    ctx.check("completion offers check", "check" in SUBCOMMANDS)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
