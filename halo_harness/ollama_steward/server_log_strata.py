"""halo_harness.ollama_steward.server_log_strata -- Halo 3.3.9.2: a Strata server's log as the steward's events
(server_rules_hf.classify and server_context_hf.Rules hand a `strata` server's lines here).

Every pattern is written from Strata's source tree, read 2026-11-02 at main ffa80d73 -- serve/server.py (its stdout,
which Strata's supervisor keeps in `<state>/runtime/<profile>.server.log`: the start narrator's "starting the engine",
the experts' loading words by the engine's flags -- into RAM, the most-used ones under a RAM budget, or mapped from the
model files -- "experts loaded: ...", the GPU's expert cache filling, the `ready: http://.../v1 (... context N tokens`
line, "parallel requests: A asked, the engine runs B", "parallel: a request has waited N s", one "done: N tokens in S s
(R tok/s) (stop, cancel=False), expert cache H% hit (+P% of the routed experts over PCIe)" per request, the RAM-tight
and RAM-budget warnings, the engine's own "prompt P tokens = R reused + X read in Y ms (pp tok/s), G generated in Z ms
(tg tok/s)" summary and its `INFO batch_slots=N` line) and strata_cli/launch (the `strata launch` output Halo keeps
before the server runs: "Downloading X of Y GB", "Downloading the engine... N%", "Strata couldn't find an engine for
this computer"). From the source, unverified against a live run: a live log may word them otherwise.

    classify(line, at=None, runtime="strata") -> event | None   one line alone:
        timing {phase: prefill | decode, tok_s, eval_tok_s, prompt_tokens, reused}; expert-cache {hit, pcie};
        slots {asked, runs} | {waited_s}; ram-tight {experts_gb, ram_gb, left_gb} | {budget_gib, free_gib};
        download {done_gb, total_gb, pct, what}; load-failed {engine}; gpu-memory; other-error
    StRules().feed(line, at=None) -> [event]   the load block (the strategy, the experts' GB, the load seconds) -> one
        load-result {strategy, window, experts, batch_slots, load_s} at the `ready:` line
"""

from __future__ import annotations

import re
from typing import Optional

from halo_harness.ollama_steward.server_rules import event

SAYS = ("load-result", "timing", "expert-cache", "slots", "ram-tight", "download", "load-failed", "gpu-memory",
        "other-error", "slow-load")
_P = r"(?:\[strata\]\s*)?"
_READY = re.compile(r"^ready: http://(\S+?)/v1\s+\(OpenAI: .*?context (\d+) tokens")
_STARTING = re.compile(_P + r"starting the engine: reading the model's weights")
_STRATEGY = (("budget", re.compile(_P + r"loading the most-used experts into RAM \((up to [\d.]+ GiB|a RAM budget)")),
             ("resident", re.compile(_P + r"loading the experts the GPU does not hold into RAM \(of ([^)]*)\)")),
             ("mapped", re.compile(_P + r"mapping the experts from the model files \(([^,)]*)")),
             ("ram", re.compile(_P + r"loading the experts into RAM \(([^)]*)\)")))
_LOADED = re.compile(_P + r"experts loaded: (.*?) \((\d+) s so far\)")
_SLOTS_INFO = re.compile(r"\bINFO batch_slots=(\d+)")
_PAR = re.compile(_P + r"parallel requests: (\d+) asked, the engine runs (\d+|one at a time)")
_WAITED = re.compile(_P + r"parallel: a request has waited (\d+) s")
_DONE = re.compile(_P + r"done: (\d+) tokens in (\d+) s \((?:([\d.]+) tok/s|no speed)\) \((\w+), cancel=\w+\)"
                   r"(?:, expert cache ([\d.]+)% hit)?(?: \(\+([\d.]+)% of the routed experts over PCIe\))?")
_ENGINE = re.compile(r"prompt (\d+) tokens = (\d+) reused \+ \d+(?: of \d+)? read in ([\d.]+) ms \(([\d.]+) tok/s\), "
                     r"(\d+) generated in ([\d.]+) ms \(([\d.]+) tok/s\)")
_ECHO = re.compile(_P + r"request prompt (\d+) cached (\d+) output (\d+) prompt_read \d+ ms total \d+ ms prefill "
                   r"([\d.]+) tok/s decode ([\d.]+) tok/s")
