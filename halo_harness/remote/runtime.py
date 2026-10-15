"""halo_harness.remote.runtime -- open / close the control socket of every session in THIS process and
keep its registry entry fresh (Halo 2.0.9 round 2; Fleet 3.0.5.0). `fleet.enabled` (default true): every
session opens its loopback socket and lists itself in `~/.halo/run/sessions.json`: the TUI (`start_for_
controller`), `halo -p` (`start_for_print`; Paperclip heartbeats and Orchestra workers are `-p` children) and
a flow's org run (`start_for_session`). A private session (`--private`, `/private on`, `fleet.private`) opens
and registers nothing; `remote.enabled` is only the Signal bridge's switch. Each open and close also tells the
fleet relay (fleet/relay_runtime.py, R2). Openers return None when off or on any failure (a socket problem never
stops a launch); `stop_one`, `stop_for` and `stop` (all of them, also at exit) are idempotent."""

from __future__ import annotations

import atexit
import contextlib
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from halo_harness.remote import fleet_identity as FI

_lock = threading.RLock()
_actives: list = []
_reopeners: list = []  # (controller, opener) for sessions that went (or started) private
_private_flag: Optional[bool] = None  # /private on|off in this process; None: --private / fleet.private decide
_atexit_registered = False
fleet_enabled, remote_enabled = FI.fleet_enabled, FI.remote_enabled


@dataclass
class Active:
    handle: object
    server: object
    session_id: str
    controller: object = None
    mode: str = ""
    entry: dict = field(default_factory=dict)
    reopen: Optional[Callable] = None
    listener: Optional[Callable] = None

    @property
    def endpoint(self) -> str:
        return self.server.endpoint or ""


def private() -> bool:
    return _private_flag if _private_flag is not None else FI.private_configured()


def private_chip() -> bool:
    """Cheap, for the status bar's `private` chip: this process holds a private session."""
    return _private_flag is True or (_private_flag is None and bool(_reopeners))


def enabled() -> bool:
    """True when sessions open their control socket: `fleet.enabled`, not private."""
    return fleet_enabled() and not private()


def active() -> Optional[Active]:
    """The first session this process opened (the TUI's, in the TUI)."""
    return _actives[0] if _actives else None


def actives() -> list:
    return list(_actives)


def _open(handle, controller=None, *, kind: Optional[str] = None, reopen=None) -> Optional[Active]:
    global _atexit_registered
    from halo_harness.remote import fleet_frames, registry
    from halo_harness.remote.control_socket import ControlServer
    with _lock:
        for act in _actives:
            if act.handle is handle or act.handle.session is handle.session:
                return act
        server = None
        try:
            if kind:
                handle.kind = kind
            handle.attach()
            server = ControlServer(handle).start()
            mode = str(handle.session.permission_engine.mode or "")
            entry = registry.make_entry(
                session_id=handle.session_id, cwd=handle.cwd, endpoint=server.endpoint, token=server.token,
                title=handle.title(), mode=mode, kind=handle.kind, harness=FI.harness(),
                project=FI.project_stub(handle.cwd), parent=FI.parent_from_env())
            registry.register(entry)
            act = Active(handle, server, entry["session_id"], controller, mode, entry, reopen)
            handle.hub.meta.update(session_id=act.session_id, harness=entry["harness"].get("id"))
            act.listener = fleet_frames.attach(act)
            handle.hub.add_observer(lambda ev, a=act: _watch_status(a, ev))
            _actives.append(act)
            if not _atexit_registered:
                atexit.register(stop)
                _atexit_registered = True
        except Exception:
            try:
                if server is not None:
                    server.close()
                handle.detach()
            except Exception:
                pass
            return None
    fleet_frames.joined(act)
    _relay("session_opened", act)
    return act


def _relay(name: str, act) -> None:  # 3.0.5.0 R2: fleet/relay_runtime.py follows these sessions
    with contextlib.suppress(Exception):  # the relay never stands in a session's way
        getattr(__import__("halo_harness.fleet.relay_runtime", fromlist=["_"]), name)(act)


def _watch_status(act: Active, ev) -> None:
    """Keep `mode` (and the key, after /clear or a fork) in the registry."""
    if ev.kind != "status" or act not in _actives:
        return
    # a sub-agent's own status events reach this tap too (agent_id, session_id "agent-<id>"): never ours
    if getattr(ev, "agent_id", None) or str(ev.data.get("session_id") or "").startswith("agent-"):
        return
    from halo_harness.remote import fleet_frames, registry
    sid, mode = ev.data.get("session_id"), ev.data.get("permission_mode")
    if sid and sid != act.session_id:
        old, act.session_id, act.mode = act.session_id, sid, str(mode or "")
        act.entry = {**act.entry, "session_id": sid, "title": act.handle.title(), "mode": act.mode,
                     "started": time.time()}
        act.handle.hub.meta["session_id"] = sid
        registry.unregister(old)
        registry.register(act.entry)
        fleet_frames.fleet_frame(act, "register")
    elif mode and mode != act.mode:
        act.mode = act.entry["mode"] = str(mode)
        registry.update(act.session_id, mode=act.mode)


