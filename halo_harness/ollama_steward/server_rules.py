"""halo_harness.ollama_steward.server_rules -- Halo 3.3.4.0 R2: the server
log's lines turned into events, the read-only watcher's rules ported with
R1's corrections (knowledge/symptoms.md is the spec; knowledge/
log-vocabulary.md names every line).

`classify(line) -> event | None` reads one line alone;
`server_context.Rules().feed(line)` adds what needs the lines around it, a
model and a clock (the cancelled prompt read, the aborted load, the retry
loop, the slow load, the stall, the server that stopped answering).

An event: {kind, severity, say, evidence, at, model, data}.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Optional

SEVERITY = {k: "error" for k in ("http-500", "no-user-query", "load-failed", "gpu-memory", "server-down",
                                  "other-error", "retry-loop", "queue-full")}
SEVERITY.update({k: "warn" for k in ("prompt-trimmed", "reply-cut", "window-full", "cancel-task", "client-gave-up",
                                     "cpu-spill", "slow-load", "stall", "reloaded", "no-prompt-cache")})
SEVERITY.update({k: "info" for k in ("loaded", "unloaded", "startup", "load-result")})  # 3.3.6.0 R3: load-result
KINDS = tuple(SEVERITY)
PAIR_LINES = 25  # the PC's log: a cancel task 3 to 19 lines from its 500
RETRY_N, RETRY_S, SLOW_LOAD_S, STALL_S, DOWN_N = 3, 180.0, 180.0, 300.0, 3

_JOURNAL = re.compile(r"^[A-Z][a-z]{2} [ \d]\d \d\d:\d\d:\d\d \S+ [^\s:]+?(?:\[\d+\])?: ")
_GIN = re.compile(r"\[GIN\]\s+(\d{4}/\d\d/\d\d)\s*-\s*(\d\d:\d\d:\d\d)\s*\|\s*(\d{3})\s*\|\s*([^|]*?)\s*\|"
                  r"\s*([^|]*?)\s*\|\s*(\w+)\s+\"?([^\"\s]+)")
_TIME = re.compile(r"\btime=(\S+)")
_TRUNC = re.compile(r"limit=(\d+)\s+prompt=(\d+)\s+keep=(\d+)")
_OFFLOAD = re.compile(r"offloaded (\d+)/(\d+) layers")
_OVERFLOW = re.compile(r"(\d+) layers \(\s*(\d+) overflowing\)")
_STARTED = re.compile(r"llama-server started in ([\d.]+) seconds")
_CUT = re.compile(r"stop processing: n_tokens = (\d+), truncated = 1")
_OOM = re.compile(r"out of memory|cudaMalloc failed|CUDA error|runtime OOM detected", re.IGNORECASE)
_CANCEL = re.compile(r"srv\s+stop: cancel task")
_MODEL = re.compile(r'msg="template selection" model=(\S+)')
_DUR = re.compile(r"([\d.]+)(h|ms|µs|us|ns|m|s)")
_DUR_S = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 1e-3, "µs": 1e-6, "us": 1e-6, "ns": 1e-9}


def strip_prefix(line: str) -> str:
    """A journald line's `Mon DD HH:MM:SS host ollama[pid]: ` prefix removed."""
    return _JOURNAL.sub("", (line or "").rstrip("\r\n"), count=1)


def go_seconds(text: str) -> Optional[float]:
    """Gin's "20.0031019s" / "251.1156ms" / "1m3.2s" -> seconds."""
    parts = _DUR.findall(str(text or "").strip())
    return round(sum(float(n) * _DUR_S[u] for n, u in parts), 3) if parts else None


def line_time(line: str) -> Optional[float]:
    """Epoch seconds of a slog `time=` or a [GIN] date (local time), else None."""
    m = _TIME.search(line)
    try:
        if m:
            return _dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00")).timestamp()
        g = _GIN.search(line)
        if g:
            return _dt.datetime.strptime(f"{g.group(1)} {g.group(2)}", "%Y/%m/%d %H:%M:%S").timestamp()
    except ValueError:
        return None
    return None


def _short_model(name: str) -> str:
    return re.sub(r"^registry\.ollama\.ai/(?:library/)?", "", name.strip('"'))


def event(kind: str, say: str, evidence: str, *, at=None, model=None, **data) -> dict:
    return {"kind": kind, "severity": SEVERITY.get(kind, "info"), "say": say, "evidence": (evidence or "")[:400],
            "at": at, "model": model, "data": data}


