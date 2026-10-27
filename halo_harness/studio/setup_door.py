"""halo_harness.studio.setup_door -- the doors into Studio's Setup section
(Halo 3.3.0.0 R4, "Setup is Studio": `halo init` opens Studio on Setup).

A setup target names the page and, optionally, the block whose page opens:

    SetupTarget()                 Setup                     ?mode=setup
    SetupTarget(first=True)       Setup, the first run      ?mode=setup&first=1   (`halo init`, `halo start`
                                                                                  with no provider: 3.3.1.0 R1 opens
                                                                                  nothing on its own, the rail's
                                                                                  line says "set up this box")
    SetupTarget(block="team")     Setup, the Team page      ?mode=setup&block=team (`halo setup team`, `/setup`)

It travels as an edit-target text (`setup`, `setup:first`, `setup:team`), so
`halo studio --edit setup:team`, the detached Studio's argv and
`launch.url_from_info` all carry it (studio/edit_target.py hands the `setup`
kind to `parse` here); a Studio page already open gets it as a `focus` frame
`{edit: "", mode: "setup", block, first}` (ui/src/routes/setup/door.ts).

`open_setup` starts or reuses Studio and opens the browser on it; when no
browser can open here (`HALO_NO_BROWSER`, `SSH_CONNECTION`, Linux with no
`DISPLAY` / `WAYLAND_DISPLAY`, or `webbrowser.open` answering False) the
answer says so and carries the URL. `cli_door` prints the one line a command
prints and returns True when the browser has Setup; on False the caller runs
the terminal wizard (`halo init`, `halo setup`, `halo start`).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlsplit

# The page's blocks by the word a door uses (each is a step's page, routes/setup/pages.ts stepOf); `roles` is the Team block's old name.
BLOCKS = ("providers", "local", "model", "permissions", "theme", "team", "linux", "check")
ALIASES = {"roles": "team"}
BLOCK_TITLES = {"providers": "Providers", "local": "Local models", "model": "Default model", "permissions": "Permissions",
                "theme": "Terminal theme", "team": "Team", "linux": "Linux fixes", "check": "Check"}


@dataclass(frozen=True)
class SetupTarget:
    block: str = ""
    first: bool = False

    @property
    def mode(self) -> str:
        return "setup"

    @property
    def text(self) -> str:
        """The edit-target text: `setup`, `setup:first` or `setup:<block>`."""
        if self.block:
            return f"setup:{self.block}"
        return "setup:first" if self.first else "setup"

    @property
    def display(self) -> str:
        return f"Setup ({BLOCK_TITLES[self.block]})" if self.block in BLOCK_TITLES else "Setup"

    @property
    def verb(self) -> str:
        return "use"

    @property
    def cli(self) -> str:
        return f"halo studio --edit {self.text}"

    def query(self) -> str:
        return "?mode=setup" + ("&first=1" if self.first else "") + (f"&block={self.block}" if self.block else "")

    def focus(self) -> dict:
        """The `focus` frame's data, and POST /api/focus's body."""
        return {"edit": "", "mode": "setup", "session": "", "block": self.block, "first": bool(self.first)}


def block_word(word: str) -> "tuple[Optional[str], str]":
    """`(block, '')` for a block word ('' = the whole page), or `(None, why)`."""
    w = (word or "").strip().lower()
    w = ALIASES.get(w, w)
    if not w or w in BLOCKS:
        return w, ""
    return None, f"{word!r} is not a Setup block: use one of {', '.join(BLOCKS)} (roles = team)"


def parse(text: str) -> "tuple[Optional[SetupTarget], str]":
    """`setup`, `setup:first` or `setup:<block>` -> the target; `(None, why)` for anything else."""
    kind, _sep, rest = (text or "").strip().partition(":")
    if kind.strip().lower() != "setup":
        return None, f"{text!r} is not a Setup target"
    rest = rest.strip().lower()
    if rest == "first":
        return SetupTarget(first=True), ""
    block, why = block_word(rest)
    return (SetupTarget(block=block), "") if block is not None else (None, why)


def no_browser_reason(env: "Optional[dict]" = None, platform: Optional[str] = None) -> str:
    """Why no browser can open on this box ('' when one may): the same rule for every door."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if (env.get("HALO_NO_BROWSER") or "").strip() not in ("", "0"):
        return "HALO_NO_BROWSER is set"
    if env.get("SSH_CONNECTION") or env.get("SSH_TTY"):
        return "this is an SSH session"
    if platform.startswith("linux") and not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        return "no DISPLAY or WAYLAND_DISPLAY"
    return ""


