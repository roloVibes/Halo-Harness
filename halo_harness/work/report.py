"""halo_harness.work.report -- one report row for every kind of unit (Halo
3.1.2.0 R1, docs/WORK.md).

    {"unit": "2", "kind": "lane|part|stage|step", "title": "...", "owner": "...",
     "state": "<machine word>", "native": "<the engine's word>", "cost_usd": 0.0031, "attempts": 0,
     "gate": "required|optional|none", "base": "<sha>" | null, "gave": [{"name", "kind", "path"}], "error": ""}

Every engine's report keeps its own rows (report.json `lanes` / `parts` /
`steps`, board.json `stages`) and carries these beside them under `units`
(`rows(run_dir, kind)`); `halo work` and `GET /api/work/<kind>/<run>` print
and serve the same rows for any run.
"""

from __future__ import annotations

from typing import Optional

FIELDS = ("unit", "kind", "title", "owner", "state", "native", "cost_usd", "attempts", "gate", "base", "gave", "error")


def row_of(unit) -> dict:
    """A unit's report row."""
    return {"unit": unit.id, "kind": unit.kind, "title": unit.title, "owner": unit.owner, "state": unit.state,
            "native": unit.native, "cost_usd": round(float(unit.cost_usd or 0.0), 6), "attempts": int(unit.attempts or 0),
            "gate": (unit.gate or {}).get("mode") or "none", "base": unit.base,
            "gave": [{k: g.get(k) for k in ("name", "kind", "path")} for g in unit.gives if isinstance(g, dict)],
            "error": unit.error or ""}


def rows(run_dir, kind: Optional[str] = None) -> list:
    """Every unit of the run as a report row (`kind`: lane|part|stage|step, else read from the folder)."""
    from halo_harness.work.store import UnitStore
    try:
        return UnitStore(run_dir, kind).rows()
    except ValueError:
        return []


def table(rows_: list) -> str:
    """The rows as `halo work` prints them."""
    if not rows_:
        return "  (no units yet)"
    head = f"  {'kind':<6} {'unit':<10} {'state':<8} {'native':<10} {'cost $':>8} {'att':>3} {'gate':<8} {'base':<8} " \
           f"{'owner':<16} title"
    lines = [head]
    for r in rows_:
        base = str(r.get("base") or "-")[:7]
        lines.append(f"  {r['kind']:<6} {str(r['unit'])[:10]:<10} {r['state']:<8} {str(r['native'] or '-')[:10]:<10} "
                     f"{float(r['cost_usd']):>8.4f} {int(r['attempts']):>3} {r['gate']:<8} {base:<8} "
                     f"{str(r['owner'] or '-')[:16]:<16} {r['title']}" + (f"  error: {r['error']}" if r.get("error") else ""))
    return "\n".join(lines)
