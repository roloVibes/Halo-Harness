"""halo_harness.models_library.advise_rules -- the roster adviser's four kinds of suggestion (Halo 3.3.7.0 R4;
plans/local-model-fit-brief.md Part J; models_library/advise.py gathers the inputs and ranks).

    gap(inp) / overlap(inp) / mismatch(inp) / freshness(inp) -> [suggestion]
    Suggestion = {kind, says, unlocks | frees, cost {download_gb, vram_gb, window, beside, minutes}, value, value_per_gb,
                  host, action {verb: add | retire | point | none, what, model?, host?, role?, cli}}

gap: nothing embeds (memory search, dedupe, "find similar"), nothing reads images, a lineup role with no model of its
own; overlap: two or more installed models of one family root, one purpose and one size (within 20 %) -- keep the one
measured best (tools verified, agentic ready, tok/s), retire the others; mismatch: the verifier on the coder's family,
a compactor that pivots on every summary, a lane whose model crashed here twice or more; freshness: a family the
library has a newer line of. `value` is the stated worth (unitless, per kind); value_per_gb divides it by the download
(retire and point cost no download: by 1). Arithmetic and the snapshot only: no request, no model.
"""

from __future__ import annotations

from halo_harness.models_library.advise_lines import cost, facts, options, superseded_by

VERIFY = ("verify", "verifier", "reviewer", "review", "judge", "checker")
WORKER = ("worker", "coder", "implement", "implementer", "builder", "dev")
COMPACT = ("compaction", "compactor", "small", "summarizer")
VALUE = {"embed": 8.0, "vision": 5.0, "role": 6.0, "overlap": 3.0, "family": 6.0, "compactor": 7.0, "crash": 5.0,
         "fresh": 2.0}


def _s(kind, host, says, gain_key, gain, c, value, action) -> dict:
    gb = max(1.0, float(c.get("download_gb") or 0))
    return {"kind": kind, "host": host, "says": says, gain_key: gain, "cost": c, "value": value,
            "value_per_gb": round(value / gb, 2), "action": action}


def _add(o: dict, host: str, role: str = "") -> dict:
    return {"verb": "add", "what": f"download {o['ref']} onto {host}, then verify it (the battery)", "model": o["ref"],
            "host": host, "role": role or None, "cli": f"ollama pull {o['ref']} (Local -> Library: Download and verify)"}


def _rows(inp: dict) -> list:
    return [(h, r, facts(r)) for h in inp.get("hosts") or [] for r in h.get("rows") or [] if isinstance(r, dict)]


def gap(inp: dict) -> list:
    out, rows = [], _rows(inp)
    host = (inp.get("hosts") or [{}])[0]
    name, budget = host.get("name") or "this host", host.get("budget_gb")
    if not any(f["purpose"] == "embed" for _h, _r, f in rows):
        for o in options("embed", budget, n=1):
            out.append(_s("gap", name, "you have no embedding model, so memory search, dedupe and \"find similar\" are "
                          "unavailable", "unlocks", "memory search, dedupe, find similar", cost(o["download_gb"],
                          o["download_gb"], 8192, True), VALUE["embed"], _add(o, name)))
    if not any(f["sees"] or f["purpose"] == "vision" for _h, _r, f in rows):
        for o in options("vision", budget, n=1):
            out.append(_s("gap", name, "nothing here reads images, so a screenshot or a pasted image goes to the cloud or "
                          "to nobody", "unlocks", "the eyes (screenshots, images)", cost(o["download_gb"],
                          o["download_gb"] * 1.1, 8192, None), VALUE["vision"], _add(o, name, "eyes")))
    for g in inp.get("gaps") or []:
        want = "small" if any(c in str(g["role"]) for c in COMPACT) else "chat"  # a small role wants a small model
        o = (options(want, budget, n=1) or [None])[0]
        act = _add(o, name, g["role"]) if o else {"verb": "none", "what": g.get("cli"), "cli": g.get("cli")}
        out.append(_s("gap", name, g["why"], "unlocks", f"a model of its own for `{g['role']}`",
                      cost(o["download_gb"] if o else 0, (o or {}).get("download_gb"), None, None), VALUE["role"], act))
    return out


def _named(f: dict, lanes: list) -> list:
    from halo_harness.providers.ollama import ollama_names_match
    return [ln["lane"] for ln in lanes or [] if ollama_names_match(ln.get("model"), f["name"])]


def _best(group: list, profiles: list, lanes: list) -> tuple:
    from halo_harness.providers.ollama import ollama_names_match

    def score(item):
        _h, r, f = item
        p = next((p for p in profiles if ollama_names_match(p.get("model"), f["name"])), {}) or {}
        return (p.get("tools") == "yes", bool(p.get("agentic_ready")), float((p.get("speed") or {}).get("tok_s") or 0),
                bool(_named(f, lanes)), f["version"], f["name"])
    return max(group, key=score)


