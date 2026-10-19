"""halo_harness.orchestra.coach_rules -- the coach's rules, once, for every run
kind (Halo 3.1.2.0 R1 moved the Orchestra rules here; 3.1.3.0 R1 folded the
mission and team rules in). Each rule reads unit facts -- one dict per
unit of work (docs/WORK.md: a lane, a part, a stage) -- and yields
suggestions of the one shared shape (orchestra/coach.py `suggestion`).

A fact carries `unit` (its id), `noun` (lane|part|stage), `title`,
`bio`, `state`, and what its kind has: `returned` {class: times} (and
`return_why` {class: lines}), `denied`, `refused` [{key, held, who?, why?}],
`written` (units written, None when the kind does not count them),
`claims`, `files`, `job`, `after`, `waited_s`, `duration_s`, `asked_s`,
`reply`, and for the model rules `model`, `cost_usd`, `pieces_returned`,
`lines`, `ended`. The thin loaders (coach_<kind>_rules.py) turn their run's
files into these facts and call these functions; docs/ORCHESTRA.md "The
coach" lists the rules by kind with their evidence.
"""

from __future__ import annotations

import re
from statistics import median

from halo_harness.orchestra.coach import apply_to, suggestion
from halo_harness.orchestra.coach_prices import CHEAP_PRICE, TOP_PRICE, best_for, price_of, price_words

COST_FLOOR = 0.05     # $: under it a unit is never "high cost"
SMALL_DIFF = 40       # lines written: a small diff
WAIT_SHARE = 0.5      # of the unit's time spent waiting on one other unit
CLASS_TEXT = {"gate": "the tests failed on the finished branch", "merge": "the merge's resolution failed the tests"}
NOTES = {"gate": "Before you release a unit, run the goal's test command in your worktree and fix every failure "
                 "that names your unit.",
         "merge": "Change only the lines of your claimed unit and keep the code around it as it is, so your "
                  "branch merges cleanly.",
         "restated": "Edit your claimed units with Edit before you reply; a reply that restates the task "
                     "without an edit leaves the lane empty."}


def _at(f: dict) -> str:
    return f"{f['noun']} {f['unit']}"


def _who(f: dict) -> str:
    return f.get("who") or (f"bio `{f['bio']}`" if f.get("bio") else f"{_at(f)}'s worker")


def _bio_raw(bio: str, cwd, state_dir) -> dict:
    try:
        from halo_harness.agents_yaml import resolve_agent_bio
        return resolve_agent_bio(bio, cwd=cwd, state_dir=state_dir) or {}
    except Exception:
        return {}


def _model_apply(f: dict, goal: dict, ref: str):
    if f["bio"]:
        return apply_to("bio", f["bio"], "models.preference", ref)
    return apply_to("lineup", str(goal.get("lineup") or ""), f"roles.{goal.get('worker') or 'subagent'}", ref)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def _note(f: dict, key: str):
    return apply_to("bio", f["bio"], "context.prompt_notes", NOTES[key]) if f.get("bio") and key in NOTES else None


def prompt_rules(units: list, goal: dict, cap=None) -> list:
    out = []
    what = _norm(goal.get("what"))[:80]
    for f in units:
        for cls, k in (f.get("returned") or {}).items():
            if k < 2:
                continue
            why = (f.get("return_why") or {}).get(cls) or [
                f"{_at(f)} ({f['title']}): returned {k} times, each time: {CLASS_TEXT[cls]}",
                (f"return cap {cap}; " if cap else "") + f"the {f['noun']} ended {f.get('state') or '?'}"]
            out.append(suggestion(f"prompt-{f['unit']}-{cls}", "prompt", "medium",
                                  f"tighten {_who(f)}'s prompt: {_at(f)}'s piece came back {k} times because "
                                  f"{CLASS_TEXT[cls]}", why, lane_or_part=f["unit"], bio=f.get("bio", ""),
                                  apply=_note(f, cls)))
        if f.get("written") == 0 and what and what in _norm(f.get("reply")):
            out.append(suggestion(
                f"prompt-{f['unit']}-restated", "prompt", "medium",
                f"tighten {_who(f)}'s prompt: {_at(f)}'s reply restates the goal and wrote no unit",
                [f"{_at(f)}: 0 written units of {len(f.get('claims') or [])} claimed",
                 f"its reply repeats the goal: \"{f['reply'][:120]}\""],
                lane_or_part=f["unit"], bio=f.get("bio", ""), apply=_note(f, "restated")))
    return out


