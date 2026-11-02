"""halo_harness.ollama_steward.server_log_ft -- Halo 3.3.9.1: a FreeToken server's log as the steward's events
(server_rules_hf.classify and server_context_hf.Rules hand a `freetoken` server's lines here).

Every pattern is written from FreeToken's source tree, read 2026-11-02 -- utils/logger.py (`[YYYY-MM-DD|HH:MM:SS|pid=N]
LEVEL message`, ANSI colours even into a file: the daemon strips them, daemon/logfmt.py), engine/engine.py (the load:
"Auto-selected MoE strategy", "Resolved config: moe_strategy=...", "MoE experts: <kind> via <kernel>",
"--moe-cache-auto resolved moe_cache_size=N num_pages=M", "Prefill warmup complete for lengths [...] in S s", the
pin-budget lines), server/api_server.py ("API server is ready to serve on host:port"), scheduler/status.py ("Prefill
batch, ... input throughput (token/s): X", "Decode batch, ... gen throughput (token/s): X"), moe/offload_cache.py
(`--moe-collect-stats`: "MoE decode, pinned N layers: hit H%, per layer-step miss M fetch F cpu C"), kernel/_toolchain.py
(the nvcc / CUDA mismatch). From the source, unverified against a live run: a live log may word them otherwise.

    classify(line, at=None, runtime="freetoken") -> event | None      one line alone:
        timing {phase: prefill | decode, tok_s, eval_tok_s (decode), new_tokens}; expert-cache {hit, miss, fetch, cpu,
        layers, group}; pin-cap (warn) {banks_gib, budget_gib, locked}; kernel-jit {seconds} (a warmup over JIT_S);
        load-failed {pinned | toolchain}; gpu-memory; other-error (an exception line, an ERROR line)
    FtRules().feed(line, at=None) -> [event]   the context: the model (Halo's start line), the strategy, the expert
        format, the cache size -> one load-result at "API server is ready", with load_s from Halo's start line
    line_time(line) -> epoch seconds of FreeToken's own stamp | None;  strip(line) -> the line without ANSI codes
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Optional

from halo_harness.ollama_steward.server_rules import event

SAYS = ("load-result", "timing", "expert-cache", "pin-cap", "kernel-jit", "load-failed", "gpu-memory", "other-error",
        "slow-load")
JIT_S = 60.0  # a startup warmup this long is kernels compiling, not the warmup itself (Halo's threshold)
_ANSI = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")  # daemon/logfmt.py's own pattern
_TIME = re.compile(r"^\[(\d{4}-\d\d-\d\d)\|(\d\d:\d\d:\d\d)[^\]]*\]\s*(\w+)?\s*")
_STRATEGY = re.compile(r"Auto-selected MoE strategy: (\w+)|Resolved config: moe_strategy='(\w+)'")
_EXPERTS = re.compile(r"MoE experts: (\w+) via (\S+?)(?:,|\s|$)")
_CACHE = re.compile(r"moe_cache_size=(\d+)(?:\s+num_pages=(\d+))?")
_WARM = re.compile(r"Prefill warmup complete for lengths .* in ([\d.]+) s")
_READY = re.compile(r"API server is ready to serve on (\S+)")
_PREFILL = re.compile(r"Prefill batch, .*#new-token: (\d+).*input throughput \(token/s\): ([\d.]+)")
_DECODE = re.compile(r"Decode batch, .*gen throughput \(token/s\): ([\d.]+)")
_MOE = re.compile(r"MoE decode, (\w+) (\d+) layers?: hit ([\d.]+)%, per layer-step miss ([\d.]+) fetch ([\d.]+) cpu ([\d.]+)")
_PIN_LOCK = re.compile(r"banks ([\d.]+) GiB > pin budget ([\d.]+) GiB; locking (\d+)")
_PIN_CPU = re.compile(r"banks ([\d.]+) GiB exceed the pin budget")
_PIN_STOP = re.compile(r"expert banks need ([\d.]+) GiB of pinned host RAM but the pin budget is ([\d.]+) GiB")
_TOOLCHAIN = re.compile(r"nvcc [\d.]+ would build kernels|Install a CUDA \d+\.x toolkit|nvcc: (?:not found|command not found)")
_OOM = re.compile(r"CUDA out of memory|OutOfMemoryError|cudaHostAlloc refused", re.I)
_EXC = re.compile(r"^\w*(Error|Exception): ")
_SERVED = re.compile(r"--served-model-name\s+(\S+)")
_MODEL = re.compile(r"--model\s+(\S+)")


def strip(line: str) -> str:
    return _ANSI.sub("", str(line or "")).rstrip("\r\n")


def line_time(line: str) -> Optional[float]:
    m = _TIME.match(strip(line))
    if not m:
        return None
    try:
        return _dt.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M:%S").timestamp()
    except ValueError:
        return None


def _body(text: str) -> "tuple[str, str]":
    m = _TIME.match(text)
    return (text[m.end():], (m.group(3) or "").upper()) if m else (text, "")


def classify(line: str, at=None, runtime: Optional[str] = None) -> Optional[dict]:
    rt = runtime or "freetoken"
    text = strip(line)
    if not text.strip() or text.startswith("--- halo starts:"):
        return None
    at = at if at is not None else line_time(text)
    body, level = _body(text)
    if m := _PREFILL.search(body):
        return event("timing", f"a prefill of {int(m.group(1)):,} tokens at {float(m.group(2)):g} tok/s", text, at=at,
                     runtime=rt, phase="prefill", tok_s=float(m.group(2)), new_tokens=int(m.group(1)))
    if m := _DECODE.search(body):
        return event("timing", f"decoding at {float(m.group(1)):g} tok/s", text, at=at, runtime=rt, phase="decode",
                     tok_s=float(m.group(1)), eval_tok_s=float(m.group(1)))
    if m := _MOE.search(body):
        hit = float(m.group(3)) / 100.0
        return event("expert-cache", f"the expert cache hits {hit:.0%} of the experts a step asks ({m.group(1)} "
                     f"{m.group(2)} layers)", text, at=at, runtime=rt, group=m.group(1), layers=int(m.group(2)),
                     hit=round(hit, 4), miss=float(m.group(4)), fetch=float(m.group(5)), cpu=float(m.group(6)))
    if m := _PIN_STOP.search(body):
        return event("load-failed", f"the expert banks need {m.group(1)} GiB pinned, the pin budget is {m.group(2)} GiB "
                     "(WSL caps CUDA pinning): the load stopped", text, at=at, runtime=rt, pinned=True,
                     banks_gib=float(m.group(1)), budget_gib=float(m.group(2)))
    if (m := _PIN_LOCK.search(body)) or (m2 := _PIN_CPU.search(body)):
        g = m or m2
        ev = event("pin-cap", f"{g.group(1)} GiB of expert banks over a {g.group(2) if m else '?'} GiB pin budget: "
                   + (f"{m.group(3)} layers decode on the CPU" if m else "every layer OS-locked"), text, at=at,
                   runtime=rt, banks_gib=float(g.group(1)), budget_gib=float(m.group(2)) if m else None,
                   locked=int(m.group(3)) if m else None)
        ev["severity"] = "warn"
        return ev
    if (m := _WARM.search(body)) and float(m.group(1)) >= JIT_S:
        return event("kernel-jit", f"the startup warmup took {float(m.group(1)):.0f} s: FreeToken compiled its CUDA "
                     "kernels (once per install)", text, at=at, runtime=rt, seconds=float(m.group(1)))
    if _TOOLCHAIN.search(body):
        return event("load-failed", f"the CUDA toolchain does not match: {body.strip()[:160]}", text, at=at, runtime=rt,
                     toolchain=True)
    if _OOM.search(body):
        return event("gpu-memory", f"FreeToken ran out of GPU or pinned memory: {body.strip()[:160]}", text, at=at,
                     runtime=rt)
    if _EXC.match(body.strip()) or level in ("ERROR", "CRITICAL"):
        return event("other-error", f"FreeToken logged an error: {body.strip()[:160]}", text, at=at, runtime=rt)
    return None


def _stem(path: str) -> str:
    return Path(path.strip("'\"")).name or path


class FtRules:
    """server_context_hf.Rules for a `freetoken` server: the load block's facts -> one load-result."""

    def __init__(self) -> None:
        self.runtime = "freetoken"
        self.model: Optional[str] = None
        self.window: Optional[int] = None
        self.facts: dict = {}
        self.load_at: Optional[float] = None
        self.first_at: Optional[float] = None  # FreeToken's own first stamp after Halo's start line
        self.clock: Optional[float] = None

    def feed(self, raw: str, at=None) -> list:
        text = strip(raw)
        t = line_time(text)
        self.clock = t if t is not None else (at if at is not None else self.clock)
        out: list = []
        if text.startswith("--- halo starts:"):
            m = _SERVED.search(text) or _MODEL.search(text)
            self.model = _stem(m.group(1)) if m else self.model
            self.facts, self.load_at, self.first_at = {}, self.clock, None
            return out
        if t is not None and self.first_at is None:
            self.first_at = t
        body, _lvl = _body(text)
        if m := _STRATEGY.search(body):
            self.facts["strategy"] = m.group(1) or m.group(2)
        if m := _EXPERTS.search(body):
            self.facts.update(experts=m.group(1), kernel=m.group(2))
        if (m := _CACHE.search(body)) and "resolved" in body:
            self.facts["cache_slots"] = int(m.group(1))
            if m.group(2):
                self.facts["num_pages"] = int(m.group(2))
        if m := _WARM.search(body):
            self.facts["warmup_s"] = float(m.group(1))
        if m := _READY.search(body):
            out += self._loaded(text, m.group(1))
        ev = classify(text, at=t if t is not None else at)
        if ev is not None:
            ev["model"] = ev.get("model") or self.model
            out.append(ev)
        return out

    def _loaded(self, text: str, where: str) -> list:
        f, took = self.facts, None
        start = self.first_at if self.first_at is not None else self.load_at  # one clock: the log's own, else the read's
        if isinstance(self.clock, (int, float)) and isinstance(start, (int, float)):
            took = max(0.0, self.clock - start)
        say = (f"{self.model or 'the model'} loaded on FreeToken ({f.get('strategy') or 'offload'}"
               + (f", {f['experts']} experts" if f.get("experts") else "")
               + (f", an expert cache of {f['cache_slots']:,} slots" if f.get("cache_slots") else "") + ")"
               + (f", {took:.0f} s" if took is not None else ""))
        out = [event("load-result", say, text, at=self.clock, model=self.model, runtime="freetoken", serving=where,
                     strategy=f.get("strategy"), experts=f.get("experts"), kernel=f.get("kernel"),
                     cache_slots=f.get("cache_slots"), num_pages=f.get("num_pages"), warmup_s=f.get("warmup_s"),
                     load_s=took)]
        from halo_harness.ollama_steward.server_rules import SLOW_LOAD_S
        if took is not None and took > SLOW_LOAD_S:
            out.append(event("slow-load", f"a load took {took:.0f} s (over 3 minutes): the expert banks are read from "
                             "disk into RAM first", text, at=self.clock, model=self.model, runtime="freetoken", seconds=took))
        return out

    def flush(self) -> list:
        return []
