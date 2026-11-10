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
def test_list_prints_the_contract_lines(ctx: Ctx):
    with PacksHome() as h:
        code, out, _ = halo(h, "workflows", "list")
        ctx.check(f"exit 0, the lineup, got {out[:80]!r}", code == 0 and out.startswith("squares (lineup auto; * = enabled):"))
        ctx.check(f"media enabled with its line, got {out!r}", " * [shipped] media · Reads and makes images, audio, video and PDFs"
                  " for a model that cannot, and hands back what it found. · text,files,pdf,images,audio,video -> text · low · depth 1" in out)
        ctx.check("plan listed, not enabled", "   [shipped] plan · " in out)
        code, out, _ = halo(h, "workflows", "list", "--json")
        rows = json.loads(out)["squares"]
        ctx.check("json rows carry the contract", code == 0 and any(r["ref"] == "code" and r["engine"] == "orchestra" and r["gives"] == ["repo-change", "report"] for r in rows))


@test
def test_show_enable_disable(ctx: Ctx):
    with PacksHome() as h:
        code, out, _ = halo(h, "workflows", "show", "media")
        ctx.check(f"the contract, got {out!r}", code == 0 and "  covers    pdf, vision, audio, video, media" in out
                  and "  lineup    lead auto-media on auto" in out and "  limits    depth 1 · 30 turns · 900 s" in out)
        code, out, _ = halo(h, "workflows", "enable", "review")
        ctx.check(f"one line, got {out!r}", code == 0 and out.strip() == "review enabled for the auto lineup (wrote config workflows.enabled)")
        code, out, _ = halo(h, "workflows", "list")
        ctx.check("now starred", " * [shipped] review · " in out)
        code, out, _ = halo(h, "workflows", "disable", "review")
        ctx.check(f"off again, got {out!r}", code == 0 and out.strip() == "review disabled for the auto lineup (wrote config workflows.enabled)")
        code, _out, err = halo(h, "workflows", "enable", "nope")
        ctx.check(f"an unknown square: exit 1 and where it looked, got {err!r}", code == 1 and "no workflow 'nope'" in err)


@test
def test_test_runs_the_check_and_the_router(ctx: Ctx):
    with PacksHome() as h:
        code, out, _ = halo(h, "workflows", "test", "media")
        ctx.check(f"clean and the PDF gap covered, got {out!r}", code == 0 and out.startswith("media: check clean")
                  and "router on 'summarize report.pdf' (a text-only model): gaps pdf -> media covers pdf" in out)
        code, out, _ = halo(h, "workflows", "test", "code")
        ctx.check(f"an ask word as the need, got {out!r}", code == 0 and "gaps code -> code covers code" in out)
        h.write(".halo/workflows/broken.yaml", "name: broken\ncovers: [pdfs]\nstages:\n  - id: a\n")
        code, out, _ = halo(h, "workflows", "test", "broken")
        ctx.check(f"problems listed, exit 1, got {out!r}", code == 1 and "covers 'pdfs' is not a need" in out and "not a square" in out)


@test
def test_new_copies_into_yours_and_the_old_verbs_stay(ctx: Ctx):
    with PacksHome() as h:
        code, out, _ = halo(h, "workflows", "new", "my-media", "--from", "media")
        dest = h.state / "workflows" / "my-media.yaml"
        ctx.check(f"written under yours, got {out!r}", code == 0 and dest.is_file() and "name: my-media" in dest.read_text(encoding="utf-8"))
        code, _o, err = halo(h, "workflows", "new", "my-media", "--from", "media")
        ctx.check(f"never over a file, got {err!r}", code == 1 and "is there already" in err)
        code, out, _ = halo(h, "workflows", "list")
        ctx.check("listed as yours", " [yours  ] my-media · " in out)
        code, out, _ = halo(h, "workflows", "check", "plan", "--input", "task=x")
        ctx.check(f"check reaches the old verb, got {out!r}", code == 0 and out.startswith("plan compiles: 1 job(s)"))
        code, out, _ = halo(h, "workflow", "list")
        ctx.check(f"halo workflow list keeps its pack-only answer, got {out!r}", code == 0 and out.startswith("no workflows: no pack"))


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