def outputs_rules(missing: list) -> list:
    if not missing:
        return []
    return [suggestion("prompt-missing-outputs", "prompt", "medium",
                       "say in the brief where each output goes: the plan named outputs nobody wrote",
                       [f"missing: {m}" for m in missing])]


def model_rules(units: list, goal: dict, cap: int, cat: list) -> list:
    out = []
    first = [f for f in units if f["pieces_returned"] == 0 and f["state"] in ("merged", "written")]
    for f in units:
        p = price_of(cat, f["model"])
        bad = f["pieces_returned"] >= cap or f["returned"].get("gate", 0) > 0
        if not bad or p is None or p > CHEAP_PRICE:
            continue
        better = [s for s in first if s["model"] and s["model"] != f["model"] and (price_of(cat, s["model"]) or 0) > p]
        if not better:
            continue
        s = min(better, key=lambda s: (float(s["ended"] or 0), s["unit"]))
        hit = f["pieces_returned"] >= cap
        out.append(suggestion(
            f"model-{f['unit']}-stronger", "model", "high" if hit else "medium",
            f"give {_who(f)} the model {_at(s)} used: {s['model']}",
            [f"{_at(f)} on {f['model']} ({price_words(cat, f['model'])}): "
             + (f"hit the return cap ({cap})" if hit else f"its piece came back {f['pieces_returned']} times"),
             f"{_at(s)} on {s['model']} ({price_words(cat, s['model'])}): finished first try"],
            lane_or_part=f["unit"], bio=f["bio"], apply=_model_apply(f, goal, s["model"])))
    costs = [f["cost_usd"] for f in units]
    high = max(COST_FLOOR, 2 * median(costs)) if len(costs) > 1 else COST_FLOOR
    for f in first:
        p = price_of(cat, f["model"])
        if p is None or p < TOP_PRICE or f["cost_usd"] < high or f["lines"] > SMALL_DIFF:
            continue
        kinds = set(best_for(cat, f["model"]))
        cands = [r for r in cat if r.get("ref") != f["model"] and r.get("tools") is not False
                 and 0 < (price_of(cat, r["ref"]) or 0) < TOP_PRICE and kinds <= set(best_for(cat, r["ref"]))]
        if not cands:
            continue
        pick = max(cands, key=lambda r: (price_of(cat, r["ref"]), r["ref"]))["ref"]
        out.append(suggestion(
            f"model-{f['unit']}-cheaper", "model", "low",
            f"try a cheaper model for {_who(f)}: {pick} ({price_words(cat, pick)})",
            [f"{_at(f)} on {f['model']} ({price_words(cat, f['model'])}): finished first try for "
             f"${f['cost_usd']:.4f} (the run's {f['noun']}s: median ${median(costs):.4f})",
             f"it wrote {f['lines']} line(s) in {f['written']} unit(s)",
             f"{pick} is best for the same kinds: {', '.join(sorted(kinds)) or 'none listed'}"],
            lane_or_part=f["unit"], bio=f["bio"], apply=_model_apply(f, goal, pick)))
    return out


def _tools_apply(f: dict, tool: str, cwd, state_dir):
    if not f.get("bio"):
        return None
    tl = _bio_raw(f["bio"], cwd, state_dir).get("tools") or {}
    deny, allow = tl.get("deny"), tl.get("allow")
    if isinstance(deny, list) and tool in deny:
        return apply_to("bio", f["bio"], "tools.deny", [t for t in deny if t != tool])
    if isinstance(allow, list) and tool not in allow:
        return apply_to("bio", f["bio"], "tools.allow", list(allow) + [tool])
    return None


def tools_rules(units: list, cwd=None, state_dir=None) -> list:
    out = []
    for f in units:
        by_tool: dict = {}
        for d in f.get("denied") or []:
            by_tool.setdefault(str(d.get("tool_name") or "?"), []).append(str(d.get("reason") or ""))
        for tool, reasons in by_tool.items():
            out.append(suggestion(f"tools-{f['unit']}-{tool}", "tools", "high", f"{_who(f)} could not call `{tool}`",
                                  [f"{_at(f)}: {tool} denied {len(reasons)} time(s): {reasons[0]}"],
                                  lane_or_part=f["unit"], bio=f.get("bio", ""),
                                  apply=_tools_apply(f, tool, cwd, state_dir)))
        keys: dict = {}
        for r in f.get("refused") or []:
            keys.setdefault(str(r["key"]), []).append(r)
        for key, rs in keys.items():
            waited = sum((f.get("waited_s") or {}).values())
            why = rs[0].get("why") or ([f"{_at(f)}: {len(rs)} refused claim(s) on {key}"]
                                       + [f"waited {waited:.0f}s on other {f['noun']}s' claims"] * bool(waited))
            out.append(suggestion(f"tools-{f['unit']}-claim-{key}", "tools", "medium",
                                  f"{rs[0].get('who') or _who(f)} could not write `{key}`: {rs[0]['held']}", why,
                                  lane_or_part=f["unit"], bio=f.get("bio", "")))
    return out


