"""halo_harness.studio.feed_kinds -- the frame kinds Studio's live feed asks
every session for, and the registry fields its `sessions` frame shows
(studio/events.py). Halo 3.0.5.0 (Fleet) adds `agent_state` (a row of a
session's agent tree changed), `agent_event` (an entry of a followed agent)
and `fleet` (a session joined, changed or left the registry), and the
`harness`, `project` and `parent` fields. ui/src/lib/events.ts KNOWN_KINDS
mirrors DEFAULT_KINDS."""

DEFAULT_KINDS = ("user_message", "message_start", "message_end", "text_chunk", "tool_use_start", "tool_result",
                 "tool_progress", "permission_request", "question", "plan_review", "approval_request", "todos",
                 "status", "error", "turn_done", "subagent_start", "subagent_end", "subagent_queued",
                 "subagent_progress", "notification", "phase", "compaction", "governor", "remote_attached",
                 "orchestra_state", "orchestra_claim", "orchestra_merge", "orchestra_gate", "orchestra_report",
                 "flow_state", "flow_step", "flow_gate", "flow_post", "flow_metric", "flow_report", "media_render",
                 "agent_state", "agent_event", "fleet")
PUBLIC_FIELDS = ("session_id", "title", "mode", "kind", "cwd", "started", "pid", "harness", "project", "parent")


def local_harness_id():
    """This harness's id for the `sessions` frame (3.0.5.0 R2), or None when it cannot be read."""
    try:
        from halo_harness.remote.fleet_identity import harness_id
        return harness_id()
    except Exception:
        return None
