"""tests.test_studio_modes -- Halo 3.0.2.0: `halo studio --mode <section>` and `url_for(server, mode)`
put the mode in the query ahead of the token; `/studio <section>`, `/design`, `/roles gui`
open Studio there (`url` keeps the browser shut); `/roles table` is the text table; the help and the
system prompt name Studio; 3.0.7.0: design and roles are React sections (their DOM through
tools/capture_studio.py --dom); 3.0.8.0 R2: Team; 3.1.4.0 R3: Org and Flow are gone, five sections.
Run: python -m tests.test_studio_modes
"""

from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

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
from halo_harness.commands.builtins import HeadlessFacade, _cmd_design, _cmd_roles, _cmd_studio  # noqa: E402
from halo_harness.studio import server as studio_server  # noqa: E402

test, TESTS = new_registry()


class _NoBrowser:  # records webbrowser.open calls instead of opening anything
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
        design = studio_server.url_for(srv, "design")
        bogus = studio_server.url_for(srv, "kitchen")
        gone = [studio_server.url_for(srv, m) for m in ("org", "flow")]  # 3.1.4.0: removed sections
        ctx.check("plain URL has no query", "?" not in plain and "#t=" in plain)
        ctx.check(f"design URL carries ?mode=design before #t=, got {design!r}", "/?mode=design#t=" in design)
        ctx.check("an unknown mode is ignored", bogus == plain)
        ctx.check(f"org and flow are no modes any more, got {gone}", gone == [plain, plain])
    finally:
        srv.server_close()


@test
def test_the_shell_has_six_sections_and_opens_orchestra_fleet_team_and_session_by_mode(ctx: Ctx):
    """3.1.4.0 R3: Org and Flow are gone; the keys stay positional: Orchestra Alt+1, Roles Alt+2,
    Design Alt+3, Fleet Alt+4, Team Alt+5; 3.1.4.0 R2: Session Alt+6. `halo studio --mode
    orchestra|fleet|team|session` (and `/studio team`) put it in the query, and the shell reads
    every section from `?mode=`."""
    from halo_harness.providers.config import default_state_dir
    state = Path(default_state_dir())
    srv = studio_server.start_server(port=0, cwd=state.parent / "proj", state_dir=state)
    try:
        for mode in ("orchestra", "fleet", "team", "session"):
            url = studio_server.url_for(srv, mode)
            ctx.check(f"--mode {mode} carries ?mode={mode} before #t=, got {url!r}", f"/?mode={mode}#t=" in url)
    finally:
        srv.server_close()
    ui = REPO_DIR / "halo_harness" / "studio" / "ui" / "src"
    routes = (ui / "routes" / "index.tsx").read_text(encoding="utf-8")
    ctx.check("six sections, Design on Alt+3, Fleet on Alt+4, Team on Alt+5, Session on Alt+6", routes.count('kbd: "Alt+') == 6
              and 'id: "design", title: "Design", kbd: "Alt+3"' in routes
              and 'id: "fleet", title: "Fleet", kbd: "Alt+4"' in routes and 'id: "team", title: "Team", kbd: "Alt+5"' in routes
              and 'id: "session", title: "Session", kbd: "Alt+6"' in routes
              and 'id: "org"' not in routes and 'id: "flow"' not in routes)
    store = (ui / "lib" / "store.ts").read_text(encoding="utf-8")
    ctx.check("the shell reads ?mode= for every section", "mode=(orchestra|roles|design|fleet|team|session)" in store)
    ctx.check("Alt+1..6 switch sections", "Digit[1-6]" in (ui / "shell" / "keys.ts").read_text(encoding="utf-8"))
    ctx.check("no classic page ships beside the shell (3.0.7.0 R2)", not (REPO_DIR / "halo_harness" / "studio" / "static" / "legacy").exists())
    facade = _facade()
    with _NoBrowser():
        out = _cmd_studio("fleet url", facade)
    ctx.check(f"/studio fleet url names Fleet and its URL, got {out!r}", "Fleet:" in out and "?mode=fleet#t=" in out)
    with _NoBrowser():
        out = _cmd_studio("team url", facade)
    ctx.check(f"/studio team url names Team and its URL, got {out!r}", "Team:" in out and "?mode=team#t=" in out)


