"""tests.helpers.setup_door_stubs -- the seams of Studio's Setup doors (Halo 3.3.0.0 R4,
halo_harness/studio/setup_door.py) for the tests of `halo init`, `halo setup`, `/setup` and
`halo start`: no real Studio is started and no real browser opens.

`door_stubs(...)` replaces `launch.existing_url` (a running Studio or none),
`launch.launch_detached` (records its arguments and answers a URL),
`launch.api_call` (the running Studio's `POST focus`: `pages` open),
`launch._open` and `webbrowser.open` (whether a browser takes the URL), and
sets the no-browser environment (`HALO_NO_BROWSER`, `SSH_CONNECTION`,
`SSH_TTY`, `DISPLAY`) to what the test asks; everything is put back after.
It yields a record: `launched` (the kwargs of each launch_detached call),
`opened` (each URL a browser was asked to open), `focused` (each POST body).

`fake_tty()` makes `sys.stdin.isatty()` and `sys.stdout.isatty()` answer True
around a captured stdout (the doors only run on a real terminal).
"""

from __future__ import annotations

import contextlib
import io
import os
import sys

PORT = 4567
TOKEN = "tok"


def url_for(mode=None, edit=None) -> str:
    from halo_harness.studio import launch
    return launch.url_from_info({"port": PORT, "token": TOKEN}, mode, edit)


@contextlib.contextmanager
def door_stubs(*, running: bool = False, browser: bool = True, pages: int = 0, starts: bool = True,
               env: "dict | None" = None):
    import webbrowser
    from halo_harness.studio import launch, server as S
    rec = {"launched": [], "opened": [], "focused": []}

    def existing(state_dir, mode=None, edit=None):
        return url_for(mode, edit) if running else ""

    def launch_detached(mode, *, cwd, state_dir, open_browser=True, timeout=15.0, edit=None):
        rec["launched"].append({"mode": mode, "edit": edit, "open_browser": open_browser, "cwd": cwd, "state_dir": state_dir})
        return url_for(mode, edit) if starts else ""

    def api_call(state_dir, method, path, body=None, timeout=5.0):
        rec["focused"].append(dict(body or {}))
        return 200, {"pages": pages, **(body or {})}

    def opener(url, *a, **k):
        rec["opened"].append(url)
        return browser

    keys = ("HALO_NO_BROWSER", "SSH_CONNECTION", "SSH_TTY", "DISPLAY", "WAYLAND_DISPLAY")
    before_env = {k: os.environ.get(k) for k in keys}
    want = {"HALO_NO_BROWSER": None, "SSH_CONNECTION": None, "SSH_TTY": None, "DISPLAY": ":0", "WAYLAND_DISPLAY": None}
    want.update(env or {})
    saved = {"existing_url": launch.existing_url, "launch_detached": launch.launch_detached, "api_call": launch.api_call,
             "_open": launch._open}
    saved_wb = webbrowser.open
    background = S._BACKGROUND.pop("server", None)
    try:
        for k, v in want.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        launch.existing_url, launch.launch_detached, launch.api_call = existing, launch_detached, api_call
        launch._open = lambda url: opener(url)
        webbrowser.open = opener
        yield rec
    finally:
        for name, fn in saved.items():
            setattr(launch, name, fn)
        webbrowser.open = saved_wb
        if background is not None:
            S._BACKGROUND["server"] = background
        for k, v in before_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class _Tty:
    def __init__(self, real):
        self._real = real

    def isatty(self) -> bool:
        return True

    def __getattr__(self, name):
        return getattr(self._real, name)


@contextlib.contextmanager
def fake_tty(stdin: str = ""):
    """stdin and stdout both a terminal; yields the StringIO stdout writes to."""
    out = io.StringIO()
    real_in, real_out = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = _Tty(io.StringIO(stdin)), _Tty(out)
    try:
        yield out
    finally:
        sys.stdin, sys.stdout = real_in, real_out
