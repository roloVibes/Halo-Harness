"""tests.test_start_cli -- Halo 3.1.1.0 R1: `halo start`, the guided first run
(halo_harness/start/, start_cli.py).

Every run here uses HALO_START_FAKE=1 (the fake lead, workers and judge in
start/fake.py: real git, no model) in this module's own home:
0. 3.3.15.0 R5: on the Auto lineup (team unset) it prints why the start would
   say little there and the gym, exits 0 and writes nothing; `--lineup` runs.
   Every other test runs with a custom lineup active (tests/helpers/custom_lineup.py):
   3.3.15.0 R7 seeds `crew` (a lead, two cards that write code, five lane slots).
1. `--yes`: the seven steps done in order, each screen with its why and its
   command; the run rehearses crew itself (named with its cards in the lineup
   step, the plan, the run and the report; no lineup copy written, the active
   lineup untouched), the sample repo a git repo, the run finished with its plan
   approved, the report's checks and the coach's card, the three next lines.
1b. 3.3.15.0 R7: `--lineup` overrides the active one; a missing lineup is one
   line and exit 1; a lineup with fewer lane slots runs in fewer lanes and says
   so; one with no card that writes code says so and exits 1, writing nothing;
   `my-halo-dev-cycle` is gone from halo_harness/ and docs/.
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
from contextlib import contextmanager, nullcontext, redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()

KEYS = ["lineup", "repo", "goal", "plan", "run", "report", "next"]
KEEP = "keep"  # _start's lineup: leave config's `team` as the caller set it
CREW = "crew"  # 3.3.15.0 R7: the seeded custom lineup every run here rehearses


def _crew() -> str:
    """Seed `crew` in this home once: boss (orchestrator, the lead), coder (implementer x3), fixer (implementer x2),
    research (researcher): five lane slots over two cards."""
    from halo_harness import teams_yaml as T
    if T.find_team_template_path(CREW) is None:
        ok, problems = T.save_team_template(CREW, {"name": CREW, "description": "the R7 test lineup", "agents": [
            {"agent": "orchestrator", "role": "main", "as": "boss"},
            {"agent": "implementer", "role": "coder", "as": "coder", "instances": 3},
            {"agent": "implementer", "role": "subagent", "as": "fixer", "instances": 2, "use_for": ["fix"]},
            {"agent": "researcher", "role": "researcher", "as": "research"}]})
        assert ok, problems
    return CREW


def _copies() -> list:
    return sorted(p.name for p in (_home() / "teams").glob("my-*.yaml"))


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


def _start(argv, stdin: str = "", fake: bool = True, lineup: "str | None" = CREW):
    """`cmd_start(argv)`; 3.3.15.0 R5: with `lineup` the active custom lineup (None: the Auto lineup)."""
    from halo_harness.start_cli import cmd_start
    from tests.helpers.custom_lineup import custom_lineup
    _crew()
    out, err = io.StringIO(), io.StringIO()
    old_in = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        held = nullcontext() if lineup == KEEP else custom_lineup(lineup)
        with held, _env(HALO_START_FAKE="1" if fake else None), redirect_stdout(out), redirect_stderr(err):
            rc = cmd_start(list(argv))
    finally:
        sys.stdin = old_in
    return rc, out.getvalue(), err.getvalue()


def _home() -> Path:
    from halo_harness.config.paths import bridge_home
    return Path(bridge_home())


@test
def test_on_auto_the_start_says_why_and_runs_nothing(ctx: Ctx):
    """3.3.15.0 R5: the Auto lineup (team unset): the line, the gym, exit 0, nothing under start/; --lineup runs."""
    from halo_harness.start.auto_gate import AUTO_LINE
    before = sorted((_home() / "start").glob("*/*")) if (_home() / "start").is_dir() else []
    rc, text, err = _start(["--yes"], lineup=None)
    after = sorted((_home() / "start").glob("*/*")) if (_home() / "start").is_dir() else []
    ctx.check(f"exit 0, the line and the gym, got {rc} {text!r} {err!r}", rc == 0 and AUTO_LINE in text
              and "halo gym --quick" in text and "Step 1 of 7" not in text)
    ctx.check(f"nothing written under start/, got {len(before)} -> {len(after)}", after == before)
    rc, text, _ = _start(["--json"], lineup=None)
    data = json.loads(text)
    ctx.check(f"--json: ok, not run, the reason, got {data}", rc == 0 and data == {"ok": True, "ran": False, "reason": "auto_lineup",
                                                                                     "message": AUTO_LINE})
    rc, text, err = _start(["--json", "--lineup", "halo-dev-cycle"], lineup=None)
    data = json.loads(text) if text.strip().startswith("{") else {}
    ctx.check(f"--lineup <name> runs on Auto too, that lineup itself, got {rc} {data.get('ok')} {data.get('lineup')}", rc == 0
              and data.get("ok") is True and data.get("lineup") == "halo-dev-cycle" and _copies() == [])
    rc, text, _ = _start(["--explain"], lineup=None)
    ctx.check(f"3.3.15.0 R7: --explain on Auto: the line, no card, got {rc} {text!r}", rc == 0 and AUTO_LINE in text
              and "Estimated cost" not in text and "pick or build a lineup in Agents -> Cast first" in AUTO_LINE)


@test
def test_yes_runs_every_step_through_the_fake(ctx: Ctx):
    from halo_harness.theme import get_config_value
    from tests.helpers.custom_lineup import custom_lineup
    with custom_lineup(_crew()):  # 3.3.15.0 R5: an active custom lineup, which the start must leave as it is
        team_before = get_config_value("team", "")
        rc, text, err = _start(["--yes"], lineup=KEEP)
        team_after = get_config_value("team", "")
    ctx.check(f"exit 0, got {rc} {err[-400:]!r} {text[-600:]!r}", rc == 0)
    ctx.check("the card comes first (3.2.2.0 R2)", 0 <= text.find("Estimated cost: free") < text.find("Step 1 of 7"))
    titles = ["The lineup", "The sample repo", "The goal", "The plan", "The run", "The report and the coach", "Where to go next"]
    pos = [text.find(f"Step {i} of 7: {t}") for i, t in enumerate(titles, 1)]
    ctx.check(f"seven screens in order, got {pos}", -1 not in pos and pos == sorted(pos))
    ctx.check("each screen has its why and its command", text.count("  $ ") >= 7
              and "the run rehearses yours as it is" in text and "halo orchestra run --review" in text)
    ctx.check("seven [done] marks", text.count("[done]") == 7)
    ctx.check(f"3.3.15.0 R7: no lineup copy written, got {_copies()}", _copies() == [] and "my-halo" not in text)
    step1 = text[text.find("Step 1 of 7"):text.find("Step 2 of 7")]
    ctx.check(f"step 1 names the active lineup and its roles, got {step1[:700]!r}",
              "the run rehearses crew (your active lineup)" in step1 and "the lead is boss (orchestrator)" in step1
              and "5 lane(s): coder (implementer) on the session model x3; fixer (implementer) on the session model x2" in step1)
    ctx.check("its cards as a table with tiers", "tier       card" in text and "all        boss         main" in text)
    plan = text[text.find("Step 4 of 7"):text.find("Step 5 of 7")]
    ctx.check("the plan names crew and gives each job a lane card's bio", "lineup crew: the lead is boss" in plan
              and plan.count("implementer") >= 5)
    report = text[text.find("Step 6 of 7"):text.find("Step 7 of 7")]
    ctx.check("the run and the report name crew", "lineup crew: 5 lane(s)" in text[text.find("Step 5 of 7"):text.find("Step 6 of 7")]
              and "lineup crew: the lead is boss (orchestrator)" in report)
    ctx.check("the active lineup is unchanged", team_after == team_before == CREW)
    repos = sorted((_home() / "start").glob("*/basket*"))
    ctx.check(f"the sample repo is a git repo with basket.py, got {repos}", repos and (repos[-1] / ".git").exists()
              and (repos[-1] / "basket.py").is_file())
    ctx.check("the plan was printed with the two sentences and approved", "job-5" in text and "Lanes in one layer" in text
              and "approved: 5 job(s)" in text)
    ctx.check("the run finished: five lanes merged", text.count("merged") >= 5 and "finished: branch orchestra/" in text)
    ctx.check("the report's checks and the coach", "PASS  tests_pass_finished_branch" in text and "coach: orchestra run" in text
              and "Apply opens the bio in Studio" in text)
    ctx.check("where to go next: Agents: Cast, Agents: Runs, Fleet with their commands (3.3.16.0 R1)", "halo studio --mode agents" in text
              and "halo orchestra new" in text and "halo fleet pair" in text)
    from halo_harness.orchestra.goal import list_runs, load_goal
    runs = list_runs(repos[-1])
    goal = load_goal(runs[-1] / "goal.json")
    ctx.check(f"the goal: the fixed what, plan review, the active lineup, got {goal}", goal.what == "Write the five functions of basket.py"
              and goal.plan == "review" and goal.lineup == CREW and goal.workers == 5)
    plan = json.loads((runs[-1] / "plan.json").read_text(encoding="utf-8"))
    ctx.check("plan.json: approved by the start, each job on an implementer", plan.get("approved") is True and plan.get("by") == "start"
              and [j.get("bio") for j in plan.get("jobs") or []] == ["implementer"] * 5)
    before = len(list((_home() / "start").glob("*/basket*")))
    rc2, text2, _ = _start(["--yes"])
    after = sorted((_home() / "start").glob("*/basket*"))
    ctx.check("a second start makes another sample repo (basket-2, ...) and still no copy", rc2 == 0 and _copies() == []
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
              data.get("lineup") == CREW and Path(data.get("repo", "")).is_dir() and data.get("run"))
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
    from halo_harness.start.auto_gate import AUTO_LINE
    from tests.helpers.custom_lineup import custom_lineup
    out = io.StringIO()
    with custom_lineup():
        rc = init_cli._step_offer_start(SimpleNamespace(yes=True), Console(file=out, width=120))
    ctx.check(f"non-interactive: No, init's exit 0, got {rc} {out.getvalue()!r}", rc == 0 and "halo start" in out.getvalue()
              and "--explain" in out.getvalue() and "Estimated cost" not in out.getvalue())
    out = io.StringIO()
    with custom_lineup(None):  # 3.3.15.0 R5: the console / --yes path on Auto: the line, not the offer
        rc = init_cli._step_offer_start(SimpleNamespace(yes=True), Console(file=out, width=400))
    ctx.check(f"on Auto: the line in its place, no question, got {rc} {out.getvalue()!r}", rc == 0 and AUTO_LINE in out.getvalue()
              and "halo gym --quick" in out.getvalue() and "Run the guided first run now?" not in out.getvalue())
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
              and "5 worker lane(s) 120k in / 6k out each" in got)
    got = K.estimate(parts={"main": "or:v/lead", "lanes": ["or:v/work", "or:v/lead"]}, models_by_ref=rows)
    want = (15_000 + 6_000 + 8_000 + 2_000) / 1e6 + (120_000 * 0.5 + 6_000) / 1e6 + (120_000 + 12_000) / 1e6
    ctx.check(f"3.3.15.0 R7: one lane per lane card, each on its model, got {got!r}", got.startswith(f"about ${want:.2f}")
              and "2 worker lane(s)" in got)
    ctx.check("the distinct models with their prices", K.price_lines({"main": "or:v/lead", "lanes": ["or:v/work", "or:v/lead"]}, rows)
              == ["or:v/lead: $1.00 in / $2.00 out per M tokens", "or:v/work: $0.50 in / $1.00 out per M tokens"])
    got = K.estimate(parts={"main": "ol:qwen3", "subagent": "or:v/work"}, models_by_ref=rows)
    ctx.check(f"a local lead costs nothing, got {got!r}", got.startswith(f"about ${5 * 0.066:.2f}"))
    ctx.check("every model local: free", K.estimate(parts={"main": "ol:a", "subagent": "hf:local/b"}, models_by_ref={})
              .startswith("free: every model it calls is local"))
    got = K.estimate(parts={"main": "or:v/lead", "subagent": "or:v/none"}, models_by_ref=rows)
    ctx.check(f"no price: named, never free, got {got!r}", got.startswith("unknown for or:v/none"))
    from tests.helpers.custom_lineup import custom_lineup
    with custom_lineup(_crew()):
        lines = K.card_lines(model="or:v/lead", models_by_ref=rows, today="2026-10-25")
    text = "\n".join(lines)
    ctx.check("the models it will call (--model plays every part)", "the lead (the plan, and the judge of a conflict): or:v/lead"
              in text and "5 worker lane(s) (a halo -p session each): " + ", ".join(["or:v/lead"] * 5) in text
              and "prices: or:v/lead: $1.00 in / $2.00 out per M tokens" in text)
    ctx.check("3.3.15.0 R7: the active lineup it rehearses, its lead and lanes, its cards", "The lineup it rehearses: crew (your "
              "active lineup)" in text and "lineup crew: the lead is boss (orchestrator)" in text
              and "main (boss) -> orchestrator ->" in text and "subagent (fixer) -> implementer ->" in text)
    ctx.check("seven steps, one sentence each", all(f"  {n}. " in text for n in range(1, 8)))
    ctx.check("the time and what it writes: no lineup copy", "Time: 5-20 minutes on cloud models" in text
              and "nothing for the lineup: the run reads it as it is" in text and str(_home() / "teams") not in text
              and str(_home() / "start" / "2026-10-25") in text)
    ctx.check("the lineup untouched", lines[-1] == K.UNTOUCHED)


@test
def test_explain_prints_only_the_card(ctx: Ctx):
    before = sorted((_home() / "start").glob("*/basket*"))
    rc, text, err = _start(["--explain"])
    ctx.check(f"exit 0, got {rc} {err!r}", rc == 0)
    ctx.check("the card and nothing else", text.startswith("The guided first run (halo start)") and "Step 1 of 7" not in text
              and "Estimated cost: free" in text)
    ctx.check("nothing was written", sorted((_home() / "start").glob("*/basket*")) == before)


@test
def test_lineup_overrides_the_active_one(ctx: Ctx):
    """3.3.15.0 R7: `--lineup standard` with crew active rehearses standard: two lane slots, two lanes, one line says so."""
    rc, text, err = _start(["--json", "--lineup", "standard"])
    data = json.loads(text) if text.strip().startswith("{") else {}
    step1 = "\n".join((data.get("steps") or [{}])[0].get("lines") or [])
    ctx.check(f"standard, not crew, got {rc} {data.get('lineup')} {err[-300:]!r}", rc == 0 and data.get("lineup") == "standard"
              and "the run rehearses standard (named with --lineup)" in step1)
    ctx.check(f"fewer lane slots: two lanes and the one line, got {step1[:600]!r}", "standard has 2 lane slot(s) for code" in step1
              and "the sample runs in 2 lane(s) instead of 5" in step1 and data["report"].get("status") == "finished")
    ctx.check("no copy written", _copies() == [])


@test
def test_a_missing_lineup_or_one_with_no_coder_is_one_line(ctx: Ctx):
    """3.3.15.0 R7: one line, exit 1, nothing under start/ -- for --lineup and for a gone active lineup alike."""
    days = lambda: sorted((_home() / "start").glob("*/basket*"))  # noqa: E731
    before = days()
    rc, text, _ = _start(["--yes", "--lineup", "nope"])
    ctx.check(f"--lineup nope, got {rc} {text!r}", rc == 1 and text == "halo start: no lineup named nope; `halo teams` lists them\n")
    rc, text, _ = _start(["--json"], lineup="gone")
    ctx.check(f"an active lineup that is gone, --json, got {rc} {text!r}", rc == 1 and json.loads(text) == {
        "ok": False, "ran": False, "reason": "no_lineup", "message": "no lineup named gone; `halo teams` lists them"})
    rc, text, _ = _start(["--yes"], lineup="balanced")
    ctx.check(f"balanced: no card that writes code, got {rc} {text!r}", rc == 1 and text.count("\n") == 1
              and text.startswith("halo start: balanced has no card that writes code") and "invalid" not in text)
    rc, text, _ = _start(["--explain", "--lineup", "balanced"])
    ctx.check("--explain says it too", rc == 1 and "no card that writes code" in text and "Estimated cost" not in text)
    ctx.check("nothing written under start/, no copy", days() == before and _copies() == [])


@test
def test_my_halo_dev_cycle_is_gone_from_code_and_docs(ctx: Ctx):
    """3.3.15.0 R7: no file under halo_harness/ or docs/ names the old copy (the CHANGELOG keeps its history)."""
    import subprocess
    root = Path(__file__).resolve().parent.parent
    out = subprocess.run(["git", "grep", "--untracked", "-l", "my-halo-dev-cycle", "--", "halo_harness", "docs"], cwd=str(root),
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    found = [line for line in out.stdout.splitlines() if "node_modules" not in line]
    ctx.check(f"none, got {found} (git grep exit {out.returncode}: 1 = no match)", out.returncode == 1 and found == [])
    from halo_harness.start import steps
    ctx.check("no DEFAULT_LINEUP in start/steps.py", not hasattr(steps, "DEFAULT_LINEUP"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
