"""tests.test_review_slash -- Halo 2.0.10 round 1: the text form of `/review`: the registered builtin through
a facade (print-mode path) and a real `halo -p "/review ..."` subprocess.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_openai import MockUpstream, SCENARIOS
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.helpers import review_mock as rm
from tests.test_review_cli import _env, _scripted

ensure_default_provider_credentials()
REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()


@test
def test_review_is_a_registered_builtin_with_a_hint(ctx: Ctx):
    from halo_harness.commands.builtins import _BUILTIN_SPECS
    kind, desc, hint, run = _BUILTIN_SPECS["review"]
    ctx.check("core command with usage hint", kind == "core" and "--dimensions" in hint and "--fix" in hint)


@test
def test_facade_form_returns_the_text_result(ctx: Ctx):
    from halo_harness.commands.builtins import HeadlessFacade, _cmd_review
    mock = MockUpstream().start()
    try:
        repo = rm.make_repo()
        SCENARIOS["rv-all"] = _scripted(repo)
        session = rm.new_session(mock, repo)
        session.agent_runtime.role_table = {}                # every role -> the session model
        session.model_label = "or:mock/rv-all"
        from halo_harness.model import parse_model_ref
        session.model_ref = parse_model_ref("or:mock/rv-all")
        text = _cmd_review('--dimensions correctness --level low', HeadlessFacade(cwd=repo, session=session))
        ctx.check(f"header and ranked findings, got {text[:200]!r}",
                  "2 findings (1 confirmed, 1 plausible) from 1 reviewer" in text and text.index("a.py:2") < text.index("util.py:2"))
        usage = _cmd_review("--dimensions nope", HeadlessFacade(cwd=repo, session=session))
        ctx.check(f"bad option returns usage text, got {usage[:120]!r}", "nope" in usage and "Usage: /review" in usage)
        none = _cmd_review("", HeadlessFacade(cwd=repo, session=None))
        ctx.check("no session says so", "session" in none)
    finally:
        mock.stop()


@test
def test_dash_p_slash_review_prints_the_text_form(ctx: Ctx):
    mock = MockUpstream().start()
    try:
        repo = rm.make_repo()
        SCENARIOS["rv-all"] = _scripted(repo)
        cmd = [sys.executable, "-m", "halo_harness", "-p", "/review --dimensions correctness", "--model", "or:mock/rv-all",
               "--cwd", str(repo)]
        r = subprocess.run(cmd, env=_env(mock), cwd=str(REPO_DIR), capture_output=True, text=True, encoding="utf-8",
                           timeout=240)
        ctx.check(f"exit 0, got {r.returncode} stderr={r.stderr[-300:]!r}", r.returncode == 0)
        ctx.check(f"ranked text on stdout, got {r.stdout[:200]!r}",
                  "2 findings (1 confirmed, 1 plausible)" in r.stdout and "CONFIRMED" in r.stdout)
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
