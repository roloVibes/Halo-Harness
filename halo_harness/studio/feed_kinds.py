"""halo_harness.studio.feed_kinds -- the frame kinds Studio's live feed asks
every session for, and the registry fields its `sessions` frame shows
(studio/events.py). Halo 3.0.5.0 adds `agent_state` (a row of a
session's agent tree changed), `agent_event` (an entry of a followed agent)
and `registry` (a session joined, changed or left the registry; `live` is the
Studio watcher's own: the attention queue changed), and the `harness`,
`project` and `parent` fields; 3.0.7.0 R3 `design_turn` (a Design
turn's steps, published by Studio itself); 3.2.2.0 R4 `turn_marker` (the line
a turn ends with: done / waiting on you / stopped); 3.3.16.2 `thinking_chunk` (an agent's thought as it grows,
live/think.py) and `agent_talk` (one agent's words to another, live/talk.py). ui/src/lib/events.ts KNOWN_KINDS
mirrors DEFAULT_KINDS."""

DEFAULT_KINDS = ("user_message", "message_start", "message_end", "text_chunk", "tool_use_start", "tool_result",
                 "tool_progress", "permission_request", "question", "plan_review", "approval_request", "todos",
                 "status", "error", "turn_done", "subagent_start", "subagent_end", "subagent_queued",
                 "subagent_progress", "notification", "phase", "compaction", "governor", "remote_attached",
                 "orchestra_state", "orchestra_claim", "orchestra_merge", "orchestra_gate", "orchestra_report",
                 "turn_marker", "thinking_chunk", "agent_talk",
                 "agent_state", "agent_event", "registry", "live")  # 3.3.13.0 R2: design_turn and media_render: the design pack's
PUBLIC_FIELDS = ("session_id", "title", "mode", "kind", "cwd", "started", "pid", "harness", "project", "parent")


def local_harness_id():
    """This harness's id for the `sessions` frame (3.0.5.0 R2), or None when it cannot be read."""
    try:
        from halo_harness.remote.session_identity import harness_id
        return harness_id()
    except Exception:
        return None
