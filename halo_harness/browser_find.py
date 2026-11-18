"""halo_harness.browser_find -- the browser a person named, or the Chrome on this machine (3.6.0.3: moved here, with no
change of behaviour, from the old playback's Chrome module, which then left Halo). realcheck's --browser and the suite's
Chrome driver (tests/helpers/chrome_driver.py) use it. Stdlib only; it opens nothing and starts nothing.

    named_browser(value) -> a path that exists, a command on PATH, or None
    find_chrome() -> HALO_CHROME (that one alone), else the usual install paths, then PATH; None when there is none
    none_found() -> the one line said when find_chrome() found nothing
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

CANDIDATES = ("C:/Program Files/Google/Chrome/Application/chrome.exe",
              "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")


def named_browser(value: str) -> Optional[str]:
    """The browser a person named: a path that exists, or a bare command name found on PATH; None when it names
    nothing. (3.6.0.1: shared with tests/helpers/chrome_driver.py and scripts/realcheck's --browser.)"""
    if Path(value).exists():
        return value
    if "/" not in value and os.sep not in value:
        return shutil.which(value)
    return None


def find_chrome() -> Optional[str]:
    """`HALO_CHROME` when it is set (that one alone: a value that names nothing gives None, never the person's own
    installed Chrome; 3.6.0.1), else the usual install paths, then PATH; None when there is none."""
    env = os.environ.get("HALO_CHROME", "")
    if env:
        return named_browser(env)
    for cand in CANDIDATES:
        if Path(cand).exists():
            return cand
    return next((shutil.which(n) for n in NAMES if shutil.which(n)), None)


def none_found() -> str:
    """The one line said when find_chrome() found nothing: it names HALO_CHROME and its value when that was set."""
    env = os.environ.get("HALO_CHROME", "")
    if env:
        return f"HALO_CHROME names a browser that does not exist: {env} (fix or unset it)"
    return "this needs Chrome and none was found: install Chrome or set HALO_CHROME"
