"""tests.test_browser_find -- the browser finder realcheck and the suite's Chrome driver use (halo_harness/browser_find.py;
3.6.0.3 moved it out of the replay clip's live/clip_chrome.py with no change of behaviour): HALO_CHROME first (that one
alone), then the install paths, then PATH; the one line said when none is found. Run: python -m tests.test_browser_find
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MOVED = ("CANDIDATES", "NAMES", "named_browser", "find_chrome", "none_found")


@test
def test_a_halo_chrome_that_names_nothing_never_films_in_the_installed_chrome(ctx: Ctx):
    """3.6.0.1: `halo replay clip` / Studio's Export a clip with a HALO_CHROME that names no browser fell through to
    the person's own installed Chrome. Now it finds none, and the error names the variable and its value."""
    import tempfile
    from unittest import mock
    from halo_harness import browser_find as cc
    tmp = Path(tempfile.mkdtemp(prefix="clip-find-"))
    installed = tmp / "installed-chrome"
    installed.write_text("", encoding="utf-8")
    missing = str(tmp / "no-such-chrome")
    # 3.6.0.6 W: the places come from install_places() (CANDIDATES is now the flat list of every place, for readers)
    with mock.patch.object(cc, "install_places", lambda *a, **k: [("Google Chrome", [str(installed)], ())]), \
            mock.patch("shutil.which", lambda name, *a, **k: str(installed)):
        with mock.patch.dict(os.environ, {"HALO_CHROME": missing}):
            ctx.check(f"never the installed Chrome, got {cc.find_chrome()!r}", cc.find_chrome() is None)
            why = getattr(cc, "none_found", lambda: "")()
            ctx.check(f"the error names HALO_CHROME and its value, got {why!r}", "HALO_CHROME" in why and missing in why)
        with mock.patch.dict(os.environ, {"HALO_CHROME": ""}):
            ctx.check("an unset HALO_CHROME still finds the installed Chrome", cc.find_chrome() == str(installed))
    with mock.patch.dict(os.environ, {"HALO_CHROME": "my-chromium"}), \
            mock.patch("shutil.which", lambda name, *a, **k: "/opt/bin/my-chromium" if name == "my-chromium" else None):
        ctx.check("a bare command name resolves through PATH", cc.find_chrome() == "/opt/bin/my-chromium")


def _find(system: str, *, files=(), path_cmds=None, env=None, home="/hx/someone"):
    """find_browser() on `system` with only `files` existing and only `path_cmds` ({name: path}) on PATH."""
    from halo_harness import browser_find as bf
    files = {f.replace("\\", "/") for f in files}
    cmds = path_cmds or {}
    return bf.find_browser(system=system, env=dict(env or {}), home=home, exists=lambda p: p in files,
                           which=lambda n: cmds.get(n))


@test
def test_windows_finds_edge_and_per_user_installs(ctx: Ctx):
    """3.6.0.6 W entry 1: Edge is on every Windows; Chrome, Chromium and Brave may be installed per user."""
    env = {"ProgramFiles": "C:/Program Files", "ProgramFiles(x86)": "C:/Program Files (x86)",
           "LOCALAPPDATA": "C:/hx/someone/AppData/Local"}
    edge = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
    got = _find("win32", files=[edge], env=env)
    ctx.check(f"only Edge installed -> Edge, got {got}", got == ("Microsoft Edge", edge))
    user_chrome = "C:/hx/someone/AppData/Local/Google/Chrome/Application/chrome.exe"
    got = _find("win32", files=[edge, user_chrome], env=env)
    ctx.check(f"a per-user Chrome comes before Edge, got {got}", got == ("Google Chrome", user_chrome))
    brave = "C:/hx/someone/AppData/Local/BraveSoftware/Brave-Browser/Application/brave.exe"
    got = _find("win32", files=[brave], env=env)
    ctx.check(f"a per-user Brave -> Brave, got {got}", got == ("Brave", brave))
    got = _find("win32", files=[brave, edge], env=env)
    ctx.check(f"Edge comes before Brave, got {got}", got == ("Microsoft Edge", edge))