def _remember(controller, opener) -> None:
    with _lock:
        if not any(c is controller for c, _ in _reopeners):
            _reopeners.append((controller, opener))


def start_for_controller(controller) -> Optional[Active]:
    if getattr(controller, "session", None) is None or not hasattr(controller, "add_event_tap"):
        return None

    def opener() -> Optional[Active]:
        from halo_harness.remote.handle import ControllerHandle
        return _open(ControllerHandle(controller), controller, reopen=opener)
    if not fleet_enabled():
        return None
    if private():
        _remember(controller, opener)
        return None
    return opener()


def start_for_print(session, cwd, **kw) -> "Optional[tuple]":
    """`(PrintModeHandle, Active)` or None; the caller wraps its turn stream
    with `handle.tee(...)` and calls `stop()` when the run ends."""
    if not enabled():
        return None
    from halo_harness.remote.print_handle import PrintModeHandle
    handle = PrintModeHandle(session, cwd, **kw)
    act = _open(handle, kind=FI.session_kind("print"))
    return (handle, act) if act is not None else None


def start_for_session(session, cwd, *, kind: str = "flow") -> Optional[Active]:
    """A session that runs work with no turn loop of its own (a flow's org
    run); its caller publishes events on `act.handle.hub` and calls `stop_one`."""
    if not enabled():
        return None
    from halo_harness.remote.print_handle import PrintModeHandle
    return _open(PrintModeHandle(session, cwd), kind=kind)


def stop_one(act: Optional[Active]) -> None:
    with _lock:
        if act is None or act not in _actives:
            return
        _actives.remove(act)
    from halo_harness.remote import fleet_frames, registry
    fleet_frames.fleet_frame(act, "unregister")
    for fn in (lambda: _relay("session_closed", act), lambda: registry.unregister(act.session_id),
               lambda: fleet_frames.detach(act), act.server.close, act.handle.detach):
        try:
            fn()
        except Exception:
            pass


def stop() -> None:
    for act in list(_actives):
        stop_one(act)


def stop_for(controller) -> None:
    with _lock:
        _reopeners[:] = [(c, fn) for c, fn in _reopeners if c is not controller]
        mine = [a for a in _actives if a.controller is controller]
    for act in mine:
        stop_one(act)


def set_private(on: bool) -> str:
    """`/private on|off`: close (and forget) or reopen this process's sockets."""
    global _private_flag
    with _lock:
        _private_flag = bool(on)
    if on:
        for act in list(_actives):
            if act.reopen is not None:
                _remember(act.controller, act.reopen)
            stop_one(act)
        return ("Private: on. This session closed its control socket and left the registry: Studio, "
                "`halo remote` and the fleet no longer see it. `/private off` lists it again.")
    if not fleet_enabled():
        return "Private: off. fleet.enabled is false, so no control socket opens (`halo config set fleet.enabled true`)."
    with _lock:
        pending, _reopeners[:] = list(_reopeners), []
    opened = [act for act in (fn() for _c, fn in pending) if act is not None]
    if opened:
        return f"Private: off. The control socket is open again ({opened[0].endpoint}); Studio lists this session."
    if active() is not None:
        return "Private: off. This session's control socket is already open."
    return "Private: off. Nothing to reopen in this process (a `halo -p` run started private stays private)."


def note_title(title: str) -> None:
    act = active()
    if act is not None and title:
        from halo_harness.remote import registry
        act.entry["title"] = title
        registry.update(act.session_id, title=title)


def status_line() -> str:
    """The one-line `/remote` answer: this session's socket and the registry."""
    act = active()
    try:
        from halo_harness.remote import registry
        count = len(registry.list_live())
    except Exception:
        count = 0
    plural = "" if count == 1 else "s"
    if act is None:
        hint = (" (fleet.enabled is false; `halo config set fleet.enabled true`, then restart)" if not fleet_enabled()
                else " (a private session: `/private off` lists it again)" if private() else "")
        return f"control socket: off{hint}\nregistry: {count} live session{plural}"
    return f"control socket: on {act.endpoint}\nregistry: {count} live session{plural}"
