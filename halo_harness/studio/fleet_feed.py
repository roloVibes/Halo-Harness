"""halo_harness.studio.fleet_feed -- the fleet watcher's tap on Studio's live
feed (Halo 3.0.5.0 "Fleet" round R4; 3.1.0.0 R2 cut it out of
fleet_watch_io.py): attach and detach a tap (the local sessions' frames
reach it with no browser open), and publish a frame of Studio's own.
"""

from __future__ import annotations


def attach_tap(server, tap) -> None:
    taps = getattr(server, "event_taps", None)
    if taps is None:
        taps = server.event_taps = []
    if tap not in taps:
        taps.append(tap)
    from halo_harness.studio.events import bridge_for
    bridge_for(server).start()  # the local sessions' frames reach the tap with no browser open


def detach_tap(server, tap) -> None:
    for holder in (getattr(server, "event_taps", None), getattr(getattr(server, "events", None), "taps", None)):
        if holder is not None and tap in holder:
            holder.remove(tap)


def publish(server, frame: dict) -> None:
    bridge = getattr(server, "events", None)
    if bridge is not None:
        bridge.publish_local(frame)