_TIGHT = re.compile(_P + r"WARNING: RAM is tight - the model's experts take ([\d.]+) GB of this PC's (\d+) GB, "
                    r"leaving ([\d.-]+) GB")
_BUDGET = re.compile(_P + r"WARNING: the RAM budget for experts is ([\d.]+) GiB \(--resident-budget-gib\), but this "
                     r"PC has (\d+) GiB free of (\d+) GiB")
_DL = re.compile(r"^\s*(?:\[[!X]\]\s*)?(?:(Downloading)|([^:]{3,60}?):) ([\d.]+) of ([\d.]+) GB\b")
_DL_ENGINE = re.compile(r"Downloading the engine\W+(\d+)%")
_DL_DRAFTER = re.compile(r"Downloading the (DFlash2 drafter) \(([\d.]+) GB")
_NO_ENGINE = re.compile(r"Strata couldn't find an engine for this computer|the engine did not start|"
                        r"the engine exited before it wrote anything|the engine stopped while the GPU runtime")
_FATAL = re.compile(_P + r"the GPU reported a fatal error \(([^)]*)\)")
_OOM = re.compile(r"out of memory|cudaMalloc failed|hipErrorOutOfMemory", re.I)
_ERR = re.compile(_P + r"(503: |400 invalid request: |400 malformed request|the engine reported an error: )(.*)")


def _f(x) -> Optional[float]:
    return float(x) if x not in (None, "") else None


def classify(line: str, at=None, runtime: Optional[str] = None) -> Optional[dict]:
    rt = runtime or "strata"
    text = str(line or "").rstrip("\r\n")
    if not text.strip() or text.startswith("--- halo starts:"):
        return None
    if m := _DONE.search(text):
        hit, pcie = _f(m.group(5)), _f(m.group(6))
        ev = event("timing", f"a reply of {int(m.group(1)):,} tokens at {m.group(3) or '?'} tok/s ({m.group(4)})"
                   + (f", the expert cache hit {hit:g}%" if hit is not None else ""), text, at=at, runtime=rt,
                   phase="decode", tok_s=_f(m.group(3)), eval_tok_s=_f(m.group(3)), tokens=int(m.group(1)),
                   seconds=int(m.group(2)), finish=m.group(4), hit=hit / 100.0 if hit is not None else None,
                   pcie=pcie / 100.0 if pcie is not None else None)
        return ev
    if (m := _ENGINE.search(text)) or (m2 := _ECHO.search(text)):
        if m:
            p, r, pp, tg = int(m.group(1)), int(m.group(2)), float(m.group(4)), float(m.group(7))
        else:
            p, r, pp, tg = int(m2.group(1)), int(m2.group(2)), float(m2.group(4)), float(m2.group(5))
        return event("timing", f"a prompt of {p:,} tokens ({r:,} reused) read at {pp:g} tok/s, the reply at {tg:g} tok/s",
                     text, at=at, runtime=rt, phase="prefill", tok_s=pp, eval_tok_s=tg, prompt_tokens=p, reused=r)
    if m := _PAR.search(text):
        runs = 1 if m.group(2) == "one at a time" else int(m.group(2))
        return event("slots", f"{m.group(1)} parallel requests asked, the engine runs {runs}", text, at=at, runtime=rt,
                     asked=int(m.group(1)), runs=runs)
    if m := _WAITED.search(text):
        return event("slots", f"a request waited {m.group(1)} s for a free slot", text, at=at, runtime=rt,
                     waited_s=int(m.group(1)))
    if m := _TIGHT.search(text):
        ev = event("ram-tight", f"RAM is tight: the experts take {m.group(1)} GB of {m.group(2)} GB, {m.group(3)} GB left",
                   text, at=at, runtime=rt, experts_gb=float(m.group(1)), ram_gb=float(m.group(2)),
                   left_gb=float(m.group(3)))
        ev["severity"] = "warn"
        return ev
    if m := _BUDGET.search(text):
        ev = event("ram-tight", f"the experts' RAM budget is {m.group(1)} GiB with {m.group(2)} GiB free: the rest is read "
                   "from disk", text, at=at, runtime=rt, budget_gib=float(m.group(1)), free_gib=float(m.group(2)),
                   ram_gb=float(m.group(3)))
        ev["severity"] = "warn"
        return ev
    if m := _DL_ENGINE.search(text):
        return event("download", f"downloading the engine ({m.group(1)} %)", text, at=at, runtime=rt, what="the engine",
                     pct=int(m.group(1)), done_gb=None, total_gb=None)
    if m := _DL_DRAFTER.search(text):
        return event("download", f"downloading the {m.group(1)} ({m.group(2)} GB)", text, at=at, runtime=rt,
                     what=f"the {m.group(1)}", total_gb=float(m.group(2)), done_gb=None, pct=None)
    if (m := _DL.search(text)) and "already on this computer" not in text:
        done, total = float(m.group(3)), float(m.group(4))
        what = "the model" if m.group(1) else m.group(2).strip()
        return event("download", f"downloading {what}: {done:g} of {total:g} GB", text, at=at, runtime=rt, what=what,
                     done_gb=done, total_gb=total, pct=round(100.0 * done / total) if total else None)
    if _NO_ENGINE.search(text):
        return event("load-failed", f"Strata did not start its engine: {text.strip()[:160]}", text, at=at, runtime=rt,
                     engine=True)
    if (m := _FATAL.search(text)) or _OOM.search(text):
        return event("gpu-memory", f"Strata's GPU failed: {(m.group(1) if m else text.strip())[:160]}", text, at=at,
                     runtime=rt)
    if m := _ERR.search(text):
        return event("other-error", f"Strata logged an error: {(m.group(1) + m.group(2)).strip()[:160]}", text, at=at,
                     runtime=rt)
    return None


