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
        url = existing_url(state, "fleet")
        ctx.check(f"a live port gives the URL with the mode and token, got {url!r}", url == f"http://127.0.0.1:{port}/?mode=fleet#t=abc")
        ctx.check("read_info reads it", read_info(state)["port"] == port)
    finally:
        srv.close()
        info.unlink()
    info.write_text(json.dumps({"pid": 1, "port": port, "token": "abc"}), encoding="utf-8")
    ctx.check("a dead port gives no URL", existing_url(state) == "")
    info.unlink()


def _setup_cli(argv, **stubs):
    """3.3.0.0 R4: `cmd_setup(argv)` on a fake terminal, Studio and the browser stubbed
    (tests/helpers/setup_door_stubs.py): `(rc, stdout, record)`. 3.4.0.0 B2: no terminal screen runs any more."""
    from halo_harness.setup_cli import cmd_setup
    from tests.helpers.setup_door_stubs import door_stubs, fake_tty
    with door_stubs(**stubs) as rec, fake_tty() as out:
        rc = cmd_setup(list(argv))
    return rc, out.getvalue(), rec


@test
def test_halo_setup_team_opens_setup_on_the_team_block(ctx: Ctx):
    """3.4.0.0 B2: `halo setup <page>` opens Setup on that page; `--terminal` and a box with no browser print the
    console way (`setup_cli.CONSOLE`) instead of a terminal screen."""
    rc, text, rec = _setup_cli(["team"])
    url = rec["opened"][0] if rec["opened"] else ""
    ctx.check(f"halo setup team: Studio on ?mode=setup&block=team, got {rc} {rec['launched']}", rc == 0
              and rec["launched"] and rec["launched"][0]["edit"] == "setup:team" and "?mode=setup&block=team#t=" in url)
    ctx.check(f"its line, got {text!r}", f"Setup (Team) is open in your browser: {url}. `halo setup team --terminal` runs the "
              "terminal listing instead." in text)
    rc, text, rec = _setup_cli(["roles"])
    ctx.check(f"halo setup roles: the same block, got {rec['launched']}", rc == 0 and rec["launched"][0]["edit"] == "setup:team")
    for page in ("providers", "model", "permissions", "theme", "linux", "check", "machines", "local"):
        rc, text, rec = _setup_cli([page])
        ctx.check(f"halo setup {page}: that page, got {rc} {rec['launched']}", rc == 0 and rec["launched"][-1]["edit"] == f"setup:{page}")
    rc, text, rec = _setup_cli([])
    ctx.check(f"bare halo setup: the page, got {rec['launched']}", rc == 0 and rec["launched"][0]["edit"] == "setup")
    rc, text, rec = _setup_cli(["permissions", "--terminal"])
    ctx.check(f"--terminal: the console way, no Studio, got {text!r} {rec}", rc == 0 and not rec["launched"]
              and "Setup -> permissions in a terminal: halo config set permission_mode" in text)
    rc, text, rec = _setup_cli(["model"], env={"HALO_NO_BROWSER": "1"})
    ctx.check(f"no browser: the URL, then the console way, got {text!r}", rc == 0 and not rec["opened"]
              and "Setup (Default model) is at http://127.0.0.1:" in text and "Setup -> model in a terminal: halo config set model" in text)
    rc, text, rec = _setup_cli(["kitchen"])
    ctx.check(f"an unknown word: a usage error, nothing opened, got {rc}", rc == 2 and not rec["launched"])


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