def _gin(line: str, at) -> Optional[dict]:
    g = _GIN.search(line)
    if not g:
        return None
    status, secs, client, path = int(g.group(3)), go_seconds(g.group(4)), g.group(5), g.group(7)
    took = f"{secs:g} s" if secs is not None else "?"
    if status == 499:
        return event("client-gave-up", f"the client gave up after {took}; a fast retry never helps, wait at least "
                     "as long as a load takes", line, at=at, status=499, seconds=secs, client=client, path=path)
    if status == 500:
        return event("http-500", f"a request failed with HTTP 500 after {took}: read the lines around it", line,
                     at=at, status=500, seconds=secs, client=client, path=path)
    if status == 503:
        return event("queue-full", "the request queue is full (HTTP 503): send fewer calls at once to this host",
                     line, at=at, status=503, client=client, path=path)
    return None


def classify(line: str, at=None) -> Optional[dict]:
    """One line -> an event, or None for a line no rule reads."""
    line = strip_prefix(line)
    at = at if at is not None else line_time(line)
    if "[GIN]" in line:
        return _gin(line, at)
    if "truncating input prompt" in line and (m := _TRUNC.search(line)):
        limit, prompt, keep = (int(x) for x in m.groups())
        window = 2 * limit - keep  # limit = num_ctx - (num_ctx - keep) / 2
        return event("prompt-trimmed", f"the runner cut a {prompt:,}-token prompt to {limit:,}: the request asked for "
                     f"a {window:,} window. Send the measured window (a bigger one), and compact when the prompt is "
                     "past it", line, at=at, limit=limit, prompt=prompt, keep=keep, window_sent=window)
    if "forcing full prompt re-processing" in line:  # 3.3.5.0 R4: a hybrid / SWA model keeps no prompt cache
        return event("no-prompt-cache", "the model re-reads the whole prompt every turn (no prompt cache: sliding-window "
                     "or hybrid/recurrent memory), so every call pays the full prompt read", line, at=at)
    if m := _CUT.search(line):
        n = int(m.group(1))
        return event("reply-cut", f"a reply stopped at {n:,} tokens because the window filled: keep a reply reserve "
                     "and compact", line, at=at, n_tokens=n)
    if "failed to find a memory slot" in line:
        return event("window-full", "the window filled mid-reply (no free cell for the next token): keep a reply "
                     "reserve and compact", line, at=at)
    if "no user query found in messages" in line:
        return event("no-user-query", "Ollama dropped old messages to fit the window and no user message was left "
                     "(HTTP 500): send a window that holds the whole prompt, or compact", line, at=at)
    if _CANCEL.search(line):
        return event("cancel-task", "a request was ended while its prompt was being read", line, at=at)
    if 'msg="Load failed"' in line:
        err = re.search(r'error="([^"]*)"', line)
        return event("load-failed", f"a load failed: {err.group(1) if err else 'no reason given'}", line, at=at,
                     client_abort="context canceled" in line)
    if "aborting load" in line:
        return event("client-gave-up", "the client closed the connection while the model was loading: the load "
                     "was thrown away, a fast retry starts it again from zero", line, at=at, during_load=True)
    m = _OFFLOAD.search(line)
    if m and int(m.group(1)) < int(m.group(2)):
        a, b = int(m.group(1)), int(m.group(2))
        return event("cpu-spill", f"{a} of {b} layers are on the GPU, the rest runs on the CPU (llama.cpp kept its "
                     "memory margin, or another program holds the card)", line, at=at, offloaded=a, layers=b)
    m = _OVERFLOW.search(line)
    if m and int(m.group(2)) > 0:
        return event("cpu-spill", f"{m.group(2)} of {m.group(1)} layers overflow to system RAM", line, at=at,
                     layers=int(m.group(1)), overflowing=int(m.group(2)))
    if "illegal memory access" in line:  # 3.3.6.0 R2: a CUDA abort, not a full card (ollama_steward/fingerprints.py)
        return event("gpu-memory", "llama-server hit a CUDA error (an illegal memory access) and dies: the measured "
                     "crashes were a spilled window with flash attention and a q8_0 KV cache (halo ollama crashes)", line, at=at)
    if _OOM.search(line):
        return event("gpu-memory", "the GPU ran out of memory: another model or program holds it, or the window's "
                     "cache did not fit", line, at=at)
    m = _STARTED.search(line)
    if m and float(m.group(1)) > SLOW_LOAD_S:
        return event("slow-load", f"a load took {float(m.group(1)):.0f} s (over 3 minutes)", line, at=at,
                     seconds=float(m.group(1)))
    if 'msg="server config"' in line:
        return event("startup", "the server started: its settings and card were read again", line, at=at)
    if "level=ERROR" in line:
        msg = re.search(r'msg="([^"]*)"', line)
        return event("other-error", f"the server logged an error: {msg.group(1) if msg else line[-160:]}", line, at=at)
    return None
