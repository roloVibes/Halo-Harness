"""halo_harness.remote.runtime -- open / close the control socket of every session in THIS process and
keep its registry entry fresh (Halo 2.0.9 round 2; 3.0.5.0). `control.enabled` (default true): every
session opens its loopback socket and lists itself in `~/.halo/run/sessions.json`: the TUI (`start_for_
controller`), `halo -p` (`start_for_print`; Orchestra workers are `-p` children) and
a session started without a terminal (`start_for_session`). A private session (`--private`, `/private on`, `control.private`) opens
and registers nothing; `remote.enabled` is every transport's switch (remote/notify.py). Openers return None when off or on any failure (a socket problem never
stops a launch); `stop_one`, `stop_for` and `stop` (all of them, also at exit) are idempotent."""

from __future__ import annotations

import atexit
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from halo_harness.remote import session_identity as FI

_lock = threading.RLock()
_actives: list = []
_reopeners: list = []  # (controller, opener) for sessions that went (or started) private
_private_flag: Optional[bool] = None  # /private on|off in this process; None: --private / control.private decide
_atexit_registered = False
_last_error: Optional[str] = None  # R12: why the last open failed, one plain line (None after a success)
log = logging.getLogger(__name__)
LISTED_CHECK_S = 1.0  # 3.6.0.4: a session reads sessions.json for its own row at most this often
_clock = time.monotonic  # the tests' clock for that
control_enabled, remote_enabled = FI.control_enabled, FI.remote_enabled


def last_error() -> Optional[str]:
    """One plain line saying why this process's last control-socket open failed, or None."""
    return _last_error


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
    listed_at: float = float("-inf")  # 3.6.0.4: when _keep_listed last read the file (by _clock)

    @property
    def endpoint(self) -> str:
        return self.server.endpoint or ""


def private() -> bool:
    return _private_flag if _private_flag is not None else FI.private_configured()


def private_chip() -> bool:
    """Cheap, for the status bar's `private` chip: this process holds a private session."""
    return _private_flag is True or (_private_flag is None and bool(_reopeners))


def enabled() -> bool:
    """True when sessions open their control socket: `control.enabled`, not private."""
    return control_enabled() and not private()


def active() -> Optional[Active]:
    """The first session this process opened (the TUI's, in the TUI)."""
    return _actives[0] if _actives else None


def actives() -> list:
    return list(_actives)


def _open(handle, controller=None, *, kind: Optional[str] = None, reopen=None) -> Optional[Active]:
    global _atexit_registered, _last_error
    from halo_harness.remote import agent_frames, registry
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
            entry["first_words"] = _logged_first_words(handle)  # 3.6.0.2 P70: a resumed one has some
            registry.register(entry)
            act = Active(handle, server, entry["session_id"], controller, mode, entry, reopen)
            handle.hub.meta.update(session_id=act.session_id, harness=entry["harness"].get("id"))
            act.listener = agent_frames.attach(act)
            handle.hub.add_observer(lambda ev, a=act: _watch_status(a, ev))
            handle.hub.add_observer(lambda ev, a=act: _watch_first_words(a, ev))  # 3.6.0.2 P70
            _actives.append(act)
            if not _atexit_registered:
                atexit.register(stop)
                _atexit_registered = True
        except Exception as e:
            from halo_harness.remote.control_socket import ControlSocketError
            # R12: never a silent None -- one plain line, kept for the caller (last_error) and logged
            _last_error = str(e) if isinstance(e, ControlSocketError) else \
                f"the control socket did not open ({type(e).__name__}: {e})"
            log.warning("%s", _last_error)
            try:
                if server is not None:
                    server.close()
                handle.detach()
            except Exception:
                pass
            return None
        _last_error = None
    agent_frames.joined(act)
    return act


