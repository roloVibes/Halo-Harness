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
import os
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


def _fake_webbrowser(order: list, opened: list, *, registry: dict):
    """A stand-in for the `webbrowser` module: Python's own launcher classes, a try order, `get`, an `open` per
    browser that records instead of running anything."""
    import webbrowser as W

    def get(name=None):
        if name is None:
            if not order:
                raise W.Error("could not locate runnable browser")
            name = order[0]
        return registry[name]
    for name, b in registry.items():
        b.open = (lambda n: (lambda url, *a, **k: opened.append((n, url)) or True))(name)
    return SimpleNamespace(Error=W.Error, GenericBrowser=W.GenericBrowser, BackgroundBrowser=W.BackgroundBrowser,
                           Elinks=getattr(W, "Elinks", ()), _tryorder=list(order), get=get)


@test
def test_a_text_browser_never_takes_the_terminal(ctx: Ctx):
    """fx studio batch 1 (2): Python's webbrowser registers lynx, w3m, links, elinks and www-browser whenever TERM is
    set and runs them in the FOREGROUND, on the terminal the session draws on. Every door (closing.open_url) skips
    them, keeps the no-browser rule (SSH, no display, HALO_NO_BROWSER), and still uses the person's own BROWSER."""
    import webbrowser as W
    from halo_harness.studio import setup_door as D
    opened: list = []
    reg = {"xdg-open": W.BackgroundBrowser("xdg-open"), "www-browser": W.GenericBrowser("www-browser"),
           "lynx": W.GenericBrowser("lynx"), "w3m": W.GenericBrowser("w3m")}
    if getattr(W, "Elinks", None):
        reg["elinks"] = W.Elinks("elinks")
    text_only = [n for n in reg if n != "xdg-open"]
    url = "http://127.0.0.1:9/?mode=setup"  # no key: which browser, not what it is given (tests/test_open_link_token.py)
    fake = _fake_webbrowser(text_only, opened, registry=reg)
    ok = D.open_in_a_window(url, env={"DISPLAY": ":0", "TERM": "xterm"}, platform="linux", wb=fake)
    ctx.check(f"a display but only text browsers (WSLg, a bare X box): none started, False, got {ok} {opened}",
              ok is False and opened == [])
    fake = _fake_webbrowser(["xdg-open"] + text_only, opened, registry=reg)
    ok = D.open_in_a_window(url, env={"SSH_CONNECTION": "a 1 b 22", "TERM": "xterm"}, platform="linux", wb=fake)
    ctx.check(f"over SSH: nothing at all, got {ok} {opened}", ok is False and opened == [])
    ok = D.open_in_a_window(url, env={"DISPLAY": ":0", "HALO_NO_BROWSER": "1"}, platform="linux", wb=fake)
    ctx.check(f"HALO_NO_BROWSER: nothing, got {ok} {opened}", ok is False and opened == [])
    ok = D.open_in_a_window(url, env={"DISPLAY": ":0", "TERM": "xterm"}, platform="linux", wb=fake)
    ctx.check(f"a desktop: the window browser takes it, got {ok} {opened}", ok is True and opened == [("xdg-open", url)])
    opened.clear()
    fake = _fake_webbrowser(["lynx", "xdg-open"], opened, registry=reg)
    ok = D.open_in_a_window(url, env={"DISPLAY": ":0", "BROWSER": "lynx"}, platform="linux", wb=fake)
    ctx.check(f"a text browser the person named in BROWSER is theirs to use, got {ok} {opened}",
              ok is True and opened == [("lynx", url)])
    from halo_harness import closing
    calls: list = []
    real = (D.open_in_a_window, D.no_browser_reason)
    try:  # the one place every door goes through asks the same two questions
        D.no_browser_reason = lambda *a, **k: "this is an SSH session"
        D.open_in_a_window = lambda u, **k: calls.append(u) or True
        ctx.check("closing.open_url: no browser over SSH", closing.open_url(url) is False and calls == [])
        D.no_browser_reason = lambda *a, **k: ""
        if os.name != "nt" or not closing._in_a_job():
            ctx.check(f"closing.open_url opens through open_in_a_window, got {calls}", closing.open_url(url) is True and calls == [url])
    finally:
        D.open_in_a_window, D.no_browser_reason = real


