"""halo_harness.host.ops_control -- the `control` operations (Halo 3.3.7.0 R2; host/ops.py has the registry).

    warm {model, num_ctx?, keep_alive?, beside?}   a load (providers/ollama_load.load) after the invariants
    pin  {model, num_ctx?, beside?}                the same, keep_alive -1 (kept until unloaded)
    unload {model}                                 keep_alive 0
    pivot {from, to, num_ctx?, keep_alive?}        unload A, then load B: one op, one event each
    set_num_ctx | set_num_predict | set_keep_alive | set_tools_max {model, value}
                                                   a Halo-side profile field (agent_proposals.land_user ->
                                                   changes.record with the request's scope), then verified
    set_kv_cache_type {value} | set_flash_attn {on}   stated: the exact line for the host's OS, applied: false
    rerun_battery {model, force?} | bench {model, quick?} | verify_twin {model, window?}   jobs on the host

Every op takes `host` (a name this host serves) or `port`; with one server served, neither. Nothing here changes a
server setting or restarts a server; the load, unload and the jobs are Ollama API calls.
"""

from __future__ import annotations

from halo_harness.host.ops import HOST, MODEL, PORT, Op

LOCAL_TIME = "local: time (no tokens leave the LAN)"
KV_TYPES = ("f16", "q8_0", "q4_0")


def _takes_load(ctx, model: str) -> str:
    from halo_harness.host.answers import _load_s
    try:
        s = _load_s(ctx.view, ctx.host, model)
    except Exception:
        s = None
    return f"~{int(s or 30)} s"


def _load_preview(ctx, p: dict, model: str, keep, rows=None) -> "tuple[dict, dict]":
    from halo_harness.host.invariants import check_load
    chk = check_load(ctx.view, ctx.host, model, p.get("num_ctx"), beside=p.get("beside") is True, rows=rows)
    would = [f"unload the duty steward's {chk['evict_helper']} first (the card is needed)"] if chk["evict_helper"] else []
    would.append(f"load {model} on {ctx.host.name} at {int(chk['window'] or 0):,}" + (f", kept {keep}" if keep is not None
                                                                                     else ""))
    out = {"would": would, "writes": ["nothing on disk: Ollama holds the model in memory"],
           "takes": _takes_load(ctx, model), "cost": LOCAL_TIME + " and the card's memory", "verdict": chk["verdict"],
           "window": chk["window"]}
    if not chk["ok"]:
        out["breach"] = chk["verdict"]
    return out, chk


def _load(ctx, p: dict, model: str, keep, rows=None) -> dict:
    from halo_harness.providers.ollama_load import load, unload
    prev, chk = _load_preview(ctx, p, model, keep, rows)
    if prev.get("breach"):
        return {"ok": False, "status": 422, "say": prev["breach"], "breach": True}
    if chk["evict_helper"]:
        gone = unload(ctx.host, chk["evict_helper"])
        ctx.publish("event", {"kind": "unloaded", "model": chk["evict_helper"], "say": f"the helper: {gone['say']}"})
    got = load(ctx.host, model, num_ctx=chk["window"], keep_alive=keep)
    ctx.forget_card()
    ctx.publish("event", {"kind": "loaded" if got["ok"] else "load-failed", "model": model, "say": got["say"]})
    return {**got, "verdict": chk["verdict"], "evicted": chk["evict_helper"]}


def p_warm(ctx, p):
    return _load_preview(ctx, p, p["model"], p.get("keep_alive"))[0]


def a_warm(ctx, p):
    return _load(ctx, p, p["model"], p.get("keep_alive"))


def p_pin(ctx, p):
    return _load_preview(ctx, p, p["model"], -1)[0]


def a_pin(ctx, p):
    return _load(ctx, p, p["model"], -1)


def p_unload(ctx, p):
    return {"would": [f"unload {p['model']} from {ctx.host.name} (keep_alive 0)"], "writes": ["nothing"],
            "takes": "~1 s", "cost": LOCAL_TIME}


def a_unload(ctx, p):
    from halo_harness.providers.ollama_load import unload
    got = unload(ctx.host, p["model"])
    ctx.forget_card()
    ctx.publish("event", {"kind": "unloaded" if got["ok"] else "unload-failed", "model": p["model"], "say": got["say"]})
    return got


def _without(ctx, model: str) -> list:
    from halo_harness.host.invariants import loaded
    from halo_harness.providers.ollama import ollama_names_match
    return [r for r in loaded(ctx.view, ctx.host) if not ollama_names_match(r.get("model"), model)]


def p_pivot(ctx, p):
    out, _chk = _load_preview(ctx, p, p["to"], p.get("keep_alive"), rows=_without(ctx, p["from"]))
    out["would"].insert(0, f"unload {p['from']} from {ctx.host.name}")
    return out


