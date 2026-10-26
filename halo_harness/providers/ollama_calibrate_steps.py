"""halo_harness.providers.ollama_calibrate_steps -- Halo 3.2.3.0 R1: one
calibration run (`run_calibration`), split out of `ollama_calibrate.py`
(the store), which re-exports every name here.

A step loads the model at a candidate `num_ctx` with every layer asked
onto the GPU (`num_gpu`: the model's layer count, 999 when unknown --
Ollama caps it; by default Ollama moves layers to the CPU past a window
it judges risky even with room left), then reads `/api/ps`:

- a measurement only when the load answered within its budget AND
  `/api/ps` lists the model at the candidate's own `context_length`;
  anything else is `unknown` (retried once with the budget doubled, then
  the run is `inconclusive` and records no cap);
- `size_vram < size` is `offloaded` (part on the CPU): the run steps down;
- fully on the GPU, the headroom rule splits it: `safe` when the card
  keeps at least 8 % of its memory (or 1.5 GB, the larger) free, else
  `tight`. The recorded cap is the largest SAFE window; a tight one is
  named in the line ("65k safe, 98k tight (22.1 of 23 GB), 131k does not
  fit"). No card total known (a remote host without `ssh:`): resident is
  safe.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("bridge")

MIN_CALIBRATE_CTX = 4096
UNKNOWN_SIZE_BUDGET_S = 60.0
HEADROOM_FRACTION = 0.08
HEADROOM_MIN_BYTES = int(1.5 * 1024 ** 3)
UNKNOWN_LAYERS = 999
_GB = 1024 ** 3


def _floor_pow2(n: int) -> int:
    power = 1
    while power * 2 <= n:
        power *= 2
    return power


def gpu_layers_for(model_info: Optional[dict]) -> int:
    """`num_gpu` for "every layer on the GPU": `<family>.block_count` + 1
    (the output layer), 999 when unknown (Ollama caps it at the real count)."""
    for key, value in (model_info or {}).items():
        if key.endswith(".block_count") and isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value + 1
    return UNKNOWN_LAYERS


def headroom_kind(size_vram: int, gpu_total: Optional[int]) -> str:
    """`safe` when `gpu_total - size_vram` >= max(8 % of `gpu_total`, 1.5
    GB), else `tight`; `safe` when the card's total is unknown."""
    if not isinstance(gpu_total, int) or gpu_total <= 0:
        return "safe"
    need = max(HEADROOM_FRACTION * gpu_total, HEADROOM_MIN_BYTES)
    return "safe" if gpu_total - size_vram >= need else "tight"


@dataclass(frozen=True)
class CalibrationResult:
    # "fits" | "does_not_fit" | "inconclusive" (a step stayed unknown after
    # its retry: nothing is recorded) | "unreachable" (no answer at all)
    outcome: str
    max_full_gpu_ctx: Optional[int]          # the largest SAFE window
    steps: int
    last_size: Optional[int] = None
    last_size_vram: Optional[int] = None
    failed_ctx: Optional[int] = None         # the smallest size measured offloaded above the fit
    unknown_ctx: Optional[int] = None        # the candidate that stayed unknown
    budget_s: Optional[float] = None         # the per-step budget used (the retry doubles it)
    elapsed_s: float = 0.0
    tight_ctx: Optional[int] = None          # the largest window on the GPU but under the headroom rule
    tight_vram: Optional[int] = None
    gpu_total: Optional[int] = None
    prompt_tok_s: Optional[float] = None     # prompt reading speed seen during the run, when measurable


@dataclass(frozen=True)
class StepReading:
    kind: str  # "safe" | "tight" | "offloaded" | "unknown"
    reached_host: bool
    size: Optional[int] = None
    size_vram: Optional[int] = None


def _load_model_at_num_ctx(host, model: str, *, num_ctx: int, keep_alive: Optional[str], timeout: float,
                           num_gpu: Optional[int] = None):
    """One non-streaming `/api/chat` (`num_predict: 1`) that makes Ollama
    load `model` at `num_ctx`; returns `providers.ollama.JsonReply`, so a
    load that ran past `timeout` is visible as `failure == "timeout"`."""
    from halo_harness.providers.ollama import request_json
    options = {"num_ctx": num_ctx, "num_predict": 1}
    if num_gpu:
        options["num_gpu"] = num_gpu
    body = {"model": model, "stream": False, "messages": [{"role": "user", "content": "hi"}], "options": options}
    if keep_alive is not None:
        body["keep_alive"] = keep_alive
    return request_json(host, "/api/chat", method="POST", body=body, timeout=timeout)


def _ps_entry_for_model(ps: Optional[dict], model: str) -> Optional[dict]:
    from halo_harness.providers.ollama import ollama_names_match
    for entry in (ps or {}).get("models") or []:
        if isinstance(entry, dict) and (ollama_names_match(entry.get("model"), model)
                                         or ollama_names_match(entry.get("name"), model)):
            return entry
    return None


