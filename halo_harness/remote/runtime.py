"""halo_harness.remote.runtime -- open / close the control socket for THIS
process's session and keep its registry entry fresh (Halo 2.0.9 round 2).

Behind config `remote.enabled` (default false): `start_for_controller` is
called by the TUI at mount, `start_for_print` by `headless.run_print_mode`.
Both return None when the key is off or anything fails -- a control socket
problem never stops a session from launching. `stop` is idempotent and runs
from `Controller.quit()` (every TUI quit path, including the Ctrl+C card),
from print mode's `finally`, and from an `atexit` hook (a crash).
"""

from __future__ import annotations

import atexit
import threading
from dataclasses import dataclass
from typing import Optional

_lock = threading.Lock()
_active: "Optional[Active]" = None
_atexit_registered = False


@dataclass
class Active:
    handle: object
    server: object
    session_id: str
    controller: object = None
    mode: str = ""

    @property
    def endpoint(self) -> str:
        return self.server.endpoint or ""


def enabled() -> bool:
    try:
        from halo_harness.theme import get_config_value
        value = get_config_value("remote.enabled", False)
    except Exception:
        return False
    return value is True or (isinstance(value, str) and value.strip().lower() in ("1", "true", "yes", "on"))


def active() -> Optional[Active]:
    return _active


def _open(handle, controller=None) -> Optional[Active]:
    global _active, _atexit_registered
    from halo_harness.remote import registry
    from halo_harness.remote.control_socket import ControlServer
    with _lock:
        if _active is not None:
            return _active
        server = None
        try:
            handle.attach()
            server = ControlServer(handle).start()
            sid = handle.session_id
            registry.register(registry.make_entry(
                session_id=sid, cwd=handle.cwd, endpoint=server.endpoint, token=server.token,
                title=handle.title(), mode=str(handle.session.permission_engine.mode or ""), kind=handle.kind))
            _active = Active(handle, server, sid, controller, str(handle.session.permission_engine.mode or ""))
            handle.hub.add_observer(_watch_status)
            if not _atexit_registered:
                atexit.register(stop)
                _atexit_registered = True
            return _active
        except Exception:
            try:
                if server is not None:
                    server.close()
                handle.detach()
            except Exception:
                pass
            return None


def _watch_status(ev) -> None:
    """Keep `mode` (and the key, after /clear or a fork) in the registry."""
    if ev.kind != "status" or _active is None:
        return
    from halo_harness.remote import registry
    act = _active
    sid, mode = ev.data.get("session_id"), ev.data.get("permission_mode")
    if sid and sid != act.session_id:
        old, act.session_id = act.session_id, sid
        entry = registry.make_entry(session_id=sid, cwd=act.handle.cwd, endpoint=act.server.endpoint,
                                    token=act.server.token, title=act.handle.title(), mode=str(mode or ""),
                                    kind=act.handle.kind)
        act.mode = str(mode or "")
        registry.unregister(old)
        registry.register(entry)
    elif mode and mode != act.mode:
        act.mode = str(mode)
        registry.update(act.session_id, mode=act.mode)


def start_for_controller(controller) -> Optional[Active]:
    if not enabled() or getattr(controller, "session", None) is None or not hasattr(controller, "add_event_tap"):
        return None
    from halo_harness.remote.handle import ControllerHandle
    return _open(ControllerHandle(controller), controller)


def start_for_print(session, cwd, **kw) -> "Optional[tuple]":
    """`(PrintModeHandle, Active)` or None; the caller wraps its turn stream
    with `handle.tee(...)` and calls `stop()` when the run ends."""
    if not enabled():
        return None
    from halo_harness.remote.print_handle import PrintModeHandle
    handle = PrintModeHandle(session, cwd, **kw)
    act = _open(handle)
    return (handle, act) if act is not None else None


def stop() -> None:
    global _active
    with _lock:
        act, _active = _active, None
    if act is None:
        return
    try:
        from halo_harness.remote import registry
        registry.unregister(act.session_id)
    except Exception:
        pass
    for fn in (act.server.close, act.handle.detach):
        try:
            fn()
        except Exception:
            pass


def stop_for(controller) -> None:
    act = _active
    if act is not None and act.controller is controller:
        stop()


def note_title(title: str) -> None:
    act = _active
    if act is not None and title:
        from halo_harness.remote import registry
        registry.update(act.session_id, title=title)


def status_line() -> str:
    """The one-line `/remote` answer this round."""
    act = _active
    try:
        from halo_harness.remote import registry
        count = len(registry.list_live())
    except Exception:
        count = 0
    plural = "" if count == 1 else "s"
    if act is None:
        hint = "" if enabled() else " (remote.enabled is false; `halo config set remote.enabled true`, then restart)"
        return f"control socket: off{hint}\nregistry: {count} live session{plural}"
    return f"control socket: on {act.endpoint}\nregistry: {count} live session{plural}"