def a_pivot(ctx, p):
    from halo_harness.providers.ollama_load import unload
    prev = p_pivot(ctx, p)
    if prev.get("breach"):
        return {"ok": False, "status": 422, "say": prev["breach"], "breach": True}
    gone = unload(ctx.host, p["from"])
    ctx.publish("event", {"kind": "unloaded" if gone["ok"] else "unload-failed", "model": p["from"], "say": gone["say"]})
    if not gone["ok"]:
        return {"ok": False, "say": f"pivot stopped: {gone['say']}; {p['to']} was not loaded"}
    got = _load(ctx, p, p["to"], p.get("keep_alive"), rows=_without(ctx, p["from"]))
    if not got.get("ok"):
        got["say"] = f"{got.get('say')}; {p['from']} stays unloaded"
    return {**got, "unloaded": p["from"]}


# ---- the profile fields: fixes, verified ----------------------------------------------------------

def _profile(name: str, field: str, kind: str, help_: str) -> Op:
    from halo_harness.ollama_steward.changes import WORDS, fmt

    def breach(ctx, p) -> str:
        if field != "num_ctx":
            return ""
        from halo_harness.host.answers import _plan
        from halo_harness.host.invariants import _row
        row = _row(ctx.view, ctx.host, p["model"])
        if row is None:
            return f"{p['model']} is not on {ctx.host.name}"
        got = _plan(ctx.view.host_card(ctx.host), {**row, "model": p["model"]}, int(p["value"]), ctx.host.name)
        return "" if got["fits"] is not False else f"num_ctx {int(p['value']):,} would breach {ctx.host.name}'s card: {got['says']}"

    def preview(ctx, p):
        from halo_harness.host import verify
        from halo_harness.ollama_steward.profiles import all_profiles
        key = ctx.key(p["model"])
        cur = (all_profiles().get(key) or {}).get(field)
        out = {"would": [f"{field} {fmt(cur)} -> {fmt(p['value'])} on {key} ({WORDS[ctx.scope()]})",
                         f"then measure the next {verify.verify_calls(ctx.home)} calls (at most "
                         f"{int(verify.verify_s(ctx.home))} s) and keep it or put it back"],
               "writes": [f"config.json ollama.profiles[{key!r}].{field}", "<state>/ollama/changes.jsonl: one row "
                          "(manage/revert <id> puts it back)", "<state>/host/fixes.jsonl: the verify row"],
               "takes": "~0 s, then the verify window", "cost": "local: nothing now; a new window reloads the model "
                                                                 "on its next call"}
        why = breach(ctx, p)
        if why:
            out["breach"] = why
        return out

    def apply(ctx, p):
        from halo_harness.host import verify
        from halo_harness.ollama_steward.agent_proposals import land_user
        why = breach(ctx, p)
        if why:
            return {"ok": False, "status": 422, "say": why, "breach": True}
        key, ev = ctx.key(p["model"]), ctx.evidence or {}
        before = verify.before(ctx.view, ctx.host, p["model"])
        note = ctx.why or (f"the finding {ev['finding']}" if ev.get("finding") else "; ".join(map(str, ev.get("lines") or []))[:200])
        got = land_user(ctx.home, {"key": key, "field": field, "to": p["value"]}, scope=ctx.scope(), by=ctx.by(), why=note)
        if not got.get("ok"):
            return {"ok": False, "status": 422, "say": got["line"]}
        verify.open_fix(ctx.home, change_id=got["id"], peer=ctx.peer, op=name, host=ctx.host.name, model=p["model"],
                        key=key, field=field, to=p["value"], evidence=ctx.evidence, before_=before)
        ctx.publish("event", {"kind": "fix-landed", "change": got["id"], "key": key, "say": got["line"]})
        return {"ok": True, "say": f"{got['line']}; verifying over the next {verify.verify_calls(ctx.home)} calls",
                "change_id": got["id"], "scope": ctx.scope(), "before": before}

    return Op(name, "control", {"host": HOST, "port": PORT, "model": MODEL, "value": (kind, True, help_)}, preview, apply,
              profile=True, help=f"the profile's {field} for that host and model (a fix: it cites a finding)")


LOAD = {"host": HOST, "port": PORT, "model": MODEL, "num_ctx": ("int", False, "the window to load at"),
        "beside": ("bool", False, "load beside what is loaded (both must fit)")}
TABLE = [
    Op("warm", "control", {**LOAD, "keep_alive": ("any", False, "how long Ollama keeps it")}, p_warm, a_warm,
       help="load a model (the invariants first: it fits, one resident per card)"),
    Op("pin", "control", LOAD, p_pin, a_pin, help="load a model with keep_alive -1"),
    Op("unload", "control", {"host": HOST, "port": PORT, "model": MODEL}, p_unload, a_unload, help="unload a model"),
    Op("pivot", "control", {"host": HOST, "port": PORT, "from": ("str", True, "the model to unload"),
                            "to": ("str", True, "the model to load"), "num_ctx": LOAD["num_ctx"],
                            "keep_alive": ("any", False, "how long Ollama keeps the new one")}, p_pivot, a_pivot,
       help="unload one model, load another"),
    _profile("set_num_ctx", "num_ctx", "int", "the window"),
    _profile("set_num_predict", "num_predict", "int", "the reply's room"),
    _profile("set_keep_alive", "keep_alive", "any", "how long Ollama keeps it (30m, -1, 0)"),
    _profile("set_tools_max", "tools_max", "int", "how many tools a call carries"),
]
