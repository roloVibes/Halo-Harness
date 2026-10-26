"""tests.test_start_cli -- Halo 3.1.1.0 R1: `halo start`, the guided first run
(halo_harness/start/, start_cli.py).

Every run here uses HALO_START_FAKE=1 (the fake lead, workers and judge in
start/fake.py: real git, no model) in this module's own home:
1. `--yes`: the seven steps done in order, each screen with its why and its
   command; the lineup copied to my-halo-dev-cycle (the active lineup
   untouched), the sample repo a git repo, the run finished with its plan
   approved, the report's checks and the coach's card, the three next lines.
2. `--json`: only the summary, ok, every step done, the report's checks.
3. step by step: Enter, Enter, then q at step 3 stops before the run starts.
4. step by step to the end: Enter everywhere approves the plan.
5. no provider configured (the fake off): says so, offers halo init, exit 2;
   on a terminal (3.3.0.0 R4) "Open Setup in Studio? [Y/n]": Enter opens Setup
   through halo init's door, `n` runs the terminal wizard (both stubbed).
6. the Summary's start row defaults to off (and the console question to No).
7. 3.2.2.0 R2, the card: the models it will call, the estimate's rule, what it
   writes; `--explain` prints only the card, exit 0; `--yes` prints it first.
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
    ctx.check("the card comes first (3.2.2.0 R2)", 0 <= text.find("Estimated cost: free") < text.find("Step 1 of 7"))
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
def test_no_provider_on_a_terminal_offers_setup_in_studio(ctx: Ctx):
    """3.3.0.0 R4: "Open Setup in Studio? [Y/n]": Enter opens Setup through halo init's door (stubbed) and exits 2;
    `n` runs the terminal wizard (stubbed); a door that cannot open a browser runs the wizard too."""
    from halo_harness import init_cli
    from halo_harness.start import provider
    from halo_harness.start_cli import _offer_init
    from halo_harness.studio import setup_door
    from tests.helpers.setup_door_stubs import fake_tty
    doors, inits = [], []
    saved = (setup_door.cli_door, init_cli.cmd_init)
    opens = {"ok": True}
    setup_door.cli_door = lambda target, **kw: doors.append((target, kw)) or opens["ok"]
    init_cli.cmd_init = lambda argv: inits.append(list(argv)) or 0
    try:
        with fake_tty("\n") as out:
            rc_enter = _offer_init(False)
        enter_text = out.getvalue()
        with fake_tty("n\n"):
            rc_no = _offer_init(False)
        opens["ok"] = False
        with fake_tty("y\n"):
            rc_none = _offer_init(False)
    finally:
        setup_door.cli_door, init_cli.cmd_init = saved
    ctx.check(f"the question and the line, got {enter_text!r}", "Open Setup in Studio? [Y/n]" in enter_text
              and provider.NO_PROVIDER in enter_text and "halo init opens Setup in Studio" in provider.NO_PROVIDER)
    ctx.check(f"Enter: Setup through the door (first run), exit 2, no wizard, got {rc_enter} {doors[:1]}", rc_enter == 2
              and doors and doors[0][0] == setup_door.SetupTarget(first=True) and doors[0][1].get("terminal_cli") == "halo init --terminal")
    ctx.check(f"n: the terminal wizard, got {rc_no} {inits}", rc_no == 0 and inits[:1] == [["--terminal"]])
    ctx.check(f"no browser could open: the wizard runs, got {rc_none} {inits}", rc_none == 0 and inits == [["--terminal"], ["--terminal"]]
              and len(doors) == 2)


@test
def test_the_summarys_start_row_defaults_to_off(ctx: Ctx):
    from types import SimpleNamespace
    from rich.console import Console
    from halo_harness import init_cli
    from halo_harness.start import checks as C
    out = io.StringIO()
    rc = init_cli._step_offer_start(SimpleNamespace(yes=True), Console(file=out, width=120))
    ctx.check(f"non-interactive: No, init's exit 0, got {rc} {out.getvalue()!r}", rc == 0 and "halo start" in out.getvalue()
              and "--explain" in out.getvalue() and "Estimated cost" not in out.getvalue())
    ctx.check("the question names the guided first run", init_cli.START_QUESTION.startswith("Run the guided first run now?"))
    ctx.check("the start row is the last check and off", C.KEYS[-1] == "start" and C.check("start")["default_on"] is False)
    from halo_harness.tui.dialogs.init_wizard import WizardState
    state = WizardState(cwd=Path.cwd())
    ctx.check("the wizard state does not run it unless asked", state.offer_start is False and state.run_start is False)


@test
def test_the_card_says_models_cost_and_writes(ctx: Ctx):
    from halo_harness.start import card as K
    rows = {"or:v/lead": {"price_in_per_m": 1.0, "price_out_per_m": 2.0}, "or:v/work": {"price_in_per_m": 0.5,
            "price_out_per_m": 1.0}}
    got = K.estimate(parts={"main": "or:v/lead", "subagent": "or:v/work"}, models_by_ref=rows)
    want = (15_000 + 6_000 + 8_000 + 2_000) / 1e6 + 5 * (120_000 * 0.5 + 6_000 * 1.0) / 1e6  # lead plan + judge, five lanes
    ctx.check(f"priced: the sum by the stated rule, got {got!r}", got.startswith(f"about ${want:.2f}")
              and "five worker lanes 120k in / 6k out each" in got)
    got = K.estimate(parts={"main": "ol:qwen3", "subagent": "or:v/work"}, models_by_ref=rows)
    ctx.check(f"a local lead costs nothing, got {got!r}", got.startswith(f"about ${5 * 0.066:.2f}"))
    ctx.check("every model local: free", K.estimate(parts={"main": "ol:a", "subagent": "hf:local/b"}, models_by_ref={})
              .startswith("free: every model it calls is local"))
    got = K.estimate(parts={"main": "or:v/lead", "subagent": "or:v/none"}, models_by_ref=rows)
    ctx.check(f"no price: named, never free, got {got!r}", got.startswith("unknown for or:v/none"))
    lines = K.card_lines(model="or:v/lead", models_by_ref=rows, today="2026-10-25")
    text = "\n".join(lines)
    ctx.check("the models it will call (--model plays every part)", "the lead (the plan, and the judge of a conflict): or:v/lead"
              in text and "five workers (one lane each, a halo -p session): or:v/lead" in text)
    ctx.check("the copied lineup's cards, alias -> bio -> model", "main (boss) -> orchestrator ->" in text)
    ctx.check("seven steps, one sentence each", all(f"  {n}. " in text for n in range(1, 8)))
    ctx.check("the time and what it writes", "Time: 5-20 minutes on cloud models" in text
              and str(_home() / "teams" / "my-halo-dev-cycle.yaml") in text and str(_home() / "start" / "2026-10-25") in text)
    ctx.check("the active lineup untouched", lines[-1].startswith("Your active lineup is not touched"))


@test
def test_explain_prints_only_the_card(ctx: Ctx):
    before = sorted((_home() / "start").glob("*/basket*"))
    rc, text, err = _start(["--explain"])
    ctx.check(f"exit 0, got {rc} {err!r}", rc == 0)
    ctx.check("the card and nothing else", text.startswith("The guided first run (halo start)") and "Step 1 of 7" not in text
              and "Estimated cost: free" in text)
    ctx.check("nothing was written", sorted((_home() / "start").glob("*/basket*")) == before)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
