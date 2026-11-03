"""halo_harness.ollama_steward.server_log_tensorfold -- Halo 3.3.9.3: a TensorFold server's log as the steward's events
(server_rules_hf.classify and server_context_hf.Rules hand a `tensorfold` server's lines here; its `/health` and
`/metrics` are read beside the log by server_stats_tensorfold.py).

Every pattern is written from TensorFold's source tree, read 2026-11-02 at main 532589e4 -- zig/src/server/log.zig (each
line "[tensorfold] ...", with TENSORFOLD_LOG_TIME=1 after its UTC time "2026-11-02T10:00:00.123Z"; fatal startup lines
are "tensorfold: <why>" on stderr), zig/src/native/cuda_startup.zig (the capacity line "CUDA sm_89 device 0 (<GPU>):
model 16.02 GiB; 4 streams at once, 1.12 GiB each at a 32768-token window, of ... GiB left after a ... GiB reserve;
..."), zig/src/server/serve.zig ("serving <name> at http://<host>:<port>/v1 (sampling: ...; drafts: ...; context: N;
loaded in S s)"), zig/src/server/chat.zig (one "done <id> prompt=P cached=C ... tokens=T ... finish=F ... ttft=X
decode=Y elapsed=Z queued=Q tok/s=R" per request, and the max_tokens-while-thinking warning), log.zig's "ended <id>
reason=error (<why>) ..." and zig/src/server/live.zig's "N connections (W waiting) . decode ... tok/s" (drawn on a
terminal only). From the source, unverified against a live run: the Metal capacity line's wording is not in the source
read, so the reader keys on "N streams at once" and the backend word.

    classify(line, at=None, runtime="tensorfold") -> event | None   one line alone:
        capacity {backend, sm, device, model_gib, streams, window}; timing {phase: decode, tok_s, prompt_tokens,
        cached, tokens, queued_s, ttft_s}; queue {connections, waiting}; reply-cut; load-failed {why}; gpu-memory;
        other-error
    TfRules().feed(line, at=None) -> [event]   `--- halo starts:` -> load-start; the capacity line's facts and the
        serving line -> one load-result {window, streams, backend, sm, device, model_gib, load_s} (+ slow-load)
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Optional

from halo_harness.ollama_steward.server_rules import event

SAYS = ("load-start", "load-result", "capacity", "timing", "queue", "reply-cut", "load-failed", "gpu-memory",
        "other-error", "slow-load")
_STAMP = re.compile(r"^(\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d)(?:\.(\d+))?Z\s+")
_P = r"(?:\[tensorfold\]\s*)?"
_CAP = re.compile(_P + r"(?:CUDA sm_(\d+) device \d+ \(([^),]*)[^)]*\)|(Metal)\s*(?:\(([^),]*)[^)]*\))?)[^:]*: model ([\d.]+) GiB"
                  r".*?; (\d+) streams? at once(?:, ([\d.]+) GiB each at a (\d+)-token window)?")
_SERVING = re.compile(_P + r"serving (\S+) at http://(\S+?)/v1 \(.*?context: (\d+|unlimited); loaded in ([\d.]+)s\)")
_DONE = re.compile(_P + r"done (\S+) prompt=(\d+) cached=(\d+) .*?tokens=(\d+) .*?finish=(\w+).*? ttft=([\d.]+) "
                   r"decode=([\d.]+) elapsed=([\d.]+) queued=([\d.]+) tok/s=([\d.]+)")
_ENDED = re.compile(_P + r"ended (\S+) reason=error \(([^)]*)\)")
_LIVE = re.compile(_P + r"(\d+) connections? \((\d+) waiting\)")
_THINK_CUT = re.compile(_P + r"warning: a reply reached max_tokens while still thinking")
_FATAL = re.compile(r"^tensorfold(?: serve)?: (?:error: )?(.+)$")
_OOM = re.compile(r"out of memory|OutOfMemory|cudaErrorMemoryAllocation|CUDA_ERROR_OUT_OF_MEMORY", re.I)


def line_time(line: str) -> Optional[float]:
    m = _STAMP.match(line)
    if not m:
        return None
    try:
        t = _dt.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None
    return t.timestamp() + (int(m.group(3)) / 10 ** len(m.group(3)) if m.group(3) else 0.0)


def _strip(line: str) -> str:
    return _STAMP.sub("", line, count=1)


def classify(line: str, at=None, runtime: Optional[str] = None) -> Optional[dict]:
    rt = runtime or "tensorfold"
    raw = str(line or "").rstrip("\r\n")
    if not raw.strip() or raw.startswith("--- halo starts:"):
        return None
    at = line_time(raw) if line_time(raw) is not None else at
    text = _strip(raw)
    if m := _DONE.search(text):
        tok_s, queued = float(m.group(10)), float(m.group(9))
        return event("timing", f"a reply of {int(m.group(4)):,} tokens at {tok_s:g} tok/s ({m.group(5)})"
                     + (f", {queued:g} s queued" if queued else ""), raw, at=at, runtime=rt, phase="decode",
                     tok_s=tok_s, eval_tok_s=tok_s, prompt_tokens=int(m.group(2)), cached=int(m.group(3)),
                     tokens=int(m.group(4)), finish=m.group(5), ttft_s=float(m.group(6)), queued_s=queued)
    if m := _CAP.search(text):
        backend = "metal" if m.group(3) else "cuda"
        sm = int(m.group(1)) if m.group(1) else None
        device = m.group(2) or m.group(4)
        streams = int(m.group(6))
        return event("capacity", f"{streams} streams at once on {backend}" + (f" sm_{sm}" if sm else "")
                     + (f" ({device})" if device else "") + f", the model {m.group(5)} GiB", raw, at=at, runtime=rt,
                     backend=backend, sm=sm, device=device, model_gib=float(m.group(5)), streams=streams,
                     window=int(m.group(8)) if m.group(8) else None)
    if m := _LIVE.search(text):
        return event("queue", f"{m.group(1)} connections, {m.group(2)} waiting", raw, at=at, runtime=rt,
                     connections=int(m.group(1)), waiting=int(m.group(2)), source="log")
    if _THINK_CUT.search(text):
        return event("reply-cut", "a reply reached max_tokens while still thinking: its content is empty", raw, at=at,
                     runtime=rt, thinking=True)
    if m := _ENDED.search(text):
        kind = "gpu-memory" if _OOM.search(m.group(2)) else "other-error"
        return event(kind, f"TensorFold ended a request: {m.group(2)}", raw, at=at, runtime=rt, why=m.group(2))
    if m := _FATAL.match(text):
        return event("load-failed", f"TensorFold did not start: {m.group(1).strip()[:160]}", raw, at=at, runtime=rt,
                     why=m.group(1).strip()[:200])
    if _OOM.search(text):
        return event("gpu-memory", f"TensorFold ran out of memory: {text.strip()[:160]}", raw, at=at, runtime=rt)
    return None


class TfRules:
    """server_context_hf.Rules for a `tensorfold` server: the start, the capacity line and the serving line -> one
    load-start and one load-result."""

    def __init__(self) -> None:
        self.runtime = "tensorfold"
        self.model: Optional[str] = None
        self.facts: dict = {}
        self.load_at: Optional[float] = None
        self.clock: Optional[float] = None

    def feed(self, raw: str, at=None) -> list:
        text = str(raw or "").rstrip("\r\n")
        t = line_time(text)
        self.clock = t if t is not None else (at if at is not None else self.clock)
        if text.startswith("--- halo starts:"):
            m = re.search(r"--name (\S+)", text)
            self.model = m.group(1) if m else self.model
            self.facts, self.load_at = {}, self.clock
            return [event("load-start", f"Halo started TensorFold for {self.model or 'a model'}", text, at=self.clock,
                          model=self.model, runtime="tensorfold")]
        out: list = []
        if m := _SERVING.search(_strip(text)):
            self.model = m.group(1)
            out += self._loaded(text, None if m.group(3) == "unlimited" else int(m.group(3)), float(m.group(4)))
            return out
        ev = classify(text, at=at)
        if ev is not None:
            if ev["kind"] == "capacity":
                self.facts = dict(ev["data"])
            ev["model"] = ev.get("model") or self.model
            out.append(ev)
        return out

    def _loaded(self, text: str, window: Optional[int], load_s: float) -> list:
        f = self.facts
        say = (f"{self.model} loaded on TensorFold ({f.get('backend') or 'its backend'}"
               + (f" sm_{f['sm']}" if f.get("sm") else "") + (f", {f['streams']} streams" if f.get("streams") else "")
               + (f", window {window:,}" if window else "") + f"), {load_s:.0f} s")
        out = [event("load-result", say, text, at=self.clock, model=self.model, runtime="tensorfold", window=window,
                     streams=f.get("streams"), backend=f.get("backend"), sm=f.get("sm"), device=f.get("device"),
                     model_gib=f.get("model_gib"), load_s=load_s)]
        from halo_harness.ollama_steward.server_rules import SLOW_LOAD_S
        if load_s > SLOW_LOAD_S:
            out.append(event("slow-load", f"a load took {load_s:.0f} s (over 3 minutes): TensorFold reads the whole "
                             "checkpoint into memory before it opens its port", text, at=self.clock, model=self.model,
                             runtime="tensorfold", seconds=load_s))
        self.facts = {**f, "ready": True}
        return out

    def flush(self) -> list:
        return []
