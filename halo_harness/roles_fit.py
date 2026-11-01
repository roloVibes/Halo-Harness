"""halo_harness.roles_fit -- the spawn-time fit verdict for every lane (Halo 3.3.7.0 R3; plans/local-model-fit-brief.md
D1 5). `roles.vram_aware_override` redirects its four roles (small, researcher, judge, subagent_default) to main's
model when they would not fit beside it, as before; every other lane is told, not redirected: before a child spawns
on a different local model on main's card, the session states whether it fits beside main, what it evicts and the
swap time -- the child's first event.

    observe(role, raw_value, main_ref)   vram_aware_override's call for every role (remembered, judged at spawn)
    verdict(role, child_ref, main_ref, *, state_dir=None) -> Verdict | None
    Verdict = {fits_beside_main, evicts [model], swap_s, swap_from, host, main, child, role, window, line}
        None: not two different `ol:` models on one host, or the card / catalog was not read (nothing is guessed)
    for_child(child) -> Verdict | None   the child's model against its parent's (agent/subagent.py)
    first_events(child, *, turn=0) -> a generator: the verdict's line, then (when it does not fit beside main) the
        pivot (local_sched/pivot.py: one at a time per card, the minimum residency)

The arithmetic is local_sched/warm_set.pack over main's lane and the child's (weights + KV at each lane's window,
the per-card reserve, the helper's footprint); `evicts` the loaded models that would have to go for the child
(largest first, `/api/ps` now); `swap_s` the child's load time (local_sched/swap_cost: the ledger, the speed card,
the weights).
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from halo_harness import events

log = logging.getLogger("bridge")

SEEN: dict = {}  # (role, model, main) -> monotonic: what vram_aware_override saw last


def observe(role: str, raw_value, main_ref) -> None:
    try:
        from halo_harness.roles import role_value_parts
        model, _e = role_value_parts(raw_value)
        if isinstance(model, str) and model.startswith("ol:"):
            SEEN[(str(role), model, str(getattr(main_ref, "raw", main_ref) or ""))] = time.monotonic()
    except Exception:
        pass


def _ref(raw) -> "tuple[Optional[str], Optional[str]]":
    from halo_harness.local_sched.facts import split_ref
    s = str(getattr(raw, "raw", raw) or "")
    return split_ref(s) if s.startswith("ol:") else (None, None)


def _evicts(rows: list, child: str, need: float, room: int) -> list:
    from halo_harness.providers.ollama import ollama_names_match
    others = [r for r in rows if not ollama_names_match(r.get("model") or r.get("name"), child)]
    free = room - sum(int(r.get("size_vram") or r.get("size") or 0) for r in others)
    out = []
    for r in sorted(others, key=lambda r: -int(r.get("size_vram") or r.get("size") or 0)):
        if free >= need:
            break
        out.append(str(r.get("model") or r.get("name")))
        free += int(r.get("size_vram") or r.get("size") or 0)
    return out


def verdict(role: str, child_ref, main_ref, *, state_dir=None) -> Optional[dict]:
    from halo_harness.local_sched import facts as F
    from halo_harness.providers.ollama import ollama_names_match
    child, ch = _ref(child_ref)
    main, mh = _ref(main_ref)
    if not child or not main or ollama_names_match(child, main):
        return None
    host, other = F.host_named(ch), F.host_named(mh)
    if host is None or other is None or str(host.url).rstrip("/") != str(other.url).rstrip("/"):
        return None
    from halo_harness.local_sched.swap_cost import secs
    from halo_harness.local_sched.warm_set import pack
    rows = F.loaded(host)
    lanes = [{"lane": "main", "model": main, "host": host.name}, {"lane": role or "child", "model": child, "host": host.name}]
    ws = pack(host, lanes, rows=rows, state_dir=state_dir)
    m_main = next((m for m in ws["warm"] + ws["pivots"] if ollama_names_match(m["model"], main)), None)
    m_child = next((m for m in ws["warm"] + ws["pivots"] if ollama_names_match(m["model"], child)), None)
    if m_main is None or m_child is None:
        return None
    fits = any(m is m_child for m in ws["warm"])
    warm_now = F.is_loaded(rows, child, m_child["window"])
    from halo_harness.local_sched.reserve import cloud_target, held, route_line  # 3.3.7.0 R5: L4, never evict a claim
    blocked = bool(ws.get("claims")) and not fits and not warm_now and bool(m_child.get("never"))
    free_rows = [r for r in rows if not held(host, r.get("model") or r.get("name"), state_dir=state_dir)]
    evicts = [] if fits or warm_now else _evicts(free_rows, child, float(m_child["need"] or 0), int(ws["usable"]))
    swap_s = None if warm_now else m_child.get("load_s")
    sizes = f"{m_main['gb']:.1f} + {m_child['gb']:.1f} of {F.gb(ws['usable'])} GB"
    who = f"fit: {role or 'the child'} on {child} {{}} beside main ({main}) on {host.name}"
    if fits:
        line = who.format("fits") + f" ({sizes}): no swap" + (", already warm" if warm_now else "")
    else:
        gone = ", ".join(evicts) if evicts else "nothing loaded now"
        if warm_now:
            tail = "already loaded, main reloads after it"
        elif swap_s is not None:
            tail = f"evicts {gone}, ~{secs(swap_s)} to load ({m_child.get('load_from')})"
        else:
            tail = f"evicts {gone}; load time unknown"
        line = who.format("does not fit") + f" ({sizes}): {tail}"
    route_to = (cloud_target() or str(getattr(main_ref, "raw", main_ref) or "")) if blocked else None
    if blocked:
        line = who.format("does not fit") + f" ({sizes}): " + route_line(host, route_to, state_dir=state_dir)
    return {"fits_beside_main": fits, "evicts": evicts, "swap_s": swap_s, "swap_from": m_child.get("load_from"),
            "blocked": blocked, "route_to": route_to,
            "host": host.name, "main": main, "child": child, "role": role, "window": m_child["window"],
            "warm_now": warm_now, "loaded_main": F.is_loaded(rows, main), "line": line}


def for_child(child) -> Optional[dict]:
    parent = getattr(child, "_parent_model_raw", None)
    ref = getattr(child, "model_ref", None)
    if not isinstance(parent, str) or ref is None or getattr(ref, "provider", "") != "ollama":
        return None
    try:
        return verdict(getattr(child, "role_name", None) or "", ref, parent, state_dir=getattr(child, "state_dir", None))
    except Exception:
        log.debug("roles_fit: the spawn verdict could not be read", exc_info=True)
        return None


def first_events(child, *, turn: int = 0):
    v = for_child(child)
    if v is None:
        return None
    yield events.turn_marker("fit", v["line"], turn=turn, verdict={k: x for k, x in v.items() if k != "line"})
    if v.get("blocked") and v.get("route_to"):  # 3.3.7.0 R5: routed around a reservation, never evicting it
        from halo_harness.agent.preflight import _switch
        try:
            yield from _switch(child, v["route_to"], turn)
        except Exception:
            log.debug("roles_fit: the switch around the reservation failed", exc_info=True)
        return v
    if v["fits_beside_main"] or v["warm_now"]:
        return v
    from halo_harness.local_sched import facts as F
    from halo_harness.local_sched.pivot import plan, run
    host = F.host_named(v["host"])
    frm = v["main"] if v["loaded_main"] else (v["evicts"][0] if v["evicts"] else None)
    labels = ("main" if frm == v["main"] else None, v["role"] or "the child")
    p = plan(host, frm, v["child"], window=v["window"], labels=labels, state_dir=getattr(child, "state_dir", None))
    try:
        yield from run(p, host=host, session=child, turn=turn)
    except Exception:
        log.debug("roles_fit: the pivot failed", exc_info=True)
    return v
