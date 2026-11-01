"""halo_harness.ollama_steward.server_context_hf -- Halo 3.3.8.0 R2: the local servers' log rules that need the lines
around a line (server_rules_hf.classify reads one line alone), the sibling of server_context.Rules:

- the model: `--alias` / `--model` on Halo's own `--- halo starts:` line, llama-server's `loading model '<path>'`,
  LM Studio's `[LM STUDIO SERVER] [<model>]`;
- the window truth: llama.cpp's `n_ctx = N`, `n_ctx_per_seq = N` and the server's `n_ctx_slot = N` (the window per
  slot, what a request really gets), `n_slots = N`; LM Studio's "loaded with context length of only N tokens";
- the load: from `loading model` (or Halo's start line) to `main: model loaded` / `all slots are
  idle` / `starting the main loop` -> one `load-result` event {window, n_ctx, n_slots, offloaded, layers, load_s} and `slow-load` past 180 s
  (the read clock times it: llama-server prints no timestamps; a read from the top cannot time it).

    Rules(runtime).feed(line, at=None) -> [event]     .flush() -> []     .window -> the slot window seen last
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from halo_harness.ollama_steward.server_rules import SLOW_LOAD_S, _OFFLOAD, event
from halo_harness.ollama_steward.server_rules_hf import classify, line_time

_ALIAS = re.compile(r"(?:--alias|-a)\s+(\S+)")
_MODEL_ARG = re.compile(r"(?:--model|-m)\s+(\S+)")
_LOADING = re.compile(r"loading model '([^']+)'")
_LMS_MODEL = re.compile(r"\[LM STUDIO SERVER\]\s*\[([^\]]+)\]")
_SLOT = re.compile(r"n_ctx_slot\s*=\s*(\d+)|new slot,? n_ctx\s*=\s*(\d+)|n_ctx_per_seq\s*(?:\(|=)\s*(\d+)")
_NCTX = re.compile(r"\bn_ctx\s*=\s*(\d+)")
_SLOTS = re.compile(r"n_slots\s*=\s*(\d+)")
_LMS_CTX = re.compile(r"context length of only (\d+) tokens", re.I)
_DONE = ("main: model loaded", "starting the main loop", "all slots are idle")


def _stem(path: str) -> str:
    p = Path(path.strip("'\""))
    return p.stem if p.suffix.lower() == ".gguf" else p.name or path


class Rules:
    def __init__(self, runtime: Optional[str] = None) -> None:
        self.runtime = runtime or "llama-server"
        self.model: Optional[str] = None
        self.alias: Optional[str] = None  # Halo's own start line names the model it serves (--alias)
        self.window: Optional[int] = None
        self.n_ctx: Optional[int] = None
        self.n_slots: Optional[int] = None
        self.layers: Optional[tuple] = None
        self.load_at: Optional[float] = None
        self.loading = False
        self.clock: Optional[float] = None

    def _start(self, at) -> None:
        self.loading, self.load_at, self.layers = True, at, None

    def _track(self, line: str, at) -> list:
        out: list = []
        if line.startswith("--- halo starts:"):
            m = _ALIAS.search(line) or _MODEL_ARG.search(line)
            self.alias = _stem(m.group(1)) if m else None
            self.model = self.alias or self.model
            self._start(at)
            return out
        if (m := _LOADING.search(line)) and "load_model" in line:
            self.model = self.alias or _stem(m.group(1))
            if not self.loading:
                self._start(at)
        if m := _LMS_MODEL.search(line):
            self.model = m.group(1).strip()
        if m := _SLOT.search(line):
            self.window = int(next(g for g in m.groups() if g))
        elif (m := _NCTX.search(line)) and ("llama_context" in line or "llama_new_context" in line):
            self.n_ctx = int(m.group(1))
        if m := _SLOTS.search(line):
            self.n_slots = int(m.group(1))
        if m := _LMS_CTX.search(line):
            self.window = int(m.group(1))
        if (m := _OFFLOAD.search(line)) and self.loading:
            self.layers = (int(m.group(1)), int(m.group(2)))
        if self.loading and any(d in line for d in _DONE):
            out += self._loaded(line, at)
        return out

    def _loaded(self, line: str, at) -> list:
        self.loading = False
        took = (at - self.load_at) if isinstance(at, (int, float)) and isinstance(self.load_at, (int, float)) else None
        window = self.window or self.n_ctx
        a, b = self.layers or (None, None)
        say = (f"{self.model or 'the model'} loaded on {self.runtime}: window {window:,} per slot" if window else
               f"{self.model or 'the model'} loaded on {self.runtime}")
        say += f" ({self.n_slots} slots)" if self.n_slots and self.n_slots > 1 else ""
        say += f", {a}/{b} layers on the GPU" if a is not None else ""
        say += f", {took:.0f} s" if took is not None else ""
        out = [event("load-result", say, line, at=at, model=self.model, runtime=self.runtime, window=window,
                     n_ctx=self.n_ctx, n_slots=self.n_slots, offloaded=a, layers=b, load_s=took)]
        if took is not None and took > SLOW_LOAD_S:
            out.append(event("slow-load", f"a load took {took:.0f} s (over 3 minutes)", line, at=at, model=self.model,
                             runtime=self.runtime, seconds=took))
        return out

    def feed(self, raw: str, at=None) -> list:
        line = str(raw or "").rstrip("\r\n")
        ev = classify(line, runtime=self.runtime)  # the line's own time first, the read clock (`at`) else
        if ev is not None and ev.get("at") is None:
            ev["at"] = at
        t = line_time(line)
        self.clock = t if t is not None else (at if at is not None else self.clock)
        out = self._track(line, self.clock)
        if ev is not None:
            ev["model"] = ev.get("model") or self.model
            ev["data"].setdefault("runtime", self.runtime)
            if self.window and ev["kind"] in ("prompt-trimmed", "reply-cut", "window-full"):
                ev["data"].setdefault("window", self.window)
            if ev["kind"] == "load-failed":
                self.loading = False
            out.append(ev)
        return out

    def flush(self) -> list:
        return []
