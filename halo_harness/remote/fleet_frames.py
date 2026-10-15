"""halo_harness.remote.fleet_frames -- the Fleet frames a session publishes on
its control-socket feed (Halo 3.0.5.0 "Fleet" round R1).

* `agent_state`: every change to a row of the session's agent tree (data =
  the row, `agent_id` = that agent; agent/agent_registry.py);
* `agent_event`: each transcript entry of an agent someone follows
  (`agent_follow`; data = the entry, agent/agent_transcript.py);
* `fleet`: this session joining, changing or leaving the registry (data =
  the entry's public fields plus `action`: register | update | unregister),
  and `action: hello` as the first frame every new subscriber gets.

Every frame also carries `session_id` and `harness` (the harness id), set on
the hub's `meta` when the socket opens. The `subagent_*` frames are as before.
"""

from __future__ import annotations

import threading
import time


def _frame(kind: str, data: dict, agent_id=None) -> dict:
    return {"event": kind, "data": data, "turn": None, "agent_id": agent_id, "ts": time.time()}


def attach(act):
    """Publish the session's agent-tree changes on its hub; returns the listener."""
    from halo_harness.agent.agent_registry import tree_for
    hub = act.handle.hub

    def listener(kind: str, agent_id: str, data: dict) -> None:
        hub.publish_frame(_frame(kind, data, agent_id))
    tree_for(act.handle.session).add_listener(listener)
    return listener


def detach(act) -> None:
    tree = getattr(getattr(act.handle, "session", None), "_fleet_tree", None)
    if tree is not None and act.listener is not None:
        tree.remove_listener(act.listener)


def _fleet(act, action: str) -> dict:
    from halo_harness.remote.registry import public_entry
    return _frame("fleet", {**public_entry(act.entry), "action": action})


def fleet_frame(act, action: str) -> None:
    try:
        act.handle.hub.publish_frame(_fleet(act, action))
    except Exception:
        pass


def joined(act) -> None:
    """Announce the registration, then fill in the git-aware `project` off
    the opening thread (a slow or missing git never delays a launch)."""
    fleet_frame(act, "register")
    act.handle.hub.greeting = lambda: _fleet(act, "hello")  # every new subscriber's first frame

    def fill() -> None:
        from halo_harness.remote import fleet_identity, registry
        try:
            project = fleet_identity.project(act.handle.cwd)
        except Exception:
            return
        if project != act.entry.get("project"):
            act.entry["project"] = project
            if registry.update(act.session_id, project=project):
                fleet_frame(act, "update")
    threading.Thread(target=fill, daemon=True, name="halo-fleet-project").start()
