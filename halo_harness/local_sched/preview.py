"""halo_harness.local_sched.preview -- a map's swap preview and its hygiene lines (Halo 3.3.7.0 R3;
plans/local-model-fit-brief.md D1 3 and 8; 3.6.0.0 R5b: the map in use, where it was a lineup).

    lanes_for(name=None, *, main_ref=None, cwd=None, state_dir=None) -> (lanes, declared, name)
        `name`: a map (None: the map in use, crew/in_use.py); main is the session's model (config `model`) unless given
    preview(name=None, *, main_ref=None, cwd=None, state_dir=None, lanes=None) -> Preview   (lanes: the caller's)
    Preview = {lineup, hosts [WarmSet], swaps, swap_s, cards, declared [model], lines [str], hygiene [str]}

The lines: one warm-set line per card (local_sched/warm_set.pack), then the total -- "this map swaps 7x on one
card ~ 3 m 02 s of loading a pass" or "its local models co-reside: 0 swaps a pass". The hygiene lines: a verify
lane and a worker lane on one card (share weights: "0 swaps between them"; different weights: each hand-off a
swap, unless both stay warm), a lane that never fits beside main, a lane that could not be judged (no catalog
row, no card read), and a `warm:` list that cannot co-reside. Arithmetic only: nothing loads.
"""

from __future__ import annotations

from typing import Optional

VERIFY = ("verify", "verifier", "reviewer", "review", "judge", "checker", "tester")
WORKER = ("worker", "coder", "implement", "implementer", "builder", "dev", "developer")


def warm_problems(data) -> list:
    """A 1.x lineup file's `warm:` list's shape (teams_yaml.validate_team_template, while that validator stays)."""
    raw = (data or {}).get("warm") if isinstance(data, dict) else None
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(isinstance(x, str) and x.strip() for x in raw):
        return ['"warm" must be a list of lane names or model references (the models that stay loaded together)']
    return []


def declared_models(raw, lanes: list) -> list:
    """A `warm:` entry names a lane ("coder") or a model (`qwen3-coder:30b`, `ol:qwen3-coder:30b@pc`)."""
    from halo_harness.local_sched.facts import split_ref
    out = []
    for item in raw if isinstance(raw, list) else []:
        s = str(item or "").strip()
        hit = next((ln["model"] for ln in lanes if ln["lane"] == s), None)
        out.append(hit or split_ref(s)[0])
    return [m for m in out if m]


def lanes_for(name=None, *, main_ref: Optional[str] = None, cwd=None, state_dir=None) -> "tuple[list, list, str]":
    """The local lanes of the map `name` (None: the one in use): main and each agent on an `ol:` model. A map declares
    no `warm:` list, so `declared` is empty."""
    from halo_harness.crew.in_use import lanes, map_name
    name = name or map_name(cwd)
    if not name:
        return [], [], ""
    return lanes(name, main_ref=main_ref, cwd=cwd, state_dir=state_dir), [], str(name)


def _kind(lane: str, words) -> bool:
    lane = lane.lower()
    return any(w in lane for w in words)


def _hygiene(ws: dict, lanes: list) -> list:
    from halo_harness.local_sched.swap_cost import secs
    out: list = []
    host = ws["host"]
    models = ws["warm"] + ws["pivots"] + ws["unknown"]
    of = lambda lane: next((m for m in models if lane in m["lanes"]), None)  # noqa: E731
    warm = {m["model"] for m in ws["warm"]}
    for v in [ln for ln in lanes if _kind(ln["lane"], VERIFY)]:
        for w in [ln for ln in lanes if _kind(ln["lane"], WORKER) and ln["lane"] != v["lane"]]:
            a, b = of(v["lane"]), of(w["lane"])
            if not a or not b:
                continue
            if a is b:
                out.append(f"{v['lane']} and {w['lane']} share weights ({a['model']}): 0 swaps between them")
            elif a["model"] in warm and b["model"] in warm:
                out.append(f"{v['lane']} ({a['model']}) and {w['lane']} ({b['model']}) run on different weights, both "
                           f"warm on {host}: no swap between them")
            else:
                cost = max(float(a.get("load_s") or 0), float(b.get("load_s") or 0))
                out.append(f"{v['lane']} ({a['model']}) and {w['lane']} ({b['model']}) run on different weights that do "
                           f"not co-reside on {host}: each hand-off between them is a swap"
                           + (f" (~{secs(cost)})" if cost else "") + "; one model for both lanes makes it 0")
    main = of("main")
    if main is not None and main["model"] in warm:
        for m in ws["pivots"]:
            lanes_ = [x for x in m["lanes"] if x != "main"]
            if lanes_:
                out.append(f"{', '.join(lanes_)} ({m['model']}) never fits beside main ({main['model']}) on {host}: "
                           f"{m['why']}; every hand-off to it is a pivot"
                           + (f" (~{secs(m['load_s'])})" if m.get("load_s") else ""))
    for m in ws["unknown"]:
        gone = "was deleted from" in str(m["why"])  # 3.3.7.0 R4: the dead-tag line (ollama_steward/dead_tag.py)
        out.append(f"{', '.join(m['lanes'])} ({m['model']}) on {host}: " + (m["why"] if gone else f"not judged -- {m['why']}"))
    return out


