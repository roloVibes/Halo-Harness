"""halo_signal.service -- `bin/signal.py service`: the bridge, as the service the supervisor keeps running
(pack.yaml `contributes.services`: autostart, restart on-failure, health.json younger than 90 s).

It moves an older Halo's ~/.halo/remote/ Signal files into the data folder once, clears inbox/ files older than a
day, and then: with the pack's `on` false (`/signal off`) or `remote.enabled` false it writes `off` and ends with 0
(the supervisor leaves it stopped); with no signal-cli or no account it writes the one line that says what to do and
ends with 3 (the supervisor tries again later, 5 s doubling to 300 s, so an install is picked up); otherwise it runs
the bridge until the supervisor's stop file appears or it is told to stop. `transport_factory` is the tests' seam.
"""

from __future__ import annotations

import signal as _signal
import threading

from halo_harness.ext import remote as R

from halo_signal import box, files, media, settings
from halo_signal.health import Health


def make_transport(cfg: dict):
    from halo_signal.transport import SignalTransport
    return SignalTransport(cfg)


def preflight(h: Health) -> "tuple[dict | None, int]":
    for line in files.migrate():
        print(line, flush=True)
    media.sweep(files.path("inbox"))
    if not settings.get("on"):
        h.write("off", "the bridge is off (/signal on turns it back on)")
        return None, 0
    if not R.enabled():
        h.write("off", "remote.enabled is false, every transport's switch (halo config set remote.enabled true)")
        return None, 0
    if R.offline():
        h.write("off", "Halo's offline mode is on, and Signal is on the network (halo config set network.offline false)")
        return None, 0
    cfg = settings.load_signal()
    argv, where = box.find(cfg)
    if argv is None:
        h.write("stopped", f"{where} -- install it: {box.install_line()}")
        return None, 3
    if not cfg.get("account"):
        h.write("stopped", "no Signal account yet: link this computer (/signal link) or register a number "
                           "(/signal register +<number>)")
        return None, 3
    cfg["binary"] = argv
    return cfg, 0


def main(argv=None, *, transport_factory=make_transport, stop: "threading.Event | None" = None) -> int:
    h = Health()
    cfg, code = preflight(h)
    if cfg is None:
        print(h.line, flush=True)
        return code
    config = {**settings.bridge(), "identity_model": cfg.get("identity_model"), "own_aci": cfg.get("own_aci"),
              "model": settings.get("model")}
    stop = stop or threading.Event()
    for sig in (getattr(_signal, "SIGTERM", None), getattr(_signal, "SIGBREAK", None)):
        if sig is not None:
            try:
                _signal.signal(sig, lambda *_a: stop.set())
            except (ValueError, OSError):
                pass
    tail = str(cfg.get("account") or "")[-4:]
    print(f"signal bridge: answering for the account ending {tail}; the supervisor's stop file or Ctrl+C ends it",
          flush=True)
    from halo_signal.bridge import Bridge
    bridge = Bridge(config, transport_factory(cfg), health=h)
    try:
        bridge.run(stop)
    except KeyboardInterrupt:
        stop.set()
    if bridge.ended:  # 3.3.13.1 (REMOTE-2): a switch turned off while it ran: one line, exit 0 (it stays stopped)
        print(f"signal bridge: {bridge.ended}", flush=True)
    return 0