def overlap(inp: dict) -> list:
    groups: dict = {}
    for item in _rows(inp):
        h, _r, f = item
        if f["purpose"] == "embed" or not f["params_b"]:
            continue
        key = (h["name"], f["stem"], f["purpose"])
        groups.setdefault(key, []).append(item)
    out = []
    for (host, stem, purpose), items in groups.items():
        for i, seed in enumerate(items):
            same = [x for x in items if abs(x[2]["params_b"] - seed[2]["params_b"]) <= 0.2 * seed[2]["params_b"]]
            if len(same) < 2 or same[0] is not seed:
                continue
            lanes = inp.get("lanes") or []
            keep = _best(same, inp.get("profiles") or [], lanes)
            used = [x for x in same if x is not keep and _named(x[2], lanes)]
            gone = [x for x in same if x is not keep and not _named(x[2], lanes)]
            if not gone:
                continue
            frees = round(sum(x[2]["size_gb"] or 0 for x in gone), 1)
            names = ", ".join(x[2]["name"] for x in same)
            kept = "".join(f"; {x[2]['name']} stays while {', '.join(_named(x[2], lanes))} "
                           f"name{'s' * (len(_named(x[2], lanes)) == 1)} it" for x in used)
            out.append(_s("overlap", host, f"{len(same)} {stem} models of about {seed[2]['params_b']:g}B ({names}) cover "
                          f"the same ground ({purpose}); keep {keep[2]['name']} (measured best here){kept}", "frees",
                          f"{frees:g} GB of disk by retiring {', '.join(x[2]['name'] for x in gone)}",
                          cost(0, None, None, None), VALUE["overlap"] + len(gone),
                          {"verb": "retire", "what": f"retire {gone[0][2]['name']} from {host} (the shelf keeps its "
                           "re-pull line)", "model": gone[0][2]["name"], "host": host,
                           "cli": f"halo models retire {gone[0][2]['name']} --host {host}"}))
    return out


def _lane(lanes: list, names: tuple):
    return next((ln for ln in lanes if any(n in str(ln.get("lane") or "").lower() for n in names)), None)


def mismatch(inp: dict) -> list:
    from halo_harness.models_library.advise_lines import lineage
    out, lanes = [], inp.get("lanes") or []
    v, w = _lane(lanes, VERIFY), _lane(lanes, WORKER)
    root = lambda m: (lineage(m) or (str(m).split(":")[0],))[0]  # noqa: E731
    if v and w and root(v["model"]) == root(w["model"]):
        other = [f for _h, _r, f in _rows(inp) if f["stem"] != root(v["model"]) and f["purpose"] in ("chat", "code")]
        host = v.get("host") or "this host"
        if other:
            to = f"ol:{other[0]['name']}@{host}"
            act = {"verb": "point", "what": f"point `{v['lane']}` at {to}", "role": v["lane"], "model": to, "host": host,
                   "cli": f"halo roles point {v['lane']} {to}"}
            c = cost(0, other[0]["size_gb"], None, None)
        else:
            o = (options("chat", (inp.get("hosts") or [{}])[0].get("budget_gb"), n=1, avoid_family=root(v["model"]))
                 or [None])[0]
            act = _add(o, host, v["lane"]) if o else {"verb": "none", "what": "", "cli": ""}
            c = cost(o["download_gb"] if o else 0, (o or {}).get("download_gb"), None, None)
        out.append(_s("mismatch", host, f"your verifier ({v['lane']}: {v['model']}) is the same family as your coder "
                      f"({w['lane']}: {w['model']}), so their blind spots overlap", "unlocks",
                      "a second family checking the first", c, VALUE["family"], act))
    pv = inp.get("preview") or {}
    for ws in pv.get("hosts") or []:
        for m in ws.get("pivots") or []:
            lane = next((x for x in m.get("lanes") or [] if any(c in x for c in COMPACT)), None)
            if not lane:
                continue
            o = (options("small", ws.get("budget") and ws["budget"] / 1e9, n=1) or [None])[0]
            act = _add(o, ws["host"], lane) if o else {"verb": "none", "what": "", "cli": ""}
            out.append(_s("mismatch", ws["host"], f"every summary costs a {m.get('gb') or '?'} GB pivot ({lane} on "
                          f"{m['model']} does not fit beside main) because there is no compactor that co-resides",
                          "unlocks", "summaries with no swap", cost((o or {}).get("download_gb") or 0,
                          (o or {}).get("download_gb"), 8192, True), VALUE["compactor"], act))
    for fp in inp.get("crashes") or []:
        ln = next((x for x in lanes if x["model"] == fp.get("model")), None)
        if ln and int(fp.get("count") or 1) >= 2:
            out.append(_s("mismatch", fp.get("host") or "", f"`{ln['lane']}` runs {fp['model']}, which crashed here "
                          f"{fp.get('count')}x ({fp.get('signature')} at {fp.get('window_used') or '?'})", "unlocks",
                          "a lane that does not crash", cost(0, None, fp.get("window_used"), None), VALUE["crash"],
                          {"verb": "none", "what": "see the fix", "cli": "halo ollama crashes --why"}))
    return out


def freshness(inp: dict) -> list:
    out = []
    from halo_harness.models_library.advise_lines import lineage
    have = [lineage(f["name"]) for _h, _r, f in _rows(inp)]
    for h, r, f in _rows(inp):
        new = superseded_by(f["name"])
        top = lineage(new["name"]) if new else None
        if not new or any(x and top and x[0] == top[0] and x[2] == top[2] and x[1] >= top[1] for x in have):
            continue  # the newer line is installed already: the overlap rule says what to retire
        from halo_harness.models_library.advise_lines import option_for
        o = option_for(new["name"], f["params_b"], h.get("budget_gb"))
        act = _add(o, h["name"]) if o else {"verb": "none", "what": f"the library's {new['name']}",
                                            "cli": f"halo models browse {new['name']}"}
        out.append(_s("freshness", h["name"], f"{f['name']}'s family has a newer line in the library: {new['name']}"
                      + (f" (updated {new['updated']})" if new.get("updated") else "") + "; when the two measure the same, "
                      "prefer the newer", "unlocks", f"the newer {new['name']}", cost((o or {}).get("download_gb") or 0,
                      (o or {}).get("download_gb"), None, None), VALUE["fresh"], act))
    return out
