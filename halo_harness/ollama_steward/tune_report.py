"""halo_harness.ollama_steward.tune_report -- Halo 3.3.6.0 R5: the tuning report, the planner's options for a whole
host in one place (`halo local tune`, the Benchmarks page's second block).

    report_for(state_dir, host_name, *, card=None, catalog=None) -> {host, says, budget, warm_set, models, findings,
        options, os}
    format_report(r) -> lines

Over the host's installed models (the roles' models first), its hardware card, the speed cards (the bench) and
fit.plan: (a) the warm set that fits together and what a pivot to each other model costs (its cold load); (b) per model
its window alone, beside the warm set and with a q8_0 KV cache (providers/kv_dial.py; "verified" when the bench loaded
it at that KV type, else "computed"); (c) the reply reserve each needs (the bench's `reserve_floor`); (d) the findings
rules_card / rules_host raise for this host. Every option is {id, line, kind: halo | server, writes, takes, apply:
[{key, field, to}] | None, server: {os: {set, revert, restart}} | None, scope_default}: a Halo-side one lands with Apply
(tune_lines.apply -> agent_proposals.land_user, with a scope: keep, or session for the bench's trial settings while a
session is open), a server-side one prints
the exact line for your shell and the line that reverts it, and nothing runs it. No request but the cached reads.
"""

from __future__ import annotations

import hashlib
from typing import Optional

GIB = 2 ** 30
DEFAULT_WINDOW = 32768


def _gib(n) -> str:
    return f"{(n or 0) / GIB:.1f} GiB"


def _k(n) -> str:
    return f"{n // 1024}k" if isinstance(n, int) and n >= 1024 else str(n or "?")


def _opt(kind: str, line: str, writes: str, takes: str, apply=None, server=None) -> dict:
    oid = "t-" + hashlib.sha1(f"{kind}|{line}".encode("utf-8")).hexdigest()[:6]
    return {"id": oid, "line": line, "kind": kind, "writes": writes, "takes": takes, "apply": apply, "server": server,
            "scope_default": "keep" if kind == "halo" else None}


def _asked(state_dir, name: str) -> dict:
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.ollama_steward.profiles import short_model
    out: dict = {}
    for x in read_calls(state_dir, since=7 * 86400.0, host=name) if state_dir is not None else []:
        if x.get("kind") == "calibrate" or not x.get("model"):
            continue
        a = out.setdefault(short_model(x["model"]), {"calls": 0, "max_prompt": 0, "load_ms": 0.0})
        a["calls"] += 1
        a["max_prompt"] = max(a["max_prompt"], int(x.get("prompt_eval_count") or 0))
        a["load_ms"] = max(a["load_ms"], float(x.get("load_ms") or 0))
    return out


def _role_models(name: str) -> list:
    from halo_harness.providers.placement_apply import _host_of
    from halo_harness.roles import configured_role_table, role_value_parts
    from halo_harness.theme import get_config_value
    refs = [get_config_value("model", default=None)] + [role_value_parts(v)[0] for v in configured_role_table().values()]
    out = []
    for ref in refs:
        if isinstance(ref, str) and ref.startswith("ol:"):
            from halo_harness.providers.local_bench_runs import _on_host
            m, _h = _host_of(ref)
            if _on_host(ref, name) and m not in out:
                out.append(m)
    return out


def _pivot(state_dir, name: str, model: str, row: dict, sc: Optional[dict]) -> dict:
    if sc and isinstance(sc.get("cold_load_s"), (int, float)):
        return {"model": model, "cold_load_s": sc["cold_load_s"], "source": "the bench"}
    from halo_harness.providers.measured import measured_for
    ld = (measured_for(name, model, state_dir=state_dir).get("load_s") or {}) if state_dir is not None else {}
    if isinstance(ld.get("value"), (int, float)):
        return {"model": model, "cold_load_s": ld["value"], "source": ld.get("source")}
    return {"model": model, "cold_load_s": round((row.get("size") or 0) / 1e9 * 1.5, 0), "source": "estimated from its size"}


