"""halo_harness.studio.halo_terminal -- Setup's Done opens a terminal running halo when no `halo init` waits for it
(Halo 3.3.15.0 R6; studio/setup_done.py `post_done`).

    open_halo(cwd)   -> (opened, line)

Where a terminal comes from:

    Windows   a new console window (CREATE_NEW_CONSOLE) running halo
    macOS     Terminal.app through osascript
    Linux     with a display (DISPLAY / WAYLAND_DISPLAY): $TERMINAL, then x-terminal-emulator, qterminal (Kali's),
              xfce4-terminal, gnome-terminal, konsole, mate-terminal, kitty, alacritty, foot, xterm -- the first found
              on PATH, given the right flag for "run this command"

halo itself is `halo` on PATH, else this Python with `-m halo_harness`; it starts in `cwd` with Studio's environment,
so it is the same home Studio serves and the session shows in Studio's Session section as any `halo` does. When none of
the above is there (a Linux box with no display or no known terminal, SSH, VMware's text console) nothing starts and
the line says so: NO_TERMINAL. A process under a test home (`BRIDGE_TEST_HOME`) never opens a window unless the test
passes its own `spawn`.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from typing import Callable, Optional

INIT_LINE = "halo is starting in your terminal"
OPENED_LINE = "halo is starting in a new terminal window ({name})"
NO_TERMINAL = "no terminal found to start halo in; run `halo` yourself"

# (program, the words before the command it runs)
LINUX_TERMINALS = (("x-terminal-emulator", ["-e"]), ("qterminal", ["-e"]), ("xfce4-terminal", ["-x"]),
                   ("gnome-terminal", ["--"]), ("konsole", ["-e"]), ("mate-terminal", ["-x"]), ("kitty", []),
                   ("alacritty", ["-e"]), ("foot", []), ("xterm", ["-e"]))


def halo_argv(which: Callable = shutil.which) -> list:
    found = which("halo")
    return [found] if found else [sys.executable, "-m", "halo_harness"]


def terminal_argv(cwd, *, env=None, platform: Optional[str] = None, which: Callable = shutil.which) -> "tuple[str, list]":
    """`(name, argv)` that opens a terminal running halo in `cwd`; `("", [])` when there is none here."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    halo = halo_argv(which)
    if platform.startswith("win"):
        return "a console window", halo
    if platform == "darwin":
        if not which("osascript"):
            return "", []
        script = f"cd {shlex.quote(str(cwd))} && {' '.join(shlex.quote(p) for p in halo)}"
        return "Terminal", ["osascript", "-e", f'tell application "Terminal" to do script {_applescript(script)}']
    if not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")) or env.get("SSH_CONNECTION") or env.get("SSH_TTY"):
        return "", []
    own = shlex.split(env.get("TERMINAL") or "")
    if own and which(own[0]):
        return own[0], own + ["-e"] + halo
    for name, flag in LINUX_TERMINALS:
        if which(name):
            return name, [name] + flag + halo
    return "", []


def _applescript(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def open_halo(cwd, *, env=None, platform: Optional[str] = None, which: Callable = shutil.which,
              spawn: Optional[Callable] = None) -> "tuple[bool, str]":
    """Open a terminal running halo in `cwd`: `(True, OPENED_LINE)`, or `(False, NO_TERMINAL)` when none can open."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if spawn is None and env.get("BRIDGE_TEST_HOME"):
        return False, NO_TERMINAL
    name, argv = terminal_argv(cwd, env=env, platform=platform, which=which)
    if not argv:
        return False, NO_TERMINAL
    kwargs: dict = {"cwd": str(cwd), "stdin": subprocess.DEVNULL}
    if platform.startswith("win"):
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    else:
        kwargs.update(start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        (spawn or subprocess.Popen)(argv, **kwargs)
    except (OSError, ValueError):
        return False, NO_TERMINAL
    return True, OPENED_LINE.format(name=name)
