"""halo_harness.ollama_steward.rules_crash -- Halo 3.3.6.0 R3: a crash fingerprint that repeats proposes the fix
(plans/local-model-fit-brief.md G11's second half; fingerprints.py, fingerprint_facts.py).

    crash_rules(ctx) -> [finding]     rules.run_rules adds them beside the other rules
    fixes_for(fp, host, profile=None) -> [{side, line, cost}]
    staged_line(host, running) -> "0.40.13 is staged on <host>; the crash fix is in it -- restart Ollama there" | ""

A fingerprint with `count >= 2` (the same host, model, signature, window, KV type, flash attention and spill) is one
`error` finding per host and model. Halo's side is the proposal the steward's apply modes take (`ollama.steward.apply`:
auto applies it, review writes it down): a smaller window in the profile (`num_ctx`, half the crash window, never
under 8,192, never over the profile's battery-measured usable window). The rest are stated actions only, `fixes` on
the finding and the first as its `server_hint`: f16 KV (`OLLAMA_KV_CACHE_TYPE=f16`, the q8_0 KV off), flash attention
off (`OLLAMA_FLASH_ATTENTION=0`: Ollama 0.40 takes neither per request, so both are server settings), a fitted twin
(`halo ollama tune <model> --window N`) and, on a Windows host with an update staged, the restart that runs it.
Halo never changes a server setting or restarts a server.
"""

from __future__ import annotations

import re
from typing import Optional

from halo_harness.ollama_steward.rules import finding, proposal

FLOOR = 8192
STEP = 4096
KNOWN_FIX = "0.40.13"  # the measured CUDA IMA (FA + q8_0 KV + a spill) was gone on 0.40.13 (knowledge/server-log.md)
SEAMS: dict = {}  # "staged": fn(host) -> version | "" (the tests' seam; doctor_local_ids.staged_update otherwise)


def _vt(v) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", str(v or ""))[:3]) or (0,)


def staged_line(host, running: Optional[str]) -> str:
    """The stated restart when an Ollama update newer than `running` is staged on that machine."""
    try:
        if "staged" in SEAMS:
            staged = SEAMS["staged"](host) or ""
        else:
            from halo_harness.doctor_local_ids import staged_update
            staged = staged_update(host)
    except Exception:
        staged = ""
    name = getattr(host, "name", None) or str(host or "the host")
    if not staged or (running and staged != "an update" and _vt(staged) <= _vt(running)):
        return ""
    has_fix = staged != "an update" and _vt(staged) >= _vt(KNOWN_FIX)
    return (f"{staged} is staged on {name}; " + ("the crash fix is in it" if has_fix else "it may carry the crash fix") +
            " -- restart Ollama there")


def _smaller(fp: dict, profile: Optional[dict]) -> Optional[int]:
    w = fp.get("window_used") or fp.get("num_ctx_requested")
    if not isinstance(w, int) or w <= FLOOR:
        return None
    to = max(FLOOR, (w // 2) // STEP * STEP)
    usable = (((profile or {}).get("window") or {}).get("usable"))
    if isinstance(usable, int) and FLOOR <= usable < to:
        to = usable // STEP * STEP or usable
    return to if to < w else None


def _on(v) -> bool:
    return str(v).lower() in ("on", "true", "1", "enabled")


def fixes_for(fp: dict, host=None, profile: Optional[dict] = None) -> list:
    """Every fix for a repeated crash, each said as one stated action: Halo's side first, then the host's."""
    model, name = fp.get("model") or "the model", getattr(host, "name", None) or fp.get("host") or "the host"
    out = []
    to = _smaller(fp, profile)
    if to:
        out.append({"side": "halo", "line": f"a {to:,} window for {model} on {name} (the profile's num_ctx): the crash "
                    "window spilled", "cost": "a shorter context; compaction runs sooner"})
    if str(fp.get("kv_cache_type") or "").lower() == "q8_0":
        out.append({"side": "host", "line": f"OLLAMA_KV_CACHE_TYPE=f16 on {name} (the q8_0 KV off), then restart Ollama there",
                    "cost": "the KV cache takes twice the memory: a smaller window fits"})
    if _on(fp.get("flash_attention")):
        out.append({"side": "host", "line": f"OLLAMA_FLASH_ATTENTION=0 on {name} (flash attention off), then restart Ollama "
                    "there; Ollama takes it per server, not per request", "cost": "slower prompt reads, more memory per token"})
    if fp.get("spill") and fp.get("model"):
        out.append({"side": "halo", "line": f"a fitted twin: halo ollama tune {model} --host {name} --window {to or 32768}",
                    "cost": "one model create on the host (the weights are shared)"})
    staged = staged_line(host if host is not None else name, fp.get("ollama_version"))
    if staged:
        out.append({"side": "host", "line": staged, "cost": "a restart of Ollama on that machine"})
    return out


def _profile(state_dir, model, host_name):
    try:
        from halo_harness.providers.ollama_capability import profile_for
        return profile_for(state_dir, model, host_name) if state_dir is not None and model else None
    except Exception:
        return None


def crash_rules(ctx: dict) -> list:
    from halo_harness.ollama_steward.fingerprints import WORDS, read
    from halo_harness.ollama_steward.profiles import key_for
    state_dir = ctx.get("state_dir")
    if state_dir is None:
        return []
    hosts = {h.name.lower(): h for h in ctx.get("hosts") or []}
    seen, out = set(), []
    for fp in read(state_dir):
        if int(fp.get("count") or 1) < 2 or fp.get("from") or not fp.get("model"):
            continue
        host = hosts.get(str(fp.get("host") or "").lower())
        name = host.name if host is not None else str(fp.get("host") or "?")
        key = key_for(name, fp["model"])
        if key in seen:
            continue
        seen.add(key)
        group = {"host": name, "model": fp["model"], "key": key}
        fixes = fixes_for(fp, host, _profile(state_dir, fp["model"], name))
        to = _smaller(fp, _profile(state_dir, fp["model"], name))
        cur = ((ctx.get("profiles") or {}).get(key) or {}).get("num_ctx") or fp.get("window_used")
        prop = proposal("num_ctx", cur, to, f"{fp['count']} crashes ({fp.get('signature')}) at "
                        f"{fp.get('window_used') or '?'}") if to and (not isinstance(cur, int) or to < cur) else None
        hint_fix = next((f for f in fixes if f["side"] == "host"), None)
        text = (f"{fp['model']} crashed {fp['count']} times on {name} with the same settings "
                f"({WORDS.get(fp.get('signature'), fp.get('signature'))}" +
                (", after a spill" if fp.get("spill") else "") + "): " +
                ("; ".join(f["line"] for f in fixes[:3]) or "no fix is known for this signature yet"))
        out.append(finding("crash-repeats", group, "error", text, numbers={"count": fp["count"], "window": fp.get("window_used")},
                           proposal=prop, server_hint={"env": None, "line": hint_fix["line"], "cost": hint_fix["cost"]}
                           if hint_fix else None, fixes=fixes, fingerprint=fp.get("line")))
    return out