def _vram_aware(ws: dict, group: list) -> "tuple[list, str]":
    """roles.vram_aware_override's four (small, researcher, judge, subagent_default) run on main's model when theirs
    does not fit beside it: (the lanes as they run, the line) -- unchanged and "" when none is moved."""
    from halo_harness.roles import VRAM_AWARE_ROLE_NAMES
    main = next((ln["model"] for ln in group if ln["lane"] == "main"), None)
    moved = [m for m in ws["pivots"] if main and m["lanes"] and all(x in VRAM_AWARE_ROLE_NAMES for x in m["lanes"])]
    if not moved:
        return group, ""
    lanes = {x for m in moved for x in m["lanes"]}
    out = [dict(ln, model=main) if ln["lane"] in lanes else ln for ln in group]
    return out, (f"{', '.join(sorted(lanes))} ({', '.join(m['model'] for m in moved)}) do not fit beside main ({main}) "
                 f"on {ws['host']}: they run on main's model instead (the VRAM-aware rule), no swap")


def preview(lineup=None, *, main_ref: Optional[str] = None, cwd=None, state_dir=None, lanes=None) -> dict:
    from halo_harness.local_sched.facts import host_named
    from halo_harness.local_sched.swap_cost import secs
    from halo_harness.local_sched.warm_set import by_host, pack
    from halo_harness.providers.ollama import ollama_names_match
    if lanes is None:
        lanes, declared, name = lanes_for(lineup, main_ref=main_ref, cwd=cwd, state_dir=state_dir)
    else:  # 3.6.0.0 R5c: the caller's lanes (the adviser's: a plain session's roles too)
        declared, name = [], str(lineup or "")
    out = {"lineup": name, "hosts": [], "swaps": 0, "swap_s": 0.0, "cards": 0, "declared": declared, "lines": [],
           "hygiene": [], "lanes": lanes}
    if not lanes:
        out["lines"] = [f"{name}: no local lanes (no `ol:` models): nothing to schedule"]
        return out
    for host_name, group in by_host(lanes).items():
        host = host_named(host_name)
        if host is None:
            out["hygiene"].append(f"{', '.join(ln['lane'] for ln in group)}: no Ollama host named {host_name!r} here")
            continue
        mine = [d for d in declared if any(ollama_names_match(d, ln["model"]) for ln in group)]
        ws = pack(host, group, declared=mine, state_dir=state_dir)
        group, said = _vram_aware(ws, group)
        if said:  # the four roles the VRAM-aware rule redirects run on main's model: packed again as they run
            ws = pack(host, group, declared=mine, state_dir=state_dir)
            out["hygiene"].append(said)
        out["hosts"].append(ws)
        out["lines"].append(ws["line"])
        out["hygiene"] += _hygiene(ws, group)
        left = [d for d in mine if not any(ollama_names_match(d, w["model"]) for w in ws["warm"])]
        if left and ws["warm"] + ws["pivots"]:
            why = next((p["why"] for p in ws["pivots"] if any(ollama_names_match(d, p["model"]) for d in left)), "")
            out["hygiene"].append(f"warm: declares {', '.join(mine)}; they cannot co-reside on {host_name}: "
                                  f"{', '.join(left)} {why or 'is not judged'}")
    out["swaps"] = sum(ws["swaps"] for ws in out["hosts"])
    out["swap_s"] = round(sum(ws["swap_s"] for ws in out["hosts"]), 1)
    out["cards"] = len([ws for ws in out["hosts"] if ws["swaps"]])
    judged = [ws for ws in out["hosts"] if ws["warm"] or ws["pivots"]]
    if out["swaps"]:
        where = "one card" if out["cards"] == 1 else f"{out['cards']} cards"
        out["lines"].append(f"this map swaps {out['swaps']}x on {where} ~ {secs(out['swap_s'])} of loading a pass")
    elif judged:
        out["lines"].append("this map's local models co-reside: 0 swaps a pass")
    return out
