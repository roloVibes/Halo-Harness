"""halo_harness.packs.manifest_bundle -- a bundle: a pack with a resource claim (Halo 3.3.7.0 R5;
plans/local-model-fit-brief.md Part L5; docs/EXTENSION_API.md "Bundles").

A pack becomes a capability bundle with one more block in its pack.yaml:

    bundle:
      needs:                                   # each role the bundle needs, with the models that can fill it
        chat: {any_of: [lfm3:1.7b, qwen3-coder:30b-gpu], window: 8192}
        stt:  {any_of: [faster-whisper:large-v3-turbo, faster-whisper:small.en], device: cpu-or-gpu}
        tts:  {any_of: [kokoro-82m], device: cpu}
      reservation: {model: lfm3:1.7b, vram_gb: 1.2, keep_alive: -1, priority: high}
      routing: {task_work: coder-or-cloud, never_evict: reserved}
      latency_budget_ms: 1500

    bundle_lines(data) -> [one line per problem]      validate_manifest's call (manifest.py)
    block(data) -> the normalized bundle | None       defaults filled in: device gpu, keep_alive -1, priority normal,
                                                      task_work coder-or-cloud, never_evict reserved, escalation on;
                                                      3.3.8.0 R4 (manifest_bundle_claims.py): `reservations` (each
                                                      with host, min_free_gb, priority), `schedule`, `priority`,
                                                      `min_free_gb`; `reservation` = the one on the default host
    is_bundle(pack_or_manifest) -> bool
    runtime(model) -> "ollama" | "voice"              a speech model (faster-whisper, kokoro, ...) runs beside Ollama, not
                                                      in it: Voice (3.3.8.0) brings it; this round knows its size only
    voice_gb(model) -> GB on a GPU | None             the speech models' published sizes (VOICE_GB)
    reserved_model(b) -> the tag the reservation holds (a needs role names that need's first any_of)

`reservation.model` is a tag one of the needs lists, or a needs role (whichever of its `any_of` the verdict picks);
`vram_gb` left out is computed by the verdict (local_sched/bundle_fit.py: the weights plus the KV at the need's window
on that card). Shape only here and in schemas/pack_yaml.py; the arithmetic is the verdict's.
"""

from __future__ import annotations

import re
from typing import Optional

DEVICES = ("gpu", "cpu", "cpu-or-gpu")
PRIORITIES = ("high", "normal", "low")
TASK_WORK = ("coder", "coder-or-cloud", "cloud", "local")
NEVER_EVICT = ("reserved", "none")
ESCALATION = ("on", "off")
RUNTIMES = ("ollama", "voice")
ROLE_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
DURATION_RE = re.compile(r"^\d+(\.\d+)?[smh]$")
#: the speech models a bundle may name: their size on a GPU (GB), from their published weights
VOICE_GB = {"faster-whisper:large-v3-turbo": 1.5, "faster-whisper:large-v3": 3.0, "faster-whisper:medium.en": 1.5,
            "faster-whisper:small.en": 0.5, "faster-whisper:base.en": 0.2, "parakeet-tdt:0.6b": 1.2,
            "kokoro-82m": 0.3, "qwen3-tts:0.6b": 1.4}
VOICE_PREFIXES = ("faster-whisper", "whisper", "parakeet", "kokoro", "qwen3-tts", "silero")


def runtime(model: str, declared: Optional[str] = None) -> str:
    if declared in RUNTIMES:
        return declared
    return "voice" if str(model or "").lower().startswith(VOICE_PREFIXES) else "ollama"


def voice_gb(model: str) -> Optional[float]:
    return VOICE_GB.get(str(model or "").lower())


def _raw(data) -> Optional[dict]:
    manifest = getattr(data, "manifest", data)
    raw = manifest.get("bundle") if isinstance(manifest, dict) else None
    return raw if isinstance(raw, dict) else None


def is_bundle(data) -> bool:
    return _raw(data) is not None