def _state_dir() -> Path:
    from halo_harness.providers.config import default_state_dir
    return Path(default_state_dir())


def open_setup(target: SetupTarget, *, cwd=None, state_dir=None, why: Optional[str] = None,
               timeout: float = 15.0) -> dict:
    """`{"url", "how": focused|opened|started|printed|failed, "pages", "target", "why"}`: Studio on Setup.

    A Studio already running for this home is reused (its open pages take the `focus` frame, else the browser
    opens the URL); none: one starts in the background (`launch_detached`, no browser of its own) and this
    process opens the browser, so a browser that cannot open is known here. `why` (default `no_browser_reason()`)
    set: Studio is found or started and only the URL is the answer."""
    from halo_harness.studio import edit_open, launch
    state_dir = Path(state_dir) if state_dir is not None else _state_dir()
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    why = no_browser_reason() if why is None else why
    running = edit_open._focus_in_process(target, publish=False) or launch.existing_url(state_dir, target.mode, target.text)
    if running:
        out = edit_open.open_edit(target, cwd=cwd, state_dir=state_dir, open_browser=not why, timeout=timeout)
    else:
        url = launch.launch_detached(target.mode, cwd=cwd, state_dir=state_dir, open_browser=False, timeout=timeout,
                                     edit=target.text)
        how = "failed" if not url else ("printed" if why else ("started" if launch._open(url) else "printed"))
        out = {"url": url, "how": how, "pages": 0, "target": target.display}
    if out.get("how") == "printed" and not why:
        why = "no browser took the URL"
    out["why"] = why if out.get("how") == "printed" else ""
    out["target"] = target.display
    return out


def forward_hint(url: str) -> str:
    """The port-forward line `halo studio` prints, for this URL's port ('' when it has none)."""
    try:
        port = urlsplit(url).port
    except ValueError:
        port = None
    if not port:
        return ""
    return f"Over SSH: ssh -L {port}:127.0.0.1:{port} <host>, then open the same URL on your machine."


def cli_door(target: SetupTarget, *, terminal_cli: str, fallback: str, say: Callable[[str], None] = print,
             cwd=None, state_dir=None, wait: bool = False) -> bool:
    """A command's door: open Setup and print one line; True when the browser has it. False: the URL (with the
    port-forward hint) or why Studio did not start is printed, then `fallback` ("the terminal wizard runs here
    instead.") and the caller runs it. `wait` (3.3.3.0 R1, `halo init`): the one line also says the terminal
    waits for Setup's Done (halo_harness/init_wait.py)."""
    try:
        out = open_setup(target, cwd=cwd, state_dir=state_dir)
    except Exception as e:  # Studio could not be reached or started: the terminal path runs
        out = {"url": "", "how": "failed", "why": f"{type(e).__name__}: {e}"}
    url, how = out.get("url") or "", out.get("how")
    if how in ("focused", "opened", "started") and url:
        where = "in the Studio page already open" if how == "focused" else "in your browser"
        if wait:
            say(f"{target.display} is open {where}: {url}. Press Done there and halo starts here (Ctrl+C stops "
                f"waiting; `{terminal_cli}` runs the terminal {fallback}).")
        else:
            say(f"{target.display} is open {where}: {url}. `{terminal_cli}` runs the terminal {fallback} instead.")
        if how == "started":
            say("Studio keeps running in the background; halo studio --stop ends it.")
        return True
    if url:
        say(f"{target.display} is at {url} (no browser opens here: {out.get('why') or 'none answered'}).")
        hint = forward_hint(url)
        if hint:
            say(hint)
    else:
        say(f"Studio did not start{(': ' + out['why']) if out.get('why') else ''}.")
    say(f"The terminal {fallback} runs here instead.")
    return False
