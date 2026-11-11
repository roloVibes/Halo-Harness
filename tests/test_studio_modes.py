"""tests.test_studio_modes -- Halo 3.0.2.0: `halo studio --mode <section>` and `url_for(server, mode)`
put the mode in the query ahead of the token; `/studio <section>`, `/roles gui`
open Studio there (3.3.13.0 R2: `/design` and `--mode design` are the design pack's: tests/test_pack_design.py) (`url` keeps the browser shut); `/roles table` is the text table; the help and the
system prompt name Studio; 3.0.7.0: design and roles are React sections (their DOM through
tools/capture_studio.py --dom); 3.0.8.0 R2: Team; 3.1.4.0 R3: Org and Flow are gone; R2: Session, six sections;
3.3.16.0 R1: Agents took in Team, Roles and Orchestra; R2: and Fleet (six sections; the four words are doors that say the new one).
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

from tests.helpers.runner import SkipTest, Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.fake_home import build_fake_home  # noqa: E402
from halo_harness.commands.registry import Registry  # noqa: E402
from halo_harness.commands.builtins import HeadlessFacade, _cmd_roles, _cmd_studio  # noqa: E402
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
        roles = studio_server.url_for(srv, "roles")
        pack = studio_server.url_for(srv, "design--design")
        bogus = studio_server.url_for(srv, "kitchen")
        gone = [studio_server.url_for(srv, m) for m in ("org", "flow", "design")]  # 3.1.4.0; 3.3.13.0 R2: design
        ctx.check("plain URL has no query", "?" not in plain and "#t=" in plain)
        ctx.check(f"roles URL carries ?mode=roles before #t=, got {roles!r}", "/?mode=roles#t=" in roles)
        ctx.check(f"a pack's section rides the query too (3.3.13.0 R2), got {pack!r}", "/?mode=design--design#t=" in pack)
        ctx.check("an unknown mode is ignored", bogus == plain)
        ctx.check(f"org, flow and design are no core modes any more, got {gone}", gone == [plain, plain, plain])
    finally:
        srv.server_close()


@test
def test_the_shell_has_six_sections_and_opens_each_by_mode(ctx: Ctx):
    """3.1.4.0 R3: Org and Flow are gone; the keys stay positional; 3.3.16.0 R2: Session Alt+1, Agents Alt+2, Local
    Alt+3, Packs Alt+4, Setup Alt+5, Settings Alt+6 (Fleet folded into Agents). `halo studio --mode agents|orchestra|fleet|team|session`
    (and `/studio team`) put it in the query, and the shell reads every section from `?mode=` (roles, orchestra and team
    land on Agents' views: ui/src/lib/agentsDoor.ts)."""
    from halo_harness.providers.config import default_state_dir
    state = Path(default_state_dir())
    srv = studio_server.start_server(port=0, cwd=state.parent / "proj", state_dir=state)
    try:
        for mode in ("agents", "orchestra", "fleet", "team", "session"):
            url = studio_server.url_for(srv, mode)
            ctx.check(f"--mode {mode} carries ?mode={mode} before #t=, got {url!r}", f"/?mode={mode}#t=" in url)
    finally:
        srv.server_close()
    ui = REPO_DIR / "halo_harness" / "studio" / "ui" / "src"
    routes = (ui / "routes" / "index.tsx").read_text(encoding="utf-8")
    ctx.check("six sections (3.3.16.0 R2), Session on Alt+1, Agents on Alt+2, Local on Alt+3, Packs on Alt+4, Setup on Alt+5, Settings on Alt+6",
              routes.count('kbd: "Alt+') == 6 and 'id: "packs", title: "Packs", kbd: "Alt+4"' in routes
              and 'id: "setup", title: "Setup", kbd: "Alt+5"' in routes and 'id: "settings", title: "Settings", kbd: "Alt+6"' in routes
              and 'id: "local", title: "Local", kbd: "Alt+3"' in routes
              and 'id: "session", title: "Session", kbd: "Alt+1"' in routes and 'id: "agents", title: "Agents", kbd: "Alt+2"' in routes
              and 'id: "fleet"' not in routes and 'id: "team"' not in routes and 'id: "roles"' not in routes
              and 'id: "orchestra"' not in routes and 'id: "design"' not in routes
              and 'id: "org"' not in routes and 'id: "flow"' not in routes)
    start = (ui / "lib" / "sectionStart.ts").read_text(encoding="utf-8")
    ctx.check("the shell reads ?mode= for a core section or a pack's (<pack>--<section>) and the moved word design",
              "MODE_RE" in start and "(?:--[A-Za-z0-9]" in start and "design: { pack: \"design\", section: \"design--design\" }" in start)
    ctx.check("Alt+1..6 switch the core sections, Alt+7 to Alt+0 the pack sections (3.3.16.0 R2)",
              "Digit[0-9]" in (ui / "shell" / "keys.ts").read_text(encoding="utf-8"))
    ctx.check("no classic page ships beside the shell (3.0.7.0 R2)", not (REPO_DIR / "halo_harness" / "studio" / "static" / "legacy").exists())
    facade = _facade()
    with _NoBrowser():
        out = _cmd_studio("fleet url", facade)
    ctx.check(f"/studio fleet url: Agents -> Live on the fleet, its URL and the new door once, got {out!r}", "Agents -> Live, the fleet scope:" in out
              and "?mode=fleet#t=" in out and out.count("Fleet is Agents -> Live now, the fleet scope on") == 1 and "Setup -> Machines" in out)
    with _NoBrowser():
        out = _cmd_studio("team url", facade)
    ctx.check(f"/studio team url: Agents -> Live (3.4.0.0 D), its URL and the new door, got {out!r}", "Agents -> Live:" in out and "?mode=team#t=" in out
              and "Team is Agents -> Live now (Alt+2 in Studio; halo studio --mode agents)" in out and "Team's board is gone" in out)
    with _NoBrowser():
        out = _cmd_studio("agents url", facade)
    ctx.check(f"/studio agents url names Agents, no door line, got {out!r}", "Agents:" in out and "?mode=agents#t=" in out and " now (Alt+2" not in out)


@test
def test_setup_is_the_banners_fifth_frame_and_has_its_doors(ctx: Ctx):
    """3.3.0.0 R4: studio-setup.png (tools/capture_studio.py --mode setup) is a banner tile (3.3.16.0 R1: the fifth), the banner
    is up to date with it, and `halo init` / `halo setup team` URLs carry Setup's door words."""
    import subprocess
    sys.path.insert(0, str(REPO_DIR / "tools"))
    try:
        import studio_modes_banner as B
    except ModuleNotFoundError as e:  # the banner tool draws with Pillow, an optional extra CI does not install
        raise SkipTest(f"the banner tool needs {e.name} (pip install Pillow)")
    ctx.check(f"six frames, Agents on Alt 2, Local on Alt 3, Setup on Alt 5 and Settings last on Alt 6 (3.3.16.0 R2), got {[f[1] for f in B.FRAMES]}",
              len(B.FRAMES) == 6 and B.FRAMES[1][:3] == ("studio-agents.png", "Agents", "Alt 2") and B.FRAMES[2][:3] == ("studio-local.png", "Local", "Alt 3")
              and B.FRAMES[4][:3] == ("studio-setup.png", "Setup", "Alt 5") and B.FRAMES[-1][:3] == ("studio-settings.png", "Settings", "Alt 6"))
    for name in ("studio-agents.png", "studio-setup.png", "studio-settings.png", "studio-local.png"):
        f = REPO_DIR / "docs" / "media" / name
        ctx.check(f"{name} exists and is under 1 MB", f.is_file() and 10_000 < f.stat().st_size < 1024 * 1024)
    shot = REPO_DIR / "docs" / "media" / "studio-setup.png"
    ctx.check("the Setup capture exists and is under 1 MB", shot.is_file() and 10_000 < shot.stat().st_size < 1024 * 1024)
    banner = REPO_DIR / "docs" / "media" / "studio-modes.png"
    ctx.check("the banner is under 1 MB", banner.is_file() and banner.stat().st_size < 1024 * 1024)
    r = subprocess.run([sys.executable, str(REPO_DIR / "tools" / "studio_modes_banner.py"), "--check"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120, cwd=str(REPO_DIR))
    ctx.check(f"the banner is rendered from the six captures, got {r.returncode} {r.stdout.strip()!r}", r.returncode == 0)
    from halo_harness.providers.config import default_state_dir
    state = Path(default_state_dir())
    srv = studio_server.start_server(port=0, cwd=state.parent / "proj", state_dir=state)
    try:
        first, team = studio_server.url_for(srv, "setup", "setup:first"), studio_server.url_for(srv, "setup", "setup:team")
    finally:
        srv.server_close()
    ctx.check(f"halo init's door, got {first!r}", "/?mode=setup&first=1#t=" in first)
    ctx.check(f"halo setup team's door, got {team!r}", "/?mode=setup&block=team#t=" in team)
    capture = (REPO_DIR / "tools" / "capture_studio.py").read_text(encoding="utf-8")
    ctx.check("capture_studio renders it (--mode setup)", '"setup"' in capture and "capture_setup" in capture)


@test
def test_slash_studio_and_roles_open_that_mode(ctx: Ctx):
    facade = _facade()
    with _NoBrowser() as nb:
        out = _cmd_studio("roles url", facade)
        ctx.check(f"/studio roles url: Agents -> Cast, its URL and the new door once, got {out!r}", "Agents -> Cast:" in out
                  and "?mode=roles#t=" in out and out.count("Roles is Agents -> Cast now (Alt+2 in Studio; halo studio --mode agents)") == 1)
        ctx.check("`url` keeps the browser shut", nb.calls == [])
        out = _cmd_roles("gui url", facade)
        ctx.check(f"/roles gui url opens Agents on Cast, got {out!r}", "Agents -> Cast:" in out and "?mode=roles#t=" in out)
        out = _cmd_studio("orchestra url", facade)
        ctx.check(f"/studio orchestra url: Agents -> Live and the new door (3.4.0.0 D: Runs went), got {out!r}", "Agents -> Live: Run a goal" in out
                  and "Orchestra is Agents -> Live now" in out and "Runs is gone: a goal runs on Live" in out)
        out = _cmd_studio("url", facade)
        ctx.check("bare /studio keeps the saved mode (no query)", "?mode=" not in out)
        out = _cmd_studio("design", facade)
        ctx.check(f"3.3.13.0 R2: /studio design with the pack off says how to turn it on, got {out!r}",
                  "design pack" in out and "halo pack enable design" in out and nb.calls == [])
        _cmd_studio("fleet", facade)
        ctx.check(f"without `url` the browser opens on the mode URL, got {nb.calls}", len(nb.calls) == 1 and "?mode=fleet#t=" in nb.calls[0])


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
    for word in ("studio", "teams", "agents", "pack", "--mode agents", "/studio and /roles", "halo pack install design"):
        ctx.check(f"halo --help mentions {word!r}", word in text)
    for mod, fn in (("halo_harness.roles_cli", "cmd_roles"), ("halo_harness.teams_cli", "cmd_teams"), ("halo_harness.agents_cli", "cmd_agents")):
        import importlib
        buf = io.StringIO()
        err = io.StringIO()
        from contextlib import redirect_stderr
        with redirect_stdout(buf), redirect_stderr(err):
            getattr(importlib.import_module(mod), fn)(["--help"])
        ctx.check(f"{mod} --help points at the GUI", "halo studio --mode agents" in err.getvalue() + buf.getvalue())


@test
def test_system_prompt_tells_the_model_about_studio(ctx: Ctx):
    from halo_harness.agent.prompt import build_harness_self_description
    text = build_harness_self_description([{"name": "Bash"}, {"name": "Read"}])
    ctx.check("names Halo Studio", "**Halo Studio**" in text)
    ctx.check("names its sections and a pack's (3.3.13.0 R2; 3.3.16.0 R1: Agents)", "Agents (" in text and "Session (" in text and "design pack's Design" in text and "Org (" not in text)
    ctx.check("names the command", "halo studio --mode agents" in text and "--mode design--design" in text)
    ctx.check("names the slash commands", "`/studio` or `/roles`" in text and "`/design`" in text)


from tests.helpers.studio_modes_dom import dom as _dom, need_chrome as _need_chrome  # noqa: E402


@test
def test_design_opens_as_the_packs_page(ctx: Ctx):
    """3.0.7.0 R3, the design pack's since 3.3.13.0 R2: its tests/capture_design.py --dom (the pack enabled in the
    capture's home, `?mode=design--design`): the Start view without a project, then the thread and the artboards of
    a seeded one, drawn by the pack's own module."""
    import json
    import subprocess
    _need_chrome()
    from tests.helpers.chrome_driver import driver_env
    script = REPO_DIR / "halo_harness" / "templates" / "packs" / "design" / "tests" / "capture_design.py"
    r = subprocess.run([sys.executable, str(script), "--dom"], capture_output=True, encoding="utf-8", errors="replace",
                       timeout=300, env=driver_env(REPO_DIR), cwd=str(REPO_DIR))
    try:
        design = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        design = {"error": (r.stdout + r.stderr)[-400:]}
    start, seeded = design.get("start", {}), design.get("design", {})
    ctx.check(f"Design without a project: the pack's page, the Start view, got {start or design}",
              start.get("pack-view") == 1 and start.get("design-start") == 1 and start.get("design-artboard") == 0)
    ctx.check(f"Design over a seeded project: the thread with two turns, two artboards, two pins, got {seeded}",
              seeded.get("design-thread") == 1 and seeded.get("design-turn") == 2 and seeded.get("design-artboard") == 2
              and seeded.get("design-pin") == 2 and seeded.get("design-start") == 0)
    ui = REPO_DIR / "halo_harness" / "studio" / "ui" / "src"
    routes = (ui / "routes" / "index.tsx").read_text(encoding="utf-8")
    ctx.check("no section is framed any more (3.0.7.0 R2)", "legacyPanels" not in routes and "view: AgentsView" in routes
              and "designPanels" not in routes)
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
              and start.get("panel-title") == 0 and start.get("legacy-frame") == 0)
    ctx.check(f"the canvas, eight cards, three tier boxes, the edges, got {roles}",
              roles.get("roles-canvas") == 1 and roles.get("roles-card") == 8 and roles.get("roles-tier") == 3 and (roles.get("roles-edge") or 0) >= 7
              and roles.get("roles-start") == 0 and roles.get("legacy-frame") == 0)
    ctx.check(f"six panels (their titles; 3.3.2.0 R3: no about line), the problem row, got {roles}", roles.get("panel-title") == 6 and (roles.get("roles-problem") or 0) >= 1)
    ctx.check(f"the bio form, the model table (one row per catalog model) and its Test button, got {roles}",
              roles.get("bio-form") == 1 and roles.get("model-row") == 7 and (roles.get("model-test") or 0) >= 1)


@test
def test_orchestra_opens_a_planned_run_on_the_plan_canvas(ctx: Ctx):
    """3.0.9.0 R2; 3.4.0.0 D "the runs fold": a seeded review run waiting for its plan is its lead on Agents -> Live,
    waiting on you with Review the plan; nothing opens by itself (no plan panel, no goal panel), and the old
    `--mode orchestra` door lands on Live with Run a goal on its bar (tests/helpers/studio_plan.py drives the rest)."""
    _need_chrome()
    got = _dom("orchestra")
    plan, old = got.get("plan") or {}, got.get("old_door") or {}
    ctx.check(f"the lead on Live with Review the plan, nothing open, got {plan or got}", plan.get("agents-live-lead") == 1
              and plan.get("agents-live-review") == 1 and plan.get("orchestra-plan") == 0 and plan.get("run-goal-drawer") == 0
              and plan.get("section-tab") == 6 and plan.get("orchestra-root") == 0)
    ctx.check(f"the old door: Live, Run a goal on its bar, no Start view, got {old}", old.get("roles-live-map") == 1
              and old.get("live-run-goal") == 1 and old.get("start-view") == 0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    print_results(results, passed, failed, skipped)
    sys.exit(1 if failed else 0)