def report_for(state_dir, host_name: str, *, card: Optional[dict] = None, catalog: Optional[dict] = None) -> dict:
    from halo_harness.ollama_steward import fit as F
    from halo_harness.ollama_steward import tune_lines as T
    from halo_harness.ollama_steward.profiles import all_profiles, key_for, short_model
    from halo_harness.providers.local_bench_runs import load as load_card
    from halo_harness.providers.ollama import resolve_ollama_host
    host = resolve_ollama_host(host_name)
    if host is not None and (card is None or catalog is None):
        from halo_harness.studio import ollama_hosts_view as V
        card = V.card_of(host) if card is None else card
        catalog = V.catalog_of(host) if catalog is None else catalog
    rows = {short_model(r.get("model") or r.get("name")): r for r in (catalog or {}).get("models") or []
            if isinstance(r, dict) and isinstance(r.get("size"), int)}
    out = {"host": host_name, "budget": None, "warm_set": None, "models": [], "findings": [], "options": [],
           "os": T.os_of(host, card)}
    if not card or not rows:
        out["says"] = f"nothing to plan on {host_name}: " + ("no hardware card read yet" if not card else "no installed models")
        return out
    b = F.card_budget(card, host_name)
    out["budget"] = {k: b[k] for k in ("total", "others", "budget", "kv", "parallel")}
    profiles, asked, roles = all_profiles(), _asked(state_dir, host_name), _role_models(host_name)
    order = sorted(rows, key=lambda m: (m not in roles, roles.index(m) if m in roles else 0, -(asked.get(m) or {}).get("calls", 0),
                                        -rows[m]["size"]))
    info = {m: rows[m].get("model_info") or {} for m in order}
    win = {}
    trained = {m: next((v for k, v in info[m].items() if k.endswith(".context_length") and isinstance(v, int)), None)
               for m in order}
    for m in order:
        win[m] = (profiles.get(key_for(host_name, m)) or {}).get("num_ctx") or min(trained[m] or DEFAULT_WINDOW, DEFAULT_WINDOW)
    need = {m: (F._need(b, rows[m], win[m]) if info[m] else rows[m]["size"] + 512 * 2 ** 20) or 0 for m in order}
    reserve = (512 if b["metal"] else 457) * 2 ** 20 * b["cards"]
    warm, used = [], reserve
    for m in order:
        if used + need[m] <= b["budget"]:
            warm.append(m)
            used += need[m]
    cards = {m: load_card(state_dir, host_name, m, rows[m].get("digest")) if state_dir is not None else None for m in order}
    pivots = [_pivot(state_dir, host_name, m, rows[m], cards[m]) for m in order if m not in warm]
    out["warm_set"] = {"models": warm, "used": int(used), "budget": b["budget"], "pivots": pivots,
                       "line": (" + ".join(f"{m} at {_k(win[m])}" for m in warm) + f" fit together: {_gib(used)} of "
                                f"{_gib(b['budget'])}") if warm else f"no model fits {host_name}'s card at its window"}
    for p in pivots:
        p["line"] = f"a pivot to {p['model']} costs ~{p['cold_load_s']:g} s of loading ({p['source']})"
    from halo_harness.providers.kv_dial import dial_for
    for m in order:
        row = {**rows[m], "model_info": info[m]}
        alone = F.model_window_on_card(card, row, step=F.STEP) if info[m] else None
        others = sum(need[o] for o in warm if o != m)
        beside = F.model_window_on_card({**card, "other_users": list(card.get("other_users") or []) + [{"bytes": int(others)}]},
                                        row, step=F.STEP) if info[m] else None
        dial = dial_for(host, m, state_dir=state_dir, card=card, row=row) if host is not None and info[m] else None
        q8 = next((r["window"] for r in (dial or {}).get("rows") or [] if r["kv"] == "q8_0"), None)
        cap = lambda w: min(w, trained[m]) if isinstance(w, int) and trained[m] else w  # noqa: E731  (never past training)
        alone, beside, q8 = cap(alone), cap(beside), cap(q8)
        sc = cards[m] or {}
        kv_ok = (sc.get("kv") or {}).get("type") == "q8_0" and (sc.get("kv") or {}).get("verified_window")
        prof = profiles.get(key_for(host_name, m)) or {}
        out["models"].append({"model": m, "role": m in roles, "window": win[m], "alone": alone, "beside": beside,
                              "q8_0": q8, "q8_0_from": "verified by the bench" if kv_ok else "computed",
                              "max_gpu_window": sc.get("max_gpu_window"), "reserve_floor": sc.get("reserve_floor"),
                              "num_predict": prof.get("num_predict"),
                              "line": f"{m}: its catalog row has no shape, so its windows are not worked out" if not info[m] else
                                      f"{m}: alone {_k(alone)} · beside the warm set {_k(beside) if m in warm or beside else 'no room'}"
                                      f" · with q8_0 KV {_k(q8)} ({'verified by the bench' if kv_ok else 'computed'})"
                                      + (f" · the bench: on the GPU up to {_k(sc['max_gpu_window'])}" if sc.get("max_gpu_window") else "")
                                      + (f" · reply reserve {sc['reserve_floor']:,}" if sc.get("reserve_floor") else "")})
    out["findings"] = _findings(state_dir, host_name, card, rows)
    from halo_harness.ollama_steward.tune_options import options
    out["options"] = options(state_dir, host, host_name, card, b, rows, order, win, warm, asked, roles, cards,
                             out["models"], out["os"])
    live = _live_session()
    for o in out["options"]:  # the bench's trial settings last the session when one is open; yours keep
        if o.pop("trial", False) and live:
            o["scope_default"] = "session"
    out["says"] = (f"{len(warm)} of {len(order)} models stay warm together on {host_name}; {len(out['options'])} "
                   f"option{'s' if len(out['options']) != 1 else ''}")
    return out


