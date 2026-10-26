"""tests.test_wizard_studio_doors -- Halo 3.0.2.0, after the owner's Kali
review of the wizard: the Team step has a Custom roles switch and an Open
Studio (Roles) button (the terminal editors are no longer buttons; the
Orgs step is gone since 3.1.4.0); `studio/launch.py` finds a running Studio
by its studio.json and `halo studio --stop` ends it; the prompt and the
Agent tool explain delegation with roles off (the game themes' plain-bar
check went with the themes in 3.1.5.0).

Run: python -m tests.test_wizard_studio_doors
"""

from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import io
import json
import socket
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _run(coro):
    return asyncio.run(coro)


@test
def test_team_step_has_the_switch_and_the_studio_button(ctx: Ctx):
    from textual.widgets import Button, OptionList, Switch
    from halo_harness.roles import roles_mode_enabled, set_roles_enabled
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState

    async def body():
        set_roles_enabled(False)
        state = WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True)
        app = InitWizardApp(state)
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause(0.2)
            step = app.screen
            sw = step.query_one("#wiz-roles-switch", Switch)
            ctx.check("the Custom roles switch starts off on a fresh install", sw.value is False)
            step.query_one("#wiz-team-studio", Button)
            ctx.check("the terminal editors are no longer buttons", not step.query("#wiz-team-customize") and not step.query("#wiz-team-agents"))
            lst = step.query_one("#wiz-team-lineups-list", OptionList)
            sw.value = True
            await pilot.pause(0.2)
            ctx.check(f"switching on highlights the first lineup, got {lst.highlighted}", lst.highlighted == 1)
            name = str(lst.get_option_at_index(lst.highlighted).id)
            step.commit()
            ctx.check(f"Next with the switch on applies {name!r} and turns roles on", roles_mode_enabled() is True)
            lst.highlighted = 0
            await pilot.pause(0.2)
            ctx.check("highlighting the first row turns the switch off", sw.value is False)
            step.commit()
            ctx.check("and Next then turns roles off", roles_mode_enabled() is False)
    _run(body())


@test
def test_launch_finds_a_running_studio_and_stop_reports_none(ctx: Ctx):
    from halo_harness.providers.config import default_state_dir
    from halo_harness.studio.launch import existing_url, read_info
    from halo_harness.studio.server import cmd_studio, studio_info_path
    state = Path(default_state_dir())
    state.mkdir(parents=True, exist_ok=True)
    info = studio_info_path(state)
    if info.exists():
        info.unlink()
    ctx.check("no studio.json -> no URL", existing_url(state, "roles") == "")
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cmd_studio(["--stop"])
    ctx.check(f"--stop with nothing running says so and exits 1, got {code} {buf.getvalue()!r}", code == 1 and "no Studio" in buf.getvalue())
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        info.write_text(json.dumps({"pid": 1, "port": port, "token": "abc"}), encoding="utf-8")
        url = existing_url(state, "design")
        ctx.check(f"a live port gives the URL with the mode and token, got {url!r}", url == f"http://127.0.0.1:{port}/?mode=design#t=abc")
        ctx.check("read_info reads it", read_info(state)["port"] == port)
    finally:
        srv.close()
        info.unlink()
    info.write_text(json.dumps({"pid": 1, "port": port, "token": "abc"}), encoding="utf-8")
    ctx.check("a dead port gives no URL", existing_url(state) == "")
    info.unlink()


def _setup_cli(argv, **stubs):
    """3.3.0.0 R4: `cmd_setup(argv)` on a fake terminal, Studio and the browser stubbed
    (tests/helpers/setup_door_stubs.py), the terminal screen stubbed: `(rc, stdout, record, screens run)`."""
    from halo_harness.setup_cli import cmd_setup
    from halo_harness.tui.dialogs import init_wizard
    from tests.helpers.setup_door_stubs import door_stubs, fake_tty
    screens: list = []

    class _Wizard:
        def __init__(self, state):
            self.state = state

        def run(self):
            screens.append(tuple(self.state.step_keys))
    saved = init_wizard.InitWizardApp
    init_wizard.InitWizardApp = _Wizard
    try:
        with door_stubs(**stubs) as rec, fake_tty() as out:
            rc = cmd_setup(list(argv))
    finally:
        init_wizard.InitWizardApp = saved
    return rc, out.getvalue(), rec, screens


@test
def test_halo_setup_team_opens_setup_on_the_team_block(ctx: Ctx):
    rc, text, rec, screens = _setup_cli(["team"])
    url = rec["opened"][0] if rec["opened"] else ""
    ctx.check(f"halo setup team: Studio on ?mode=setup&block=team, no screen, got {rc} {rec['launched']} {screens}", rc == 0
              and rec["launched"] and rec["launched"][0]["edit"] == "setup:team" and "?mode=setup&block=team#t=" in url and not screens)
    ctx.check(f"its line, got {text!r}", f"Setup (Team) is open in your browser: {url}. `halo setup team --terminal` runs the "
              "terminal screen instead." in text)
    rc, text, rec, screens = _setup_cli(["roles"])
    ctx.check(f"halo setup roles: the same block, got {rec['launched']}", rc == 0 and rec["launched"][0]["edit"] == "setup:team")
    rc, text, rec, screens = _setup_cli([])
    ctx.check(f"bare halo setup: the page, got {rec['launched']}", rc == 0 and rec["launched"][0]["edit"] == "setup" and not screens)
    rc, text, rec, screens = _setup_cli(["team", "--terminal"])
    ctx.check(f"--terminal: the terminal screen, no Studio, got {screens} {rec}", rc == 0 and screens == [("team",)] and not rec["launched"])
    rc, text, rec, screens = _setup_cli(["team"], env={"HALO_NO_BROWSER": "1"})
    ctx.check(f"no browser: the URL, then the screen, got {text!r} {screens}", rc == 0 and screens == [("team",)] and not rec["opened"]
              and "Setup (Team) is at http://127.0.0.1:" in text and "The terminal screen runs here instead." in text)
    rc, text, rec, screens = _setup_cli(["kitchen"])
    ctx.check(f"an unknown word: a usage error, nothing opened, got {rc}", rc == 2 and not rec["launched"] and not screens)


@test
def test_prompt_and_agent_tool_explain_delegation_with_roles_off(ctx: Ctx):
    from halo_harness.agent.prompt import build_system_prompt
    from halo_harness.roles import set_roles_enabled
    text = build_system_prompt(model_label="m", cwd=REPO_DIR, tool_definitions=[{"name": "Agent"}])
    ctx.check("the prompt says delegation is expected and how to pick a cheaper model",
              "Delegation is expected" in text and "`model:`" in text and "not \navailable" not in text)
    from halo_harness.tools.agent import AgentTool
    set_roles_enabled(False)
    desc = AgentTool().description
    ctx.check(f"the Agent tool says roles are off and to pass model, got ...{desc[200:420]!r}", "custom roles are off" in desc and "`model`" in desc)
    set_roles_enabled(True)
    ctx.check("and on when they are on", "custom roles are on" in AgentTool().description)
    set_roles_enabled(False)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    print_results(results, passed, failed, skipped)
    sys.exit(1 if failed else 0)
