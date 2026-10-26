"""halo_harness.providers.ollama_tune -- Halo 3.2.3.0 R3: a tuned twin.

Ollama moves part of a model to the CPU past a window it judges risky
(49,152 on the owner's card) even when the GPU has room. A tuned twin is a
derived model on the same host, made through `/api/create` with `from` =
the original, so it shares the original's blobs (no extra disk), and two
parameters: `num_ctx` = the window calibration measured as SAFE (or
`--window N`) and `num_gpu` = every layer (`<family>.block_count` + 1 from
`/api/show`, 999 when unknown; Ollama caps it at the real count).

The name rule (`twin_name`): `-halo` is appended to the model's name and
the tag is kept -- `qwen3.8:27b` -> `qwen3.8-halo:27b`, `qwen3` ->
`qwen3-halo:latest`, `user/coder:7b` -> `user/coder-halo:7b`.

How a twin is recognised (`twin_origin`): Ollama drops Modelfile comments,
so the marker is what `/api/show` keeps -- `details.parent_model` (Ollama
records the `from` model there), `parameters` carrying both `num_ctx` and
`num_gpu`, and the name following the rule. Halo also keeps its own record
of each twin it made (`twins` in `~/.halo/ollama-fit.json`), read when a
server leaves `parent_model` empty. `remove_twin` deletes only a model
those facts call a twin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from halo_harness.providers.ollama_tune_names import (  # the name rule and the marker, re-exported
    TWIN_SUFFIX, _int, is_twin, k_window, origin_from_twin_name, parse_parameters, short_name, twin_name,
    twin_note, twin_origin,
)
from halo_harness.providers.ollama_tune_store import forget_twin, lookup_twin_record, record_twin

__all__ = ["TWIN_SUFFIX", "TuneError", "TwinPlan", "TwinResult", "create_twin", "is_twin", "k_window",
           "origin_from_twin_name", "parse_parameters", "plan_twin", "remove_twin", "short_name", "twin_name",
           "twin_note", "twin_origin"]


class TuneError(Exception):
    """One line saying why a twin cannot be planned, made or removed;
    `kind` is "unreachable", "missing", "already_twin", "no_window",
    "ollama_error" or "not_twin"."""

    def __init__(self, message: str, kind: str = "ollama_error"):
        super().__init__(message)
        self.message, self.kind = message, kind


def _state(state_dir):
    if state_dir is not None:
        return state_dir
    from halo_harness.config.paths import bridge_home
    return bridge_home()


@dataclass(frozen=True)
class TwinPlan:
    host_name: str
    host_url: str
    model: str
    twin: str
    window: int
    layers: int
    modelfile: str
    line: str
    measured: bool                       # the window is the recorded safe one
    parameters: dict = field(default_factory=dict)

    @property
    def ref(self) -> str:
        return f"ol:{self.twin}@{self.host_name}"


def _show_or_raise(host, model: str) -> dict:
    from halo_harness.providers.ollama import request_json
    reply = request_json(host, "/api/show", method="POST", body={"model": model})
    if reply.failure in ("unreachable", "timeout"):
        raise TuneError(f"no answer from '{host.name}' ({host.url})", "unreachable")
    if not isinstance(reply.body, dict):
        raise TuneError(f"{model} is not on '{host.name}': `halo ollama --host {host.name}` lists its models",
                        "missing")
    return reply.body


def plan_twin(host, model: str, window: Optional[int] = None, *, state_dir=None) -> TwinPlan:
    """The Modelfile of `model`'s twin on `host` (`FROM`, `PARAMETER
    num_ctx`, `PARAMETER num_gpu`) and one line of what `create_twin` will
    do. The window is `window` or the recorded safe window (R1's store);
    held at the model's trained context. Raises `TuneError`."""
    from halo_harness.providers.ollama import trained_context_for
    from halo_harness.providers.ollama_calibrate import gpu_layers_for, lookup_learned_cap
    state_dir = _state(state_dir)
    model = short_name(model)
    show = _show_or_raise(host, model)
    origin = twin_origin(show, name=model, record=lookup_twin_record(state_dir, host_url=host.url, twin=model))
    if origin:
        raise TuneError(f"{model} is a tuned twin already (of {origin}); tune {origin} instead", "already_twin")
    cap = lookup_learned_cap(state_dir, host_url=host.url, model=model)
    if window is None:
        if cap is None:
            raise TuneError(f"no safe window recorded for {model} on '{host.name}': `halo ollama calibrate "
                            f"{model} --host {host.name}` measures one (or pass --window N)", "no_window")
        window, source = cap, f"the safe window calibrated on '{host.name}'"
    else:
        source = "--window" + (", the calibrated safe window" if window == cap else "")
    trained = trained_context_for({"models": [{"model": model, "model_info": show.get("model_info") or {},
                                               "details": show.get("details") or {}}]}, model)
    if isinstance(trained, int) and trained > 0 and window > trained:
        window, source = trained, f"{source}, held at its trained {trained:,}"
    layers = gpu_layers_for(show.get("model_info"))
    twin = twin_name(model)
    modelfile = f"FROM {model}\nPARAMETER num_ctx {window}\nPARAMETER num_gpu {layers}\n"
    line = (f"{twin} on '{host.name}': FROM {model}, num_ctx {window:,} ({source}), num_gpu {layers} "
            f"(every layer on the GPU); it shares {model}'s weights, no extra disk")
    return TwinPlan(host_name=host.name, host_url=host.url, model=model, twin=twin, window=window, layers=layers,
                    modelfile=modelfile, line=line, measured=(cap is not None and window == cap),
                    parameters={"num_ctx": window, "num_gpu": layers})


