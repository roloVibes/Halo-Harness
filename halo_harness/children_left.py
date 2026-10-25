"""halo_harness.children_left -- what a quit leaves running of this home, in
words (Halo 3.2.2.0 R3), so `halo update` never surprises anyone: the quit's
one line ends with "left running: 1 background run from a shell (halo bg
stop <id>), Studio (another session is open; halo studio --stop)" -- only
the kinds that apply, each with the command that ends it; '' when nothing is
left.

Called after children_stop.stop_for_quit has stopped its targets, so every
live entry still in children.json is one the quit left on purpose.
"""

from __future__ import annotations

import os
from typing import Optional

from halo_harness import children as C


def _supervisor_live(state_dir) -> bool:
    try:
        from halo_harness.supervise import pulse
        return bool(pulse.read(C._state(state_dir)).get("running"))
    except Exception:
        return False


def _group(rows: list, suffix: str, command_for) -> str:
    """"1 background run from a shell (halo bg stop ab12)" / "2 ... (halo bg stop ab12, halo bg stop cd34)"."""
    what = rows[0].get("what") or "halo"
    n = len(rows)
    commands = ", ".join(dict.fromkeys(command_for(r) for r in rows))
    return f"{n} {C.label(what, n)} {suffix} ({commands})"


def left_running(state_dir=None, *, others: Optional[bool] = None) -> str:
    """"left running: ..." for what this home still runs after a quit, or ''."""
    from halo_harness.children_stop import other_live_sessions, studio_entry
    from halo_harness.update_stop import stop_command
    if others is None:
        others = bool(other_live_sessions())
    me = os.getpid()
    rows = [e for e in C.prune(state_dir) if e.get("pid") != me]
    parts: list = []
    supervisor = _supervisor_live(state_dir) or any(e.get("what") == "supervisor" for e in rows)
    shell: dict = {}
    owned: dict = {}
    for e in rows:
        what = e.get("what") or "halo"
        if what in ("supervisor", "studio"):
            continue
        if e.get("owner_pid") is None:
            shell.setdefault(what, []).append(e)
        elif e.get("owner_pid") != me:
            owned.setdefault(what, []).append(e)
    for group in shell.values():
        parts.append(_group(group, "from a shell", stop_command))
    for group in owned.values():
        parts.append(_group(group, "of a running halo", lambda r: f"it ends with pid {r.get('owner_pid')}"))
    if others and (studio_entry(state_dir) or any(e.get("what") == "studio" for e in rows)):
        parts.append("Studio (another session is open; halo studio --stop)")
    if supervisor:
        parts.append("supervisor (halo supervise stop)")
    return "left running: " + ", ".join(parts) if parts else ""


def quit_line(stopped: str, state_dir=None) -> str:
    """The quit's one line: what it stopped, then what it left."""
    try:
        left = left_running(state_dir)
    except Exception:
        left = ""
    return "; ".join(p for p in (stopped, left) if p)
