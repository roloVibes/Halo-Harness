"""halo_harness.headless_session -- a session with no terminal (Halo 3.3.11.0 R2): `halo --headless
--session-for studio`. Studio's server starts one from the Session section (studio/sessions_new_api.py); it runs
the SAME loop the TUI runs and writes the same session log under `~/.halo/sessions/`, so `halo --resume <id>`
opens it later in a terminal like any other session.

How it differs from the TUI:

* the controller is `tui/bootstrap.build_controller`'s, started without the Textual app; this process is the
  one reader of `controller.events` (the TUI's drain loop), so the queue never grows, and the events still reach
  the control socket's feed through the controller's tap;
* the control socket (`remote/runtime._open`) is its ONLY door: the registry row says `kind: headless` and
  `parent: studio:<pid>` (`--session-for` names who started it; `HALO_SESSION_PARENT`, when the starter set it,
  wins), so Fleet, the Map, Session and `halo studio --session` list it as a session of this harness;
* an ask (a permission card, a question, a plan, an approval) parks: the session is interactive, so its waiter
  holds the turn until an `answer` comes through the socket (Studio's Prompt panel); `status` lists the parked
  asks with the time each was first seen (`parked`), which the Fleet attention row reads;
* `/quit` (or `/exit`) through the socket's `slash`, the socket's `shutdown` (Studio's "End session"), SIGTERM
  or the worker ending stop it; the registry row goes with it. A quit here never stops the Studio that started
  it (`Controller.quit_stops_children` False): only what this process itself started.
"""

from __future__ import annotations

import os
import queue
import signal
import sys
import threading
import time
from typing import Optional

from halo_harness.remote.handle import ControllerHandle

KIND = "headless"
DRAIN_S = 0.2
CARD_KINDS = ("permission", "question", "plan", "approval")


class HeadlessHandle(ControllerHandle):
    """The TUI's handle with this process's own ending (`done`) and the parked asks in its status."""
    kind = KIND

    def __init__(self, controller, done: threading.Event) -> None:
        super().__init__(controller)
        self.done = done
        self._seen: dict = {}  # ask id -> when this handle first saw it parked
        self._seen_lock = threading.Lock()

    def _close_after_shutdown(self, text: str) -> None:
        self.done.set()

    def parked(self, pending: Optional[dict] = None) -> list:
        """`[{id, kind, since}]`: every ask the session waits on now, oldest first."""
        pending = self._pending() if pending is None else pending
        now = time.time()
        rows = []
        with self._seen_lock:
            live = set()
            for kind in CARD_KINDS:
                for rid in pending.get(kind) or []:
                    rid = str(rid)
                    live.add(rid)
                    rows.append({"id": rid, "kind": kind, "since": self._seen.setdefault(rid, now)})
            for gone in [k for k in self._seen if k not in live]:
                self._seen.pop(gone, None)
        return sorted(rows, key=lambda r: (r["since"], r["id"]))

    def status(self) -> dict:
        data = super().status()
        data.update(parked=self.parked(data.get("pending") or {}), accepts_turns=True)
        return data

    def run_slash(self, name: str, args: str = "") -> str:
        if (name or "").lstrip("/").strip() in ("quit", "exit"):
            self._note("/quit")
            self.done.set()
            return "Ending this session (no terminal): the registry row goes with it; `halo --resume` opens its log."
        return super().run_slash(name, args)


def _say_no_door(line: str) -> int:
    print(f"halo: {line}", file=sys.stderr)
    return 2


def _mark_parent(who: str) -> None:
    from halo_harness.remote import session_identity as FI
    if not FI.parent_from_env():
        os.environ[FI.PARENT_ENV] = f"{who or 'studio'}:{os.getppid()}"


def _stop_own_children(state_dir) -> None:
    """What this process itself started (a background run, a schedule fire); never the Studio above it."""
    try:
        from halo_harness import children as C
        from halo_harness.children_stop import stop_entry
        me = os.getpid()
        for e in C.prune(state_dir):
            if e.get("owner_pid") == me and e.get("what") != "studio":
                stop_entry(e, state_dir=state_dir, timeout=5.0)
    except Exception:
        pass


def _autoname(controller) -> None:
    """The TUI's first-turn title (`tui/app.py _autoname_worker`), into the registry row."""
    try:
        title = controller.maybe_autoname_title()
    except Exception:
        title = None
    if title:
        from halo_harness.remote.runtime import note_title
        note_title(title)


def _watch_turns(handle, controller) -> None:
    named = threading.Event()

    def on_event(ev) -> None:
        if ev.kind == "turn_done" and not getattr(ev, "agent_id", None) and not named.is_set():
            named.set()
            threading.Thread(target=_autoname, args=(controller,), daemon=True, name="halo-headless-title").start()
    handle.hub.add_observer(on_event)


def drain(controller, done: threading.Event) -> None:
    """The TUI's drain loop without the TUI: read every event until the worker ends or `done` is set."""
    while not done.is_set():
        try:
            ev = controller.events.get(timeout=DRAIN_S)
        except queue.Empty:
            continue
        if ev is None:  # the worker is gone
            return


def run(args) -> int:
    """`halo --headless`: build, open the socket, serve until the end; the exit code."""
    from halo_harness.remote import runtime
    if getattr(args, "print_mode", False):
        return _say_no_door("--headless runs a whole session; it does not take -p/--print")
    if not runtime.control_enabled():
        return _say_no_door("control.enabled is false: a session with no terminal has its control socket as its only door "
                       "(`halo config set control.enabled true`)")
    if getattr(args, "private", False) or runtime.private():
        return _say_no_door("a private session opens no control socket, and a session with no terminal has no other door")
    _mark_parent(getattr(args, "session_for", None) or "studio")
    from halo_harness.tui.bootstrap import build_controller
    controller, _registry, _facade = build_controller(args)
    controller.quit_stops_children = False
    done = threading.Event()
    controller.on_control_shutdown = lambda _text: done.set()
    controller.start()
    handle = HeadlessHandle(controller, done)
    act = runtime._open(handle, controller)  # noqa: SLF001  (start_for_controller with this handle and kind)
    if act is None:
        controller.quit()
        print("halo: the control socket did not open, so this session would have no door; it ended", file=sys.stderr)
        return 1
    _watch_turns(handle, controller)
    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGBREAK", None)):
        if sig is not None:
            try:
                signal.signal(sig, lambda *_a: done.set())
            except (ValueError, OSError):
                pass
    print(f"halo: headless session {act.session_id} (no terminal; its door: {act.endpoint})", flush=True)
    try:
        drain(controller, done)
    except KeyboardInterrupt:
        pass
    finally:
        code = controller.quit()
        _stop_own_children(controller.state_dir)
    print(f"halo: headless session {act.session_id} ended", flush=True)
    return int(code or 0)
