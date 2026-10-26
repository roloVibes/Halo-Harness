"""tests.test_setup_door -- the doors into Studio's Setup (Halo 3.3.0.0 R4,
halo_harness/studio/setup_door.py): the Setup targets and their URLs
(`?mode=setup&first=1`, `&block=team`), the no-browser rule, `open_setup`
starting or reusing Studio (no real Studio, no real browser: every seam is
tests/helpers/setup_door_stubs.py), the one line each door prints, `POST
focus` carrying the block and the first run, and `/setup` in the TUI (the
door; `--terminal` keeps the screen). `halo init` is tests/test_init_cli.py,
`halo setup team` tests/test_wizard_studio_doors.py, `halo start`
tests/test_start_cli.py.
Run: python -m tests.test_setup_door
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.setup_door_stubs import PORT, door_stubs  # noqa: E402

test, TESTS = new_registry()


@test
def test_targets_and_their_urls(ctx: Ctx):
    from halo_harness.studio import launch
    from halo_harness.studio.edit_target import parse, resolve
    from halo_harness.studio.setup_door import SetupTarget
    got = {t: parse(t)[0] for t in ("setup", "setup:first", "setup:team", "setup:roles", "setup:check")}
    ctx.check(f"the texts parse to their targets, got {got}", got["setup"] == SetupTarget() and got["setup:first"] == SetupTarget(first=True)
              and got["setup:team"] == SetupTarget(block="team") and got["setup:roles"] == SetupTarget(block="team")
              and got["setup:check"] == SetupTarget(block="check"))
    bad, why = parse("setup:kitchen")
    ctx.check(f"an unknown block says the blocks, got {why!r}", bad is None and "providers" in why and "team" in why)
    ctx.check("a bare `setup` resolves too (the TUI's /edit setup)", resolve("setup")[0] == SetupTarget())
    first = launch.url_from_info({"port": PORT, "token": "t"}, "setup", "setup:first")
    team = launch.url_from_info({"port": PORT, "token": "t"}, "setup", "setup:team")
    ctx.check(f"halo init's URL, got {first}", first == f"http://127.0.0.1:{PORT}/?mode=setup&first=1#t=t")
    ctx.check(f"halo setup team's URL, got {team}", team == f"http://127.0.0.1:{PORT}/?mode=setup&block=team#t=t")
    f = SetupTarget(block="team").focus()
    ctx.check(f"the focus frame names the section and the block, got {f}", f == {"edit": "", "mode": "setup", "session": "",
                                                                                     "block": "team", "first": False})
    ctx.check("the outcome names the block", SetupTarget(block="team").display == "Setup (Team)" and SetupTarget().display == "Setup")


@test
def test_the_no_browser_rule(ctx: Ctx):
    from halo_harness.studio.setup_door import no_browser_reason as why
    ctx.check("a Windows desktop: a browser may open", why({}, "win32") == "" and why({}, "darwin") == "")
    ctx.check("HALO_NO_BROWSER", why({"HALO_NO_BROWSER": "1"}, "win32") == "HALO_NO_BROWSER is set" and why({"HALO_NO_BROWSER": "0"}, "win32") == "")
    ctx.check("SSH_CONNECTION", why({"SSH_CONNECTION": "192.0.2.10 5 192.0.2.20 22"}, "win32") == "this is an SSH session")
    ctx.check("Linux with no display", why({}, "linux") == "no DISPLAY or WAYLAND_DISPLAY" and why({"DISPLAY": ":0"}, "linux") == ""
              and why({"WAYLAND_DISPLAY": "wayland-0"}, "linux") == "")


@test
def test_open_setup_starts_studio_and_opens_the_browser(ctx: Ctx):
    from halo_harness.studio.setup_door import SetupTarget, open_setup
    with door_stubs() as rec:
        out = open_setup(SetupTarget(first=True), cwd=Path.cwd(), why="")
    ctx.check(f"started, the browser opened by this process, got {out} {rec}", out["how"] == "started" and out["why"] == ""
              and rec["launched"] and rec["launched"][0]["edit"] == "setup:first" and rec["launched"][0]["open_browser"] is False
              and rec["opened"] == [out["url"]] and "?mode=setup&first=1#t=" in out["url"])
    with door_stubs(browser=False) as rec:
        out = open_setup(SetupTarget(first=True), cwd=Path.cwd(), why="")
    ctx.check(f"no browser took it: printed, and why, got {out}", out["how"] == "printed" and out["why"] == "no browser took the URL")
    with door_stubs() as rec:
        out = open_setup(SetupTarget(first=True), cwd=Path.cwd(), why="this is an SSH session")
    ctx.check(f"no browser here: Studio started, no browser asked, got {out} {rec}", out["how"] == "printed" and not rec["opened"]
              and out["why"] == "this is an SSH session" and rec["launched"][0]["open_browser"] is False)
    with door_stubs(starts=False) as rec:
        out = open_setup(SetupTarget(), cwd=Path.cwd(), why="")
    ctx.check(f"Studio did not start: failed, got {out}", out["how"] == "failed" and out["url"] == "" and not rec["opened"])


@test
def test_open_setup_reuses_the_running_studio(ctx: Ctx):
    from halo_harness.studio.setup_door import SetupTarget, open_setup
    with door_stubs(running=True, pages=1) as rec:
        out = open_setup(SetupTarget(block="team"), cwd=Path.cwd(), why="")
    ctx.check(f"a page open: it took the focus frame, nothing launched, got {out} {rec}", out["how"] == "focused" and not rec["launched"]
              and rec["focused"] == [{"edit": "", "mode": "setup", "session": "", "block": "team", "first": False}] and not rec["opened"])
    with door_stubs(running=True, pages=0) as rec:
        out = open_setup(SetupTarget(block="team"), cwd=Path.cwd(), why="")
    ctx.check(f"no page open: the browser opens the URL, got {out}", out["how"] == "opened" and rec["opened"] == [out["url"]]
              and "?mode=setup&block=team#t=" in out["url"])
    with door_stubs(running=True) as rec:
        out = open_setup(SetupTarget(block="team"), cwd=Path.cwd(), why="no DISPLAY or WAYLAND_DISPLAY")
    ctx.check(f"no browser here: the running Studio's URL only, got {out}", out["how"] == "printed" and not rec["focused"] and not rec["opened"])


@test
def test_cli_door_lines(ctx: Ctx):
    from halo_harness.studio.setup_door import SetupTarget, cli_door
    lines: list = []
    with door_stubs() as rec:
        ok = cli_door(SetupTarget(first=True), terminal_cli="halo init --terminal", fallback="wizard", say=lines.append)
    url = rec["opened"][0] if rec["opened"] else "?"
    ctx.check(f"opened: the brief's line, got {lines}", ok is True and lines[0] ==
              f"Setup is open in your browser: {url}. `halo init --terminal` runs the terminal wizard instead.")
    lines = []
    with door_stubs(env={"HALO_NO_BROWSER": "1"}) as rec:
        ok = cli_door(SetupTarget(first=True), terminal_cli="halo init --terminal", fallback="wizard", say=lines.append)
    text = "\n".join(lines)
    ctx.check(f"no browser: the URL, the port-forward hint, the wizard runs, got {lines}", ok is False and not rec["opened"]
              and f"Setup is at http://127.0.0.1:{PORT}/?mode=setup&first=1#t=" in text and "HALO_NO_BROWSER is set" in text
              and f"ssh -L {PORT}:127.0.0.1:{PORT} <host>" in text and lines[-1] == "The terminal wizard runs here instead.")
    lines = []
    with door_stubs(starts=False):
        ok = cli_door(SetupTarget(block="team"), terminal_cli="halo setup team --terminal", fallback="screen", say=lines.append)
    ctx.check(f"Studio did not start: said, the screen runs, got {lines}", ok is False and lines[0].startswith("Studio did not start")
              and lines[-1] == "The terminal screen runs here instead.")


@test
def test_post_focus_carries_the_block_and_the_first_run(ctx: Ctx):
    from halo_harness.studio.focus_api import post_focus
    req = lambda body: SimpleNamespace(body=body, server=None)  # noqa: E731
    st, data = post_focus(req({"mode": "setup", "block": "roles", "first": True}))
    ctx.check(f"mode setup with a block: 200 with it, got {st} {data}", st == 200 and data["block"] == "team" and data["first"] is True)
    st, data = post_focus(req({"mode": "setup", "block": "kitchen"}))
    ctx.check(f"an unknown block: 422, got {st} {data}", st == 422 and data.get("problems"))
    st, data = post_focus(req({"edit": "setup:team"}))
    ctx.check(f"an edit text setup:team: 200, mode setup, got {st} {data}", st == 200 and data["mode"] == "setup" and data["edit"] == "setup:team")


class _App:
    """What tui/slash.py and tui/studio_open.py touch on the app; workers run at once."""

    def __init__(self):
        self.cwd = Path.cwd()
        self.lines: list = []
        self.notes: list = []
        self.pushed: list = []
        self.transcript = SimpleNamespace(add_note=self._note)

    async def _note(self, text, kind="note"):
        self.notes.append(text)

    def call_later(self, fn, *a, **k):
        self.lines.append(a[0])

    def call_from_thread(self, fn, *a, **k):
        return fn(*a, **k)

    def run_worker(self, work, **kw):
        return work()

    def push_screen(self, screen):
        self.pushed.append(screen)

    def notify(self, text, **kw):
        self.lines.append(text)


@test
def test_slash_setup_opens_setup_and_terminal_keeps_the_screen(ctx: Ctx):
    from halo_harness.tui import slash
    from halo_harness.tui.dialogs import init_wizard
    app = _App()
    with door_stubs(running=True, pages=1) as rec:
        asyncio.run(slash.handle_slash(app, "setup", "team"))
    ctx.check(f"/setup team: the open page took Setup on the Team block, got {app.lines} {rec['focused']}",
              rec["focused"] and rec["focused"][0]["block"] == "team" and len(app.lines) == 1
              and app.lines[0].startswith("Opened Setup (Team) in the Studio page already open") and not app.pushed)
    app = _App()
    with door_stubs(running=True, pages=0, browser=False):
        asyncio.run(slash.handle_slash(app, "setup", ""))
    ctx.check(f"no browser took it: the URL and the --terminal hint, got {app.lines}", len(app.lines) == 1
              and app.lines[0].startswith("Studio is at http") and "?mode=setup#t=" in app.lines[0]
              and "/setup --terminal opens the terminal screen" in app.lines[0])
    built: list = []
    saved = (init_wizard.build_truncated_state, init_wizard.first_step_screen)
    init_wizard.build_truncated_state = lambda cwd, step_keys, on_finish: built.append(step_keys) or "state"
    init_wizard.first_step_screen = lambda state: f"screen:{state}"
    try:
        app = _App()
        with door_stubs() as rec:
            asyncio.run(slash.handle_slash(app, "setup", "--terminal team"))
            asyncio.run(slash.handle_slash(app, "setup", "--terminal"))
            asyncio.run(slash.handle_slash(app, "setup", "kitchen"))
    finally:
        init_wizard.build_truncated_state, init_wizard.first_step_screen = saved
    ctx.check(f"/setup --terminal [team]: the terminal screens, no Studio, got {built} {rec}", built == [("roles",), ("roles", "summary")]
              and app.pushed == ["screen:state", "screen:state"] and not rec["launched"] and not rec["opened"])
    ctx.check(f"an unknown word: the usage, got {app.notes}", app.notes and "/setup [team|roles] [--terminal]" in app.notes[-1])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
