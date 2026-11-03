"""halo_harness.local_sched.place -- the placement solver across machines (Halo 3.3.7.0 R3; plans/local-model-fit-
brief.md G12, the multi-host form of the pivot scheduler): where each lane's model should run.

    answer(host, lane) -> {host, via ("host" | "local"), fits, now, warm, evicts, load_s, installed, capable,
        need_bytes, usable_bytes, verdict}
        a host a paired halo host serves answers with its own `route` (3.3.7.0 R1; the helper's footprint is in
        `usable_with_helper_gb`, the room this solver uses); any other configured host -- this machine's included,
        with no `halo host` running -- from the local reads (local_sched/facts: its card, the catalog row, /api/ps)
    solve(lanes, *, hosts=None, answers=None, claims=None) -> {rows [Row], line, lanes}
        3.3.7.0 R5 (L4): `claims` ({host: [claim]}, else local_sched/reserve.claims per host): a bundle's reservation is
        never evicted -- a lane that would not fit beside it is out on that host ("meta-glasses holds 1.2 GB there"),
        the reserved model itself counts as held there; a lane moved off its own host by a claim carries `routed`, one
        line: "meta-glasses holds 1.2 GB on pc; worker goes to samus rather than evicting it"
        Row = {lane, model, host, from_host, moved, fits, warm, now, load_s, installed, score, why, says}
    apply(plan) -> [line]   `host_for` on each moved lane's `<host>|<model>|<role>` profile (agent_proposals.land_user:
        Halo-side only, one row in changes.jsonl each; nothing pulls, nothing loads until a lane asks)

The rule, lane by lane, the heaviest first (main stays on its own host: the session runs there): a host whose
profile says the model cannot do what the lane needs (tools) is out, one where it does not fit is out; of the rest
the score weighs warm (+30), fits beside what this plan already put on that card (+15; the same model already
placed there: +20, shared weights), fits now without evicting (+10), the lane's own host (+5), minus half the load
seconds, minus 5 a model it evicts, minus 25 when it would pivot beside this plan's other models, minus 50 when the
model is not pulled there, minus 40 when the host could not be read. Deterministic: a tie goes to the lane's own
host, then the name. Every row says the number behind it. 3.3.8.0 R3: the pool (local_pool/route.PoolHost) is one more
option when it has members: its `route` answer, minus its decode penalty (38, the research's 21-55 % midpoint).
3.3.8.0 R4: the penalty the pool's bench card measured when it has one; the candidates are fleet-wide by default
(local_sched/place_advice.candidates: every paired host's served card and the pool); `detail` keeps every candidate's
score, why and numbers on each row (`options`: the adviser's placement scores, `halo local place`). 3.3.9.1: a FreeToken
server (freetoken/route.FtHost) is one more option: warm for the model it serves, else a restart with its loading tax.
3.3.9.2: a Strata server (strata/route.StHost) the same way, its own loading tax.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.local_sched import facts as F

DETAIL = ("load_s", "warm", "now", "evicts", "penalty_pct", "fits", "via", "installed", "ft_tax")  # 3.3.8.0 R4: each option's numbers


def _tools(lane: str) -> bool:
    from halo_harness.providers.placement import TOOL_ROLES, role_of
    return role_of(lane) in TOOL_ROLES


def _via_host(host, lane: dict, window: int) -> Optional[dict]:
    from halo_harness.local_sched.pivot import _client
    c = _client(host)
    if c is None:
        return None
    from halo_harness.ollama_steward.host_client import HostError
    try:
        r = c.route({"model": lane["model"], "window": window, "tools": _tools(lane["lane"])})
    except HostError:
        return None
    usable = r.get("usable_with_helper_gb")
    return {"host": host.name, "via": "host", "fits": r.get("fits"), "now": r.get("now"), "warm": r.get("warm"),
            "evicts": list(r.get("evicts") or []), "load_s": r.get("load_s"), "installed": r.get("installed"),
            "capable": r.get("capable"), "need_bytes": r.get("need_bytes"),
            "usable_bytes": int(float(usable) * F.GIB) if isinstance(usable, (int, float)) else None,
            "verdict": r.get("verdict") or ""}


def _local(host, lane: dict, window: int, state_dir=None) -> dict:
    from halo_harness.local_sched.swap_cost import load_s_for
    from halo_harness.providers.ollama import ollama_names_match
    card, rows = F.card(host), F.loaded(host)
    row, src = F.row(host, lane["model"])
    b = F.budget(card, host.name)
    helper = F.helper(host, rows)
    room = F.usable(b, helper)
    out = {"host": host.name, "via": "local", "installed": src.startswith("installed"), "capable": None,
           "usable_bytes": room or None, "evicts": [], "warm": F.is_loaded(rows, lane["model"], window)}
    need = F.together(b, [{"row": row, "window": window}]) if row and b.get("budget") else None
    out["need_bytes"] = int(need) if need else None
    out["fits"] = None if need is None else need <= room
    others = [r for r in rows if not ollama_names_match(r.get("model"), lane["model"])
              and not (helper and ollama_names_match(r.get("model"), helper["model"]))]
    free = room - sum(int(r.get("size_vram") or 0) for r in others)
    out["now"] = bool(out["fits"]) and (out["warm"] or (need or 0) <= free)
    for r in sorted(others, key=lambda r: -int(r.get("size_vram") or 0)):
        if not out["fits"] or out["now"] or free >= (need or 0):
            break
        out["evicts"].append(r.get("model"))
        free += int(r.get("size_vram") or 0)
    out["load_s"] = None if out["warm"] else load_s_for(host, lane["model"], state_dir=state_dir, row=row,
                                                       fetch=False)["s"]
    if _tools(lane["lane"]):
        from halo_harness.providers.placement import profile_for_ref
        p = profile_for_ref(f"ol:{lane['model']}@{host.name}", state_dir) or {}
        out["capable"] = None if p.get("tools") not in ("yes", "no") else p["tools"] == "yes"
    out["verdict"] = (src if "was deleted from" in src else "not read (no card or no catalog row)" if out["fits"] is None else
                      f"{'fits' if out['fits'] else 'does not fit'} ({F.gb(need)} of {F.gb(room)} GB)")
    return out


def answer(host, lane: dict, *, state_dir=None) -> dict:
    if getattr(host, "pool", False):  # 3.3.8.0 R3: the pool answers like a host (local_pool/route.py)
        from halo_harness.local_pool.route import route
        return route({"model": lane["model"], "window": lane.get("window")}, state_dir=state_dir)
    if getattr(host, "freetoken", False):  # 3.3.9.1: a FreeToken server answers like a host (freetoken/route.py)
        from halo_harness.freetoken.route import route as ft_route
        return ft_route(host, {"model": lane["model"], "window": lane.get("window")}, state_dir=state_dir)
    if getattr(host, "strata", False):  # 3.3.9.2: a Strata server answers like a host (strata/route.py)
        from halo_harness.strata.route import route as st_route
        return st_route(host, {"model": lane["model"], "window": lane.get("window")}, state_dir=state_dir)
    window, _src = F.window(host, lane["model"], role=lane["lane"])
    return _via_host(host, lane, window) or _local(host, lane, window, state_dir)


def _score(a: dict, lane: dict, planned: dict) -> "tuple[Optional[float], str]":
    from halo_harness.local_sched.swap_cost import secs
    from halo_harness.providers.ollama import ollama_names_match
    if a.get("capable") is False:
        return None, "its profile says it cannot call tools there"
    if a.get("fits") is False:
        return None, a.get("verdict") or "does not fit"
    s, why = 100.0, []
    if a.get("fits") is None:
        s, why = s - 40, ["not read"]
    mine = planned.setdefault(a["host"], {"bytes": 0, "models": []})
    held_b = int(mine.get("claimed") or 0)  # 3.3.7.0 R5: a bundle's reservation there is never evicted
    reserved = any(ollama_names_match(c.get("model"), lane["model"]) for c in mine.get("held") or [] if c.get("model"))
    if (held_b and not reserved and a.get("need_bytes") and a.get("usable_bytes")
            and a["need_bytes"] + held_b > a["usable_bytes"]):
        return None, f"{mine['words']} there"
    if reserved:
        s, why = s + 20, why + ["reserved there for " + ", ".join(sorted({str(c["bundle"]) for c in mine["held"]}))]
    elif any(ollama_names_match(m, lane["model"]) for m in mine["models"]):
        s, why = s + 20, why + ["shares weights with a lane placed there"]
    elif a.get("need_bytes") and a.get("usable_bytes"):
        if mine["bytes"] + held_b + a["need_bytes"] <= a["usable_bytes"]:
            s += 15
        else:
            s, why = s - 25, why + [f"pivots beside {', '.join(mine['models'])}"]
    if a.get("warm"):
        s, why = s + 30, why + ["warm"]
    elif a.get("now"):
        s, why = s + 10, why + ["fits now"]
    if a.get("load_s"):
        s, why = s - float(a["load_s"]) / 2, why + [f"{secs(a['load_s'])} load"]
    if a.get("evicts"):
        s, why = s - 5 * len(a["evicts"]), why + [f"evicts {', '.join(a['evicts'])}"]
    if a.get("installed") is False:
        s, why = s - 50, why + ["not pulled there"]
    if a.get("measured") and a.get("speed"):  # 3.3.8.0 R4: the pool's own bench card (local_pool/speed.figures)
        s, why = s - float(a.get("penalty_pct") or 0), why + [f"pooled: {a['speed']}"]
    elif a.get("penalty_pct"):  # the pool's cost: the research's RPC decode penalty until a bench measures its own
        s, why = s - float(a["penalty_pct"]), why + [f"pooled: -{a['penalty_pct']:g} % decode ({a.get('penalty_from')})"]
    if a["host"] == lane.get("host"):
        s += 5
    return round(s, 1), ", ".join(["fits"] + why if a.get("fits") else why)


def _claimed(hosts: list, claims: Optional[dict], state_dir) -> dict:
    """{host: {bytes, models, claimed, held, words}} seeded with each card's reservations (3.3.7.0 R5, L4)."""
    from halo_harness.local_sched.reserve import claims as read, holds_words
    out: dict = {}
    for h in hosts:
        cs = (claims or {}).get(h.name) if claims is not None else read(h, state_dir=state_dir)
        cs = [c for c in cs or [] if float(c.get("gb") or 0) > 0]
        if cs:
            out[h.name] = {"bytes": 0, "models": [], "held": cs, "claimed": int(sum(float(c["gb"]) for c in cs) * F.GIB),
                           "words": holds_words(h, state_dir=state_dir) if claims is None else
                           f"{', '.join(sorted({c['bundle'] for c in cs}))} holds {sum(float(c['gb']) for c in cs):.1f} GB"}
    return out


