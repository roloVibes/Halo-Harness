"""halo_harness.ollama_steward.tune_options -- Halo 3.3.6.0 R5: the tuning report's options (tune_report.py builds the
rest of the report): fit.plan's options for the host's installed models (the roles' models first), the bench's facts
(a window past the one that stayed on the GPU, a reply reserve under the one that avoided cuts), keep_alive 0 for the
models outside the warm set, and the server-side settings (the KV cache type, flash attention, the parallel slots, an
Ollama update) as the exact lines for the host's shell with the line that reverts each. Halo-side options carry
`apply` (profile changes, profiles.CHANGEABLE); server-side ones carry `server` and nothing runs them.
"""

from __future__ import annotations

from halo_harness.ollama_steward.tune_report import _k, _opt

TAKES_HALO = "at once: the next call to that model reads it"


def _halo(line: str, changes: list, *, reload_s=None) -> dict:
    writes = ", ".join(f"ollama.profiles[\"{c['key']}\"].{c['field']}" for c in changes) + " in config.json"
    takes = TAKES_HALO + (f" (a new window reloads it: ~{reload_s:g} s)" if reload_s and any(c["field"] == "num_ctx"
                                                                                           for c in changes) else "")
    return _opt("halo", line, writes, takes, apply=changes)


def _server(name: str, line: str, block: dict, takes: str = "") -> dict:
    return _opt("server", line, f"nothing here: you run the line on {name}",
                takes or f"a restart of Ollama on {name} (every model unloads)", server=block)


def _plain(line: str, revert: str) -> dict:
    return {"any": {"set": line, "revert": revert, "restart": "no restart"}}


def options(state_dir, host, name: str, card: dict, b: dict, rows: dict, order: list, win: dict, warm: list,
            asked: dict, roles: list, cards: dict, models: list, os_name) -> list:
    from halo_harness.ollama_steward import fit as F
    from halo_harness.ollama_steward import tune_lines as T
    from halo_harness.ollama_steward.profiles import key_for
    out: list = []
    loads = {m: (cards.get(m) or {}).get("cold_load_s") for m in order}
    plan_in = [{"model": m, "window": win[m], "max_prompt": (asked.get(m) or {}).get("max_prompt", 0),
                "calls": (asked.get(m) or {}).get("calls", 0) + (10 ** 6 if m in roles else 0),
                "load_ms": (loads.get(m) or 0) * 1000 or (asked.get(m) or {}).get("load_ms", 0)} for m in order]
    plan = F.plan(card, plan_in, rows, host_name=name)
    for o in plan.get("options") or []:
        if o["kind"] == "kv-q8_0":
            continue  # the KV option below says it with the lines per OS
        line = f"{o['says']} (you lose: {o['lose']})"
        if o.get("changes"):
            ch = [{"key": c["key"], "field": c["field"], "to": c["to"]} for c in o["changes"]]
            out.append(_halo(line, ch, reload_s=max([v for v in loads.values() if v] or [0]) or None))
        elif o.get("server_hint"):
            hint = o["server_hint"]["line"]
            undo = (f"ollama rm {hint.split()[-1]}" if hint.startswith("ollama pull") else
                    "ollama rm <the twin's name> (halo models rm)")
            out.append(_server(name, line, _plain(hint, undo), takes=o["server_hint"].get("cost") or ""))
    for m in models:
        key, g, rf = key_for(name, m["model"]), m.get("max_gpu_window"), m.get("reserve_floor")
        if g and win[m["model"]] > g:
            out.append({**_halo(f"num_ctx {g:,} for {m['model']}: the bench saw it spill to the CPU past {_k(g)}",
                                [{"key": key, "field": "num_ctx", "to": g}], reload_s=loads.get(m["model"])), "trial": True})
        if rf and (m.get("num_predict") or 0) < rf:
            out.append({**_halo(f"num_predict {rf:,} for {m['model']}: the bench cut its replies under {rf:,}",
                                [{"key": key, "field": "num_predict", "to": rf}]), "trial": True})
    planned = {(c["key"], c["field"]) for o in out for c in o.get("apply") or []}
    for m in order:
        if m not in warm and (key_for(name, m), "keep_alive") not in planned:
            secs = loads.get(m)
            out.append(_halo(f"keep_alive 0 for {m}: unloaded after each call, so the warm set stays loaded"
                             + (f" (each call to it pays a load: ~{secs:g} s)" if secs else ""),
                             [{"key": key_for(name, m), "field": "keep_alive", "to": "0"}]))
    server = card.get("server") or {}
    from halo_harness.providers.kv_dial import crashes_with_fa_q8
    crashes = crashes_with_fa_q8(state_dir, name)
    fa = str(server.get("flash_attention")).lower() in ("true", "1", "on", "enabled")
    grow = [m for m in models if m.get("q8_0") and m.get("alone") and m["q8_0"] > m["alone"]]
    if b["kv"] in ("f16", "bf16", "f32") and grow:
        eg = grow[0]
        line = (f"OLLAMA_KV_CACHE_TYPE=q8_0 on {name}: every model's cache halves ({eg['model']} {_k(eg['alone'])} -> "
                f"{_k(eg['q8_0'])}); q8_0 KV: a small quality cost")
        if crashes:
            line += f"; {crashes} crash{'es' if crashes != 1 else ''} here with FA + q8_0 KV (halo ollama crashes --why)"
        out.append(_server(name, line, T.server_block("env", "OLLAMA_KV_CACHE_TYPE", "q8_0", os_name)))
        if not fa:
            out.append(_server(name, f"OLLAMA_FLASH_ATTENTION=1 on {name}: a q8_0 KV cache needs flash attention",
                               T.server_block("env", "OLLAMA_FLASH_ATTENTION", "1", os_name)))
    elif b["kv"] == "q8_0" and crashes:
        out.append(_server(name, f"OLLAMA_KV_CACHE_TYPE=f16 on {name}: {crashes} crash{'es' if crashes != 1 else ''} "
                                 "here with FA + q8_0 KV; the windows shrink back", T.server_block("env", "OLLAMA_KV_CACHE_TYPE", "f16", os_name)))
    if int(b.get("parallel") or 1) > 1:
        out.append(_server(name, f"OLLAMA_NUM_PARALLEL=1 on {name}: each of the {b['parallel']} slots holds its own "
                                 "KV cache; one slot gives every model a larger window", T.server_block("env", "OLLAMA_NUM_PARALLEL", "1", os_name)))
    from halo_harness.ollama_steward.rules_crash import KNOWN_FIX, _vt
    v = server.get("version")
    if v and _vt(v) < _vt(KNOWN_FIX):
        out.append(_server(name, f"update Ollama on {name} from {v} to {KNOWN_FIX} or newer (the CUDA crash fix)",
                           T.server_block("update", "", "", os_name), takes=f"a download and a restart of Ollama on {name}"))
    seen, uniq = set(), []
    for o in out:
        if o["id"] not in seen:
            seen.add(o["id"])
            uniq.append(o)
    return uniq
