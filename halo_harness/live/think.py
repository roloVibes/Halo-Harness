"""halo_harness.live.think -- an agent's thinking on the feed (Halo 3.3.16.2, the owner: "make watching a model think
much better").

The loop yields a `thinking_delta` for every piece of reasoning the provider streams (native Anthropic thinking as it
comes; the OpenAI-dialect `reasoning_content` / `reasoning_details` of DeepSeek, Kimi, GLM, OpenRouter and Ollama's
`thinking` once, at the end of the stream). The control socket's hub never forwarded those deltas
(remote/feed.py NOT_FORWARDED). `ThinkFeed` turns one agent's deltas into `thinking_chunk` frames the agent tree
publishes for EVERY agent of the session (agent/agent_observe.py), so Studio's Live column shows each thought as one
growing THINK row:

    {"id": "t<n>", "text": "<the new part>"}                         while the thought grows (at most every FLUSH_S)
    {"id": "t<n>", "text": "<the rest>", "end": true, "ms": 4200}     when the agent acts (a tool, text, the turn's end)
    {"id": "t<n>", "text": "", "end": true, "tokens": 812}            at message_end, when the provider reports
                                                                      `reasoning_tokens` for that call

`ms` is the wall time from the thought's first delta to its end, sent only when the thought came in more than one
delta (a one-shot reasoning block has no length of its own). A model with no thinking yields no frame: nothing is
invented. Nothing here calls a model.
"""
from __future__ import annotations

import itertools
import time

FLUSH_S = 0.6
FLUSH_BYTES = 1200
CHUNK_CAP = 8000  # one frame's text at most (a one-shot reasoning block is cut, the transcript keeps it whole)
ENDERS = frozenset({"text_delta", "tool_use_start", "tool_use_ready", "message_end", "turn_done", "error",
                    "permission_request", "question", "plan_review", "approval_request"})
_IDS = itertools.count(1)


class ThinkFeed:
    """One agent's thoughts: `feed(ev)` -> the frame data to publish (a list, often empty)."""

    def __init__(self, clock=time.monotonic) -> None:
        self.clock = clock
        self.id = ""
        self.parts: list = []
        self.size = 0
        self.t0 = 0.0
        self.sent_at = 0.0
        self.deltas = 0
        self.last_id = ""  # the thought message_end's reasoning_tokens belong to

    @property
    def open(self) -> bool:
        return bool(self.id)

    def feed(self, ev) -> list:
        kind = getattr(ev, "kind", "")
        data = getattr(ev, "data", None) or {}
        if kind == "thinking_delta":
            return self._delta(str(data.get("text") or ""))
        out = self.end() if kind in ENDERS else []
        if kind == "message_end":
            tokens = (data.get("usage") or {}).get("reasoning_tokens") if isinstance(data.get("usage"), dict) else None
            if isinstance(tokens, int) and not isinstance(tokens, bool) and tokens > 0 and self.last_id:
                out.append({"id": self.last_id, "text": "", "end": True, "tokens": tokens})
            self.last_id = ""
        return out

    def _delta(self, piece: str) -> list:
        if not piece:
            return []
        now = self.clock()
        if not self.id:
            self.id, self.t0, self.sent_at, self.deltas = f"t{next(_IDS)}", now, now, 0
            self.last_id = self.id
        self.deltas += 1
        self.parts.append(piece)
        self.size += len(piece.encode("utf-8", "replace"))
        if self.size >= FLUSH_BYTES or now - self.sent_at >= FLUSH_S:
            return [self._chunk(end=False)]
        return []

    def end(self) -> list:
        """The thought's last frame (its rest, `end`, and `ms` when it streamed); [] when no thought is open."""
        if not self.id:
            return []
        out = self._chunk(end=True)
        self.id, self.deltas = "", 0
        return [out]

    def _chunk(self, *, end: bool) -> dict:
        text = "".join(self.parts)
        self.parts, self.size, self.sent_at = [], 0, self.clock()
        d = {"id": self.id, "text": text[:CHUNK_CAP]}
        if len(text) > CHUNK_CAP:
            d["cut"] = True
        if end:
            d["end"] = True
            if self.deltas > 1:
                d["ms"] = int(round((self.clock() - self.t0) * 1000))
        return d
