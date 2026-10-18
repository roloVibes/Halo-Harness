"""halo_harness.work.handoff -- what a unit takes from others and hands on
(Halo 3.1.2.0 R1, docs/WORK.md).

    needs: [{"from": "<unit or job id>", "take": "all|summary|outputs|block|<a give's name>"}]
    gives: [{"name", "kind": "summary|files|artifact|output|block|handback", "path"}]
    after: ["<ids it starts after>"]       base: "<the commit it started from>" | null

What each kind declares:

* lane: `handoff.needs` / `gave` / `after` / `base` of lanes/<n>.json
  (orchestra/handoff.py); its ids are job ids (`job-1`).
* part: `depends_on` (needs, each `take` the part's own), `outputs` plus
  its hand-back (gives), `base` (fleet/mission_handoff.py).
* stage: the blocks it reads (needs, `take: block`) and writes (gives),
  `stage_done:<stage>` (after).
* step: the `$.<step>` refs of its inputs (needs, `take: output`), its
  `steps/<n>.json` output (gives), the steps it reads (after).

`upstreams(unit)` is everything a unit waits for; `graph(units)` and
`layers(units)` order a run's units by it (orchestra/handoff_spec.layers),
which is what R2 schedules on.
"""

from __future__ import annotations


def need(src, take: str = "all") -> dict:
    return {"from": str(src), "take": str(take or "all")}


def give(name: str, kind: str, path=None) -> dict:
    return {"name": str(name), "kind": str(kind), "path": path}


def upstreams(unit) -> list:
    """The ids `unit` starts after: its `after` plus every need's `from`, in order, once each."""
    out = []
    for x in list(unit.after or []) + [n.get("from") for n in unit.needs or [] if isinstance(n, dict)]:
        if x not in (None, "") and str(x) not in out:
            out.append(str(x))
    return out


def graph(units: list) -> dict:
    """`{unit id: [upstream unit ids]}`; a lane's job ids (`job-2`) are read as its lane id."""
    ids = {str(u.id) for u in units}
    alias = {str((u.extra or {}).get("job")): str(u.id) for u in units if (u.extra or {}).get("job")}
    return {str(u.id): [alias.get(x, x) for x in upstreams(u) if alias.get(x, x) in ids] for u in units}


def layers(units: list) -> dict:
    """`{unit id: layer}` (0 = no upstream)."""
    from halo_harness.orchestra.handoff_spec import layers as _layers
    return {str(k): int(v) for k, v in _layers(graph(units)).items()}
