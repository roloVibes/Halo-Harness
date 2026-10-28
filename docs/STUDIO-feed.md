# Studio: the live feed

Read this when you want how Studio's pages get their live frames: the Server-Sent Events stream, its kinds and its catch-up.

Part of [Halo Studio](STUDIO.md), which lists every part.

## The live feed

`GET /api/events?t=<token>&sessions=all|<session id>` is a Server-Sent Events stream. Studio watches the live-session registry
(`~/.halo/run/sessions.json`) every 2 s and attaches to each running session's control socket (`subscribe`, 1 s timeouts, off
the request threads); every frame is `{session_id, event, data, turn, agent_id, ts}` under `event: <kind>`, a `sessions` frame
lists the attached sessions (title, mode, kind, cwd, started, pid; never an endpoint or token) whenever one attaches or
detaches, and `: ping` keeps the stream open every 15 s. Each browser gets its own queue of 512 frames (the oldest dropped
first). The shell's status bar, the Orchestra panels and the rail's Session dot read it. Studio's own Orchestra runner publishes
its run log here too (`orchestra_*` frames), and its files watcher `files_changed` (3.2.2.0: [what is on
disk](STUDIO-shell.md#what-is-on-disk-as-it-changes-3220)).

**What Session reads, and the delays that remain (3.1.8.0).** The Session tab (and Fleet) reads the feed, not a poll: a
session's own `message_end` (the end of each model call) and `status` (a turn's start and end) frames move its spend, tokens,
turns, context, model and busy dot on the frame the terminal's status bar moves on (a frame with an `agent_id`, or whose
`data.session_id` starts with `agent-`, is a sub-agent's and moves nothing of the session's); `agent_state` moves an agent's row
(its state, tool, model calls, cost and, since 3.1.8.0, its tokens); `agent_event` and the raw `text_chunk` / `tool_use_start` /
`tool_result` frames fill the streams and Live; `fleet` and `sessions` frames and the asks, `turn_done` and `subagent_start` /
`subagent_end` re-read `GET /api/fleet` for the tree. A local session's `turn_done`, `message_end` or `status` drops GET fleet's
cached snapshot, so a re-read never answers from before it. What still stands between the terminal and the tab, each with its
number:

| Stage | Delay |
|---|---|
| a session's own figures (`message_end`, `status`) | none added: the socket, Studio's pump and the browser's stream pass each frame on as it comes |
| the spend's ticker | counts up over 600 ms (a drop shows at once) |
| text | one `text_chunk` per 2.0 s or 1800 bytes, sent early when any other frame comes (remote/feed.py) |
| an agent row's text and cost alone | at most once per 1.0 s, the last change at the end of that second; a state, tool, model-call or task change goes at once (agent/agent_registry.py) |
| GET fleet's snapshot | kept 1.0 s (dropped on the frames above); each session's socket probe times out after 1.0 s and the snapshot waits at most 1.5 s for them (fleet/local_view.py) |
| the re-read after a frame | 300 ms (an unknown session, an agent leaving waiting), 350 ms (a fleet frame), 400 ms (a sessions frame), 600 ms (an ask, turn_done, a sub-agent's start or end), 800 ms (a command's answer) |
| a GET answer against a frame | an answer asked before a frame, or up to 2.5 s after it, keeps the frame's figures: the higher spend, tokens and turns, the frame's context, and its busy dot unless an ask waits; an older answer never lands after a newer one |
| a new session | attached within 2 s (the registry scan); a pump that errors waits 10 s before it tries again |
| the sparkline | a point on every change, and every 5 s while nothing moves |
| the feed down | GET fleet every 4 s until it is back |
