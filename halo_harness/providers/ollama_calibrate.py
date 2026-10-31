"""halo_harness.providers.ollama_calibrate -- Halo 2.0.3 round 5b item 1/2:
"fit calibration from Ollama's own telemetry, no GPU tool required."
`halo ollama calibrate <model> [--host NAME] [--start N]` (and the same
procedure run automatically the first time a model is used on a host with
no learned cap) loads a model at a candidate `num_ctx`, reads `/api/ps`
back (`size` vs `size_vram`), and steps down by powers of two until the
model is FULLY resident -- a measured fact, never a GPU-memory guess.
Results persist in `~/.halo/ollama-fit.json` (state dir), mirroring
`providers.ollama_capability`'s own cache-file pattern (atomic tmp+replace
write, `{}`/missing-file degrades to empty rather than raising).

A learned cap never expires on its own (brief item 2) -- it is re-measured
only by an explicit `halo ollama calibrate` or when the model's own
`digest` changes (a different `ollama pull`) or `ollama_version` changes
(a server upgrade may change how memory is actually used); `lookup_
learned_cap` treats either mismatch as "no learned cap at all" rather
than trusting a stale measurement. The SAME file also keeps the last real
turn's throughput numbers per (host, model) -- brief item 7, `halo ollama`
prints them -- since both are small, rarely-written, host+model-keyed
facts about one Ollama installation; no reason for a second file.

Halo 3.2.3.0 R1: a step is a measurement only when the load answered
within its budget (`load_budget_s`: the model's size and the host) and
`/api/ps` lists the model at the candidate's own `context_length`; a
timeout or a missing entry is `unknown`, retried once with the budget
doubled, then the run ends `inconclusive` and records no cap.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger("bridge")

_FIT_STORE_FILENAME = "ollama-fit.json"


def _fit_store_path(state_dir) -> Path:
    return Path(state_dir) / _FIT_STORE_FILENAME


def load_fit_store(state_dir) -> dict:
    """`{"entries": [...], "last_turns": {...}}`; a fresh shape (never
    raises) when the file is missing, unreadable, or not a dict -- a lost
    store just means every host+model gets auto-calibrated/measured again,
    same cost as a fresh install."""
    path = _fit_store_path(state_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict):
        data = {}
    if not isinstance(data.get("entries"), list):
        data["entries"] = []
    if not isinstance(data.get("last_turns"), dict):
        data["last_turns"] = {}
    return data


def save_fit_store(state_dir, data: dict) -> None:
    path = _fit_store_path(state_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        import os
        import threading
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        log.debug("ollama: could not persist fit store to %s", path, exc_info=True)


def _find_entry(entries: list, *, host_url: str, model: str) -> Optional[dict]:
    """Review fix pass (finding 9): matched via `ollama_names_match`, not
    a bare `==` -- `halo ollama calibrate qwen3:latest` and an `ol:qwen3`
    session used to never see each other's entry (an untagged ref never
    found its own `:latest`-qualified record), so the session auto-
    calibrated again on every fresh process. Imported lazily (same
    pattern every other cross-module call in this file already uses) --
    `providers.ollama` never imports this module at all, so there is no
    real cycle, just the house habit of keeping this module's own import
    list free of its sibling providers."""
    from halo_harness.providers.ollama import ollama_names_match
    for entry in entries:
        if (isinstance(entry, dict) and entry.get("host_url") == host_url
                and ollama_names_match(entry.get("model"), model)):
            return entry
    return None


def has_calibration_entry(state_dir, *, host_url: str, model: str, digest: Optional[str] = None,
                           ollama_version: Optional[str] = None) -> bool:
    """True iff SOME entry exists for (host_url, model) -- this is what
    gates auto-calibration (brief: run it "the first time a model is
    used on a host with no learned cap").

    Review fix pass (finding 10): `digest`/`ollama_version`, when given,
    make this STALENESS-AWARE -- the SAME mismatch rule `lookup_learned_
    cap`/`has_recorded_does_not_fit` already apply, so an entry whose own
    recorded digest/version disagrees is treated exactly like no entry at
    all. Commit 9af8dac promised "re-measured... when the model digest or
    Ollama version changes"; nothing re-measured automatically because
    THIS gate never checked either one -- a re-pulled model (new digest)
    or an upgraded server (new version) kept a stale entry looking
    "already calibrated" forever. Omitted (the default, `None`/`None`)
    keeps the OLD "some entry exists at all, regardless of staleness"
    answer, for a caller with no digest/version to compare against."""
    entry = _find_entry(load_fit_store(state_dir)["entries"], host_url=host_url, model=model)
    if entry is None:
        return False
    if digest is not None and entry.get("digest") is not None and entry.get("digest") != digest:
        return False
    if ollama_version is not None and entry.get("ollama_version") is not None \
            and entry.get("ollama_version") != ollama_version:
        return False
    return True


def lookup_learned_cap(state_dir, *, host_url: str, model: str, digest: Optional[str] = None,
                        ollama_version: Optional[str] = None) -> Optional[int]:
    """The learned `max_full_gpu_ctx` for (host_url, model), or `None`
    when there's no entry, the entry itself recorded "does not fit"
    (`max_full_gpu_ctx` stored as `None`), or -- a digest/version MISMATCH
    -- `digest`/`ollama_version` are given AND differ from what the entry
    recorded (a re-pulled model or an upgraded server invalidates a prior
    measurement; brief item 2: "re-measured... when the model digest or
    Ollama version changes"). `digest=None`/`ollama_version=None` (the
    live per-turn hot path, `providers.ollama_hw.resolve_context_decision`
    -- never pays for a fresh `/api/version` probe just for this) skips
    that specific check, trusting the entry on host_url+model alone."""
    entry = _find_entry(load_fit_store(state_dir)["entries"], host_url=host_url, model=model)
    if entry is None:
        return None
    if digest is not None and entry.get("digest") is not None and entry.get("digest") != digest:
        return None
    if ollama_version is not None and entry.get("ollama_version") is not None \
            and entry.get("ollama_version") != ollama_version:
        return None
    cap = entry.get("max_full_gpu_ctx")
    return cap if isinstance(cap, int) and not isinstance(cap, bool) and cap > 0 else None


def has_recorded_does_not_fit(state_dir, *, host_url: str, model: str, digest: Optional[str] = None,
                               ollama_version: Optional[str] = None) -> bool:
    """Review fix pass (finding 5): `lookup_learned_cap` returns `None`
    for BOTH "no entry at all" and "the entry itself recorded does not
    fit" -- indistinguishable to every caller that only reads that one
    function, which is exactly why a model a measurement already proved
    does not fit was getting treated as "nothing known" (the largest
    window available) instead of the conservative fallback. This is the
    missing other half of the SAME lookup: True only when an entry
    exists, its own digest/version match (same guard as `lookup_learned_
    cap`, so a re-pulled model or an upgraded server never keeps a stale
    does-not-fit verdict either), AND it recorded `max_full_gpu_ctx` as
    `None` (the "does not fit even at the floor" outcome -- see
    `record_calibration`'s own docstring)."""
    entry = _find_entry(load_fit_store(state_dir)["entries"], host_url=host_url, model=model)
    if entry is None:
        return False
    if digest is not None and entry.get("digest") is not None and entry.get("digest") != digest:
        return False
    if ollama_version is not None and entry.get("ollama_version") is not None \
            and entry.get("ollama_version") != ollama_version:
        return False
    return entry.get("max_full_gpu_ctx") is None


def record_calibration(state_dir, *, host_url: str, model: str, digest: Optional[str],
                        max_full_gpu_ctx: Optional[int], ollama_version: Optional[str],
                        tight_ctx: Optional[int] = None, tight_vram: Optional[int] = None,
                        gpu_total: Optional[int] = None) -> dict:
    """Upserts the (host_url, model) entry -- `{host_url, model, digest,
    max_full_gpu_ctx, measured_at, ollama_version}` (brief item 2's exact
    schema). `max_full_gpu_ctx=None` is a VALID, meaningful recording
    ("measured: does not fit even at the floor") -- distinct from no entry
    at all -- so `has_calibration_entry` still returns True for it and
    auto-calibrate does not keep retrying every turn."""
    from halo_harness.filelock import file_lock
    record = {"host_url": host_url, "model": model, "digest": digest,
              "max_full_gpu_ctx": max_full_gpu_ctx, "measured_at": time.time(),
              "ollama_version": ollama_version}
    if tight_ctx:
        # Halo 3.2.3.0 R1: the window on the GPU but under the headroom rule.
        record.update({"tight_ctx": tight_ctx, "tight_vram": tight_vram, "gpu_total": gpu_total})
    with file_lock(_fit_store_path(state_dir)):
        store = load_fit_store(state_dir)
        entries = store["entries"]
        entry = _find_entry(entries, host_url=host_url, model=model)
        if entry is not None:
            entry.clear()
            entry.update(record)
        else:
            entries.append(record)
        marks = store.get("inconclusive")
        if isinstance(marks, dict):
            marks.pop(_model_key(host_url, model), None)
        discards = store.get("floor_discards")
        if isinstance(discards, dict) and discards.pop(_model_key(host_url, model), None) is not None:
            # measured again after a discard under the prompt floor: kept
            # from now on (the floor raises the window over it anyway)
            record["after_floor_discard"] = True
        save_fit_store(state_dir, store)
    return record


def auto_calibrate_enabled(env=None) -> bool:
    """`ollama.auto_calibrate` (default True) -- brief item 2: "opt out
    with `ollama.auto_calibrate: false`". Never raises on a typo'd
    config value (anything that isn't a plain bool is treated as "not
    explicitly disabled", i.e. True)."""
    del env  # accepted for call-site symmetry with other *_enabled helpers; config is process-wide, not per-env
    from halo_harness.theme import get_config_value
    value = get_config_value("ollama.auto_calibrate", default=True)
    return value is not False


# The run itself (steps, headroom rule, the outcome line) lives in
# `ollama_calibrate_steps`; every name is re-exported here.
from halo_harness.providers.ollama_calibrate_steps import (  # noqa: E402,F401
    _GB,
    HEADROOM_FRACTION, HEADROOM_MIN_BYTES, MIN_CALIBRATE_CTX, UNKNOWN_LAYERS, UNKNOWN_SIZE_BUDGET_S,
    CalibrationResult, StepReading, _floor_pow2, _load_model_at_num_ctx, _ps_entry_for_model, gpu_layers_for,
    headroom_kind, measure_step, run_calibration,
)

# Halo 3.2.3.0 R1: the per-step load budget scales with the model's size
# and the host -- a 17 GB model over the LAN needs 20-55 s just to load.
LOCAL_BUDGET_BASE_S, LOCAL_BUDGET_PER_GB_S = 20.0, 4.0
REMOTE_BUDGET_BASE_S, REMOTE_BUDGET_PER_GB_S = 40.0, 6.0


def load_budget_s(model_size_gb: "Optional[float]", remote: bool) -> float:
    """Seconds one calibration step waits for a load: local 20 s + 4 s per
    GB, remote 40 s + 6 s per GB; 60 s when the size is unknown."""
    if not isinstance(model_size_gb, (int, float)) or isinstance(model_size_gb, bool) or model_size_gb <= 0:
        return UNKNOWN_SIZE_BUDGET_S
    if remote:
        return REMOTE_BUDGET_BASE_S + REMOTE_BUDGET_PER_GB_S * float(model_size_gb)
    return LOCAL_BUDGET_BASE_S + LOCAL_BUDGET_PER_GB_S * float(model_size_gb)


def model_size_gb(catalog: Optional[dict], model: str) -> Optional[float]:
    """The model's on-disk size in GB from its catalog row (`/api/tags`'s
    `size`), or None."""
    from halo_harness.providers.ollama_hw import catalog_row
    size = (catalog_row(catalog, model) or {}).get("size")
    if isinstance(size, int) and not isinstance(size, bool) and size > 0:
        return size / (1024 ** 3)
    return None


def outcome_line(model: str, host_name: str, result: CalibrationResult, *, window: Optional[int] = None,
                 source: Optional[str] = None) -> str:
    """The one line a calibration ends with: "<model> on <host>: 32k fits,
    65k does not (1 min 50 s)"; with a tight size "65k safe, 98k tight
    (22.1 of 23 GB), 131k does not fit (...)"; "...: inconclusive, the
    window stays at 32k (trained)" when nothing was measured."""
    from halo_harness.providers.ollama_prompt import fmt_duration, fmt_window
    took = fmt_duration(result.elapsed_s)
    tight = ""
    if result.tight_ctx:
        of = (f" ({result.tight_vram / _GB:.1f} of {result.gpu_total / _GB:.0f} GB)"
              if result.tight_vram and result.gpu_total else "")
        tight = f", {fmt_window(result.tight_ctx)} tight{of}"
    if result.outcome == "fits":
        if tight:
            failed = f", {fmt_window(result.failed_ctx)} does not fit" if result.failed_ctx else ""
            return f"{model} on {host_name}: {fmt_window(result.max_full_gpu_ctx)} safe{tight}{failed} ({took})"
        not_fit = f", {fmt_window(result.failed_ctx)} does not" if result.failed_ctx else ""
        return f"{model} on {host_name}: {fmt_window(result.max_full_gpu_ctx)} fits{not_fit} ({took})"
    if result.outcome == "does_not_fit":
        return (f"{model} on {host_name}: no safe window down to {fmt_window(MIN_CALIBRATE_CTX)}{tight} "
                f"({took})")
    stays = f", the window stays at {fmt_window(window)} ({source or '?'})" if window else ""
    if result.outcome == "unreachable":
        return f"{model} on {host_name}: no answer from the host ({took}), nothing recorded{stays}"
    budget = f"{result.budget_s:.0f} s" if result.budget_s else "the budget"
    what = (f" ({fmt_window(result.unknown_ctx)} did not load within {budget}, then {budget} x 2; nothing recorded)"
            if result.unknown_ctx else " (nothing recorded)")
    return f"{model} on {host_name}: inconclusive{what}{stays}"


def current_window(host, model: str) -> "tuple[Optional[int], Optional[str]]":
    """(num_ctx, source word) a request for `model` on `host` resolves to
    right now -- for the inconclusive line; (None, None) on any failure."""
    try:
        from types import SimpleNamespace
        from halo_harness.providers.ollama_hw import resolve_context_decision
        from halo_harness.providers.ollama_prompt import source_word
        decision = resolve_context_decision(SimpleNamespace(host=host.name, model=model, raw=f"ol:{model}"))
        return decision.num_ctx, source_word(decision.source)
    except Exception:
        log.debug("ollama: window lookup for the calibration line failed", exc_info=True)
        return None, None


def run_auto_calibration(host, model: str, *, state_dir, timeout: Optional[float] = None) -> Optional[str]:
    """The first-use calibration `agent/loop.py` runs in a background
    thread before the first request to a (host, model) pair with no
    entry. The per-step budget is `load_budget_s` for this model's size
    and host (`timeout` overrides it). `fits`/`does_not_fit` are recorded;
    `inconclusive`/`unreachable` record nothing but an inconclusive marker
    for `halo ollama` (`record_inconclusive`), so a fresh process measures
    again. Returns the one outcome line, or None on any failure (never
    raises)."""
    from halo_harness.providers.ollama import get_catalog, probe_version, trained_context_for
    from halo_harness.providers.ollama_hw import catalog_row, estimate_fit_for_host, is_local_host
    try:
        catalog = get_catalog(host)
        row = catalog_row(catalog, model)
        if row is None:
            return None
        digest = row.get("digest")
        version_info = probe_version(host)
        ollama_version = (version_info or {}).get("version") if isinstance(version_info, dict) else None
        start = estimate_fit_for_host(host, model, catalog)
        if not isinstance(start, int) or isinstance(start, bool) or start <= 0:
            start = 32768
        budget = timeout if isinstance(timeout, (int, float)) and timeout > 0 else \
            load_budget_s(model_size_gb(catalog, model), not is_local_host(host))
        result = run_calibration(host, model, start_ctx=start, keep_alive=host.keep_alive,
                                  trained_context=trained_context_for(catalog, model), step_up=True,
                                  budget_s=budget, num_gpu=gpu_layers_for(row.get("model_info")),
                                  gpu_total=host_gpu_total_bytes(host))
        if result.prompt_tok_s:
            record_prompt_speed(state_dir, host_url=host.url, model=model, tok_s=result.prompt_tok_s)
        if result.outcome in ("inconclusive", "unreachable"):
            if result.outcome == "inconclusive":
                record_inconclusive(state_dir, host_url=host.url, model=model, budget_s=budget,
                                    candidate=result.unknown_ctx)
            window, source = current_window(host, model)
            return outcome_line(model, host.name, result, window=window, source=source)
        record_calibration(state_dir, host_url=host.url, model=model, digest=digest,
                            max_full_gpu_ctx=result.max_full_gpu_ctx, ollama_version=ollama_version,
                            tight_ctx=result.tight_ctx, tight_vram=result.tight_vram, gpu_total=result.gpu_total)
        return outcome_line(model, host.name, result)
    except Exception:
        log.debug("ollama: auto-calibration failed for %s@%s", model, host.name, exc_info=True)
        return None


def host_gpu_total_bytes(host, *, runner=None) -> Optional[int]:
    """The host's usable GPU memory (`gpu_budget_bytes`, summed over
    cards): the OS probe locally, the ssh probe for a remote host with
    `ssh:`, else None (the headroom rule then calls every resident load
    safe)."""
    try:
        from halo_harness.providers.ollama_hw import (
            get_local_gpu_memories, get_ssh_gpu_memory, gpu_budget_bytes, is_local_host,
        )
        if is_local_host(host):
            cards = get_local_gpu_memories(runner=runner)
        elif getattr(host, "ssh", None):
            cards = [get_ssh_gpu_memory(host.ssh, runner=runner)]
        else:
            return None
        budgets = [gpu_budget_bytes(c) for c in cards if c is not None]
        total = sum(b for b in budgets if b)
        return total or None
    except Exception:
        log.debug("ollama: GPU total read failed", exc_info=True)
        return None


_SPEED_WINDOW = 10


def record_prompt_speed(state_dir, *, host_url: str, model: str, tok_s: Optional[float]) -> None:
    """Folds one prompt reading speed (tokens/s) into the rolling average
    for (host, model): `prompt_speed[<host>|<model>] = {prompt_tok_s, n}`,
    a running mean over the last 10 readings. Kept beside the calibration
    entries, not in them, so an uncalibrated model never gains an entry."""
    if not isinstance(tok_s, (int, float)) or isinstance(tok_s, bool) or tok_s <= 0:
        return
    from halo_harness.filelock import file_lock
    with file_lock(_fit_store_path(state_dir)):
        store = load_fit_store(state_dir)
        speeds = store.get("prompt_speed") if isinstance(store.get("prompt_speed"), dict) else {}
        key = _model_key(host_url, model)
        old = speeds.get(key) if isinstance(speeds.get(key), dict) else {}
        n = min(int(old.get("n") or 0) + 1, _SPEED_WINDOW)
        avg = float(old.get("prompt_tok_s") or tok_s)
        avg = avg + (float(tok_s) - avg) / n
        speeds[key] = {"prompt_tok_s": round(avg, 1), "n": n, "at": time.time()}
        store["prompt_speed"] = speeds
        save_fit_store(state_dir, store)


def get_prompt_speed(state_dir, *, host_url: str, model: str) -> Optional[float]:
    """The rolling prompt reading speed (tokens/s) for (host, model), or None."""
    speeds = load_fit_store(state_dir).get("prompt_speed")
    row = speeds.get(_model_key(host_url, model)) if isinstance(speeds, dict) else None
    value = row.get("prompt_tok_s") if isinstance(row, dict) else None
    return value if isinstance(value, (int, float)) and value > 0 else None


def lookup_tight(state_dir, *, host_url: str, model: str) -> Optional[dict]:
    """`{tight_ctx, tight_vram, gpu_total}` recorded by the last
    calibration of (host, model), or None."""
    entry = _find_entry(load_fit_store(state_dir)["entries"], host_url=host_url, model=model)
    if not entry or not entry.get("tight_ctx"):
        return None
    return {k: entry.get(k) for k in ("tight_ctx", "tight_vram", "gpu_total")}


def _model_key(host_url: str, model: str) -> str:
    from halo_harness.providers.ollama import normalize_ollama_model_name
    return f"{host_url}|{normalize_ollama_model_name(model)}"


def record_inconclusive(state_dir, *, host_url: str, model: str, budget_s: Optional[float],
                         candidate: Optional[int]) -> None:
    """Notes that the last calibration of (host, model) measured nothing
    (`halo ollama` says `inconclusive`). Not a calibration entry:
    `has_calibration_entry`/`lookup_learned_cap` never read it."""
    from halo_harness.filelock import file_lock
    with file_lock(_fit_store_path(state_dir)):
        store = load_fit_store(state_dir)
        marks = store.get("inconclusive") if isinstance(store.get("inconclusive"), dict) else {}
        marks[_model_key(host_url, model)] = {"at": time.time(), "budget_s": budget_s, "num_ctx": candidate}
        store["inconclusive"] = marks
        save_fit_store(state_dir, store)


def calibration_state(state_dir, *, host_url: str, model: str) -> str:
    """`calibrated` (an entry with a cap), `inconclusive` (the last run
    measured nothing) or `estimated` (no measurement: the window comes
    from the trained context, memory or a default)."""
    if lookup_learned_cap(state_dir, host_url=host_url, model=model) is not None:
        return "calibrated"
    marks = load_fit_store(state_dir).get("inconclusive")
    if isinstance(marks, dict) and _model_key(host_url, model) in marks:
        return "inconclusive"
    return "estimated"


def discard_calibration(state_dir, *, host_url: str, model: str) -> bool:
    """Removes the (host, model) entry (a cap below the prompt floor is
    discarded so the model is measured again); True when one was removed."""
    from halo_harness.filelock import file_lock
    with file_lock(_fit_store_path(state_dir)):
        store = load_fit_store(state_dir)
        entry = _find_entry(store["entries"], host_url=host_url, model=model)
        if entry is None:
            return False
        store["entries"] = [e for e in store["entries"] if e is not entry]
        discards = store.get("floor_discards") if isinstance(store.get("floor_discards"), dict) else {}
        discards[_model_key(host_url, model)] = time.time()
        store["floor_discards"] = discards
        save_fit_store(state_dir, store)
    return True


def remeasured_after_floor(state_dir, *, host_url: str, model: str) -> bool:
    """True when the (host, model) entry was measured after an earlier
    discard under the prompt floor -- it is not discarded a second time
    (one re-measurement, not one per launch)."""
    entry = _find_entry(load_fit_store(state_dir)["entries"], host_url=host_url, model=model)
    return bool(entry and entry.get("after_floor_discard"))


def record_last_turn_throughput(state_dir, *, host_url: str, model: str, tokens_per_second: "Optional[float]",
                                 prefill_seconds: "Optional[float]", offloaded: "Optional[bool]",
                                 output_tokens: "Optional[int]" = None,
                                 prompt_floor: "Optional[int]" = None,
                                 cache_reused_pct: "Optional[int]" = None) -> None:
    """Brief item 7: "`halo ollama` prints the last turn's numbers per
    host" -- persisted (not just kept in the live process's own memory) so
    a SEPARATE `halo ollama` CLI invocation, always a fresh process, can
    read back what the last real TUI/print-mode turn measured. Overwritten
    every turn (one record per (host_url, model), no history kept).

    Review fix pass (finding 9): the key normalizes `model` through
    `normalize_ollama_model_name` (`<name>` and `<name>:latest` are one
    key) -- recorded under a session's own raw ref (often untagged), it
    used to miss the panel's own tagged catalog-row lookup entirely."""
    from halo_harness.providers.ollama import normalize_ollama_model_name
    from halo_harness.filelock import file_lock
    with file_lock(_fit_store_path(state_dir)):
        store = load_fit_store(state_dir)
        store["last_turns"][f"{host_url}|{normalize_ollama_model_name(model)}"] = {
            "tokens_per_second": tokens_per_second, "prefill_seconds": prefill_seconds,
            "offloaded": offloaded, "output_tokens": output_tokens, "prompt_floor": prompt_floor,
            "cache_reused_pct": cache_reused_pct, "at": time.time(),  # 3.3.5.0 R4: the prompt cache's share
        }
        save_fit_store(state_dir, store)


def get_last_turn_throughput(state_dir, *, host_url: str, model: str) -> Optional[dict]:
    """FIX PASS (finding 9): reads through the SAME `normalize_ollama_
    model_name` key the write side now uses -- `model_picker.py`'s
    column and `halo ollama`'s panel both look this up by whatever
    string the catalog happens to spell the model as, which must match
    regardless of how the turn that recorded it was addressed."""
    from halo_harness.providers.ollama import normalize_ollama_model_name
    entry = load_fit_store(state_dir)["last_turns"].get(f"{host_url}|{normalize_ollama_model_name(model)}")
    return entry if isinstance(entry, dict) else None