def _need_lines(role, need) -> "list[str]":
    where = f"bundle.needs.{role}"
    if not isinstance(role, str) or not ROLE_RE.match(role):
        return [f"bundle.needs: {role!r} is not a role name (lower-case, digits, _ and -)"]
    if not isinstance(need, dict):
        return [f"{where}: a mapping ({{any_of: [model, ...], window?, device?}})"]
    out = []
    names = need.get("any_of")
    if not isinstance(names, list) or not names or not all(isinstance(n, str) and n.strip() for n in names):
        out.append(f"{where}.any_of: required, the models that can fill it, best first ([lfm3:1.7b, ...])")
    w = need.get("window")
    if w is not None and (not isinstance(w, int) or isinstance(w, bool) or w < 512):
        out.append(f"{where}.window: {w!r} is not a window in tokens (512 or more)")
    if need.get("device") is not None and need.get("device") not in DEVICES:
        out.append(f"{where}.device: {need.get('device')!r} is not one of {', '.join(DEVICES)}")
    if need.get("runtime") is not None and need.get("runtime") not in RUNTIMES:
        out.append(f"{where}.runtime: {need.get('runtime')!r} is not one of {', '.join(RUNTIMES)}")
    for flag in ("vision", "tools"):
        if need.get(flag) is not None and not isinstance(need.get(flag), bool):
            out.append(f"{where}.{flag}: true or false")
    return out


def _reservation_lines(res, needs: dict) -> "list[str]":
    if res is None:
        return []
    if not isinstance(res, dict):
        return ["bundle.reservation: a mapping ({model, vram_gb?, keep_alive?, priority?}), or leave it out"]
    out = []
    model = res.get("model")
    named = {n for need in needs.values() if isinstance(need, dict) for n in need.get("any_of") or [] if isinstance(n, str)}
    if not isinstance(model, str) or not model.strip():
        out.append("bundle.reservation.model: required (a model one of the needs lists, or a needs role)")
    elif model not in needs and model not in named:
        out.append(f"bundle.reservation.model: {model!r} is neither a needs role nor a model a need lists")
    elif runtime(_first(needs, model) or model) == "voice":
        out.append(f"bundle.reservation.model: {model!r} is a speech model; a reservation holds an Ollama model")
    gb = res.get("vram_gb")
    if gb is not None and (not isinstance(gb, (int, float)) or isinstance(gb, bool) or gb <= 0):
        out.append(f"bundle.reservation.vram_gb: {gb!r} is not a size in GB (leave it out and the verdict computes it)")
    keep = res.get("keep_alive")
    if keep is not None and not (keep == -1 or (isinstance(keep, str) and (keep == "-1" or DURATION_RE.match(keep)))):
        out.append(f"bundle.reservation.keep_alive: {keep!r} is not -1 or a duration (30m, 2h)")
    if res.get("priority") is not None and res.get("priority") not in PRIORITIES:
        out.append(f"bundle.reservation.priority: {res.get('priority')!r} is not one of {', '.join(PRIORITIES)}")
    w = res.get("window")
    if w is not None and (not isinstance(w, int) or isinstance(w, bool) or w < 512):
        out.append(f"bundle.reservation.window: {w!r} is not a window in tokens (512 or more)")
    return out


def _routing_lines(r) -> "list[str]":
    if r is None:
        return []
    if not isinstance(r, dict):
        return ["bundle.routing: a mapping ({task_work, never_evict, escalation})"]
    out = []
    for key, allowed in (("task_work", TASK_WORK), ("never_evict", NEVER_EVICT), ("escalation", ESCALATION)):
        v = r.get(key)
        if isinstance(v, bool) and key == "escalation":
            continue  # YAML reads a bare on / off as true / false
        if v is not None and v not in allowed:
            out.append(f"bundle.routing.{key}: {v!r} is not one of {', '.join(allowed)}")
    return out


