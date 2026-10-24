"""halo_harness.packs.resolve -- which enabled packs can run, and in what
order (Halo 3.2.0.0 R1).

`resolve(packs, enabled=..., api_version=..., halo_version=...)` answers
`(order, problems)`: `order` lists the ids that run, every pack after the
packs it requires (ties by id); `problems` maps an id to its lines. One
line each for: a manifest problem, an extension API or a Halo version
outside the pack's range, a required pack that is missing, not enabled,
at a version outside the range, or not running itself, and a `requires`
cycle. A pack with a problem contributes nothing; the packs that require
it say so.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.packs import semver as V
from halo_harness.packs.manifest import requirement_range


def _versions(api_version: Optional[str], halo_version: Optional[str]) -> "tuple[str, str]":
    if api_version is None:
        from halo_harness.ext import API_VERSION as api_version
    if halo_version is None:
        from halo_harness import __version__ as halo_version
    return str(api_version), str(halo_version)


def compat_lines(pack, *, api_version=None, halo_version=None) -> "list[str]":
    """The pack's `halo_api` and `halo` ranges against this Halo, one line each in the policy's words
    (3.2.0.0 R7, ext/compat.py: no `max` means the `min`'s major only):
    "pack doc-review needs extension API 1.2 to 1.9; this Halo has 1.0", "pack x needs Halo >= 3.3; this is 3.2.0.0"."""
    from halo_harness.ext.compat import compatible, range_words
    api, halo = _versions(api_version, halo_version)
    out = []
    api_range = pack.manifest.get("halo_api")
    if isinstance(api_range, dict) and not V.range_problem(api_range) and not compatible(api_range, api):
        out.append(f"pack {pack.id} needs extension API {range_words(api_range)}; this Halo has {api}")
    halo_range = pack.manifest.get("halo")
    if isinstance(halo_range, dict) and not V.range_problem(halo_range) and not V.in_range(halo, halo_range):
        out.append(f"pack {pack.id} needs Halo {V.describe(halo_range)}; this is {halo}")
    return out


def _requires(pack) -> "list[dict]":
    reqs = pack.manifest.get("requires")
    return [r for r in reqs if isinstance(r, dict) and isinstance(r.get("pack"), str)] if isinstance(reqs, list) else []


def _cycle(start: str, graph: "dict[str, list[str]]") -> "Optional[list[str]]":
    stack, path = [(start, iter(graph.get(start, [])))], [start]
    while stack:
        node, children = stack[-1]
        nxt = next(children, None)
        if nxt is None:
            stack.pop()
            path.pop()
            continue
        if nxt == start:
            return path + [start]
        if nxt in graph and nxt not in path:
            stack.append((nxt, iter(graph.get(nxt, []))))
            path.append(nxt)
    return None


def resolve(packs, *, enabled, api_version=None, halo_version=None) -> "tuple[list[str], dict[str, list[str]]]":
    by_id = {p.id: p for p in packs}
    on = [p for p in packs if p.id in set(enabled)]
    problems: "dict[str, list[str]]" = {}
    for p in on:
        lines = [f"{p.id}: pack.yaml: {line}" for line in p.problems]
        lines += compat_lines(p, api_version=api_version, halo_version=halo_version)
        for req in _requires(p):
            dep = by_id.get(req["pack"])
            rng = requirement_range(req) or {}
            if dep is None:
                lines.append(f"{p.id} requires {req['pack']}, which is not installed")
            elif dep.id not in set(enabled):
                lines.append(f"{p.id} requires {dep.id}, which is installed but not enabled (halo pack enable {dep.id})")
            elif rng and not V.in_range(dep.version, rng):
                lines.append(f"{p.id} requires {dep.id} {V.describe(rng)}; {dep.version or 'no version'} is installed")
        if lines:
            problems[p.id] = lines
    graph = {p.id: [r["pack"] for r in _requires(p) if r["pack"] in by_id] for p in on}
    for p in on:
        cycle = _cycle(p.id, graph)
        if cycle:
            problems.setdefault(p.id, []).append(
                f"{p.id} is in a requires cycle: {' -> '.join(cycle)}")
    order: "list[str]" = []
    placed: "set[str]" = set()
    pending = sorted(p.id for p in on if p.id not in problems)
    while pending:
        progressed = False
        for pid in list(pending):
            deps = graph.get(pid, [])
            bad = [d for d in deps if d in problems]
            if bad:
                problems.setdefault(pid, []).append(f"{pid} requires {bad[0]}, which does not run (see its lines)")
                pending.remove(pid)
                progressed = True
            elif all(d in placed for d in deps):
                order.append(pid)
                placed.add(pid)
                pending.remove(pid)
                progressed = True
        if not progressed:  # only a cycle can stall here; _cycle has named it
            for pid in pending:
                problems.setdefault(pid, []).append(f"{pid} waits on a pack that does not run")
            break
    return order, problems
