"""tests.test_start_cli -- Halo 3.1.1.0 R1: `halo start`, the ten-minute guided
first run (halo_harness/start/, start_cli.py).

Every run here uses HALO_START_FAKE=1 (the fake lead, workers and judge in
start/fake.py: real git, no model) in this module's own home:
1. `--yes`: the seven steps done in order, each screen with its why and its
   command; the lineup copied to my-halo-dev-cycle (the active lineup
   untouched), the sample repo a git repo, the run finished with its plan
   approved, the report's checks and the coach's card, the three next lines.
2. `--json`: only the summary, ok, every step done, the report's checks.
3. step by step: Enter, Enter, then q at step 3 stops before the run starts.
4. step by step to the end: Enter everywhere approves the plan.
5. no provider configured (the fake off): says so, offers halo init, exit 2.
6. the wizard's last step: "Run the ten-minute start now?" defaults to No.
Run: python -m tests.test_start_cli
"""
from __future__ import annotations

import io
import json
import os
import sys
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()

KEYS = ["lineup", "repo", "goal", "plan", "run", "report", "next"]


@contextmanager
def _env(**values):
    before = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in before.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _start(argv, stdin: str = "", fake: bool = True):
    from halo_harness.start_cli import cmd_start
    out, err = io.StringIO(), io.StringIO()
    old_in = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        with _env(HALO_START_FAKE="1" if fake else None), redirect_stdout(out), redirect_stderr(err):
            rc = cmd_start(list(argv))
    finally:
        sys.stdin = old_in
    return rc, out.getvalue(), err.getvalue()


def _home() -> Path:
    from halo_harness.config.paths import bridge_home
    return Path(bridge_home())


@test
def test_yes_runs_every_step_through_the_fake(ctx: Ctx):
    from halo_harness.theme import get_config_value
    team_before = get_config_value("team", "")
    rc, text, err = _start(["--yes"])
    ctx.check(f"exit 0, got {rc} {err[-400:]!r} {text[-600:]!r}", rc == 0)
    titles = ["The lineup", "The sample repo", "The goal", "The plan", "The run", "The report and the coach", "Where to go next"]
    pos = [text.find(f"Step {i} of 7: {t}") for i, t in enumerate(titles, 1)]
    ctx.check(f"seven screens in order, got {pos}", -1 not in pos and pos == sorted(pos))
    ctx.check("each screen has its why and its command", text.count("  $ ") >= 7
              and "a copy of a shipped one is yours to edit" in text and "halo orchestra run --review" in text)
    ctx.check("seven [done] marks", text.count("[done]") == 7)
    lineup = _home() / "teams" / "my-halo-dev-cycle.yaml"
    ctx.check(f"the lineup copied into your scope, got {lineup}", lineup.is_file() and "name: my-halo-dev-cycle" in lineup.read_text(encoding="utf-8"))
    ctx.check("its cards as a table with tiers", "tier       card" in text and "all        boss         main" in text)
    ctx.check("the active lineup is unchanged", get_config_value("team", "") == team_before)
    repos = sorted((_home() / "start").glob("*/basket*"))
    ctx.check(f"the sample repo is a git repo with basket.py, got {repos}", repos and (repos[-1] / ".git").exists()
              and (repos[-1] / "basket.py").is_file())
    ctx.check("the plan was printed with the two sentences and approved", "job-5" in text and "Lanes in one layer" in text
              and "approved: 5 job(s)" in text)
    ctx.check("the run finished: five lanes merged", text.count("merged") >= 5 and "finished: branch orchestra/" in text)
    ctx.check("the report's checks and the coach", "PASS  tests_pass_finished_branch" in text and "coach: orchestra run" in text
              and "Apply opens the bio in Studio" in text)
    ctx.check("where to go next: Roles, Team, Fleet with their commands", "halo studio --mode roles" in text
              and "halo team init" in text and "halo fleet pair" in text)
    from halo_harness.orchestra.goal import list_runs, load_goal
    runs = list_runs(repos[-1])
    goal = load_goal(runs[-1] / "goal.json")
    ctx.check(f"the goal: the fixed what, plan review, the copied lineup, got {goal}", goal.what == "Write the five functions of basket.py"
              and goal.plan == "review" and goal.lineup == "my-halo-dev-cycle")
    plan = json.loads((runs[-1] / "plan.json").read_text(encoding="utf-8"))
    ctx.check("plan.json: approved by the start", plan.get("approved") is True and plan.get("by") == "start")
    before = len(list((_home() / "start").glob("*/basket*")))
    rc2, text2, _ = _start(["--yes"])
    after = sorted((_home() / "start").glob("*/basket*"))
    ctx.check("a second start keeps the copy and makes another sample repo (basket-2, ...)", rc2 == 0 and "already yours" in text2
              and len(after) == before + 1 and any(p.name.startswith("basket-") for p in after))


