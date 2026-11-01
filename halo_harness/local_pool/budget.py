"""halo_harness.local_pool.budget -- each member's free VRAM and the tensor split (Halo 3.3.8.0 R1; docs/POOL.md "Free
VRAM").

    budget(member, *, state_dir=None, home=None) -> Row
        Row = {name, host, rpc_port, kind (paired | local | address), addr, gpu, total_gb, usable_gb, resident_gb,
               resident [model], helper_gb, claims_gb, free_gb, vram_source (card | stated | unknown), source, link,
               link_word, line}
        a paired host: its card through host_client (`usable_with_helper_gb`, the models resident in its /api/ps,
        `GET residency`'s claims); this machine: the local reads (local_sched/facts, local_sched/reserve); a bare
        address: no card, so the VRAM you stated with `--vram` (vram_source "stated") or unknown
        free = usable with the helper - resident models - claims (a claimed model already resident counts once)
    budgets(members=None, *, state_dir=None, home=None) -> [Row]        the RTT of the last scan merged in
    tensor_split(rows) -> [w]      proportional to FREE VRAM (rounded to 4 places, summing to 1); the weights you set
                                   when every counted member has one
    split_from(rows) -> "free VRAM" | "the weights you set"

A host card says what the GPU holds now: its total, what other programs hold, the models resident and the duty
steward's helper. It cannot say what a process that starts after the read will take, nor what a worker with no
`halo host` (and no `nvidia-smi` read) has: that member's VRAM is the number you state. Reads only.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.local_pool import link as L
from halo_harness.local_pool.members import load, resolve

GIB = 2 ** 30


def _gb(n) -> float:
    return round(float(n or 0) / GIB, 1)


def _row(member: dict, how: dict) -> dict:
    return {"name": member["name"], "host": member["host"], "rpc_port": member["rpc_port"], "kind": how["kind"],
            "addr": how["addr"], "weight": member.get("weight"), "gpu": "", "total_gb": None, "usable_gb": None,
            "resident_gb": 0.0, "resident": [], "helper_gb": 0.0, "claims_gb": 0.0, "free_gb": None,
            "vram_source": "unknown", "source": "", "link": dict(L.UNKNOWN), "link_word": "unknown"}


def _from_card(out: dict, card: dict, usable_b: int, helper: Optional[dict], claims: list) -> None:
    gpus = [g for g in (card or {}).get("gpus") or [] if isinstance(g, dict)]
    if not gpus:
        return
    unified = bool(card.get("unified"))
    total = sum(int(g.get("available_bytes" if unified else "total_bytes") or g.get("total_bytes") or 0) for g in gpus)
    from halo_harness.providers.ollama import ollama_names_match
    hmodel = (helper or {}).get("model")
    resident = [m for m in card.get("loaded") or [] if isinstance(m, dict) and m.get("model")
                and not (hmodel and ollama_names_match(m["model"], hmodel))]
    held = sum(int(m.get("size_vram") or m.get("size") or 0) for m in resident)
    claimed = sum(float(c.get("gb") or 0) for c in claims if not any(ollama_names_match(m["model"], c.get("model") or "")
                                                                     for m in resident if c.get("model")))
    out.update(gpu=" + ".join(str(g.get("name") or "a GPU") for g in gpus), total_gb=_gb(total), usable_gb=_gb(usable_b),
               resident_gb=_gb(held), resident=[m["model"] for m in resident], helper_gb=float((helper or {}).get("gb") or 0),
               claims_gb=round(claimed, 1), vram_source="card",
               free_gb=round(max(0.0, usable_b / GIB - held / GIB - claimed), 1))


def _paired(out: dict, entry: dict, home=None) -> None:
    from halo_harness.fleet import identity, store
    from halo_harness.ollama_steward.host_client import HostClient, HostError
    key = store.key_for(entry, home)
    if key is None:
        out["source"] = f"the paired host {out['host']} has no pair key here (halo host join again)"
        return
    c = HostClient(entry, key, identity.harness()["id"])
    try:
        got = c.card()
    except HostError as e:
        out["source"] = str(e)
        return
    rows = [r for r in got.get("hosts") or [] if isinstance(r, dict)]
    r = next((x for x in rows if (x.get("card") or {}).get("gpus")), rows[0] if rows else {})
    try:
        claims = [x for x in c.get("residency").get("claims") or [] if isinstance(x, dict)
                  and str(x.get("host") or "").lower() == str(r.get("name") or "").lower()]
    except HostError:
        claims = []
    usable = r.get("usable_with_helper_gb")
    _from_card(out, r.get("card") or {}, int(float(usable) * GIB) if isinstance(usable, (int, float)) else 0,
               r.get("helper"), claims)
    out["link"] = dict(got.get("link") or L.UNKNOWN)
    out["source"] = f"the card of halo host {out['host']} at {c.addr}" + (f" ({r.get('name')})" if r.get("name") else "")


def _local(out: dict, state_dir=None) -> None:
    from halo_harness.local_sched import facts as F
    from halo_harness.local_sched.reserve import claims as claims_of
    host = F.host_named(None)
    card = F.card(host)
    loaded = F.loaded(host) if card.get("gpus") else []
    helper = F.helper(host, loaded)
    usable = F.usable(F.budget(card, getattr(host, "name", "")), helper)
    card = {**card, "loaded": loaded or card.get("loaded") or []}
    h = {"model": helper["model"], "gb": _gb(helper["bytes"])} if helper else None
    _from_card(out, card, usable, h, claims_of(host, state_dir=state_dir) if host is not None else [])
    out["link"] = L.read()
    out["source"] = f"this machine's card ({getattr(host, 'name', 'local')})" if card.get("gpus") else \
        "this machine's card was not read (no GPU listed)"


def budget(member: dict, *, state_dir=None, home=None) -> dict:
    how = resolve(member, home)
    out = _row(member, how)
    try:
        if how["kind"] == "paired":
            _paired(out, how["entry"], home)
        elif how["kind"] == "local":
            _local(out, state_dir)
        else:
            out["source"] = f"no halo host serves {member['host']}: its card is not read"
    except Exception as e:  # one member's read never takes the page down
        out["source"] = f"not read ({type(e).__name__}: {str(e)[:120]})"
    stated = member.get("vram_gb")
    if out["vram_source"] != "card" and isinstance(stated, (int, float)) and stated > 0:
        out.update(total_gb=float(stated), usable_gb=float(stated), free_gb=float(stated), vram_source="stated",
                   source=f"VRAM as you stated it ({stated:g} GB); {out['source']}")
    elif out["vram_source"] == "card" and isinstance(stated, (int, float)):
        out["source"] += f"; the card's reading wins over the {stated:g} GB you stated"
    out["link_word"] = L.word(out["link"])
    out["line"] = line(out)
    return out


def line(r: dict) -> str:
    head = f"{r['name']} ({r['host']}:{r['rpc_port']})"
    if r["free_gb"] is None:
        return f"{head}: VRAM not read -- {r['source']} (add --vram <GB> to state it)"
    if r["vram_source"] == "stated":
        return f"{head}: {r['free_gb']:.1f} GB free -- VRAM as you stated it; link {r['link_word']}"
    held = f", {r['resident_gb']:.1f} GB resident ({', '.join(r['resident'])})" if r["resident"] else ""
    claim = f", {r['claims_gb']:.1f} GB claimed" if r["claims_gb"] else ""
    helper = f" ({r['helper_gb']:.1f} GB helper out)" if r["helper_gb"] else ""
    return (f"{head}: {r['gpu']} {r['total_gb']:.1f} GB -- {r['usable_gb']:.1f} GB usable{helper}{held}{claim}, "
            f"{r['free_gb']:.1f} GB free; link {r['link_word']}")


def budgets(members: Optional[list] = None, *, state_dir=None, home=None) -> list:
    rows = [budget(m, state_dir=state_dir, home=home) for m in (load(state_dir) if members is None else members)]
    from halo_harness.local_pool.scan import rtt_of
    for r in rows:
        r.update(rtt_of(r, state_dir))
    return rows


def _counted(rows: list) -> list:
    return [r for r in rows if isinstance(r.get("free_gb"), (int, float)) and r["free_gb"] > 0]


def split_from(rows: list) -> str:
    c = _counted(rows)
    return "the weights you set" if c and all(isinstance(r.get("weight"), (int, float)) and r["weight"] > 0 for r in c) \
        else "free VRAM"


def normalize(vals: list) -> list:
    """Shares summing to 1 (4 places; the last one takes the rounding), [] when nothing is above 0."""
    vals = [max(0.0, float(v)) for v in vals]
    total = sum(vals)
    if total <= 0:
        return []
    w = [round(v / total, 4) for v in vals]
    w[-1] = round(1.0 - sum(w[:-1]), 4)
    return w


def tensor_split(rows: list) -> list:
    c = _counted(rows)
    if not c:
        return []
    return normalize([float(r["weight"]) for r in c] if split_from(rows) == "the weights you set"
                     else [float(r["free_gb"]) for r in c])
