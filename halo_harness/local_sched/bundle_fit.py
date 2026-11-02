"""halo_harness.local_sched.bundle_fit -- the honest verdict on a bundle, before anything downloads (Halo 3.3.7.0 R5;
plans/local-model-fit-brief.md L3).

    verdict(bundle, host=None, *, state_dir=None, reads_=None) -> Verdict
    Verdict = {bundle, host, state (ready | downloads | wont | unknown), says, needs [{role, tag, gb, fits, minutes,
               download_gb, installed, runtime, placed, why}], downloads [need], button {label, tags, host} | None,
               options [{says, frees_gb, kind}], latency_ms, reserved {model, gb, window} | None, usable_gb, claimed_gb,
               free_gb, total_gb, coder {model, gb, beside, spare_gb} | None, via (host | local)}

Deterministic and model-free: weights + KV at each need's window + the per-card reserve, against the usable memory
(the card's budget minus other programs and the duty steward's helper -- a paired halo host's `route` when one serves
the card) minus the other bundles' reservations. ready: everything is here and it fits, with the expected latency;
downloads: the exact tags, each with its size, its fit and the minutes, and one button that starts the existing
download + verify job; wont: what it needs against what there is, and the ways out, each a number
(local_sched/bundle_options.py). A card that was not read is `unknown` -- nothing is guessed.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.local_sched import bundle_needs as N
from halo_harness.packs.manifest_bundle import reserved_model

GIB = 2 ** 30
BARELY_GB = 2.0


def _g(n) -> float:
    """GB, unrounded: the arithmetic keeps every byte; a line rounds to one decimal when it says the number."""
    return (n or 0) / GIB


def _host(host):
    from halo_harness.local_sched.facts import host_named
    return host if host is not None and not isinstance(host, str) else host_named(host)


def _reserved(b: dict, picks: dict, rd) -> Optional[dict]:
    res = b.get("reservation")
    if not res:
        return None
    model = reserved_model(b, {r: p["model"] for r, p in picks.items() if p.get("model")})
    pick = picks.get(res.get("role") or "") or {}
    window = res.get("window") or pick.get("window") or N.DEFAULT_WINDOW
    if isinstance(res.get("vram_gb"), (int, float)):
        gb, src = float(res["vram_gb"]), "declared"
    else:
        got = rd.need(model, window) if model else {"bytes": None}
        gb, src = (_g(got["bytes"]), "computed") if got.get("bytes") else (None, "not known")
    return {"model": model, "gb": gb, "window": window, "from": src, "role": res.get("role"),
            "keep_alive": res.get("keep_alive"), "priority": res.get("priority")}


def _latency(model: Optional[str], host_name: str, state_dir) -> "tuple[Optional[int], str]":
    if not model:
        return None, ""
    from halo_harness.providers.local_bench_runs import load
    from halo_harness.providers.placement import profile_for_ref
    card = load(state_dir, host_name, model) if state_dir is not None else None
    rows = [r for r in (card or {}).get("windows") or [] if isinstance(r.get("ttft_ms"), (int, float))]
    speed = rows[0] if rows else ((profile_for_ref(f"ol:{model}@{host_name}", state_dir) or {}).get("speed") or {})
    ttft, tok_s = speed.get("ttft_ms"), speed.get("tok_s")
    if not isinstance(ttft, (int, float)) or not isinstance(tok_s, (int, float)) or tok_s <= 0:
        return None, f"latency not measured yet (no speed card for {model} on {host_name}: halo local bench {model})"
    ms = int(round(ttft + 24 / tok_s * 1000))
    from halo_harness.providers.local_bench_link import tail  # 3.3.8.1: a LAN-measured card or speed row says so
    lan = tail(card if rows else speed)
    return ms, (f"expected latency ~{ms} ms (first token {int(ttft)} ms + a 24-token sentence at {tok_s:g} tok/s"
                + (f"; {lan}: includes the link)" if lan else ")"))


def _cloud_words(b: dict) -> str:
    from halo_harness.local_sched.reserve import cloud_target
    to = cloud_target()
    return to or "a cloud model (routing.escalation.to names it)"


def verdict(bundle: dict, host=None, *, state_dir=None, reads_=None) -> dict:
    """3.3.8.0 R4: every reservation where it is held (local_sched/bundle_parts.verdict; one on the default host and no
    schedule is verdict_one's answer with `parts` [] beside it)."""
    from halo_harness.local_sched.bundle_parts import verdict as across
    return across(bundle, host, state_dir=state_dir, reads_=reads_)


def verdict_one(bundle: dict, host=None, *, state_dir=None, reads_=None) -> dict:
    from halo_harness.local_sched import bundle_options as O
    from halo_harness.local_sched.reserve import free_after_claims
    h = _host(host)
    name = str(getattr(h, "name", host) or "")
    rd = reads_ or N.reads(h, state_dir)
    coder = N.coder_of(h, state_dir) if h is not None and bundle["routing"]["task_work"] in ("coder", "coder-or-cloud") \
        else None
    picks = N.pick(bundle, rd, coder=coder, state_dir=state_dir)
    res = _reserved(bundle, picks, rd)
    if coder is not None:
        got = rd.need(coder["model"], coder["window"])
        coder["gb"] = _g(got["bytes"]) if got.get("bytes") else None
    out = {"bundle": bundle["id"], "name": bundle.get("name"), "host": name, "via": rd.via, "needs": [], "downloads": [],
           "options": [], "button": None, "latency_ms": None, "reserved": res, "coder": None}
    if h is None or not rd.usable:
        out.update(state="unknown", says=f"not judged: no card read for {name or 'this machine'} (nothing is guessed)")
        return out
    if res is not None and res.get("gb") is None:
        out.update(state="unknown", says=f"not judged: the size of {res['model']} is not known here (neither installed on "
                                         f"{name} nor in the library snapshot); give reservation.vram_gb")
        return out
    if res is not None and res.get("role") in picks and picks[res["role"]].get("gb") is None:
        picks[res["role"]]["gb"] = res["gb"]  # the declared vram_gb stands for a model this host cannot size
    unsized = [p for p in picks.values() if p["placed"] == "gpu" and p.get("model") and p.get("gb") is None]
    if unsized:
        out.update(state="unknown", says="not judged: the size of " + ", ".join(p["model"] for p in unsized) +
                   f" is not known here (neither installed on {name} nor in the library snapshot)")
        return out
    fac = free_after_claims(h, rd.usable, exclude=bundle["id"], state_dir=state_dir)
    gpu = [p for p in picks.values() if p["placed"] == "gpu" and p.get("model")]
    res_gb = (res or {}).get("gb") or 0.0
    total = res_gb + sum(float(p.get("gb") or 0) for p in gpu if p["role"] != (res or {}).get("role")) + _g(rd.reserve)
    free = _g(fac["free"])
    pe, floor = _preempt(bundle, res, fac, total, free, name)  # 3.3.8.0 R4: a lower claim gives way; the floor
    free += sum(float(c.get("gb") or 0) for c in pe["take"])
    out.update(usable_gb=round(_g(rd.usable), 1), claimed_gb=round(_g(fac["claimed"]), 1), free_gb=round(free, 1),
               total_gb=round(total, 1), claims_line=fac["line"], preempts=pe["rows"], min_free_gb=floor or None)
    for p in picks.values():
        fits = None if p.get("gb") is None else (p["placed"] == "cpu" or float(p["gb"]) + _g(rd.reserve) <= free)
        row = {"role": p["role"], "tag": p.get("model"), "gb": None if p.get("gb") is None else round(p["gb"], 1), "fits": fits, "minutes": p.get("minutes") or 0,
               "download_gb": p.get("download_gb"), "installed": p.get("installed"), "runtime": p["runtime"],
               "placed": p["placed"], "why": p.get("why", "")}
        out["needs"].append(row)
        if p["runtime"] == "ollama" and p.get("model") and p.get("installed") is False:
            out["downloads"].append(row)
    left = free - res_gb
    if coder and any(p.get("model") and _same(p["model"], coder["model"]) for p in picks.values()):
        coder = None  # the bundle's own need is the coder (coder-first): no "beside it" line
    spare = free - total - (coder or {}).get("gb", 0) if coder and coder.get("gb") else None
    beside = spare is not None and spare >= 0
    if coder:
        out["coder"] = {"model": coder["model"], "gb": round(coder["gb"], 1) if coder.get("gb") else None, "beside": beside,
                        "spare_gb": None if spare is None else round(spare, 1),
                        "window": coder["window"]}
    fits_alone = total + floor <= free and all(p.get("model") for p in picks.values())
    strict = bundle["routing"]["task_work"] == "coder"
    out["latency_ms"], lat = _latency((res or {}).get("model") or next((p["model"] for p in gpu), None), name, state_dir)
    if lat and bundle.get("latency_budget_ms") and out["latency_ms"]:
        lat += f" ({'within' if out['latency_ms'] <= bundle['latency_budget_ms'] else 'over'} the " \
               f"{bundle['latency_budget_ms']} ms budget)"
    head = _fit_line(bundle, res, left, coder, beside, spare, total, free, fac)
    voice = [p for p in picks.values() if p["runtime"] == "voice"]
    tail = ""
    if voice:
        cpu = [p for p in voice if p["placed"] == "cpu"]
        names = " and ".join("%s (%s)" % (p["role"], p["model"]) for p in cpu)
        tail = (f"; {names} on the CPU: no VRAM" if cpu else "") + " (the speech models arrive with Voice, 3.3.8.0)"
    if not fits_alone or (strict and coder and not beside):
        missing = [f"{r}: {p['why']}" for r, p in picks.items() if not p.get("model")]
        out["state"] = "wont"
        out["says"] = ("won't work -- " + ("; ".join(missing) if missing else
                       f"this bundle needs {total + (coder or {}).get('gb', 0) * strict:.1f} GB; you have "
                       f"{free:.1f} GB usable" + (f" ({fac['line']})" if fac['claims'] else "")
                       + (f"; it keeps {floor:g} GB free for tasks (min_free_gb)" if floor else "")
                       + (f"; {pe['held']}" if pe["held"] else "")))
    elif out["downloads"]:
        dl = out["downloads"]
        gbs = round(sum(float(d["download_gb"] or 0) for d in dl), 1)
        mins = sum(int(d["minutes"] or 0) for d in dl)
        out["state"] = "downloads"
        unknown = sum(1 for d in dl if not d["download_gb"])
        size = "size not known yet" if not gbs else \
            f"{gbs:g} GB, ~{mins} min" + (f" + {unknown} of a size not known yet" if unknown else "")
        each = ", ".join(f"{d['tag']} (" + (f"{d['download_gb']:g} GB" if d["download_gb"] else "size not known: not in "
                                            "the library snapshot") + f", {'fits' if d['fits'] else 'fit not known'})"
                         for d in dl)
        out["says"] = f"needs {len(dl)} download{'s' * (len(dl) != 1)} ({size}): {each}; then {head}"
        out["button"] = {"label": f"download {len(dl)} ({size})", "tags": [d["tag"] for d in dl],
                         "host": name}
    else:
        out["state"] = "ready"
        out["says"] = head + (f"; {lat}" if lat else "")
    if pe["rows"] and out["state"] != "wont":
        out["says"] += "; " + "; ".join(f"pre-empts {c['bundle']} ({c['priority']}, {c['gb']:.1f} GB) on {c['host']}"
                                        for c in pe["rows"])
    out["says"] += tail
    out["options"] = O.options(bundle, picks, res, coder, total=total, free=free, reserve_gb=_g(rd.reserve), rd=rd)
    return out


def _preempt(bundle: dict, res, fac: dict, total: float, free: float, host: str) -> "tuple[dict, float]":
    """({rows, take, held}, the min_free_gb floor): the lower claims this bundle's priority takes when it does not fit
    beside them (local_sched/preempt.py); nothing is taken here -- `halo pack on` does it, said."""
    from halo_harness.local_sched import preempt as PE
    prio = (res or {}).get("priority") or bundle.get("priority") or "normal"
    floor = float((res or {}).get("min_free_gb") or bundle.get("min_free_gb") or 0.0)
    if total + floor <= free:
        return {"rows": [], "take": [], "held": ""}, floor
    got = PE.plan(fac["claims"], need_gb=total + floor, free_gb=free, priority=prio, bundle=bundle["id"])
    rows = [{"bundle": c.get("bundle"), "host": c.get("host") or host, "gb": float(c.get("gb") or 0),
             "priority": c.get("priority") or "normal", "via": c.get("via")} for c in got["take"]]
    return {"rows": rows, "take": got["take"], "held": "" if got["ok"] else PE.held_line(bundle["id"], prio,
                                                                                         got["held_by"])}, floor


def _same(a, b) -> bool:
    from halo_harness.providers.ollama import ollama_names_match
    return ollama_names_match(a, b)


def _fit_line(b, res, left, coder, beside, spare, total, free, fac) -> str:
    if res:
        head = f"fits today -- {res['gb']:.1f} GB reserved leaves ~{left:.1f} GB"
    elif not b.get("needs"):
        return "ready -- it needs no model and reserves nothing"
    else:
        head = f"fits today -- nothing reserved ({total:.1f} of {free:.1f} GB when it runs)"
    if coder and coder.get("gb") is not None and not res:
        head += (f", beside the coder ({coder['gb']:.1f} GB)" if beside else
                 f"; asking it while the coder ({coder['gb']:.1f} GB) is loaded pivots the coder out (nothing is reserved)")
    elif coder and coder.get("gb") is not None:
        if beside:
            head += f", the coder ({coder['gb']:.1f} GB) still fits beside it" + (", barely" if spare < BARELY_GB else "")
        elif b["routing"]["task_work"] == "coder-or-cloud":
            head += (f", the coder ({coder['gb']:.1f} GB) does not fit beside it: task work goes to {_cloud_words(b)} "
                     "while it is on")
        else:
            head += f", the coder ({coder['gb']:.1f} GB) does not fit beside it"
    return head