def wait_pairs(units: list) -> dict:
    """{(unit, other): [why]}: a unit that spent WAIT_SHARE of its time or more waiting on another's claims."""
    by_n, pairs = {f["unit"]: f for f in units}, {}
    for f in units:
        for other, secs in (f.get("waited_s") or {}).items():
            if other in by_n and f.get("duration_s") and secs >= WAIT_SHARE * f["duration_s"]:
                pairs.setdefault((f["unit"], other), []).append(
                    f"{_at(f)} waited {secs:.0f}s of its {f['duration_s']:.0f}s on {_at(by_n[other])}'s claims")
    return pairs


def conflict_pairs(units: list, conflicts: list, order: list, pairs=None) -> dict:
    """Add {(unit, other): [why]} for each judged conflict: the last unit merged before it that touched that file."""
    by_n, pairs = {f["unit"]: f for f in units}, dict(pairs or {})
    for c in conflicts:
        n, rel = c.get("unit"), str(c.get("file") or "")
        others = [m for m in (order[:order.index(n)] if n in order else []) if m in by_n and rel in by_n[m]["files"]]
        if n in by_n and others:
            pairs.setdefault((n, others[-1]), []).append(
                f"merging {_at(by_n[n])} conflicted in {rel} with {_at(by_n[others[-1]])}'s change; a judge resolved it")
    return pairs


def structure_rules(units: list, pairs: dict, run: str, *, dep: str = "after", note: str = "", plan: bool = True) -> list:
    by_n, out = {f["unit"]: f for f in units}, []
    for (a, b), why in sorted(pairs.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        fa, fb = by_n[a], by_n[b]
        out.append(suggestion(
            f"structure-{a}-after-{b}", "structure", "medium",
            f"give {_at(fa)} `{dep}: {fb['job']}` so it starts from {_at(fb)}'s finished head", why + [note] * bool(note),
            lane_or_part=a, bio=fa.get("bio", ""),
            apply=apply_to("plan", run, f"{fa['job']}.after", sorted(set(fa.get("after") or []) | {fb["job"]}))
            if plan else None))
    for f in units:
        if f.get("written") == 0:
            out.append(suggestion(
                f"structure-{f['unit']}-drop", "structure", "low",
                f"drop {_at(f)} ({f['title']}) or merge its claims into another {f['noun']}",
                [f"{_at(f)} wrote nothing (claimed {', '.join(f.get('claims') or []) or 'nothing'}); it ended "
                 f"{f.get('state') or '?'}"], lane_or_part=f["unit"], bio=f.get("bio", ""),
                apply=apply_to("plan", run, f"{f['job']}.drop", True) if plan else None))
    return out


def coordination_rules(loops: list, units=(), mid=None) -> list:
    """`loops`: [{unit|None, noun, n, limit, why}] (unit None: the run's quality gate)."""
    out = []
    for lp in loops:
        if lp["n"] <= lp["limit"]:
            continue
        if lp.get("unit") is None:
            out.append(suggestion("coordination-gate-loops", "coordination", "medium",
                                  f"the quality gate looped {lp['n']} times: split the failing work differently or "
                                  "give the goal a narrower DONE WHEN", lp["why"]))
        else:
            out.append(suggestion(f"coordination-{lp['unit']}-loops", "coordination", "medium",
                                  f"the gate at {lp['noun']} {lp['unit']} looped {lp['n']} times: put what the redo "
                                  "asked for in its brief or its acceptance", lp["why"], lane_or_part=lp["unit"]))
    for f in units:
        secs = f.get("asked_s")
        if mid is not None and secs is not None and secs > mid:
            out.append(suggestion(f"coordination-{f['unit']}-asked", "coordination", "medium",
                                  f"{_at(f)} waited {secs:.0f}s for {f.get('where') or 'its harness'}'s owner to allow "
                                  f"it: pin it to a harness that runs {f['noun']}s without asking, or answer sooner",
                                  [f"{_at(f)}: asked for {secs:.0f}s", f"the median {f['noun']} took {mid:.0f}s"],
                                  lane_or_part=f["unit"]))
    return out