@test
def test_a_browser_named_in_BROWSER_is_never_replaced(ctx: Ctx):
    """fx jb3 (realcheck, macOS installed, studio / Ctrl+C: Safari and 16 helpers left running): BROWSER names a
    program and it does not take the address (it exits non-zero, or a Ctrl+C killed it): Halo answers False and
    never walks on to the system's browser in its place (closing.open_url's Windows rule, now on every system)."""
    import webbrowser as W
    from halo_harness.studio import setup_door as D
    opened: list = []
    reg = {"standin": W.GenericBrowser("standin"), "MacOSX": W.BackgroundBrowser("open"),
           "xdg-open": W.BackgroundBrowser("xdg-open")}
    url = "http://127.0.0.1:9/?mode=setup"
    real = D._own_session
    try:
        D._own_session = lambda b, u: opened.append((b.name, u)) and False  # the named program fails
        for plat, system in (("darwin", "MacOSX"), ("linux", "xdg-open")):
            opened.clear()
            fake = _fake_webbrowser(["standin", system], opened, registry=reg)
            ok = D.open_in_a_window(url, env={"DISPLAY": ":0", "BROWSER": "standin"}, platform=plat, wb=fake)
            ctx.check(f"{plat}: the named program failed: False, the system's browser never asked, got {ok} {opened}",
                      ok is False and [n for n, _u in opened] == ["standin"])
            opened.clear()
            fake = _fake_webbrowser([system], opened, registry=reg)  # BROWSER not in the try order (read before it was set)
            ok = D.open_in_a_window(url, env={"DISPLAY": ":0", "BROWSER": "standin"}, platform=plat, wb=fake)
            ctx.check(f"{plat}: a named program webbrowser never registered is still the only one, got {ok} {opened}",
                      ok is False and system not in [n for n, _u in opened])
        D._own_session = lambda b, u: opened.append((b.name, u)) or True
        opened.clear()
        fake = _fake_webbrowser(["standin", "MacOSX"], opened, registry=reg)
        ok = D.open_in_a_window(url, env={"BROWSER": "standin"}, platform="darwin", wb=fake)
        ctx.check(f"the named program took it: True, nothing else, got {ok} {opened}", ok is True and opened == [("standin", url)])
        opened.clear()
        fake = _fake_webbrowser(["MacOSX"], opened, registry=reg)
        ok = D.open_in_a_window(url, env={}, platform="darwin", wb=fake)
        ctx.check(f"no BROWSER: the system's browser as before, got {ok} {opened}", ok is True and opened == [("MacOSX", url)])
    finally:
        D._own_session = real


@test
def test_no_browser_opens_once_a_stop_was_asked(ctx: Ctx):
    """fx jb3: Studio's browser opens 0.3 s after its address prints; a Ctrl+C (or SIGTERM, an owner gone) in between
    closes Studio, and nothing may start a browser after that."""
    import webbrowser as W
    from halo_harness import closing
    from halo_harness.studio import setup_door as D
    opened: list = []
    reg = {"xdg-open": W.BackgroundBrowser("xdg-open")}
    url = "http://127.0.0.1:9/?mode=setup"
    saved = {k: closing._STATE.get(k) for k in ("closed", "owner_gone", "hard_exit")}
    try:
        for key, value in (("closed", True), ("owner_gone", True), ("hard_exit", 0)):
            closing._STATE.update(closed=False, owner_gone=False, hard_exit=None)
            closing._STATE[key] = value
            fake = _fake_webbrowser(["xdg-open"], opened, registry=reg)
            ok = D.open_in_a_window(url, env={"DISPLAY": ":0"}, platform="linux", wb=fake)
            ctx.check(f"{key}: no browser, False, got {ok} {opened}", ok is False and opened == [])
            ctx.check(f"{key}: closing.open_url answers False", closing.open_url(url) is False)
        closing._STATE.update(closed=False, owner_gone=False, hard_exit=None)
        fake = _fake_webbrowser(["xdg-open"], opened, registry=reg)
        ok = D.open_in_a_window(url, env={"DISPLAY": ":0"}, platform="linux", wb=fake)
        ctx.check(f"no stop asked: the browser opens, got {ok} {opened}", ok is True and len(opened) == 1)
    finally:
        closing._STATE.update(saved)
    src = (Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "server.py").read_text(encoding="utf-8")
    ctx.check("halo studio's finally cancels the browser timer that has not fired yet", "opener.cancel()" in src)