@test
def test_slash_studio_roles_design_open_that_mode(ctx: Ctx):
    facade = _facade()
    with _NoBrowser() as nb:
        out = _cmd_studio("roles url", facade)
        ctx.check(f"/studio roles url names Roles and its URL, got {out!r}", "Roles:" in out and "?mode=roles#t=" in out)
        ctx.check("`url` keeps the browser shut", nb.calls == [])
        out = _cmd_design("url", facade)
        ctx.check(f"/design url opens Design mode, got {out!r}", "Design:" in out and "?mode=design#t=" in out)
        out = _cmd_roles("gui url", facade)
        ctx.check(f"/roles gui url opens Roles mode, got {out!r}", "Roles:" in out and "?mode=roles#t=" in out)
        out = _cmd_studio("url", facade)
        ctx.check("bare /studio keeps the saved mode (no query)", "?mode=" not in out and "Roles | Design" in out)
        _cmd_studio("design", facade)
        ctx.check(f"without `url` the browser opens on the mode URL, got {nb.calls}", len(nb.calls) == 1 and "?mode=design#t=" in nb.calls[0])


@test
def test_roles_table_is_the_text_table(ctx: Ctx):
    facade = _facade()
    with _NoBrowser():
        table = _cmd_roles("table", facade)
        bare = _cmd_roles("", facade)
        ctx.check("`/roles table` prints exactly what bare /roles prints outside the TUI", table == bare and "Halo Studio" not in table)


@test
def test_tui_bare_roles_routes_to_the_gui(ctx: Ctx):
    src = (REPO_DIR / "halo_harness" / "tui" / "slash.py").read_text(encoding="utf-8")
    roles = src.split("async def _handle_roles(", 1)[1].split("async def ", 1)[0]
    ctx.check("bare /roles in the TUI becomes `gui`", 'args = sub = "gui"' in roles)
    ctx.check("no /org handler is left", "async def _handle_org(" not in src)


@test
def test_top_level_help_names_the_gui(ctx: Ctx):
    from halo_harness.cli import _build_parser
    text = " ".join(_build_parser().format_help().split())  # width-independent
    for word in ("studio", "design", "teams", "agents", "--mode roles|design", "/roles and /design"):
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
    ctx.check("names the two modes", "Roles (" in text and "Design (" in text and "Org (" not in text)
    ctx.check("names the command", "halo studio --mode roles|design" in text)
    ctx.check("names the slash commands", "`/roles` or `/design`" in text)


from tests.helpers.studio_modes_dom import dom as _dom, need_chrome as _need_chrome  # noqa: E402


@test
def test_design_opens_as_a_react_section(ctx: Ctx):
    """3.0.7.0 R3: `--mode design`, no framed classic page: Design's Start view without a project, then the
    thread and the artboards of a seeded one."""
    _need_chrome()
    design = _dom("design")
    start, seeded = design.get("start", {}), design.get("design", {})
    ctx.check(f"Design without a project: five tabs, the Start view, no frame, got {start or design}",
              start.get("section-tab") == 5 and start.get("design-start") == 1 and start.get("legacy-frame") == 0 and start.get("design-artboard") == 0)
    ctx.check(f"Design over a seeded project: the thread with two turns, two artboards, two pins, got {seeded}",
              seeded.get("design-thread") == 1 and seeded.get("design-turn") == 2 and seeded.get("design-artboard") == 2
              and seeded.get("design-pin") == 2 and seeded.get("design-start") == 0 and seeded.get("legacy-frame") == 0)
    ui = REPO_DIR / "halo_harness" / "studio" / "ui" / "src"
    routes = (ui / "routes" / "index.tsx").read_text(encoding="utf-8")
    ctx.check("no section is framed any more (3.0.7.0 R2)", "legacyPanels" not in routes and "panels: rolesPanels, view: RolesView" in routes
              and "...designPanels" in routes)
    ctx.check("the legacy bridge is gone", not (ui / "shell" / "legacy.ts").exists() and not (ui / "routes" / "legacy").exists())


@test
def test_roles_opens_as_a_react_section(ctx: Ctx):
    """3.0.7.0 R2: `--mode roles`: with only the shipped lineups (none active) one Start view and no panels; over a
    seeded lineup with two declared tiers and a card whose model the catalog lacks, the canvas with its eight cards
    in three tier boxes, the Problems panel's row, and, a bio clicked, the bio form with the model picker table."""
    _need_chrome()
    got = _dom("roles")
    start, roles = got.get("start", {}), got.get("roles", {})
    ctx.check(f"the Start view, no canvas and no frame, got {start or got}",
              start.get("section-tab") == 6 and start.get("roles-start") == 1 and start.get("roles-canvas") == 0
              and start.get("panel-about") == 0 and start.get("legacy-frame") == 0)
    ctx.check(f"the canvas, eight cards, three tier boxes, the edges, got {roles}",
              roles.get("roles-canvas") == 1 and roles.get("roles-card") == 8 and roles.get("roles-tier") == 3 and (roles.get("roles-edge") or 0) >= 7
              and roles.get("roles-start") == 0 and roles.get("legacy-frame") == 0)
    ctx.check(f"six panels with their about lines, the problem row, got {roles}", roles.get("panel-about") == 6 and (roles.get("roles-problem") or 0) >= 1)
    ctx.check(f"the bio form, the model table (one row per catalog model) and its Test button, got {roles}",
              roles.get("bio-form") == 1 and roles.get("model-row") == 7 and (roles.get("model-test") or 0) >= 1)


