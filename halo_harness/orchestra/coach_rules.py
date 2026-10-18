"""halo_harness.orchestra.coach_rules -- the coach's rules for an Orchestra run
(orchestra/coach.py; the facts come from coach_facts.py). Each rule names
its evidence in `why`:

* prompt: a lane whose piece came back two or more times for the same
  reason (the gate's failing tests, or a merge whose resolution failed the
  tests), or whose reply restates the goal with no written unit -> a line
  for the bio's `context.prompt_notes`.
* model: a lane that hit the return cap or failed the tests on a cheap
  model while a sibling on a dearer one finished first try -> the
  sibling's model; a lane that finished first try on a top-tier model at a
  high cost with a small diff -> a cheaper catalog model with the same
  best-for kinds. Into the bio's `models.preference`, or the lineup's role
  when the lane ran as the goal's worker role.
* tools: a denied tool call -> `tools.allow` (or `tools.deny`) of the bio;
  a refused claim -> the text only.
* structure: a lane that spent half its time or more waiting on another
  lane's claims, or a merge conflict judged between two lanes -> `after`
  in the plan; a lane that wrote nothing -> drop it from the plan.
* coordination: a quality gate that looped more than twice.
"""

from __future__ import annotations

import re
from pathlib import Path
from statistics import median

from halo_harness.orchestra import jsonl
from halo_harness.orchestra.coach import apply_to, suggestion
from halo_harness.orchestra.coach_facts import CHEAP_PRICE, TOP_PRICE, best_for, catalog as load_catalog, \
    lane_facts, price_of, price_words

COST_FLOOR = 0.05     # $: under it a lane is never "high cost"
SMALL_DIFF = 40       # lines written: a small diff
WAIT_SHARE = 0.5      # of the lane's time spent waiting on one other lane
CLASS_TEXT = {"gate": "the tests failed on the finished branch", "merge": "the merge's resolution failed the tests"}
NOTES = {"gate": "Before you release a unit, run the goal's test command in your worktree and fix every failure "
                 "that names your unit.",
         "merge": "Change only the lines of your claimed unit and keep the code around it as it is, so your "
                  "branch merges cleanly.",
         "restated": "Edit your claimed units with Edit before you reply; a reply that restates the task "
                     "without an edit leaves the lane empty."}


def _who(f: dict) -> str:
    return f"bio `{f['bio']}`" if f["bio"] else f"lane {f['lane']}'s worker"


def _bio_raw(bio: str, cwd, state_dir) -> dict:
    try:
        from halo_harness.agents_yaml import resolve_agent_bio
        return resolve_agent_bio(bio, cwd=cwd, state_dir=state_dir) or {}
    except Exception:
        return {}


def _model_apply(f: dict, goal: dict, ref: str, run: str):
    if f["bio"]:
        return apply_to("bio", f["bio"], "models.preference", ref)
    return apply_to("lineup", str(goal.get("lineup") or ""), f"roles.{goal.get('worker') or 'subagent'}", ref)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def prompt_rules(lanes: list, goal: dict, cap: int) -> list:
    out = []
    what = _norm(goal.get("what"))[:80]
    for f in lanes:
        for cls, k in f["returned"].items():
            if k >= 2:
                out.append(suggestion(
                    f"prompt-{f['lane']}-{cls}", "prompt", "medium",
                    f"tighten {_who(f)}'s prompt: lane {f['lane']}'s piece came back {k} times because "
                    f"{CLASS_TEXT[cls]}", [f"lane {f['lane']} ({f['title']}): returned {k} times, each time: "
                                           f"{CLASS_TEXT[cls]}", f"return cap {cap}; the lane ended {f['state'] or '?'}"],
                    lane_or_part=f["lane"], bio=f["bio"],
                    apply=apply_to("bio", f["bio"], "context.prompt_notes", NOTES[cls]) if f["bio"] else None))
        if not f["written"] and what and what in _norm(f["reply"]):
            out.append(suggestion(
                f"prompt-{f['lane']}-restated", "prompt", "medium",
                f"tighten {_who(f)}'s prompt: lane {f['lane']}'s reply restates the goal and wrote no unit",
                [f"lane {f['lane']}: 0 written units of {len(f['claims'])} claimed",
                 f"its reply repeats the goal: \"{f['reply'][:120]}\""],
                lane_or_part=f["lane"], bio=f["bio"],
                apply=apply_to("bio", f["bio"], "context.prompt_notes", NOTES["restated"]) if f["bio"] else None))
    return out


