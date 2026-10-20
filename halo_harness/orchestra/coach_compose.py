"""halo_harness.orchestra.coach_compose -- compose: what the coach keeps from
its probes, and the change Apply would write (Halo 3.1.6.0 R2).

The rule, over the contrast rows (orchestra/coach_compare.py), in order:

1. adopt: the judged-best candidate (the best-ranked probe) is adopted when
   it beat the reference on the tests or on the judge's rank, at no more
   than COST_X (1.5) times the reference's cost; the pick is its kind
   (`invariant` or `domain`);
2. merge: else, when the best-ranked invariant candidate and the
   best-ranked domain candidate each won on an axis (tests, rank, cost:
   cheaper with no fewer tests) and they won on different axes, the two
   overlays become one (the invariant one's parts + the domain one's, notes
   joined): the pick is `merged`;
3. keep: else nothing changes (`kept`).

A probe that did not finish wins nothing. The why line cites the contrast.

`changes(overlay, facts)` turns an overlay into the writes Apply makes
through the coach's writers (orchestra/coach_apply.py), and lists what has
nowhere to go:

    lead.model           the lineup's lead role (`roles.<lead>`), else the lead's bio models.preference
    lead.effort, notes   the lead's bio (models.effort, context.prompt_notes)
    workers.* / bios.*   each bio the lanes ran as (context.prompt_notes, models.preference,
                         limits.max_iterations, tools.allow, tools.deny); workers.model with no bio:
                         the lineup's worker role
    bios.<b>.use_for     the lineup entry of bio b (`agents.<b>.use_for`)
    plan[]               the run's plan draft (`job-<n>.after`)
"""

from __future__ import annotations

from halo_harness.orchestra.coach_probe_schema import for_bio, merge
from halo_harness.orchestra.probe_overlay import BIO_FIELDS, bio_fields, lane_bios

COST_X = 1.5
PICKS = ("invariant", "domain", "merged", "kept")


def money(x) -> str:
    return f"${float(x or 0):.4f}"


def row_line(r: dict, ref: dict, n: int) -> str:
    """One candidate's contrast in words."""
    if r.get("tests_delta") is None:
        return f"{r['kind']} {r['id']}: {r.get('status')}" + (f" ({r['stop_reason']})" if r.get("stop_reason") else "") \
            + (f": {r['error']}" if r.get("error") else "")
    tests = (f"tests {ref.get('passed')} -> {r.get('passed')} passed ({r['tests_delta']:+d})" if r.get("tests_by") == "passed"
             else f"tests {'pass' if ref.get('tests_ok') else 'fail'} -> {'pass' if r.get('tests_ok') else 'fail'}")
    x = f" = {r['cost_x']:.2f}x the run's {money(ref.get('cost_usd'))}" if r.get("cost_x") is not None else ""
    stop = f", stopped: {r['stop_reason']}" if r.get("status") != "finished" else ""
    return (f"{r['kind']} {r['id']}: {tests}, ranked {r.get('rank')} of {n} by the judge (the run itself "
            f"{r.get('ref_rank')}), {money(r.get('cost_usd'))}{x}, steps {r.get('steps')} ({r.get('steps_delta'):+d}){stop}")