@test
def test_json_prints_only_the_summary(ctx: Ctx):
    rc, text, err = _start(["--json"])
    ctx.check(f"exit 0, got {rc} {err[-300:]!r}", rc == 0)
    try:
        data = json.loads(text)
    except ValueError:
        data = {}
    ctx.check(f"stdout is one JSON object, got {text[:200]!r}", bool(data))
    ctx.check("ok, fake, every step done in order", data.get("ok") is True and data.get("fake") is True
              and [s["key"] for s in data.get("steps", [])] == KEYS and all(s["state"] == "done" for s in data["steps"]))
    ctx.check(f"the summary names the lineup, repo and run, got {data.get('lineup')} {data.get('run')}",
              data.get("lineup") == "my-halo-dev-cycle" and Path(data.get("repo", "")).is_dir() and data.get("run"))
    checks = {c["id"]: c["ok"] for c in data.get("report", {}).get("checks", [])}
    ctx.check(f"the report finished and its tests pass, got {checks}", data["report"].get("status") == "finished"
              and checks.get("tests_pass_finished_branch") is True)
    ctx.check("no screen text in --json", "Step 1 of 7" not in text)


@test
def test_q_at_step_3_stops_before_the_run(ctx: Ctx):
    from halo_harness.orchestra.goal import list_runs
    rc, text, _ = _start([], stdin="\n\nq\n")
    ctx.check(f"exit 1, got {rc} {text[-300:]!r}", rc == 1)
    ctx.check("steps 1 and 2 done, step 3 stopped", text.count("[done]") == 2 and "[stopped]" in text
              and "Step 3 of 7: The goal" in text and "Step 4 of 7" not in text)
    ctx.check("the closing line names the step", "halo start stopped at goal: stopped before goal" in text)
    repos = sorted((_home() / "start").glob("*/basket*"), key=lambda p: p.stat().st_mtime)
    ctx.check(f"the newest sample repo has no run, got {repos[-1]}", list_runs(repos[-1]) == [])


@test
def test_enter_at_every_screen_approves_and_finishes(ctx: Ctx):
    rc, text, err = _start([], stdin="\n" * 9)
    ctx.check(f"exit 0, got {rc} {err[-300:]!r} {text[-300:]!r}", rc == 0)
    ctx.check("each screen asked first, the plan asked to approve", text.count("Enter runs this step, q stops the start") == 7
              and "Enter approves the plan, s opens it on Studio's plan canvas, q stops" in text)
    ctx.check("seven steps done", text.count("[done]") == 7 and "The start is done" in text)


@test
def test_no_provider_says_so_and_offers_init(ctx: Ctx):
    from halo_harness.start import provider
    saved = (provider.configured, provider.default_model)
    provider.configured, provider.default_model = (lambda: []), (lambda: "")
    try:
        rc, text, _ = _start([], fake=False)
        rc_json, text_json, _ = _start(["--json"], fake=False)
    finally:
        provider.configured, provider.default_model = saved
    ctx.check(f"exit 2 with the line, got {rc} {text!r}", rc == 2 and "No model provider is set up yet" in text and "halo init" in text)
    ctx.check("no step ran", "Step 1 of 7" not in text)
    data = json.loads(text_json)
    ctx.check(f"--json says no_provider, got {data}", rc_json == 2 and data.get("reason") == "no_provider" and data.get("ok") is False)
    ok, line = provider.ready()
    ctx.check("ready() is a (bool, text) pair", isinstance(ok, bool) and isinstance(line, str) and line)


@test
def test_the_wizard_offers_the_start_default_no(ctx: Ctx):
    from types import SimpleNamespace
    from rich.console import Console
    from halo_harness import init_cli
    out = io.StringIO()
    rc = init_cli._step_offer_start(SimpleNamespace(yes=True), Console(file=out, width=120))
    ctx.check(f"non-interactive: No, init's exit 0, got {rc} {out.getvalue()!r}", rc == 0 and "halo start" in out.getvalue())
    ctx.check("the question is the brief's", init_cli.START_QUESTION.startswith("Run the ten-minute start now?"))
    from halo_harness.tui.dialogs.init_wizard import WizardState
    state = WizardState(cwd=Path.cwd())
    ctx.check("the wizard state does not run it unless asked", state.offer_start is False and state.run_start is False)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