def solve(lanes: list, *, hosts: Optional[list] = None, answers=None, state_dir=None, claims=None,
          detail: bool = False) -> dict:
    if hosts is None:  # 3.3.8.0 R4: fleet-wide -- every paired host's served card and the pool (place_advice.py)
        from halo_harness.local_sched.place_advice import candidates
        hosts = candidates(state_dir)
    hosts = list(hosts)
    ask = answers or (lambda h, ln: answer(h, ln, state_dir=state_dir))
    planned: dict = _claimed(hosts, claims, state_dir)
    order = sorted(range(len(lanes)), key=lambda i: (lanes[i]["lane"] != "main", i))
    rows: list = [None] * len(lanes)
    for i in order:
        ln = lanes[i]
        pool = [h for h in hosts if h.name == ln.get("host")] if ln["lane"] == "main" else hosts
        tried = []
        for h in pool:
            a = ask(h, ln)
            sc, why = _score(a, ln, planned)
            tried.append((sc, h.name != ln.get("host"), h.name, a, why))
        good = sorted([t for t in tried if t[0] is not None], key=lambda t: (-t[0], t[1], t[2]))
        opts = ([{"host": t[2], "score": t[0], "why": t[4], **{k: t[3].get(k) for k in DETAIL}} for t in tried]
                if detail else None)
        if not good:
            why = "; ".join(f"{t[2]}: {t[4]}" for t in tried) or "no Ollama host here"
            rows[i] = {"lane": ln["lane"], "model": ln["model"], "host": None, "from_host": ln.get("host"),
                       "moved": False, "score": None, "why": why, "says": f"{ln['lane']} nowhere ({why})",
                       **({"options": opts} if detail else {})}
            continue
        sc, _o, name, a, why = good[0]
        mine = planned.setdefault(name, {"bytes": 0, "models": []})
        if ln["model"] not in mine["models"]:
            mine["models"].append(ln["model"])
            mine["bytes"] += int(a.get("need_bytes") or 0)
        rows[i] = {"lane": ln["lane"], "model": ln["model"], "host": name, "from_host": ln.get("host"),
                   "moved": name != ln.get("host"), "fits": a.get("fits"), "warm": a.get("warm"), "now": a.get("now"),
                   "load_s": a.get("load_s"), "installed": a.get("installed"), "via": a.get("via"), "score": sc,
                   "why": why, "says": f"{ln['lane']} on {name} ({why})", **({"options": opts} if detail else {})}
        own = next((t for t in tried if t[2] == ln.get("host") and t[0] is None and " holds " in str(t[4])), None)
        if own is not None and name != ln.get("host"):  # one visible line: routed around a reservation
            rows[i]["routed"] = (f"{own[4].replace(' there', '')} on {ln.get('host')}; {ln['lane']} goes to {name} "
                                 "rather than evicting it")
            rows[i]["says"] += f" -- {rows[i]['routed']}"
    line = ", ".join(r["says"] for r in rows if r) or "no local lanes to place"
    return {"rows": [r for r in rows if r], "line": line, "lanes": lanes}


def apply(plan: dict) -> list:
    from halo_harness.config.paths import bridge_home
    from halo_harness.ollama_steward.agent_proposals import land_user
    from halo_harness.ollama_steward.profiles import key_for
    out = []
    for r in plan.get("rows") or []:
        if not r.get("moved") or not r.get("host") or r["lane"] == "main" or not r.get("from_host"):
            continue
        got = land_user(bridge_home(), {"key": key_for(r["from_host"], r["model"], r["lane"]), "field": "host_for",
                                        "to": r["host"]}, by="user", why="halo local place")
        out.append(got["line"])
    return out or ["nothing to write: every lane stays on the host it names"]