def model_rules(lanes: list, goal: dict, cap: int, cat: list, run: str) -> list:
    out = []
    first = [f for f in lanes if f["pieces_returned"] == 0 and f["state"] in ("merged", "written")]
    for f in lanes:
        p = price_of(cat, f["model"])
        bad = f["pieces_returned"] >= cap or f["returned"]["gate"] > 0
        if not bad or p is None or p > CHEAP_PRICE:
            continue
        better = [s for s in first if s["model"] and s["model"] != f["model"]
                  and (price_of(cat, s["model"]) or 0) > p]
        if not better:
            continue
        s = min(better, key=lambda s: (float(s["ended"] or 0), s["lane"]))
        hit = f["pieces_returned"] >= cap
        out.append(suggestion(
            f"model-{f['lane']}-stronger", "model", "high" if hit else "medium",
            f"give {_who(f)} the model lane {s['lane']} used: {s['model']}",
            [f"lane {f['lane']} on {f['model']} ({price_words(cat, f['model'])}): "
             + (f"hit the return cap ({cap})" if hit else f"its piece came back {f['pieces_returned']} times"),
             f"lane {s['lane']} on {s['model']} ({price_words(cat, s['model'])}): finished first try"],
            lane_or_part=f["lane"], bio=f["bio"], apply=_model_apply(f, goal, s["model"], run)))
    costs = [f["cost_usd"] for f in lanes]
    high = max(COST_FLOOR, 2 * median(costs)) if len(costs) > 1 else COST_FLOOR
    for f in first:
        p = price_of(cat, f["model"])
        if p is None or p < TOP_PRICE or f["cost_usd"] < high or f["lines"] > SMALL_DIFF:
            continue
        kinds = set(best_for(cat, f["model"]))
        cands = [r for r in cat if r.get("ref") != f["model"] and r.get("tools") is not False
                 and (price_of(cat, r["ref"]) is not None) and 0 < price_of(cat, r["ref"]) < TOP_PRICE
                 and kinds <= set(best_for(cat, r["ref"]))]
        if not cands:
            continue
        pick = max(cands, key=lambda r: (price_of(cat, r["ref"]), r["ref"]))["ref"]
        out.append(suggestion(
            f"model-{f['lane']}-cheaper", "model", "low",
            f"try a cheaper model for {_who(f)}: {pick} ({price_words(cat, pick)})",
            [f"lane {f['lane']} on {f['model']} ({price_words(cat, f['model'])}): finished first try for "
             f"${f['cost_usd']:.4f} (the run's lanes: median ${median(costs):.4f})",
             f"it wrote {f['lines']} line(s) in {f['written']} unit(s)",
             f"{pick} is best for the same kinds: {', '.join(sorted(kinds)) or 'none listed'}"],
            lane_or_part=f["lane"], bio=f["bio"], apply=_model_apply(f, goal, pick, run)))
    return out


def tools_rules(lanes: list, cwd, state_dir) -> list:
    out = []
    for f in lanes:
        by_tool: dict = {}
        for d in f["denied"]:
            by_tool.setdefault(str(d.get("tool_name") or "?"), []).append(str(d.get("reason") or ""))
        for tool, reasons in by_tool.items():
            apply = None
            if f["bio"]:
                tl = (_bio_raw(f["bio"], cwd, state_dir).get("tools") or {})
                deny, allow = tl.get("deny"), tl.get("allow")
                if isinstance(deny, list) and tool in deny:
                    apply = apply_to("bio", f["bio"], "tools.deny", [t for t in deny if t != tool])
                elif isinstance(allow, list) and tool not in allow:
                    apply = apply_to("bio", f["bio"], "tools.allow", list(allow) + [tool])
            out.append(suggestion(
                f"tools-{f['lane']}-{tool}", "tools", "high", f"{_who(f)} could not call `{tool}`",
                [f"lane {f['lane']}: {tool} denied {len(reasons)} time(s): {reasons[0]}"],
                lane_or_part=f["lane"], bio=f["bio"], apply=apply))
        keys: dict = {}
        for r in f["refused"]:
            keys.setdefault(str(r["key"]), []).append(r)
        for key, rs in keys.items():
            by = rs[0]["by_lane"]
            out.append(suggestion(
                f"tools-{f['lane']}-claim-{key}", "tools", "medium",
                f"{_who(f)} could not write `{key}`: " + (f"lane {by} held `{rs[0]['other']}`" if by is not None
                                                          else f"{rs[0]['by']} held `{rs[0]['other']}`"),
                [f"lane {f['lane']}: {len(rs)} refused claim(s) on {key}"]
                + [f"waited {sum(f['waited_s'].values()):.0f}s on other lanes' claims"] * bool(f["waited_s"]),
                lane_or_part=f["lane"], bio=f["bio"], apply=None))
    return out


