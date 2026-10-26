"""halo_harness.providers.ollama_tune_offer -- Halo 3.2.3.0 R3: the tuned
twins offered after a calibration. `halo ollama discover --calibrate` and
the wizard's calibrate offer both end with `TWIN_QUESTION`; Enter (or
`--twins`) runs `make_twins`: one tuned twin per model that measured a
safe window, one progress line each ("qwen3:30b on pc: tuned twin
qwen3-halo:30b made (32k window, all layers on the GPU) [ol:qwen3-halo:30b@pc]").
"""

from __future__ import annotations

from typing import Callable, Optional

TWIN_QUESTION = "make tuned twins of the models that fit? (Enter / n)"


def twin_candidates(measurements: "list[dict]") -> "list[dict]":
    """The measurements a twin is made from: outcome `fits` with a safe
    window, the model not a twin by name (a twin's own measurement is
    skipped when its original was measured too)."""
    from halo_harness.providers.ollama_tune_names import origin_from_twin_name, short_name
    fitting = [m for m in measurements or [] if isinstance(m, dict) and m.get("outcome") == "fits"
               and isinstance(m.get("max_full_gpu_ctx"), int) and m.get("max_full_gpu_ctx") > 0]
    names = {(m.get("host"), short_name(m.get("model"))) for m in measurements or [] if isinstance(m, dict)}
    out = []
    for m in fitting:
        origin = origin_from_twin_name(m.get("model") or "")
        if origin and (m.get("host"), short_name(origin)) in names:
            continue
        out.append(m)
    return out


def make_twins(measurements: "list[dict]", *, state_dir=None, on_line: "Optional[Callable[[str], None]]" = None,
               create=None) -> "list[dict]":
    """A tuned twin for every `twin_candidates` entry (from the window just
    recorded); returns `{host, model, twin, ref, ok, line}` per model. A
    model that is a twin already is skipped without a line. `create`
    replaces `providers.ollama_tune.create_twin` (a test seam)."""
    from halo_harness.providers.ollama import resolve_ollama_host
    from halo_harness.providers.ollama_tune import TuneError, create_twin, plan_twin
    create = create or create_twin
    out: "list[dict]" = []
    for m in twin_candidates(measurements):
        host = resolve_ollama_host(m.get("host"))
        model = m.get("model")
        record = {"host": m.get("host"), "model": model, "twin": None, "ref": None, "ok": False}
        if host is None:
            record["line"] = f"{model} on {m.get('host')}: no twin (the host is not in ollama.hosts)"
        else:
            try:
                plan = plan_twin(host, model, state_dir=state_dir)
            except TuneError as e:
                if e.kind == "already_twin":
                    continue
                record["line"] = f"{model} on {host.name}: no twin ({e.message})"
            else:
                try:
                    result = create(host, plan, state_dir=state_dir)
                except Exception as exc:  # one model's failure never stops the others
                    result = None
                    record["line"] = f"{model} on {host.name}: no twin ({type(exc).__name__}: {exc})"
                if result is not None:
                    record.update({"twin": plan.twin, "ref": result.ref, "ok": result.ok})
                    record["line"] = (f"{model} on {host.name}: tuned twin {plan.twin} made "
                                      f"({plan.window // 1000}k window, all layers on the GPU) [{plan.ref}]"
                                      if result.ok else f"{model} on {host.name}: no twin ({result.message})")
        out.append(record)
        if on_line is not None:
            try:
                on_line(record["line"])
            except Exception:
                pass
    return out