def compose(cands: list, rows: list, ref: dict) -> dict:
    """{pick, from: [candidate ids], overlay, why}."""
    by = {c["id"]: c for c in cands}
    n = len([r for r in rows if r.get("rank")]) + 1
    ranked = sorted([r for r in rows if r.get("rank")], key=lambda r: r["rank"])
    ref_cost = float(ref.get("cost_usd") or 0.0)
    best = ranked[0] if ranked else None
    if best and {"tests", "rank"} & set(best["wins"]) and float(best.get("cost_usd") or 0) <= COST_X * ref_cost + 1e-12:
        won = " and ".join(w for w in ("tests", "rank") if w in best["wins"])
        return {"pick": best["kind"], "from": [best["id"]], "overlay": by[best["id"]]["overlay"],
                "why": f"adopted the {best['kind']} candidate: the judge's best, it beat the run on {won} at no more "
                       f"than {COST_X:g}x its cost; {row_line(best, ref, n)}"}
    inv = next((r for r in ranked if r["kind"] == "invariant" and r["wins"]), None)
    dom = next((r for r in ranked if r["kind"] == "domain" and r["wins"]), None)
    if inv and dom and any(a != b for a in inv["wins"] for b in dom["wins"]):
        return {"pick": "merged", "from": [inv["id"], dom["id"]],
                "overlay": merge(by[inv["id"]]["overlay"], by[dom["id"]]["overlay"]),
                "why": f"merged the invariant candidate (won on {', '.join(inv['wins'])}) with the domain candidate "
                       f"(won on {', '.join(dom['wins'])}); {row_line(inv, ref, n)}; {row_line(dom, ref, n)}"}
    why = "; ".join(row_line(r, ref, n) for r in rows) or "no probe ran"
    return {"pick": "kept", "from": [], "overlay": {},
            "why": f"kept the run's harness: no candidate beat it on the tests or the judge's rank within "
                   f"{COST_X:g}x its cost, and no two won on different axes; {why}"}


def _entry(f: dict, *, role: str = "", agent: str = "") -> dict:
    for e in (f.get("lineup_raw") or {}).get("agents") or []:
        if isinstance(e, dict) and ((role and role in (e.get("as"), e.get("role"))) or (agent and e.get("agent") == agent)):
            return e
    return {}


def changes(overlay: dict, f: dict) -> "tuple[list, list]":
    """([{target, name, field, value}] Apply writes, [one line per part with nowhere to go])."""
    out, skipped = [], []
    lineup, run_id = f.get("lineup") or "", f["run_dir"].name

    def bio(name, field, value):
        out.append({"target": "bio", "name": name, "field": field, "value": value})
    lead = (overlay or {}).get("lead") or {}
    if lead.get("model"):
        if lineup and _entry(f, role=f["lead_role"]):
            out.append({"target": "lineup", "name": lineup, "field": f"roles.{f['lead_role']}", "value": lead["model"]})
        elif f.get("lead_bio"):
            bio(f["lead_bio"], "models.preference", lead["model"])
        else:
            skipped.append("lead.model: the run names no lineup with a lead role: set the lead's model in Studio's Roles")
    for k in ("effort", "prompt_notes"):
        if lead.get(k):
            if f.get("lead_bio"):
                bio(f["lead_bio"], BIO_FIELDS[k], lead[k])
            else:
                skipped.append(f"lead.{k}: the run's lead has no bio to hold it")
    workers = lane_bios(f)
    for name in sorted(set(workers) | set((overlay or {}).get("bios") or {})):
        part = for_bio(overlay, name) if name in workers else dict(((overlay or {}).get("bios") or {}).get(name) or {})
        for field, value in bio_fields(part):
            bio(name, field, value)
        if part.get("use_for"):
            if lineup and _entry(f, agent=name):
                out.append({"target": "lineup", "name": lineup, "field": f"agents.{name}.use_for", "value": part["use_for"]})
            else:
                skipped.append(f"bios.{name}.use_for: bio {name} is in no lineup the run names")
    w = (overlay or {}).get("workers") or {}
    bare = [str(l["n"]) for l in f.get("lanes") or [] if not l.get("bio")]
    if w and workers and bare:
        skipped.append(f"workers: lane(s) {', '.join(bare)} ran with no bio, so the workers' part goes to the bios only")
    if w and not workers:
        if w.get("model") and lineup and _entry(f, role=f["worker_role"]):
            out.append({"target": "lineup", "name": lineup, "field": f"roles.{f['worker_role']}", "value": w["model"]})
        skipped += [f"workers.{k}: the run's workers ran with no bio: give the worker role one in Studio's Roles"
                    for k in w if k != "model" or not (lineup and _entry(f, role=f["worker_role"]))]
    for r in (overlay or {}).get("plan") or []:
        out.append({"target": "plan", "name": run_id, "field": f"{r['job']}.after", "value": list(r["after"])})
    return out, skipped