@test
def test_macos_finds_chromium_edge_brave_in_both_applications_folders(ctx: Ctx):
    for name, app in (("Chromium", "Chromium.app/Contents/MacOS/Chromium"),
                      ("Microsoft Edge", "Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                      ("Brave", "Brave Browser.app/Contents/MacOS/Brave Browser")):
        for root in ("/Applications", "/hx/someone/Applications"):
            got = _find("darwin", files=[f"{root}/{app}"])
            ctx.check(f"{root}/{app} -> {name}, got {got}", got == (name, f"{root}/{app}"))
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    got = _find("darwin", files=[chrome, "/Applications/Chromium.app/Contents/MacOS/Chromium"])
    ctx.check(f"Google Chrome first, got {got}", got == ("Google Chrome", chrome))


@test
def test_linux_finds_edge_and_brave_on_path_in_order(ctx: Ctx):
    for cmd, name in (("microsoft-edge", "Microsoft Edge"), ("microsoft-edge-stable", "Microsoft Edge"),
                      ("brave-browser", "Brave"), ("chromium", "Chromium"), ("google-chrome", "Google Chrome")):
        got = _find("linux", path_cmds={cmd: f"/usr/bin/{cmd}"})
        ctx.check(f"`{cmd}` on PATH -> {name}, got {got}", got == (name, f"/usr/bin/{cmd}"))
    got = _find("linux", path_cmds={"brave-browser": "/usr/bin/brave-browser", "microsoft-edge": "/usr/bin/microsoft-edge",
                                    "chromium": "/usr/bin/chromium"})
    ctx.check(f"Chromium, then Edge, then Brave, got {got}", got == ("Chromium", "/usr/bin/chromium"))
    got = _find("linux", path_cmds={"brave-browser": "/usr/bin/brave-browser", "microsoft-edge": "/usr/bin/microsoft-edge"})
    ctx.check(f"Edge before Brave, got {got}", got == ("Microsoft Edge", "/usr/bin/microsoft-edge"))
    ctx.check(f"nothing -> None, got {_find('linux')}", _find("linux") is None)


@test
def test_halo_chrome_still_names_one_browser_alone_and_the_none_line_is_word_for_word(ctx: Ctx):
    import tempfile
    from unittest import mock
    from halo_harness import browser_find as bf
    tmp = Path(tempfile.mkdtemp(prefix="find-named-"))
    mine = tmp / "msedge"
    mine.write_text("", encoding="utf-8")
    edge = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
    got = _find("win32", files=[edge], env={"HALO_CHROME": str(mine)})
    ctx.check(f"HALO_CHROME wins, named by what it is, got {got}", got == ("Microsoft Edge", str(mine)))
    got = _find("win32", files=[edge], env={"HALO_CHROME": str(tmp / "nothing-here")})
    ctx.check(f"a HALO_CHROME that names nothing -> None, never the installed Edge, got {got}", got is None)
    with mock.patch.dict(os.environ, {"HALO_CHROME": ""}), mock.patch.object(bf, "find_browser", lambda **k: None):
        line = bf.none_found()
        ctx.check(f"the none line word for word, got {line!r}", line == (
            "No browser found: install Google Chrome, Chromium, Microsoft Edge or Brave, or set HALO_CHROME to a "
            "browser's path. Halo downloads none."))
        ctx.check("found_line says the same when none is found", bf.found_line() == line)
    with mock.patch.object(bf, "find_browser", lambda **k: ("Microsoft Edge", edge)):
        ctx.check(f"found_line names it and its path, got {bf.found_line()!r}",
                  bf.found_line() == f"Microsoft Edge: {edge}")
    with mock.patch.dict(os.environ, {"HALO_CHROME": str(tmp / "nothing-here")}):
        ctx.check("with HALO_CHROME set the line keeps its name and value",
                  "HALO_CHROME" in bf.none_found() and str(tmp / "nothing-here") in bf.none_found())


def _imports(path: Path) -> list:
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            out += [(node.module, a.name) for a in node.names]
        elif isinstance(node, ast.Import):
            out += [(a.name, "") for a in node.names]
    return out


@test
def test_the_finder_moved_whole_and_its_users_import_it_from_its_own_module(ctx: Ctx):
    """3.6.0.3 (R-B6): the five names live in halo_harness.browser_find (file 06 deleted the clip's module that
    re-exported them); realcheck and the suite's Chrome driver import from there; the finder opens no socket and
    starts no process, so tests.test_offline_mode needs no entry for it."""
    from halo_harness import browser_find
    for name in MOVED:
        ctx.check(f"browser_find.{name} is there", hasattr(browser_find, name))
    for rel in ("scripts/realcheck.py", "scripts/realcheck/core.py", "tests/helpers/chrome_driver.py"):
        got = _imports(ROOT / rel)
        ctx.check(f"{rel} imports named_browser from halo_harness.browser_find",
                  ("halo_harness.browser_find", "named_browser") in got
                  and not any(m.startswith("halo_harness.live.") for m, _n in got))
    mods = {m.split(".")[0] for m, _n in _imports(ROOT / "halo_harness" / "browser_find.py")}
    ctx.check(f"no network and no process in the finder, got {sorted(mods)}",
              not mods & {"socket", "urllib", "subprocess", "http"} and not any(
                  "subprocess" in m for m, _n in _imports(ROOT / "halo_harness" / "browser_find.py")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