class StRules:
    """server_context_hf.Rules for a `strata` server: the load block's facts -> one load-result."""

    def __init__(self) -> None:
        self.runtime = "strata"
        self.model: Optional[str] = None
        self.facts: dict = {}
        self.load_at: Optional[float] = None
        self.clock: Optional[float] = None

    def feed(self, raw: str, at=None) -> list:
        text = str(raw or "").rstrip("\r\n")
        self.clock = at if at is not None else self.clock
        if text.startswith("--- halo starts:") or _STARTING.search(text):
            self.facts, self.load_at = {}, self.clock
            return []
        for word, rx in _STRATEGY:
            if m := rx.search(text):
                self.facts.update(strategy=word, experts=m.group(1).strip())
                break
        if m := _LOADED.search(text):
            self.facts.update(loaded=m.group(1).strip(), loaded_s=int(m.group(2)))
        if m := _SLOTS_INFO.search(text):
            self.facts["batch_slots"] = int(m.group(1))
        out: list = []
        if m := _READY.search(text):
            out += self._ready(text, int(m.group(2)))
        ev = classify(text, at=at)
        if ev is not None:
            ev["model"] = ev.get("model") or self.model
            out.append(ev)
        return out

    def _ready(self, text: str, window: int) -> list:
        f = self.facts
        took = (self.clock - self.load_at) if isinstance(self.clock, (int, float)) and isinstance(
            self.load_at, (int, float)) else None
        took = f.get("loaded_s") if f.get("loaded_s") is not None and not took else took  # the narrator's own count
        say = (f"{self.model or 'the model'} loaded on Strata (window {window:,}"
               + (f", experts {f['strategy']}: {f['experts']}" if f.get("strategy") else "")
               + (f", {f['batch_slots']} slots" if f.get("batch_slots") else "") + ")"
               + (f", {took:.0f} s" if isinstance(took, (int, float)) else ""))
        out = [event("load-result", say, text, at=self.clock, model=self.model, runtime="strata", window=window,
                     strategy=f.get("strategy"), experts=f.get("experts"), batch_slots=f.get("batch_slots"),
                     load_s=took)]
        from halo_harness.ollama_steward.server_rules import SLOW_LOAD_S
        if isinstance(took, (int, float)) and took > SLOW_LOAD_S:
            out.append(event("slow-load", f"a load took {took:.0f} s (over 3 minutes): Strata reads the experts into RAM "
                             "first", text, at=self.clock, model=self.model, runtime="strata", seconds=took))
        self.facts = {**f, "ready": True}
        return out

    def flush(self) -> list:
        return []