def bundle_lines(data) -> "list[str]":
    """The meaning of `bundle:` (its shape is schemas/pack_yaml.bundle's); [] for a pack without one."""
    if not isinstance(data, dict) or data.get("bundle") is None:
        return []
    raw = data.get("bundle")
    if not isinstance(raw, dict):
        return ["bundle: a mapping (needs, reservation, routing, latency_budget_ms)"]
    needs = raw.get("needs") if raw.get("needs") is not None else {}
    if not isinstance(needs, dict):
        return ["bundle.needs: a mapping of role -> {any_of, window?, device?}"]
    out = [ln for role, need in needs.items() for ln in _need_lines(role, need)]
    out += _reservation_lines(raw.get("reservation"), needs) + _routing_lines(raw.get("routing"))
    from halo_harness.packs.manifest_bundle_claims import lines as claim_lines  # 3.3.8.0 R4: reservations, ...
    out += claim_lines(raw, needs, _reservation_lines)
    lat = raw.get("latency_budget_ms")
    if lat is not None and (not isinstance(lat, int) or isinstance(lat, bool) or lat <= 0):
        out.append(f"bundle.latency_budget_ms: {lat!r} is not a time in milliseconds")
    return out


def _first(needs: dict, model: str) -> Optional[str]:
    need = needs.get(model)
    names = (need or {}).get("any_of") if isinstance(need, dict) else None
    return names[0] if isinstance(names, list) and names else None


def _escalation(v) -> str:
    if v is False or v == "off":
        return "off"
    return "on"


def block(data) -> Optional[dict]:
    """The bundle with its defaults, or None when the pack is no bundle (or its block is not a mapping)."""
    raw = _raw(data)
    if raw is None:
        return None
    manifest = getattr(data, "manifest", data)
    needs = {}
    for role, need in (raw.get("needs") or {}).items() if isinstance(raw.get("needs"), dict) else ():
        if not isinstance(need, dict):
            continue
        names = [str(n).strip() for n in need.get("any_of") or [] if isinstance(n, str) and n.strip()]
        needs[str(role)] = {"any_of": names, "window": need.get("window") if isinstance(need.get("window"), int) else None,
                            "device": need.get("device") if need.get("device") in DEVICES else "gpu",
                            "vision": need.get("vision") is True, "tools": need.get("tools") is True,
                            "runtime": runtime(names[0] if names else "", need.get("runtime"))}
    def norm(res: dict) -> Optional[dict]:
        if not isinstance(res.get("model"), str) or not res["model"].strip():
            return None
        role = res["model"] if res["model"] in needs else next((r for r, n in needs.items() if res["model"] in n["any_of"]), None)
        keep = res.get("keep_alive", -1)
        return {"model": res["model"], "role": role, "vram_gb": res.get("vram_gb"),
                "keep_alive": -1 if keep in (-1, "-1", None) else keep,
                "priority": res.get("priority") if res.get("priority") in PRIORITIES else "normal",
                "window": res.get("window") if isinstance(res.get("window"), int) else (needs.get(role) or {}).get("window")}
    from halo_harness.packs.manifest_bundle_claims import normalize  # 3.3.8.0 R4: several, a schedule, a priority
    claims = normalize(raw, needs, norm)
    reservation = next((r for r in claims["reservations"] if not r.get("host")), None)  # the default host's one
    routing = raw.get("routing") if isinstance(raw.get("routing"), dict) else {}
    return {"id": str(manifest.get("id") or ""), "name": str(manifest.get("name") or manifest.get("id") or ""),
            "description": str(manifest.get("description") or ""), "needs": needs, "reservation": reservation,
            "routing": {"task_work": routing.get("task_work") if routing.get("task_work") in TASK_WORK else "coder-or-cloud",
                        "never_evict": routing.get("never_evict") if routing.get("never_evict") in NEVER_EVICT else "reserved",
                        "escalation": _escalation(routing.get("escalation"))},
            "latency_budget_ms": raw.get("latency_budget_ms") if isinstance(raw.get("latency_budget_ms"), int) else None,
            **claims}


def reserved_model(b: Optional[dict], chosen: Optional[dict] = None) -> Optional[str]:
    """The tag `b`'s reservation holds: a tag as written, or the model the verdict chose for that role (`chosen`:
    {role: tag}), else that need's first any_of."""
    res = (b or {}).get("reservation")
    if not res:
        return None
    if res["model"] in (b.get("needs") or {}):
        return (chosen or {}).get(res["model"]) or ((b["needs"][res["model"]]["any_of"] or [None])[0])
    return res["model"]