@test
def test_team_opens_as_a_react_section(ctx: Ctx):
    """3.0.8.0 R2: `--mode team`: no team file, the Start view with Make my first team, no board; over team_rig's
    team three member columns, four stage boxes, three block nodes, eight edges, three panels with their about lines."""
    _need_chrome()
    got = _dom("team")
    start, team = got.get("start", {}), got.get("team", {})
    ctx.check(f"the Start view, no board, got {start or got}", start.get("section-tab") == 6 and start.get("team-start") == 1
              and start.get("team-start-init") == 1 and start.get("team-board") == 0 and start.get("team-stage") == 0)
    ctx.check(f"the board, got {team}", team.get("team-member") == 3 and team.get("team-stage") == 4 and team.get("team-block") == 3
              and team.get("team-edge") == 8 and team.get("panel-about") == 3 and team.get("team-start") == 0 and team.get("legacy-frame") == 0)


@test
def test_orchestra_opens_a_planned_run_on_the_plan_canvas(ctx: Ctx):
    """3.0.9.0 R2: `--mode orchestra` over a seeded review run waiting for its plan: the plan panel instead
    of the console, five lanes in two layer boxes plus the empty "a new layer" box, one edge, the inspector,
    Approve and run; the Start view's form has the "Review the plan before it runs" switch."""
    _need_chrome()
    got = _dom("orchestra")
    plan, start = got.get("plan") or {}, got.get("start") or {}
    ctx.check(f"the plan panel, not the console, got {plan or got}", plan.get("orchestra-plan") == 1 and plan.get("orchestra-root") == 0
              and plan.get("panel-about") == 1 and plan.get("section-tab") == 6)
    ctx.check(f"five lanes, three boxes, one edge, the inspector and Approve, no problem, got {plan}",
              plan.get("plan-canvas") == 1 and plan.get("plan-lane") == 5 and plan.get("plan-layer") == 3 and plan.get("plan-edge") == 1
              and plan.get("plan-inspector") == 1 and plan.get("plan-approve") == 1 and plan.get("plan-problem") == 0)
    ctx.check(f"the review switch on the Start view, got {start.get('orchestra-review')}", start.get("orchestra-review") == 1)


@test
def test_start_here_on_a_fresh_home_and_gone_after_dismiss(ctx: Ctx):
    """3.1.1.0 R1: `--mode start` (tools/capture_start.py): a fresh home (only the shipped lineups, none active, no run)
    opens on the Start here overlay with its two buttons and no welcome card; after "Just look around" no overlay and the
    section's welcome instead; with a lineup active no overlay. The Roles Start view ends on its Next footer."""
    _need_chrome()
    got = _dom("start")
    first, gone, lineup = got.get("fresh") or {}, got.get("dismissed") or {}, got.get("lineup") or {}
    ctx.check(f"the home reads as fresh, got {got.get('status') or got}", (got.get("status") or {}).get("show") is True)
    ctx.check(f"fresh: the overlay, Run and Just look around, no welcome card, six tabs, got {first}",
              first.get("start-here") == 1 and first.get("start-here-run") == 1 and first.get("start-here-dismiss") == 1
              and first.get("section-help") == 0 and first.get("section-tab") == 6 and first.get("start-step") == 0)
    ctx.check(f"the Roles Start view under it, with its Next footer, got {first}", first.get("roles-start") == 1 and first.get("start-next") == 1)
    ctx.check(f"after dismiss: no overlay, the welcome instead, got {gone}", gone.get("start-here") == 0 and gone.get("section-help") == 1)
    ctx.check(f"a lineup active: no overlay, got {lineup}", lineup.get("start-here") == 0 and lineup.get("section-tab") == 6)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    print_results(results, passed, failed, skipped)
    sys.exit(1 if failed else 0)
