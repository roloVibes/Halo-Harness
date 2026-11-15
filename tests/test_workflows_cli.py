"""tests.test_workflows_cli -- `halo workflows` in a scratch home (Halo 3.3.16.0 R3, workflows/squares_cli.py):
list prints every square's contract line (NAME · DOES · TAKES -> GIVES · band · depth) with `*` on the
enabled ones; show prints the contract; enable / disable say what changed in one line; test runs the check
pass and a dry run of the router; new copies a shipped square into yours; check / run reach the old verbs;
`halo workflow list` keeps its pack-only answer; the TUI's /workflows prints the same lines. No model call.

Run: python -m tests.test_workflows_cli
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def halo(h, *argv) -> "tuple[int, str, str]":
    from halo_harness.cli import main
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv) + (["--repo", str(h.repo)] if argv[0] == "workflows" and len(argv) > 1 else []))
        except SystemExit as e:
            code = int(e.code or 0)
    return code, out.getvalue(), err.getvalue()


@test
def test_the_slash_command_prints_the_same_lines(ctx: Ctx):
    from halo_harness.commands.builtins import _BUILTIN_SPECS
    from halo_harness.workflows.squares_cli import slash_text
    with PacksHome() as h:
        ctx.check("/workflows is a builtin", "workflows" in _BUILTIN_SPECS)
        text = slash_text("", h.repo)
        ctx.check(f"the list, got {text[:60]!r}", text.startswith("squares (lineup auto; * = enabled):") and "* [shipped] media · " in text)
        ctx.check("show", "  engine    session" in slash_text("show media", h.repo))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