@test
def test_a_browser_named_in_BROWSER_runs_in_its_own_session(ctx: Ctx):
    """fx jb3, Linux and macOS, the real webbrowser module in a child: BROWSER names a program (Python runs it as a
    GenericBrowser, in the caller's process group, where the terminal's Ctrl+C reaches it); Halo starts it in its own
    session instead, with the address, and no Halo marker."""
    if os.name == "nt":
        ctx.check("POSIX only (Windows starts BROWSER through closing.open_url's own branch)", True)
        return
    import subprocess as sp
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="halo-browser-session-"))
    log, standin = root / "standin.txt", root / "standin"
    standin.write_text(f"#!{sys.executable}\nimport os, sys\nopen({str(log)!r}, 'w').write("
                       f"f'{{os.getsid(0)}} {{os.getpgid(0)}} {{os.environ.get(\"HALO_OWNER\", \"\")}} {{sys.argv[1]}}')\n")
    standin.chmod(0o755)
    code = ("import os, sys; sys.path.insert(0, sys.argv[1]); from halo_harness.closing import open_url;"
            "ok = open_url('http://127.0.0.1:9/?mode=setup'); print(ok, os.getsid(0), os.getpgid(0))")
    tree = str(Path(__file__).resolve().parent.parent)
    env = {k: v for k, v in os.environ.items() if k not in ("SSH_CONNECTION", "SSH_TTY", "HALO_NO_BROWSER")}
    env.update(PATH=str(root), BROWSER=str(standin), DISPLAY=":0", HALO_OWNER="test-marker")
    try:
        out = sp.run([sys.executable, "-c", code, tree], env=env, capture_output=True, text=True, timeout=30).stdout.split()
    except sp.TimeoutExpired:
        out = []
    got = log.read_text().split() if log.exists() else []
    ctx.check(f"the named program took the address, got {out} {got}", out[:1] == ["True"] and len(got) >= 3
              and got[-1].startswith("http://127.0.0.1:9/"))
    ctx.check(f"its own session and process group (not the caller's), got caller {out[1:]} browser {got[:2]}",
              len(out) == 3 and len(got) >= 3 and got[0] != out[1] and got[1] != out[2])
    ctx.check(f"it carries no Halo marker, got {got}", len(got) == 3)


@test
def test_a_text_browser_on_the_path_is_never_run(ctx: Ctx):
    """fx studio batch 1 (2), Linux, the real webbrowser module in a child: lynx on PATH, TERM set. Over SSH and with
    a display but no window browser, `closing.open_url` answers False at once and lynx never runs; with xdg-open on
    PATH that is what runs."""
    if not sys.platform.startswith("linux"):
        ctx.check("Linux only (macOS and Windows register no text browser first)", True)
        return
    import subprocess as sp
    import tempfile
    import time
    root = Path(tempfile.mkdtemp(prefix="halo-textbrowser-"))
    bindir, log = root / "bin", root / "ran.txt"
    bindir.mkdir()
    for name in ("lynx", "w3m", "www-browser", "xdg-open"):
        (bindir / name).write_text(f"#!/bin/sh\necho {name} >> '{log}'\nexec /bin/sleep 3\n")
        (bindir / name).chmod(0o755)
    code = ("import sys, time; sys.path.insert(0, sys.argv[1]); from halo_harness.closing import open_url;"
            "t = time.monotonic(); ok = open_url('http://127.0.0.1:9/#t=x'); print(ok, round(time.monotonic() - t, 1))")
    tree = str(Path(__file__).resolve().parent.parent)

    def run(env_extra: dict, keep: tuple) -> "tuple[str, str]":
        if log.exists():
            log.unlink()
        for name in ("lynx", "w3m", "www-browser", "xdg-open"):
            (bindir / name).chmod(0o755 if name in keep else 0o644)
        env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY", "SSH_CONNECTION", "SSH_TTY",
                                                                "BROWSER", "HALO_NO_BROWSER")}
        env.update(PATH=str(bindir), TERM="xterm-256color", **env_extra)
        try:
            out = sp.run([sys.executable, "-c", code, tree], env=env, capture_output=True, text=True, timeout=15).stdout.strip()
        except sp.TimeoutExpired:
            out = "timed out (a text browser held the terminal)"
        time.sleep(0.3)
        return out, (log.read_text() if log.exists() else "")
    out, ran = run({"SSH_CONNECTION": "a 1 b 22"}, ("lynx", "w3m", "www-browser"))
    ctx.check(f"over SSH: False at once, no text browser, got {out!r} ran {ran!r}", out.startswith("False") and ran == "")
    out, ran = run({"DISPLAY": ":0"}, ("lynx", "w3m", "www-browser"))
    ctx.check(f"a display, only text browsers: False, none ran, got {out!r} ran {ran!r}", out.startswith("False") and ran == "")
    out, ran = run({"DISPLAY": ":0"}, ("lynx", "xdg-open"))
    ctx.check(f"a display and xdg-open: True, xdg-open ran, got {out!r} ran {ran!r}", out.startswith("True") and ran.split() == ["xdg-open"])


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
def test_slash_setup_opens_setup_and_terminal_prints_the_console_way(ctx: Ctx):
    from halo_harness.tui import slash
    app = _App()
    with door_stubs(running=True, pages=1) as rec:
        asyncio.run(slash.handle_slash(app, "setup", "team"))
    ctx.check(f"/setup team: the open page took Setup on the Team block, got {app.lines} {rec['focused']}",
              rec["focused"] and rec["focused"][0]["block"] == "team" and len(app.lines) == 1
              and app.lines[0].startswith("Opened Setup (Team) in the Studio page already open") and not app.pushed)
    app = _App()
    with door_stubs(running=True, pages=1) as rec:
        asyncio.run(slash.handle_slash(app, "setup", "model"))
    ctx.check(f"/setup model: any Setup page (3.4.0.0 B2), got {rec['focused']}", rec["focused"] and rec["focused"][0]["block"] == "model")
    app = _App()
    with door_stubs(running=True, pages=0, browser=False):
        asyncio.run(slash.handle_slash(app, "setup", ""))
    ctx.check(f"no browser took it: the URL and the --terminal hint, got {app.lines}", len(app.lines) == 1
              and app.lines[0].startswith("Studio is at http") and "?mode=setup#t=" in app.lines[0]
              and "/setup --terminal prints the console way" in app.lines[0])
    app = _App()
    with door_stubs() as rec:
        asyncio.run(slash.handle_slash(app, "setup", "--terminal team"))
        asyncio.run(slash.handle_slash(app, "setup", "--terminal"))
        asyncio.run(slash.handle_slash(app, "setup", "kitchen"))
    ctx.check(f"/setup --terminal [team]: the console way, no screen, no Studio, got {app.notes} {rec}",
              not app.pushed and not rec["launched"] and not rec["opened"] and "halo maps use <name>" in app.notes[0]
              and app.notes[1].startswith("Setup in a terminal: halo init --terminal"))
    ctx.check(f"an unknown word: the usage, got {app.notes}", app.notes and app.notes[-1].startswith("Usage: /setup [providers|"))