def _watch_status(act: Active, ev) -> None:
    """Keep `mode` (and the key, after /clear or a fork) in the registry. 3.6.0.2 P16: the new row names the id it
    follows and is written BEFORE the old row leaves, so a list read always finds one of the two."""
    if ev.kind != "status" or act not in _actives:
        return
    # a sub-agent's own status events reach this tap too (agent_id, session_id "agent-<id>"): never ours
    if getattr(ev, "agent_id", None) or str(ev.data.get("session_id") or "").startswith("agent-"):
        return
    from halo_harness.remote import agent_frames, registry
    sid, mode = ev.data.get("session_id"), ev.data.get("permission_mode")
    if sid and sid != act.session_id:
        old, act.session_id, act.mode = act.session_id, sid, str(mode or "")
        act.entry = {**act.entry, "session_id": sid, "title": act.handle.title(), "mode": act.mode,
                     "started": time.time(), "follows": old,
                     "first_words": _logged_first_words(act.handle)}  # P70: "" after /clear
        act.handle.hub.meta["session_id"] = sid
        registry.register(act.entry)
        registry.unregister(old)
        agent_frames.registry_frame(act, "register")
    elif mode and mode != act.mode:
        act.mode = act.entry["mode"] = str(mode)
        registry.update(act.session_id, mode=act.mode)
    _keep_listed(act)


def _keep_listed(act: Active) -> None:
    """3.6.0.4: a session whose row left sessions.json (an older Halo pruned it after one refused probe, or its probes
    failed for 30 s while the terminal was paused) puts the row back here, at a status event it publishes anyway: no
    thread, no timer, at most one file read per LISTED_CHECK_S. S4-2: it registers OUTSIDE `_lock` (register can wait
    up to LOCK_S for the file's lock, and stop_one needs `_lock` to end the session), checking `_actives` under it
    before and after: a session that ended in between has the row it just wrote removed, so it never stays listed."""
    now = _clock()
    if now - act.listed_at < LISTED_CHECK_S:
        return
    act.listed_at = now
    from halo_harness.remote import registry
    try:
        if registry.listed(act.session_id):
            return
        with _lock:
            if act not in _actives:
                return
        registry.register(dict(act.entry))
        with _lock:
            ended = act not in _actives
        if ended:
            registry.unregister(act.session_id)
    except Exception:
        log.debug("could not put the session's registry row back", exc_info=True)


def _logged_first_words(handle) -> str:
    """3.6.0.2 P70: the first words of the first user message already in the session's log ("" for none)."""
    try:
        from halo_harness.agent.sessions import _first_user_text
        from halo_harness.remote.registry import first_words
        return first_words(_first_user_text(handle.session.log.nodes()))
    except Exception:
        return ""


def _watch_first_words(act: Active, ev) -> None:
    """3.6.0.2 P70: the main session's first `user_message` gives a row with none its `first_words`."""
    if ev.kind != "user_message" or getattr(ev, "agent_id", None) or act not in _actives:
        return
    if act.entry.get("first_words"):
        return
    from halo_harness.remote import registry
    words = registry.first_words((ev.data or {}).get("text"))
    if words:
        act.entry = {**act.entry, "first_words": words}
        registry.update(act.session_id, first_words=words)


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
    if not control_enabled():
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


def start_for_session(session, cwd, *, kind: str) -> Optional[Active]:
    """A session that runs work with no turn loop of its own (a mission
    worker); its caller publishes events on `act.handle.hub` and calls `stop_one`."""
    if not enabled():
        return None
    from halo_harness.remote.print_handle import PrintModeHandle
    return _open(PrintModeHandle(session, cwd), kind=kind)


def stop_one(act: Optional[Active]) -> None:
    with _lock:
        if act is None or act not in _actives:
            return
        _actives.remove(act)
    from halo_harness.remote import agent_frames, registry
    agent_frames.registry_frame(act, "unregister")
    for fn in (lambda: registry.unregister(act.session_id),
               lambda: agent_frames.detach(act), act.server.close, act.handle.detach):
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
                "`halo remote` no longer see it. `/private off` lists it again.")
    if not control_enabled():
        return "Private: off. control.enabled is false, so no control socket opens (`halo config set control.enabled true`)."
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
        hint = (" (control.enabled is false; `halo config set control.enabled true`, then restart)" if not control_enabled()
                else " (a private session: `/private off` lists it again)" if private() else "")
        return f"control socket: off{hint}\nregistry: {count} live session{plural}"
    return f"control socket: on {act.endpoint}\nregistry: {count} live session{plural}"
