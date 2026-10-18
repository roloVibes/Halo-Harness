"""tests.test_wizard_studio_doors -- Halo 3.0.2.0, after the owner's Kali
review of the wizard: the Team step has a Custom roles switch and an Open
Studio (Roles) button (the terminal editors are no longer buttons), the
Orgs step has Open Studio (Org); `studio/launch.py` finds a running Studio
by its studio.json and `halo studio --stop` ends it; the game themes keep
the plain status bar; the prompt and the Agent tool explain delegation
with roles off.

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
def test_orgs_step_has_the_studio_button(ctx: Ctx):
    from textual.widgets import Button
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState

    async def body():
        state = WizardState(cwd=REPO_DIR, step_keys=("orgs",), no_live=True)
        app = InitWizardApp(state)
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause(0.2)
            app.screen.query_one("#wiz-orgs-studio", Button)
            ctx.check("the Orgs step offers Studio", True)
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
        url = existing_url(state, "org")
        ctx.check(f"a live port gives the URL with the mode and token, got {url!r}", url == f"http://127.0.0.1:{port}/?mode=org#t=abc")
        ctx.check("read_info reads it", read_info(state)["port"] == port)
    finally:
        srv.close()
        info.unlink()
    info.write_text(json.dumps({"pid": 1, "port": port, "token": "abc"}), encoding="utf-8")
    ctx.check("a dead port gives no URL", existing_url(state) == "")
    info.unlink()


@test
def test_game_themes_keep_the_plain_status_bar(ctx: Ctx):
    from halo_harness.tui import hud as hud_mod
    from halo_harness.tui.hud import accent_for, bar_skin_for, skin_for
    saved, hud_mod.STATUS_BAR_OVERRIDE = hud_mod.STATUS_BAR_OVERRIDE, None  # the HUD suites force the rows on in a shared run
    try:
        _check_plain_bars(ctx, accent_for, bar_skin_for, skin_for)
    finally:
        hud_mod.STATUS_BAR_OVERRIDE = saved


def _check_plain_bars(ctx, accent_for, bar_skin_for, skin_for):
    for theme in ("doom", "metroid", "mario"):
        ctx.check(f"{theme} still has a skin (borders, frame, level)", skin_for(theme) is not None)
        ctx.check(f"{theme}'s status bar is the plain one", bar_skin_for(theme) is None and skin_for(theme).status_bar == "plain")
        ctx.check(f"{theme} tints the model label", bool(accent_for(theme)))
    ctx.check("a non-game theme has no skin and no accent", bar_skin_for("claude-dark") is None and not accent_for("claude-dark"))


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
