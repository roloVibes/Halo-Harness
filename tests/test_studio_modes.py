"""tests.test_studio_modes -- Halo 3.0.2.0: the GUI is one command away from
every door. `halo studio --mode roles|org|design` and `url_for(server, mode)`
put the mode in the query ahead of the token fragment; `/studio roles|org|
design`, `/design`, `/roles gui` and `/org gui` open Studio in that mode
(`url` keeps the browser shut); `/roles table` is the text table; the
top-level help names studio/design/teams/agents and the GUI; the system
prompt tells every model what Halo Studio is and how to open it; the page
honours `?mode=roles` over a saved mode.

Run: python -m tests.test_studio_modes
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.fake_home import build_fake_home  # noqa: E402
from halo_harness.commands.registry import Registry  # noqa: E402
from halo_harness.commands.builtins import HeadlessFacade, _cmd_design, _cmd_org, _cmd_roles, _cmd_studio  # noqa: E402
from halo_harness.studio import server as studio_server  # noqa: E402

test, TESTS = new_registry()


class _NoBrowser:
    """Record webbrowser.open calls instead of opening anything."""

    def __init__(self):
        self.calls = []

    def __enter__(self):
        self._orig = studio_server.webbrowser.open
        studio_server.webbrowser.open = lambda url, *a, **k: self.calls.append(url) or True
        return self

    def __exit__(self, *a):
        studio_server.webbrowser.open = self._orig


def _facade():
    fh = build_fake_home()
    registry = Registry.discover(fh["proj"], fh["home"])
    return HeadlessFacade(cwd=fh["proj"], registry=registry, model_ref="or:mock/model", permission_mode="default")


@test
def test_url_for_puts_the_mode_in_the_query_ahead_of_the_token(ctx: Ctx):
    from halo_harness.providers.config import default_state_dir
    state = Path(default_state_dir())
    srv = studio_server.start_server(port=0, cwd=state.parent / "proj", state_dir=state)
    try:
        plain = studio_server.url_for(srv)
        org = studio_server.url_for(srv, "org")
        bogus = studio_server.url_for(srv, "kitchen")
        ctx.check("plain URL has no query", "?" not in plain and "#t=" in plain)
        ctx.check(f"org URL carries ?mode=org before #t=, got {org!r}", "/?mode=org#t=" in org)
        ctx.check("an unknown mode is ignored", bogus == plain)
    finally:
        srv.server_close()


@test
def test_slash_studio_roles_org_design_open_that_mode(ctx: Ctx):
    facade = _facade()
    with _NoBrowser() as nb:
        out = _cmd_studio("org url", facade)
        ctx.check(f"/studio org url names Org and its URL, got {out!r}", "Org:" in out and "?mode=org#t=" in out)
        ctx.check("`url` keeps the browser shut", nb.calls == [])
        out = _cmd_design("url", facade)
        ctx.check(f"/design url opens Design mode, got {out!r}", "Design:" in out and "?mode=design#t=" in out)
        out = _cmd_roles("gui url", facade)
        ctx.check(f"/roles gui url opens Roles mode, got {out!r}", "Roles:" in out and "?mode=roles#t=" in out)
        out = _cmd_org("gui url", facade)
        ctx.check(f"/org gui url opens Org mode, got {out!r}", "?mode=org#t=" in out)
        out = _cmd_studio("url", facade)
        ctx.check("bare /studio keeps the saved mode (no query)", "?mode=" not in out and "Roles | Org | Design" in out)
        _cmd_studio("design", facade)
        ctx.check(f"without `url` the browser opens on the mode URL, got {nb.calls}", len(nb.calls) == 1 and "?mode=design#t=" in nb.calls[0])


@test
def test_roles_table_is_the_text_table_and_org_list_still_lists(ctx: Ctx):
    facade = _facade()
    with _NoBrowser():
        table = _cmd_roles("table", facade)
        bare = _cmd_roles("", facade)
        ctx.check("`/roles table` prints exactly what bare /roles prints outside the TUI", table == bare and "Halo Studio" not in table)
        listed = _cmd_org("list", facade)
        ctx.check("`/org list` is still the text list", "Organizations" in listed and "Halo Studio" not in listed)


@test
def test_tui_bare_roles_and_org_route_to_the_gui(ctx: Ctx):
    src = (REPO_DIR / "halo_harness" / "tui" / "slash.py").read_text(encoding="utf-8")
    roles = src.split("async def _handle_roles(", 1)[1].split("async def ", 1)[0]
    org = src.split("async def _handle_org(", 1)[1].split("async def ", 1)[0]
    ctx.check("bare /roles in the TUI becomes `gui`", 'args = sub = "gui"' in roles)
    ctx.check("bare /org in the TUI becomes `gui`", 'args = sub = "gui"' in org)


@test
def test_top_level_help_names_the_gui(ctx: Ctx):
    from halo_harness.cli import _build_parser
    text = _build_parser().format_help()
    for word in ("studio", "design", "teams", "agents", "paperclip", "--mode roles|org|design", "/roles, /org and /design"):
        ctx.check(f"halo --help mentions {word!r}", word in text)
    for mod, fn in (("halo_harness.roles_cli", "cmd_roles"), ("halo_harness.teams_cli", "cmd_teams"), ("halo_harness.agents_cli", "cmd_agents")):
        import importlib
        buf = io.StringIO()
        err = io.StringIO()
        from contextlib import redirect_stderr
        with redirect_stdout(buf), redirect_stderr(err):
            getattr(importlib.import_module(mod), fn)(["--help"])
        ctx.check(f"{mod} --help points at the GUI", "halo studio --mode roles" in err.getvalue() + buf.getvalue())


@test
def test_system_prompt_tells_the_model_about_studio(ctx: Ctx):
    from halo_harness.agent.prompt import build_harness_self_description
    text = build_harness_self_description([{"name": "Bash"}, {"name": "Read"}])
    ctx.check("names Halo Studio", "**Halo Studio**" in text)
    ctx.check("names the three modes", "Roles (" in text and "Org (" in text and "Design (" in text)
    ctx.check("names the command", "halo studio --mode roles|org|design" in text)
    ctx.check("names the slash commands", "`/roles`, `/org` or `/design`" in text)


@test
def test_page_honours_mode_query_over_the_saved_mode(ctx: Ctx):
    js = (REPO_DIR / "halo_harness" / "studio" / "static" / "legacy" / "app.js").read_text(encoding="utf-8")
    ctx.check("app.js reads ?mode=roles|org|design", "mode=(roles|org|design)" in js)
    ctx.check("the asked mode beats the saved one", "const mode = asked || saved;" in js)


@test
def test_model_picker_is_a_grouped_dropdown_of_the_whole_catalog(ctx: Ctx):
    js = (REPO_DIR / "halo_harness" / "studio" / "static" / "legacy" / "inspector.js").read_text(encoding="utf-8")
    picker = js.split("function modelPicker(", 1)[1].split("function chips(", 1)[0]
    ctx.check("the picker is a <select> with <optgroup>s", "<select" in picker and "<optgroup" in picker)
    ctx.check("no row cap (the old popup showed the first 60 rows only)", "slice(0, 60)" not in js)
    ctx.check("a filter box narrows the list", 'class="mono filter"' in picker)
    ctx.check("a hand-typed ref is still possible", "Type a ref..." in picker)
    ctx.check("groups are route and vendor", 'route === "or" && rest.includes("/")' in js)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    print_results(results, passed, failed, skipped)
    sys.exit(1 if failed else 0)