def structure_rules(run_dir: Path, lanes: list, run: str) -> list:
    pairs: dict = {}
    by_n = {f["lane"]: f for f in lanes}
    for f in lanes:
        for other, secs in f["waited_s"].items():
            if other in by_n and f["duration_s"] and secs >= WAIT_SHARE * f["duration_s"]:
                pairs.setdefault((f["lane"], other), []).append(
                    f"lane {f['lane']} waited {secs:.0f}s of its {f['duration_s']:.0f}s on lane {other}'s claims")
    merge = jsonl.read_json(run_dir / "merge.json", {}) or {}
    order = [int(n) for n in merge.get("order") or [] if str(n).isdigit()]
    for c in merge.get("conflicts") or []:
        n, rel = c.get("lane"), str(c.get("file") or "")
        before = order[:order.index(n)] if n in order else []
        others = [m for m in before if m in by_n and any(k.split("#")[0] == rel for k in by_n[m]["claims"])]
        if n in by_n and others:
            pairs.setdefault((n, others[-1]), []).append(
                f"merging lane {n} conflicted in {rel} with lane {others[-1]}'s change; a judge resolved it")
    out = []
    for (a, b), why in sorted(pairs.items()):
        fa, fb = by_n[a], by_n[b]
        out.append(suggestion(
            f"structure-{a}-after-{b}", "structure", "medium",
            f"give lane {a} `after: {fb['job']}` so it starts from lane {b}'s finished head", why,
            lane_or_part=a, bio=fa["bio"],
            apply=apply_to("plan", run, f"{fa['job']}.after", sorted(set(fa["after"]) | {fb["job"]}))))
    for f in lanes:
        if not f["written"]:
            out.append(suggestion(
                f"structure-{f['lane']}-drop", "structure", "low",
                f"drop lane {f['lane']} ({f['title']}) or merge its claims into another lane",
                [f"lane {f['lane']} wrote no unit (claimed {', '.join(f['claims']) or 'nothing'}); it ended "
                 f"{f['state'] or '?'}"], lane_or_part=f["lane"], bio=f["bio"],
                apply=apply_to("plan", run, f"{f['job']}.drop", True)))
    return out


def coordination_rules(events: list) -> list:
    loops = [e for e in events if e.get("kind") == "gate" and str(e.get("text") or "").startswith("tests fail")]
    if len(loops) <= 2:
        return []
    return [suggestion("coordination-gate-loops", "coordination", "medium",
                       f"the quality gate looped {len(loops)} times: split the failing work differently or "
                       "give the goal a narrower DONE WHEN",
                       [f"+{float(e.get('elapsed_s') or 0):.0f}s {e.get('text')}; sent back: "
                        f"{', '.join(f'lane {n}' for n in (e.get('data') or {}).get('back') or []) or 'none'}"
                        for e in loops])]


def orchestra(run_dir, *, catalog=None, cwd=None, state_dir=None) -> tuple:
    from halo_harness.orchestra.lanes import lane_rows
    run_dir = Path(run_dir)
    goal = jsonl.read_json(run_dir / "goal.json", {}) or {}
    report = jsonl.read_json(run_dir / "report.json", {}) or {}
    events = jsonl.read_lines(run_dir / "events.jsonl")
    if cwd is None:
        from halo_harness.orchestra.goal import repo_root_of
        cwd = repo_root_of(run_dir)
    cat = catalog if catalog is not None else load_catalog(state_dir)
    lanes = lane_facts(run_dir, goal, lane_rows(run_dir), events, cwd=cwd, state_dir=state_dir)
    cap = int(goal.get("return_cap") or 2)
    found = (prompt_rules(lanes, goal, cap) + model_rules(lanes, goal, cap, cat, run_dir.name)
             + tools_rules(lanes, cwd, state_dir) + structure_rules(run_dir, lanes, run_dir.name)
             + coordination_rules(events))
    keep = ("lane", "job", "bio", "model", "state", "pieces_returned", "cost_usd", "duration_s", "written", "lines",
            "returned", "waited_s")
    evidence = {"status": report.get("status"), "cost_usd": report.get("cost_usd"), "return_cap": cap,
                "lanes": [{k: f[k] for k in keep} | {"denied": len(f["denied"]), "refused": len(f["refused"])}
                          for f in lanes],
                "gate_loops": sum(1 for e in events if e.get("kind") == "gate"
                                  and str(e.get("text") or "").startswith("tests fail")),
                "conflicts": len((jsonl.read_json(run_dir / "merge.json", {}) or {}).get("conflicts") or [])}
    return found, evidence
