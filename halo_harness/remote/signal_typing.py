"""halo_harness.remote.signal_typing -- the typing indicator while a turn runs.

Signal shows "typing" for 15 seconds unless it is stopped, so a running turn
re-sends `sendTyping` every `interval` seconds (default 10) and one
`stop: true` when the turn ends. All sends happen on the keeper's own thread,
so the bridge loop never waits on signal-cli for them.
"""

from __future__ import annotations

import threading

from halo_harness.remote.signal_errors import SignalError


class TypingKeeper:
    def __init__(self, transport, interval: float = 10.0) -> None:
        self.transport = transport
        self.interval = interval
        self._lock = threading.Lock()
        self._active: dict = {}

    def start(self, recipient: str) -> bool:
        """Begin typing for `recipient`; False when already typing."""
        with self._lock:
            if recipient in self._active:
                return False
            ev = threading.Event()
            self._active[recipient] = ev
        threading.Thread(target=self._run, args=(recipient, ev), daemon=True, name="halo-signal-typing").start()
        return True

    def stop(self, recipient: str) -> None:
        with self._lock:
            ev = self._active.pop(recipient, None)
        if ev is not None:
            ev.set()

    def stop_all(self) -> None:
        with self._lock:
            events = list(self._active.values())
            self._active.clear()
        for ev in events:
            ev.set()

    def active(self) -> list:
        with self._lock:
            return sorted(self._active)

    def _send(self, recipient: str, stop: bool) -> None:
        try:
            self.transport.send_typing(recipient, stop=stop)
        except SignalError:
            pass
        except Exception:
            pass

    def _run(self, recipient: str, ev: threading.Event) -> None:
        self._send(recipient, False)
        while not ev.wait(self.interval):
            self._send(recipient, False)
        self._send(recipient, True)
