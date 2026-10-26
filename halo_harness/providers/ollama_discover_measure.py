"""halo_harness.providers.ollama_discover_measure -- Halo 3.2.3.0 R2: the
found servers' models measured right after they are added, so the first
real turn on one never runs into a window that trims its prompt.

`measure_models` runs `providers.ollama_calibrate.run_calibration` (with
the budget it takes, 60 s per step unless the caller passes one) for each
model of a host, one at a time, records every settled answer through
`record_calibration`, and hands one progress line per model to `on_line`:
"qwen3:30b on pc: 32k fits, 65k does not (2 min 10 s)". `halo ollama
discover --calibrate` and the wizard's calibrate offer both call it.
"""

from __future__ import annotations

import math
import time
from typing import Callable, Optional

# The outcomes `record_calibration` stores; any other outcome (no answer,
# or a run that ends without a settled measurement) records nothing.
_RECORDED = ("fits", "does_not_fit")


def k_tokens(n: Optional[int]) -> str:
    return f"{int(n) // 1000}k" if isinstance(n, int) and n > 0 else "?"


def duration_text(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    minutes, secs = divmod(seconds, 60)
    return f"{minutes} min {secs} s" if minutes else f"{secs} s"


def estimate_minutes(model_count: int) -> int:
    """The offer's "about N minutes": roughly a minute per model (each is
    loaded a few times at different windows)."""
    return max(1, int(math.ceil(model_count)))


def _outcome_text(result, up_bound: int) -> str:
    outcome = getattr(result, "outcome", None)
    best = getattr(result, "max_full_gpu_ctx", None)
    if outcome == "fits":
        if isinstance(best, int) and best * 2 <= up_bound:
            return f"{k_tokens(best)} fits, {k_tokens(best * 2)} does not"
        return f"{k_tokens(best)} fits ({k_tokens(best * 2 if isinstance(best, int) else None)} is past its " \
               f"{k_tokens(up_bound)} window)"
    if outcome == "does_not_fit":
        from halo_harness.providers.ollama_calibrate import MIN_CALIBRATE_CTX
        return f"does not fit fully in GPU memory even at {k_tokens(MIN_CALIBRATE_CTX)}"
    if outcome == "unreachable":
        return "no answer from the host, nothing recorded"
    return f"{outcome or 'no result'}, nothing recorded"


def measure_models(host, models: "list[str]", *, timeout: Optional[float] = None, state_dir=None,
                   on_line: "Optional[Callable[[str], None]]" = None) -> "list[dict]":
    """One calibration per model of `host` (an `OllamaHost`); returns one
    `{host, url, model, outcome, max_full_gpu_ctx, seconds, line}` dict per
    model. Never raises: a model that errors gets a line saying so."""
    from halo_harness.providers.ollama import (HARD_CONTEXT_CAP, get_catalog, probe_version,
                                               trained_context_for)
    from halo_harness.providers.ollama_calibrate import (gpu_layers_for, host_gpu_total_bytes, record_calibration,
                                                         run_calibration)
    from halo_harness.providers.ollama_hw import catalog_row, estimate_fit_for_host
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    out: "list[dict]" = []
    catalog = get_catalog(host, force=True)
    info = probe_version(host)
    version = info.get("version") if isinstance(info, dict) else None
    # Halo 3.2.3.0 R3: the same loads as `halo ollama calibrate` -- every
    # layer on the GPU and the card's size for the headroom rule, so the
    # window recorded here is the SAFE one a tuned twin is made from.
    gpu_total = host_gpu_total_bytes(host)
    for model in models:
        started = time.monotonic()
        record = {"host": host.name, "url": host.url, "model": model, "outcome": None,
                  "max_full_gpu_ctx": None, "seconds": 0.0}
        try:
            trained = trained_context_for(catalog, model)
            estimate = estimate_fit_for_host(host, model, catalog)
            start = estimate if isinstance(estimate, int) and not isinstance(estimate, bool) and estimate > 0 \
                else 32768
            row = catalog_row(catalog, model) or {}
            kwargs = {"start_ctx": start, "keep_alive": host.keep_alive, "step_up": True,
                      "trained_context": trained, "num_gpu": gpu_layers_for(row.get("model_info")),
                      "gpu_total": gpu_total}
            if timeout:
                kwargs["timeout"] = float(timeout)
            result = run_calibration(host, model, **kwargs)
            record["outcome"] = result.outcome
            record["max_full_gpu_ctx"] = result.max_full_gpu_ctx
            if result.outcome in _RECORDED:
                record_calibration(state_dir, host_url=host.url, model=model, digest=row.get("digest"),
                                   max_full_gpu_ctx=result.max_full_gpu_ctx, ollama_version=version,
                                   tight_ctx=getattr(result, "tight_ctx", None), tight_vram=getattr(result, "tight_vram", None),
                                   gpu_total=getattr(result, "gpu_total", None))
            up_bound = min(trained, HARD_CONTEXT_CAP) if isinstance(trained, int) and trained > 0 \
                else HARD_CONTEXT_CAP
            text = _outcome_text(result, up_bound)
        except Exception as exc:  # one model's failure never stops the others
            record["outcome"] = "error"
            text = f"could not be measured ({type(exc).__name__}: {exc})"
        record["seconds"] = round(time.monotonic() - started, 1)
        record["line"] = f"{model} on {host.name}: {text} ({duration_text(record['seconds'])})"
        out.append(record)
        if on_line is not None:
            try:
                on_line(record["line"])
            except Exception:
                pass
    return out


def measure_hosts(host_names: "list[str]", *, models_by_host: "Optional[dict]" = None,
                  timeout: Optional[float] = None, state_dir=None,
                  on_line: "Optional[Callable[[str], None]]" = None) -> "list[dict]":
    """`measure_models` for every model of each named `ollama.hosts`
    entry (the models from `models_by_host[name]` when given, else the
    host's own catalog)."""
    from halo_harness.providers.ollama import get_catalog, resolve_ollama_host
    out: "list[dict]" = []
    for name in host_names:
        host = resolve_ollama_host(name)
        if host is None:
            continue
        models = list((models_by_host or {}).get(name) or [])
        if not models:
            models = [m.get("model") or m.get("name") for m in (get_catalog(host).get("models") or [])
                      if isinstance(m, dict) and (m.get("model") or m.get("name"))]
        out.extend(measure_models(host, models, timeout=timeout, state_dir=state_dir, on_line=on_line))
    return out
