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

from halo_harness.selfexec import python_argv  # 3.6.0.0 R10: never the working folder's copy
import os
import shlex
import shutil
from halo_harness import subprocess_safe as subprocess
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
    return [found] if found else python_argv()


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
        # fx studio batch 2: `do script` types into a fresh login shell, so Studio's home and HALO_* go in by name
        exports = "".join(f"export {k}={shlex.quote(v)}; " for k, v in sorted(_carried(env).items()))
        script = f"{exports}cd {shlex.quote(str(cwd))} && {' '.join(shlex.quote(p) for p in halo)}"
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


def _carried(env) -> dict:
    """The variables a halo started by Terminal.app needs from Studio: its home and HALO_*, never the owner markers
    and never a secret (they ride on osascript's command line)."""
    from halo_harness.closing import scrubbed_env
    return {k: v for k, v in scrubbed_env(dict(env)).items()
            if (k == "BRIDGE_STATE_DIR" or k.startswith("HALO_")) and k.replace("_", "").isalnum()
            and not any(w in k for w in ("TOKEN", "KEY", "SECRET", "PASS"))}


def _osascript_answer(proc) -> str:
    """'' when Terminal took the script (or macOS is still asking the person about it); else osascript's last line
    (-1743: Automation for Terminal not allowed)."""
    try:
        _out, err = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        return ""
    if not proc.returncode:
        return ""
    lines = (err or b"").decode("utf-8", "replace").strip().splitlines()
    return (lines[-1] if lines else f"osascript exited {proc.returncode}").strip()


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
    kwargs: dict = {"cwd": str(cwd)}
    if platform.startswith("win"):  # no standard handle at all: one given makes Popen pass all three, and halo's stdin
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10)  # is NUL, not its console's keys
    else:
        kwargs.update(start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                      stderr=subprocess.PIPE if platform == "darwin" else subprocess.DEVNULL)
    if spawn is None:  # 3.6.0.0 R10: a terminal window the person opened is its own session, never Studio's child
        from halo_harness.closing import kept_kwargs
        kwargs = kept_kwargs(kwargs)
    try:
        proc = (spawn or subprocess.Popen)(argv, **kwargs)
        from halo_harness.closing import register_kept
        register_kept(proc, "terminal", argv)
    except (OSError, ValueError):
        return False, NO_TERMINAL
    if platform == "darwin":  # fx studio batch 2: osascript says whether macOS let it reach Terminal
        refused = _osascript_answer(proc)
        if refused:
            return False, f"Terminal did not open ({refused}); run `halo` yourself"
    return True, OPENED_LINE.format(name=name)
