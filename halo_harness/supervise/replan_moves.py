"""halo_harness.supervise.replan_moves -- what a checked replan changes, lane by
lane (Halo 3.1.8.0 R2): the moves replan_plan.check found and the lines the
goal_plan row, the plan.json revision and events.jsonl show.

    {kind: model | bio, lane, job, from, to}      a different model (or bio) for a kept lane
    {kind: retry, lane, job}                       its worker runs again with the contrast as context
    {kind: split, lane, job, into: [{job, lane, claims}]}   a lane replaced by two or more parts
    {kind: assist, lane, job, of, of_lane, bio}    a specialist's new lane before the lane it assists
"""

from __future__ import annotations

from halo_harness.supervise.drift import DONE


def moves_of(out, run_dir, jobs: dict, files: dict, left_ids: dict, kept: dict, parts: dict, plan: dict,
             by_id: dict) -> None:
    """Fill `out` (replan_plan.Checked): its moves, the lanes re-queued, the hand-off notes, the old jobs."""
    from halo_harness.supervise.replan_plan import _keys
    from halo_harness.supervise.replan_prompt import context
    assisted = set(out.assists.values())
    for jid, p in kept.items():
        n = left_ids[jid]
        old, new, lane = jobs[n], plan[n], files.get(n, {})
        changed = False
        for k in ("model", "bio"):
            if str(old.get(k) or "") != str(new.get(k) or ""):
                out.moves.append({"kind": k, "lane": n, "job": jid, "from": str(old.get(k) or lane.get(k) or ""),
                                  "to": str(new.get(k) or "")})
                changed = True
        if p.get("retry") is True:
            out.moves.append({"kind": "retry", "lane": n, "job": jid})
            out.notes[n] = context(run_dir, n, lane) or "the supervisor asked for a retry of this lane"
        if p.get("retry") is True or jid in assisted or (changed and lane.get("state") in DONE):
            out.requeue.append(n)
        if changed or p.get("retry") is True or jid in assisted:
            out.before.append(dict(old))
    for src, ps in parts.items():
        out.moves.append({"kind": "split", "lane": left_ids[src], "job": src,
                          "into": [{"job": str(p["id"]), "lane": by_id[str(p["id"])], "claims": _keys(p)} for p in ps]})
    for m, target in out.assists.items():
        out.moves.append({"kind": "assist", "lane": m, "job": plan[m]["id"], "of": target, "of_lane": left_ids[target],
                          "bio": str(plan[m].get("bio") or "")})
        out.notes.setdefault(left_ids[target], "")
        out.notes[left_ids[target]] = (out.notes[left_ids[target]] + "\n" if out.notes[left_ids[target]] else "") + (
            f"a specialist ({plan[m]['id']}, lane {m}) looked at your units first; its summary is in your hand-offs")


def diff_lines(moves: list) -> list:
    out = []
    for m in moves:
        head = f"lane {m.get('lane')} ({m.get('job')})"
        if m["kind"] in ("model", "bio"):
            out.append(f"{head}: {m['kind']} {m.get('from') or 'the default'} -> {m.get('to') or 'the default'}")
        elif m["kind"] == "retry":
            out.append(f"{head}: retry with the contrast as context")
        elif m["kind"] == "split":
            out.append(f"{head} split -> " + ", ".join(
                f"{p['job']} (lane {p['lane']}: {len(p['claims'])} unit{'s' if len(p['claims']) != 1 else ''})"
                for p in m.get("into") or []))
        elif m["kind"] == "assist":
            out.append(f"+ {head} assists lane {m.get('of_lane')} ({m.get('of')})" + (f", bio {m['bio']}" if m.get("bio") else ""))
    return out