@dataclass(frozen=True)
class TwinResult:
    ok: bool
    message: str
    ref: Optional[str] = None
    twin: Optional[str] = None


def _status_text(obj: dict) -> Optional[str]:
    text = obj.get("error") or obj.get("status")
    if not text:
        return None
    total, done = obj.get("total"), obj.get("completed")
    if isinstance(total, int) and total > 0 and isinstance(done, int):
        return f"{text} ({100 * done // total} %)"
    return str(text)


def create_twin(host, plan: TwinPlan, *, on_progress: "Optional[Callable[[str], None]]" = None,
                state_dir=None) -> TwinResult:
    """`/api/create` (`from` + `parameters`), each streamed status line
    handed to `on_progress`, then `/api/show` on the twin to confirm both
    parameters. Records the twin (and, when the window is the measured
    one, the twin's calibration entry: no second calibration). Never raises."""
    from halo_harness.providers.ollama import create_model, fetch_show, reset_catalog_cache
    from halo_harness.providers.ollama_calibrate import lookup_tight, record_calibration
    state_dir = _state(state_dir)

    def _on_status(obj):
        text = _status_text(obj) if isinstance(obj, dict) else None
        if text and on_progress is not None:
            on_progress(text)

    ok, message = create_model(host, plan.twin, from_model=plan.model, parameters=dict(plan.parameters),
                               on_status=_on_status)
    if not ok:
        return TwinResult(False, f"Ollama on '{host.name}' did not make {plan.twin}: {message}")
    reset_catalog_cache()
    show = fetch_show(host, plan.twin)
    params = parse_parameters((show or {}).get("parameters"))
    got = (_int(params.get("num_ctx")), _int(params.get("num_gpu")))
    if show is None or got != (plan.window, plan.layers):
        return TwinResult(False, f"{plan.twin} was made but /api/show on '{host.name}' reads num_ctx {got[0]}, "
                                 f"num_gpu {got[1]} (asked {plan.window}, {plan.layers})", plan.ref, plan.twin)
    record_twin(state_dir, host_url=host.url, twin=plan.twin, origin=plan.model, window=plan.window,
                layers=plan.layers)
    if plan.measured:
        tight = lookup_tight(state_dir, host_url=host.url, model=plan.model) or {}
        record_calibration(state_dir, host_url=host.url, model=plan.twin, digest=None,
                           max_full_gpu_ctx=plan.window, ollama_version=None, tight_ctx=tight.get("tight_ctx"),
                           tight_vram=tight.get("tight_vram"), gpu_total=tight.get("gpu_total"))
    return TwinResult(True, f"made {plan.twin}: /api/show reads num_ctx {plan.window}, num_gpu {plan.layers}",
                      plan.ref, plan.twin)


def remove_twin(host, name: str, *, state_dir=None) -> TwinResult:
    """`/api/delete` of `name` when it is a tuned twin; an original is
    left alone (one line). Never raises."""
    from halo_harness.providers.ollama import request_json, reset_catalog_cache
    state_dir = _state(state_dir)
    name = short_name(name)
    try:
        show = _show_or_raise(host, name)
    except TuneError as e:
        return TwinResult(False, e.message)
    origin = twin_origin(show, name=name, record=lookup_twin_record(state_dir, host_url=host.url, twin=name))
    if not origin:
        from halo_harness.providers.ollama import fetch_show
        twin = twin_name(name)
        hint = (f" (its twin here is {twin})" if twin != name and twin_origin(
            fetch_show(host, twin), name=twin, record=lookup_twin_record(state_dir, host_url=host.url, twin=twin))
            else "")
        return TwinResult(False, f"not a twin: {name} is an original; halo ollama tune makes twins and removes "
                                 f"only them{hint}")
    reply = request_json(host, "/api/delete", method="DELETE", body={"model": name})
    if reply.body is None:
        return TwinResult(False, f"Ollama on '{host.name}' did not delete {name}: "
                                 f"{reply.failure}{' ' + str(reply.status) if reply.status else ''}")
    forget_twin(state_dir, host_url=host.url, twin=name)
    reset_catalog_cache()
    return TwinResult(True, f"removed {name} from '{host.name}' ({origin} and its weights stay)",
                      f"ol:{name}@{host.name}", name)
