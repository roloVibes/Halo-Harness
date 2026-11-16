"""halo_harness.term_profile -- what the terminal Halo writes to says it supports (3.6.0.0 R12).

An Apple silicon Mac beeped when a session started in Apple Terminal (`TERM_PROGRAM=Apple_Terminal`, no
`COLORTERM`). The captured start-up bytes held three sequences that terminal does not know:

* `ESC ] 22 ; default BEL` -- Textual's pointer-shape request (the kitty pointer-shape protocol), sent once when
  the first screen mounts and again whenever the pointer shape changes. Apple Terminal has no OSC 22; an OSC it does
  not know ends early and the BEL that was meant to close it rings the bell.
* `ESC [ ? 2048 $ p` -- Textual's DECRQM query for in-band resize. Textual itself already skips its other `$p`
  query on Apple Terminal ("it writes a single 'p' into the terminal"); this one it does not.
* `ESC ] 2 ; halo BEL` -- Halo's own window title (termtitle.py). Apple Terminal does take a BEL-closed title, but a
  title is cosmetic and the start-up must hold no BEL byte at all, so Halo leaves the title to Apple Terminal there.

Every other terminal keeps exactly what it had. `env` defaults to the process environment.
"""

from __future__ import annotations

import os
from typing import Optional


def is_apple_terminal(env: Optional[dict] = None) -> bool:
    env = os.environ if env is None else env
    return (env.get("TERM_PROGRAM") or "") == "Apple_Terminal"


def sets_title(env: Optional[dict] = None) -> bool:
    """Whether Halo writes its OSC 2 window title (BEL-closed) to this terminal."""
    return not is_apple_terminal(env)


# Terminals known to take OSC 22 (the kitty pointer-shape protocol), by TERM or TERM_PROGRAM.
_OSC22_TERMS = ("xterm-kitty", "foot", "foot-extra", "xterm-ghostty", "wezterm")
_OSC22_PROGRAMS = ("kitty", "ghostty", "WezTerm")


def _terminal_unnamed(env) -> bool:
    """fix pass 2: over ssh TERM_PROGRAM does not arrive (ssh forwards TERM and LANG/LC_* only) and sudo resets the
    environment, so an Apple Terminal there looked like any other terminal and got the BEL-closed OSC 22 again.
    True when the session runs over ssh or sudo and the terminal is not one known to take OSC 22."""
    if not (env.get("SSH_CONNECTION") or env.get("SSH_TTY") or env.get("SSH_CLIENT") or env.get("SUDO_USER")):
        return False
    return (env.get("TERM") or "") not in _OSC22_TERMS and (env.get("TERM_PROGRAM") or "") not in _OSC22_PROGRAMS


def takes_pointer_shape(env: Optional[dict] = None) -> bool:
    """Whether Textual's OSC 22 pointer-shape request may be sent."""
    env = os.environ if env is None else env
    return not is_apple_terminal(env) and not _terminal_unnamed(env)


def takes_mode_queries(env: Optional[dict] = None) -> bool:
    """Whether a DECRQM `CSI ? Pn $ p` mode query may be sent."""
    env = os.environ if env is None else env
    return not is_apple_terminal(env) and not _terminal_unnamed(env)


def quiet_driver(driver_class):
    """`driver_class` itself, or on a terminal that does not take DECRQM queries a subclass of it that leaves out
    the in-band-resize query (that terminal never answers it, so nothing else changes)."""
    if takes_mode_queries() or not hasattr(driver_class, "_query_in_band_window_resize"):
        return driver_class

    class QuietDriver(driver_class):
        def _query_in_band_window_resize(self) -> None:
            return None

    QuietDriver.__name__ = QuietDriver.__qualname__ = f"Quiet{driver_class.__name__}"
    return QuietDriver