def measure_step(host, model: str, num_ctx: int, *, keep_alive: Optional[str], budget_s: float,
                 num_gpu: Optional[int] = None, gpu_total: Optional[int] = None,
                 speed_box: Optional[list] = None) -> StepReading:
    """One load at `num_ctx`, then `/api/ps` (see the module docstring for
    the rule). A server whose `/api/ps` carries no `context_length` at all
    is taken at its word. `speed_box` collects the load reply's
    `(prompt_eval_count, prompt_eval_duration)`."""
    from halo_harness.providers.ollama import fetch_ps
    reply = _load_model_at_num_ctx(host, model, num_ctx=num_ctx, keep_alive=keep_alive, timeout=budget_s,
                                   num_gpu=num_gpu)
    if reply.failure is not None:
        return StepReading("unknown", reached_host=reply.failure != "unreachable")
    if speed_box is not None and isinstance(reply.body, dict):
        speed_box.append((reply.body.get("prompt_eval_count"), reply.body.get("prompt_eval_duration")))
    entry = _ps_entry_for_model(fetch_ps(host), model)
    if entry is None:
        return StepReading("unknown", reached_host=True)
    loaded_ctx = entry.get("context_length")
    if isinstance(loaded_ctx, int) and loaded_ctx != num_ctx:
        return StepReading("unknown", reached_host=True)
    size, size_vram = entry.get("size"), entry.get("size_vram")
    if not (isinstance(size, int) and isinstance(size_vram, int) and size > 0):
        return StepReading("unknown", reached_host=True)
    kind = "offloaded" if size_vram < size else headroom_kind(size_vram, gpu_total)
    return StepReading(kind, True, size, size_vram)


def run_calibration(host, model: str, *, start_ctx: int, min_ctx: int = MIN_CALIBRATE_CTX,
                     keep_alive: Optional[str] = None, timeout: Optional[float] = None,
                     step_up: bool = False, trained_context: Optional[int] = None,
                     hard_cap: Optional[int] = None, budget_s: Optional[float] = None,
                     on_step=None, num_gpu: Optional[int] = UNKNOWN_LAYERS,
                     gpu_total: Optional[int] = None) -> CalibrationResult:
    """Step DOWN by halves from `start_ctx` (floored to a power of two,
    never below `min_ctx`) to the first SAFE load (`does_not_fit` past the
    floor); with `step_up`, double from there until a load is tight or
    offloaded (bounded by min(trained context, hard cap)), then try the
    midpoint (x 1.5) once. `budget_s` (`timeout` is its older name; 60 s
    when neither) is the per-step budget. `on_step(ctx, reading)` is
    called after every load."""
    from halo_harness.providers.ollama import HARD_CONTEXT_CAP
    from halo_harness.providers.ollama_prompt import prompt_speed
    budget = next((float(b) for b in (budget_s, timeout) if isinstance(b, (int, float)) and b > 0),
                  UNKNOWN_SIZE_BUDGET_S)
    hard_cap = hard_cap if isinstance(hard_cap, int) and hard_cap > 0 else HARD_CONTEXT_CAP
    up_bound = min(trained_context, hard_cap) if isinstance(trained_context, int) and trained_context > 0 \
        else hard_cap
    t0 = time.monotonic()
    st = {"steps": 0, "reached": False, "last": (None, None), "tight": None, "tight_vram": None}
    speeds: list = []

    def _measure(ctx: int) -> StepReading:
        reading = StepReading("unknown", False)
        for step_budget in (budget, budget * 2):
            st["steps"] += 1
            reading = measure_step(host, model, ctx, keep_alive=keep_alive, budget_s=step_budget,
                                   num_gpu=num_gpu, gpu_total=gpu_total, speed_box=speeds)
            st["reached"] = st["reached"] or reading.reached_host
            if on_step is not None:
                try:
                    on_step(ctx, reading)
                except Exception:
                    log.debug("ollama: calibration on_step callback raised", exc_info=True)
            if reading.kind != "unknown":
                st["last"] = (reading.size, reading.size_vram)
                if reading.kind == "tight" and (st["tight"] is None or ctx > st["tight"]):
                    st["tight"], st["tight_vram"] = ctx, reading.size_vram
                return reading
        return reading

    def _result(outcome: str, fit=None, failed=None, unknown=None) -> CalibrationResult:
        rates = [prompt_speed(c, d) for c, d in speeds]
        rates = [r for r in rates if r is not None]
        return CalibrationResult(outcome=outcome, max_full_gpu_ctx=fit, steps=st["steps"],
                                  last_size=st["last"][0], last_size_vram=st["last"][1],
                                  failed_ctx=failed, unknown_ctx=unknown, budget_s=budget,
                                  elapsed_s=time.monotonic() - t0, tight_ctx=st["tight"],
                                  tight_vram=st["tight_vram"], gpu_total=gpu_total,
                                  prompt_tok_s=(sum(rates) / len(rates)) if rates else None)

    def _unknown(ctx: int) -> CalibrationResult:
        return _result("inconclusive" if st["reached"] else "unreachable", unknown=ctx)

    candidate = max(_floor_pow2(max(1, start_ctx)), min_ctx)
    failed: Optional[int] = None
    safe: Optional[int] = None
    while candidate >= min_ctx:
        reading = _measure(candidate)
        if reading.kind == "unknown":
            return _unknown(candidate)
        if reading.kind == "safe":
            safe = candidate
            break
        if reading.kind == "offloaded":
            failed = candidate
        candidate //= 2
    if safe is None:
        # On the GPU but never with the headroom: the largest tight window
        # is still a working window (better than the conservative fallback).
        if st["tight"] is not None:
            return _result("fits", fit=st["tight"], failed=failed)
        return _result("does_not_fit", failed=failed)
    if not step_up:
        return _result("fits", fit=safe, failed=failed)
    above = failed if failed is not None else st["tight"]
    if above is None:
        up = safe * 2
        while up <= up_bound:
            reading = _measure(up)
            if reading.kind == "unknown":
                return _unknown(up)
            if reading.kind != "safe":
                failed = up if reading.kind == "offloaded" else failed
                above = up
                break
            safe = up
            up *= 2
    mid = safe * 3 // 2
    if above is not None and above == safe * 2 and mid <= up_bound:
        reading = _measure(mid)
        if reading.kind == "unknown":
            return _unknown(mid)
        if reading.kind == "safe":
            safe = mid
        elif reading.kind == "offloaded":
            failed = mid
    return _result("fits", fit=safe, failed=failed)