@test
def test_halo_setup_a_pack_opens_its_first_block_waiting(ctx: Ctx):
    """3.3.11.0 R3: `halo setup <pack>` -> Setup on `?block=pack:<id>:<block>` (the first block waiting); no terminal:
    a line per block and the edit target; a disabled pack: one line, exit 1; a word that is no pack: the usage, 2."""
    import contextlib
    import io
    from halo_harness.packs.setup_state import DONE, mark
    from halo_harness.setup_cli import cmd_setup
    from halo_harness.studio.edit_target import parse
    from halo_harness.studio.setup_door import SetupTarget
    from tests.helpers.packs_home import PacksHome
    from tests.helpers.setup_door_stubs import fake_tty
    key = "pack:setup-blocks:reach"
    t = parse(f"setup:{key}")[0]
    ctx.check(f"the target, its URL and its words, got {t}", t == SetupTarget(block=key) and t.display == "Setup (setup-blocks: reach)"
              and t.query() == f"?mode=setup&block={key}")
    with PacksHome() as h:
        h.install(h.source("setup-blocks"), enable=True)
        mark("setup-blocks", "prefs", DONE)
        with door_stubs() as rec, fake_tty() as out:
            rc = cmd_setup(["setup-blocks"])
        url = rec["opened"][0] if rec["opened"] else ""
        ctx.check(f"Studio on the first block waiting, got {rc} {rec['launched']}", rc == 0 and rec["launched"]
                  and rec["launched"][0]["edit"] == f"setup:{key}" and f"?mode=setup&block={key}#t=" in url)
        ctx.check(f"its line, got {out.getvalue()!r}", f"Setup (setup-blocks: reach) is open in your browser: {url}. "
                  "`halo setup setup-blocks --terminal` runs the terminal listing instead." in out.getvalue())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_setup(["setup-blocks"])  # no terminal here: the listing
        ctx.check(f"no terminal: each block with its state, then the target, got {rc} {buf.getvalue()!r}", rc == 0
                  and buf.getvalue().splitlines() == ["setup-blocks -- Review preferences (form): done",
                                                      "setup-blocks -- Reach the review service (check): waiting",
                                                      "setup-blocks -- Before you start (note): waiting",
                                                      f"open them in Studio: halo studio --edit setup:{key}"])
        from halo_harness.packs.grants import disable
        disable("setup-blocks")
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            rc = cmd_setup(["setup-blocks"])
            bad = cmd_setup(["kitchen"])
        ctx.check(f"disabled: one line, exit 1; no pack: the usage, 2, got {rc} {bad} {err.getvalue()!r}", rc == 1 and bad == 2
                  and "setup-blocks does not run here" in err.getvalue() and "an enabled pack's id" in err.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