def _live_session() -> bool:
    try:
        from halo_harness.remote.registry import list_live
        return bool(list_live())
    except Exception:
        return False


def _findings(state_dir, name: str, card: dict, rows: dict) -> list:
    if state_dir is None:
        return []
    try:
        from halo_harness.ollama_steward import rules_card, rules_host
        from halo_harness.ollama_steward.rules import gather
        ctx = gather(state_dir, host=name, cards={name: card}, catalogs={name: rows})
        found = [f for g in ctx["groups"] for rule in rules_card.RULES for f in rule(g, ctx) or []]
        found += rules_host.host_rules(ctx)
    except Exception:
        return []
    return [{"id": f["id"], "rule": f["rule"], "severity": f["severity"], "model": f["model"],
             "line": f"{f['severity']} {f['model']}: {f['finding']}"} for f in found]


def format_report(r: dict) -> list:
    out = [f"'{r['host']}': {r.get('says', '')}"]
    b = r.get("budget")
    if b:
        out.append(f"  the card: {_gib(b['budget'])} for models ({_gib(b['others'])} held by other programs), KV "
                   f"{b['kv']}, {b['parallel']} slot{'s' if b['parallel'] != 1 else ''}")
    ws = r.get("warm_set")
    if ws:
        out.append(f"  warm set: {ws['line']}")
        out.extend(f"    {p['line']}" for p in ws["pivots"])
    out.extend(f"  {m['line']}" for m in r.get("models") or [])
    out.extend(f"  finding: {f['line']}" for f in r.get("findings") or [])
    for o in r.get("options") or []:
        out.append(f"  [{o['id']}] {o['kind']}: {o['line']} -- writes {o['writes']}; takes {o['takes']}")
        for os_name, s in (o.get("server") or {}).items():
            out.append(f"      {os_name}: {s['set']}   (revert: {s['revert']}; then {s['restart']})")
    return out
