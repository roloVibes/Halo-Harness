"""halo_harness.packs.event_triggers -- a bio's trigger on a pack's event
(Halo 3.2.0.0 R5; agents_schedule.py's TeamScheduler polls it each tick).

A bio's `triggers:` already starts it on a Halo event (`{on: event, name:
<kind>}`, one shot per session). The name space now holds pack events too:

    triggers:
      - {on: event, name: "doc-review:review.done", prompt: "Summarise the review"}
      - {event: "doc-review:review.done"}      # the same, short

A `<pack>:<kind>` name fires the bio when that pack publishes that kind
after the trigger was armed, from any process: publish_event appends every
event to the pack's events log (packs/events_log.py), which this reads.

    normalize(trigger) -> the trigger with the short form spelled out
    poll(scheduler)    -> fires each armed pack-event trigger whose event came
"""

from __future__ import annotations


def normalize(t):
    if isinstance(t, dict) and "event" in t and "on" not in t:
        return dict({k: v for k, v in t.items() if k != "event"}, on="event", name=t["event"])
    return t


def poll(scheduler) -> None:
    from halo_harness.packs.events_log import is_pack_event, since
    with scheduler._lock:
        pending = [t for t in scheduler.triggers if t.get("on") == "event" and not t.get("fired")
                   and is_pack_event(t.get("on_value"))]
    due = []
    for t in pending:
        if since(t["on_value"], float(t.get("armed_at") or 0)):
            with scheduler._lock:
                if not t.get("fired"):
                    t["fired"] = True
                    due.append(t)
    for t in due:
        scheduler._fire(t, f"event {t['on_value']}")
