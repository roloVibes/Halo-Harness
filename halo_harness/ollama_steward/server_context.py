"""halo_harness.ollama_steward.server_context -- Halo 3.3.4.0 R2: the server
log rules that need the lines around a line, a model and a clock
(`server_rules.classify` reads one line alone):

- a 500 within PAIR_LINES of "srv stop: cancel task" is `cancel-task` (the
  client went away while the prompt was being read: its timeout, not a
  server error); a 500 right after "no user query found" is that event's,
  not a second one;
- a 499 after "aborting load" is one `client-gave-up` with `during_load`;
  the "Load failed ... context canceled" beside it is part of it;
- `retry-loop`: 3 or more 500s in 3 minutes for one model (the model of
  the newest "template selection" line);
- `slow-load` (a load over 3 minutes) and `stall` (an active request with
  no progress for 5 minutes) also fire from `tick(now)` while watching;
- `server-down`: `api_result(False)` three times in a row.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.ollama_steward.server_rules import (
    _MODEL, _STARTED, DOWN_N, PAIR_LINES, RETRY_N, RETRY_S, SLOW_LOAD_S, STALL_S, _short_model, classify, event,
    line_time, strip_prefix,
)


class Rules:
    """The rules that need the lines around a line, a model and a clock."""

    def __init__(self) -> None:
        self.n = 0
        self.clock: Optional[float] = None
        self.model: Optional[str] = None
        self.pending: list = []  # [(line no, event, waits for)] a 500 or an aborted load waiting for its partner
        self.marks: dict = {}  # "cancel" / "no-user-query" / "abort" -> the line number it was last seen
        self.fails: dict = {}  # model -> [times of 500s]
        self.looping: set = set()
        self.load_at: Optional[float] = None
        self.active_at: Optional[float] = None
        self.flagged: set = set()
        self.down = 0

    def _near(self, mark: str, lines: int) -> bool:
        return mark in self.marks and self.n - self.marks[mark] <= lines

    def _expire(self) -> list:
        out = [e for n, e, _w in self.pending if self.n - n > PAIR_LINES]
        self.pending = [p for p in self.pending if self.n - p[0] <= PAIR_LINES]
        return out

    def feed(self, raw: str, at=None) -> list:
        """One line -> the events it completes (possibly none)."""
        self.n += 1
        line = strip_prefix(raw)
        t = at if at is not None else line_time(line)
        self.clock = t if t is not None else self.clock
        if m := _MODEL.search(line):
            self.model = _short_model(m.group(1))
        self._activity(line)
        ev = classify(line, at=self.clock)
        out = self._expire()
        if ev is None:
            return out
        ev["model"] = ev.get("model") or self.model
        kind = ev["kind"]
        if kind == "cancel-task":  # one cancel pairs with one 500, before or after it
            hit = next((p for p in self.pending if p[2] == "cancel"), None)
            if hit:
                self.pending.remove(hit)
                out.append(self._cancelled(hit[1], line))
            else:
                self.marks["cancel"] = self.n
            return out
        if kind == "no-user-query":
            self.marks["no-user-query"] = self.n
        if kind == "http-500":
            out += self._count_500()
            if self._near("no-user-query", 5):  # that 500 is the chat prompt error's own
                del self.marks["no-user-query"]
                return out
            if self._near("cancel", PAIR_LINES):
                del self.marks["cancel"]
                return out + [self._cancelled(ev, line)]
            self.pending.append((self.n, ev, "cancel"))
            return out
        if kind == "client-gave-up" and ev["data"].get("during_load"):
            self.marks["abort"] = self.n
            self.pending.append((self.n, ev, "499"))
            return out
        if kind == "client-gave-up":
            hit = next((p for p in self.pending if p[2] == "499"), None)
            if hit:
                self.pending.remove(hit)
                ev["say"] = (f"the client gave up after {ev['data'].get('seconds')} s while the model was loading: "
                             "the load was thrown away; a fast retry never helps, wait at least a load's time")
                ev["data"]["during_load"] = True
            return out + [ev]
        if kind == "load-failed" and ev["data"].get("client_abort") and self._near("abort", 3):
            return out
        return out + [ev]

    def _cancelled(self, ev: dict, cancel_line: str) -> dict:
        took = ev["data"].get("seconds")
        new = event("cancel-task", f"a request was ended while its prompt was still being read (HTTP 500 after "
                    f"{took} s): the client's timeout, not a server error -- wait at least as long as the prompt "
                    "takes at this host's prompt speed", ev["evidence"] + " / " + cancel_line.strip(),
                    at=ev["at"], model=ev.get("model"), **ev["data"])
        return new

    def _count_500(self) -> list:
        model, now = self.model or "?", self.clock or 0.0
        times = [t for t in self.fails.get(model, []) if now - t <= RETRY_S] + [now]
        self.fails[model] = times
        if len(times) < RETRY_N:
            self.looping.discard(model)
            return []
        if model in self.looping:
            return []
        self.looping.add(model)
        return [event("retry-loop", f"{len(times)} requests failed with HTTP 500 in 3 minutes for {model}: a request "
                      "that cannot succeed is resent unchanged -- change it first (compact, the measured window, a "
                      "longer wait)", f"{len(times)} x HTTP 500", at=self.clock, model=model, count=len(times))]

    def _activity(self, line: str) -> None:
        t = self.clock
        if 'msg="starting llama-server"' in line:
            self.load_at, self.flagged = t, self.flagged - {"slow-load"}
        elif _STARTED.search(line) or 'msg="Load failed"' in line:
            self.load_at = None
        if "processing task" in line or "new prompt" in line or "print_timing" in line:
            self.active_at, self.flagged = t, self.flagged - {"stall"}
        elif "stop processing" in line or "all slots are idle" in line:
            self.active_at = None

    def tick(self, now: float) -> list:
        """Time-based rules while watching (a load or a request with no progress); also emits a waiting 500."""
        out = [e for _n, e, _w in self.pending if e.get("at") is not None and now - e["at"] > 10]
        self.pending = [p for p in self.pending if p[1] not in out]
        if self.load_at is not None and now - self.load_at > SLOW_LOAD_S and "slow-load" not in self.flagged:
            self.flagged.add("slow-load")
            out.append(event("slow-load", "a load has run for over 3 minutes; keep the request open until it ends",
                             "starting llama-server", at=now, model=self.model))
        if self.active_at is not None and now - self.active_at > STALL_S and "stall" not in self.flagged:
            self.flagged.add("stall")
            out.append(event("stall", "a request has made no progress for 5 minutes", "no slot progress", at=now,
                             model=self.model))
        return out

    def flush(self) -> list:
        """Every waiting event (the end of a read from the top)."""
        out = [e for _n, e, _w in self.pending]
        self.pending = []
        return out

    def api_result(self, ok: bool, now: float) -> list:
        self.down = 0 if ok else self.down + 1
        if self.down == DOWN_N:
            return [event("server-down", "the server did not answer /api/version three times in a row",
                          "GET /api/version", at=now)]
        return []
