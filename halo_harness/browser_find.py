"""halo_harness.browser_find -- the browser a person named, or one already on this machine: Google Chrome, Chromium,
Microsoft Edge or Brave (3.6.0.3: moved here from the old playback's Chrome module; 3.6.0.6 W: Edge, Brave, Chromium
everywhere, per-user installs on Windows, ~/Applications on macOS). The built-in Browser tool (browser_cdp.py),
realcheck's --browser and the suite's Chrome driver (tests/helpers/chrome_driver.py) use it. Stdlib only; it opens
nothing and starts nothing.

    named_browser(value) -> a path that exists, a command on PATH, or None
    find_browser()       -> (its name a person reads, its path): HALO_CHROME (that one alone), else Google Chrome,
                            Chromium, Microsoft Edge, Brave, each in its installers' places and then by its names on
                            PATH; None when there is none
    find_chrome()        -> find_browser()'s path (the name its callers have always used)
    found_line()         -> "Google Chrome: <path>", or none_found()
    none_found()         -> the one line said when nothing was found
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional

# (the name a person reads, {system: install places}, names on PATH), in the order they are tried. A place is a
# template: {pf} Program Files, {pf86} Program Files (x86), {local} %LOCALAPPDATA%, {home} the home folder.
BROWSERS = (
    ("Google Chrome",
     {"win32": ("{pf}/Google/Chrome/Application/chrome.exe", "{pf86}/Google/Chrome/Application/chrome.exe",
                "{local}/Google/Chrome/Application/chrome.exe"),
      "darwin": ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                 "{home}/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")},
     ("google-chrome", "google-chrome-stable", "chrome")),
    ("Chromium",
     {"win32": ("{local}/Chromium/Application/chrome.exe", "{pf}/Chromium/Application/chrome.exe"),
      "darwin": ("/Applications/Chromium.app/Contents/MacOS/Chromium",
                 "{home}/Applications/Chromium.app/Contents/MacOS/Chromium")},
     ("chromium", "chromium-browser")),
    ("Microsoft Edge",
     {"win32": ("{pf86}/Microsoft/Edge/Application/msedge.exe", "{pf}/Microsoft/Edge/Application/msedge.exe",
                "{local}/Microsoft/Edge/Application/msedge.exe"),
      "darwin": ("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                 "{home}/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")},
     ("microsoft-edge", "microsoft-edge-stable", "msedge")),
    ("Brave",
     {"win32": ("{pf}/BraveSoftware/Brave-Browser/Application/brave.exe",
                "{pf86}/BraveSoftware/Brave-Browser/Application/brave.exe",
                "{local}/BraveSoftware/Brave-Browser/Application/brave.exe"),
      "darwin": ("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                 "{home}/Applications/Brave Browser.app/Contents/MacOS/Brave Browser")},
     ("brave-browser", "brave-browser-stable", "brave")),
)
# kept for their readers: every place and every PATH name, in the order above
CANDIDATES = tuple(p for _n, places, _c in BROWSERS for ps in places.values() for p in ps)
NAMES = tuple(c for _n, _p, cmds in BROWSERS for c in cmds)


def named_browser(value: str) -> Optional[str]:
    """The browser a person named: a path that exists, or a bare command name found on PATH; None when it names
    nothing. (3.6.0.1: shared with tests/helpers/chrome_driver.py and scripts/realcheck's --browser.)"""
    if Path(value).exists():
        return value
    if "/" not in value and os.sep not in value:
        return shutil.which(value)
    return None


def install_places(system: Optional[str] = None, env: Optional[dict] = None,
                   home: Optional[str] = None) -> "list[tuple[str, list, tuple]]":
    """[(name, [install paths on `system`], PATH names)] in the order they are tried (inputs injectable)."""
    system = system or sys.platform
    env = os.environ if env is None else env
    home = home if home is not None else str(Path.home())
    key = "win32" if system.startswith("win") else "darwin" if system == "darwin" else "linux"
    fill = {"pf": env.get("ProgramFiles") or "C:/Program Files",
            "pf86": env.get("ProgramFiles(x86)") or "C:/Program Files (x86)",
            "local": env.get("LOCALAPPDATA") or "", "home": home}
    out = []
    for name, places, cmds in BROWSERS:
        paths = []
        for tpl in places.get(key, ()):
            if "{local}" in tpl and not fill["local"]:
                continue
            paths.append(tpl.format(**fill).replace("\\", "/"))
        out.append((name, paths, cmds))
    return out


def label_of(path: str) -> str:
    """The name a person reads for the browser at `path` ("a browser" when it is none of the four)."""
    low = os.path.basename(str(path)).lower()
    for name, words in (("Microsoft Edge", ("edge",)), ("Brave", ("brave",)), ("Chromium", ("chromium",)),
                        ("Google Chrome", ("chrome",))):
        if any(w in low for w in words):
            return name
    return "a browser"


def find_browser(*, system: Optional[str] = None, env: Optional[dict] = None, home: Optional[str] = None,
                 exists: Optional[Callable[[str], bool]] = None,
                 which: Optional[Callable[[str], Optional[str]]] = None) -> "Optional[tuple[str, str]]":
    """(name, path) of the first browser found: `HALO_CHROME` when it is set (that one alone: a value that names
    nothing gives None, never the person's own installed browser; 3.6.0.1), else Google Chrome, Chromium, Microsoft
    Edge, Brave, each in its installers' places and then by its names on PATH. None when there is none."""
    env = os.environ if env is None else env
    exists = exists or (lambda p: Path(p).exists())
    which = which or shutil.which
    named = env.get("HALO_CHROME", "")
    if named:
        got = named_browser(named)
        return (label_of(got), got) if got else None
    for name, paths, cmds in install_places(system, env, home):
        for p in paths:
            if exists(p):
                return name, p
        for c in cmds:
            got = which(c)
            if got:
                return name, got
    return None


def find_chrome() -> Optional[str]:
    """The path of find_browser()'s browser, or None (the name every caller has used since 3.6.0.1)."""
    got = find_browser()
    return got[1] if got else None


def found_line() -> str:
    """Which browser Halo would use, in words a person reads, with its path; or the one line of none_found()."""
    got = find_browser()
    return f"{got[0]}: {got[1]}" if got else none_found()


def none_found() -> str:
    """The one line said when find_chrome() found nothing: it names HALO_CHROME and its value when that was set."""
    env = os.environ.get("HALO_CHROME", "")
    if env:
        return f"HALO_CHROME names a browser that does not exist: {env} (fix or unset it)"
    return ("No browser found: install Google Chrome, Chromium, Microsoft Edge or Brave, or set HALO_CHROME to a "
            "browser's path. Halo downloads none.")
