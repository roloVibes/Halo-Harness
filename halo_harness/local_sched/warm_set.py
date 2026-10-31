"""halo_harness.local_sched.warm_set -- the warm set: which of a lineup's local models co-reside on one card, and how
often one pass of the lineup swaps (Halo 3.3.7.0 R3; plans/local-model-fit-brief.md D1 2, G6).

    lanes_of(role_table, main_ref=None) -> [{lane, ref, model, host}]   the `ol:` lanes, main first
    by_host(lanes) -> {host name: [lane]}
    pack(host, lanes, *, card=None, rows=None, declared=None, state_dir=None) -> WarmSet
    WarmSet = {host, budget, usable, helper, others, warm [model], pivots [model], unknown [model], used, swaps,
               swap_s, loads [model name], sequence [model name], line}
        model = {model, lanes, window, window_from, need, gb, row_from, load_s, load_from, why?, never?, warm_now}

The packing: main's model first (the session comes back to it after every hand-off), then the models more lanes
use, then the lineup's order -- a lineup's own `warm:` list goes first, in its order. A model joins the set when
the set with it fits the card: its weights (the catalog row, else the library snapshot) plus the KV at the largest
window its lanes ask (fit._need), with the per-card reserve, against the card's budget (its total minus what other
programs hold) minus the duty steward's helper while it is resident. A model that does not fit is a pivot; one
with no row or no card read is `unknown` (nothing is guessed). One pass of the lineup is main, then each lane and
back to main; the swaps are the loads a pass needs in the steady state (two passes from the warm set, the second
one counted), each load evicting the residents used furthest ahead and keeping back any that still fit beside it.
Arithmetic only: nothing loads here.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.local_sched import facts as F


def _same(a, b) -> bool:
    from halo_harness.providers.ollama import ollama_names_match
    return bool(a) and bool(b) and ollama_names_match(a, b)


def lanes_of(role_table: Optional[dict], main_ref: Optional[str] = None) -> list:
    from halo_harness.roles import role_value_parts
    default = getattr(F.host_named(None), "name", None)
    out: list = []

    def add(lane: str, value) -> None:
        ref, _effort = role_value_parts(value)
        if isinstance(ref, str) and ref.startswith("ol:"):
            model, host = F.split_ref(ref)
            if model:
                out.append({"lane": lane, "ref": ref, "model": model, "host": host or default})
    if main_ref:
        add("main", main_ref)
    for lane, value in (role_table or {}).items():
        if not (lane == "main" and main_ref):
            add(str(lane), value)
    return out


def by_host(lanes: list) -> dict:
    out: dict = {}
    for ln in lanes:
        out.setdefault(ln.get("host") or "", []).append(ln)
    return out


def sequence(lanes: list) -> list:
    """One pass: main, then each lane and back to main (main hands out the work); without a local main, the lanes."""
    main = next((ln["model"] for ln in lanes if ln["lane"] == "main"), None)
    rest = [ln["model"] for ln in lanes if ln["lane"] != "main"]
    if main is None:
        return rest
    seq = [main]
    for m in rest:
        seq += [m, main]
    return seq


def _models(host, lanes: list, card: dict) -> list:
    out: list = []
    for ln in lanes:
        m = next((x for x in out if _same(x["model"], ln["model"])), None)
        if m is None:
            m = {"model": ln["model"], "lanes": []}
            out.append(m)
        m["lanes"].append(ln["lane"])
    for m in out:
        row, src = F.row(host, m["model"])
        ws = [F.window(host, m["model"], role=lane, row_=row, card_=card) for lane in m["lanes"]]
        m["row"], m["row_from"] = row, src
        m["window"], m["window_from"] = max(ws, key=lambda w: w[0])
    return out


def _simulate(seq: list, warm: list, models: dict, b: dict, room: int) -> list:
    """The loads of one pass in the steady state: two passes run from the warm set, the second one's loads counted;
    each load evicts the residents used furthest ahead, then keeps back any that still fit beside it."""
    resident, loads, run = list(warm), [], seq + seq
    fits = lambda names: F.together(b, [models[r] for r in names]) <= room  # noqa: E731
    for i, name in enumerate(run):
        if any(_same(name, r) for r in resident) or models.get(name, {}).get("need") is None:
            continue

        def next_use(r, i=i):
            return next((j for j in range(i + 1, len(run)) if _same(run[j], r)), len(run) + 1)
        gone = []
        while resident and not fits(resident + [name]):
            gone.append(max(resident, key=next_use))
            resident.remove(gone[-1])
        for r in sorted(gone, key=next_use):
            if fits(resident + [r, name]):
                resident.append(r)
        resident.append(name)
        if i >= len(seq):
            loads.append(name)
    return loads


def pack(host, lanes: list, *, card: Optional[dict] = None, rows: Optional[list] = None,
         declared: Optional[list] = None, state_dir=None) -> dict:
    from halo_harness.local_sched.swap_cost import load_s_for, secs
    name = str(getattr(host, "name", "") or "")
    card = F.card(host) if card is None else card
    rows = F.loaded(host) if rows is None else rows
    helper = F.helper(host, rows)
    b = F.budget(card, name)
    room = F.usable(b, helper)
    models = _models(host, lanes, card)
    main = next((ln["model"] for ln in lanes if ln["lane"] == "main"), None)
    first = [d for d in declared or []]
    rank = lambda m: (next((i for i, d in enumerate(first) if _same(d, m["model"])), len(first)),  # noqa: E731
                      not _same(m["model"], main), -len(m["lanes"]), models.index(m))
    warm, pivots, unknown = [], [], []
    for m in sorted(models, key=rank):
        m["need"] = F.need(b, m["row"], m["window"])
        m["gb"] = float(F.gb(m["need"])) if m["need"] else None
        m["warm_now"] = F.is_loaded(rows, m["model"], m["window"])
        if m["need"] is None or not room:
            m["why"] = m["row_from"] if m["row"] is None else f"no card read for {name}"
            unknown.append(m)
        elif F.together(b, warm + [m]) <= room:
            warm.append(m)
        else:
            alone = F.together(b, [m]) <= room
            m["never"] = not alone
            beside = ", ".join(w["model"] for w in warm)
            m["why"] = (f"does not fit beside {beside} ({F.gb(F.together(b, warm))} + {m['gb']:.1f} of {F.gb(room)} GB)"
                        if alone else f"does not fit the card at {m['window']:,} even alone "
                                      f"({F.gb(F.together(b, [m]))} of {F.gb(room)} GB)")
            pivots.append(m)
    for m in warm + pivots:
        c = load_s_for(host, m["model"], state_dir=state_dir, row=m["row"], fetch=False)
        m["load_s"], m["load_from"] = c["s"], c["source"]
    by_name = {m["model"]: m for m in models}
    seq = sequence(lanes)
    loads = _simulate(seq, [m["model"] for m in warm], by_name, b, room)
    swap_s = sum(float(by_name[x].get("load_s") or 0) for x in loads)
    used = F.together(b, warm)
    out = {"host": name, "budget": int(b.get("budget") or 0), "usable": room, "helper": helper,
           "others": int(b.get("others") or 0), "warm": warm, "pivots": pivots, "unknown": unknown, "used": used,
           "swaps": len(loads), "swap_s": round(swap_s, 1), "loads": loads, "sequence": seq}
    for m in models:
        m.pop("row", None)
    label = lambda m: f"{m['model']} ({', '.join(m['lanes'])})"  # noqa: E731
    if not warm and not pivots:
        out["line"] = f"warm on {name}: not judged ({'; '.join(m['why'] for m in unknown) or 'no local lanes'})"
        return out
    line = f"warm on {name}: {', '.join(label(m) for m in warm) or 'nothing'} -- {F.gb(used)} of {F.gb(room)} GB"
    if helper:
        line += f" (the helper {helper['model']} holds {F.gb(helper['bytes'])} GB)"
    if pivots:
        line += f"; {', '.join(label(m) for m in pivots)} pivot{'s' if len(pivots) == 1 else ''}"
    line += (f"; {len(loads)} swap{'s' * (len(loads) != 1)} a pass, ~{secs(swap_s)} of loading" if loads
             else "; no swaps a pass")
    out["line"] = line
    return out
