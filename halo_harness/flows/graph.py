"""halo_harness.flows.graph -- a flow's steps as a graph (Halo 3.0.9.0 round
R2: Studio's "Show as graph") and the one edit it allows, the order.

`step_deps(spec)` -> `{step id: [the steps it reads]}`: the `$.<step>` refs
in its `inputs` and `set` (flows/refs.py), plus what a step needs without a
ref: a `confirm` step confirms the render before it, a `metrics` step
samples the post before it, `done` comes after every other step.
`step_layers(spec)` puts a step one layer below the deepest step it reads
(layer 0: nothing to read). Steps in one layer do not read each other, so
their order in the file is free: `reorder(text, order)` rewrites the flow
file's `steps:` list in a new order, moving each step's lines as they are
(comments kept); when the list is not in the plain one-item-per-`- ` shape
it falls back to a YAML dump of the reordered mapping.
"""

from __future__ import annotations

import re

from halo_harness.flows.refs import parse_ref, refs_in

_STEPS = re.compile(r"^steps:\s*(#.*)?$")
_ITEM = re.compile(r"^(\s*)- ")


def _steps(spec: dict) -> list:
    return [s for s in (spec or {}).get("steps") or [] if isinstance(s, dict) and s.get("id")]


def step_deps(spec: dict) -> dict:
    steps = _steps(spec)
    ids = [str(s["id"]) for s in steps]
    out: dict = {}
    for i, s in enumerate(steps):
        sid, kind, before = str(s["id"]), s.get("kind"), steps[:i]
        deps = []
        for ref in refs_in([s.get("inputs"), s.get("set")]):
            try:
                target = str(parse_ref(ref)[0])
            except ValueError:
                continue
            if target in ids and target != sid and target not in deps:
                deps.append(target)
        want = {"confirm": "render", "metrics": "post"}.get(str(kind))
        if want and not deps:
            last = [str(b["id"]) for b in before if b.get("kind") == want]
            deps += last[-1:]
        if kind == "done":
            deps = [str(b["id"]) for b in before]
        out[sid] = deps
    return out


def step_layers(spec: dict) -> dict:
    deps, memo = step_deps(spec), {}

    def depth(sid: str, path: tuple) -> int:
        if sid in memo:
            return memo[sid]
        ups = [u for u in deps.get(sid) or [] if u in deps and u not in path]
        memo[sid] = 0 if not ups else 1 + max(depth(u, path + (sid,)) for u in ups)
        return memo[sid]
    return {sid: depth(sid, ()) for sid in deps}


def graph_rows(spec: dict) -> list:
    """`[{id, kind, uses, deps, layer, gate}]` in file order."""
    deps, layer = step_deps(spec), step_layers(spec)
    return [{"id": str(s["id"]), "kind": s.get("kind"), "uses": str(s.get("uses") or ""), "deps": deps.get(str(s["id"]), []),
             "layer": layer.get(str(s["id"]), 0), "gate": s.get("kind") == "confirm" or bool(s.get("gate"))}
            for s in _steps(spec)]


def _blocks(text: str):
    """`(head, items, tail)` of the steps list, or None when it is not plain."""
    import yaml
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if _STEPS.match(line.rstrip("\r\n"))), None)
    if start is None:
        return None
    indent, items, cur, end = None, [], None, len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        bare = line.strip()
        m = _ITEM.match(line)
        if m and (indent is None or len(m.group(1)) == len(indent)):
            indent = m.group(1)
            cur = [line]
            items.append(cur)
            continue
        if bare and not bare.startswith("#") and (indent is None or not line.startswith(indent + " ")):
            end = i
            break
        if cur is None:
            return None
        cur.append(line)
    if not items:
        return None
    ids = []
    for block in items:
        try:
            parsed = yaml.safe_load("".join(block))
        except yaml.YAMLError:
            return None
        if not (isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict) and parsed[0].get("id")):
            return None
        ids.append(str(parsed[0]["id"]))
    return "".join(lines[:start + 1]), list(zip(ids, items)), "".join(lines[end:])


def reorder(text: str, order: list) -> str:
    """`text` (a flow file) with its steps in `order` (every step id once).
    Raises ValueError when `order` is not the file's step ids."""
    import yaml
    data = yaml.safe_load(text)
    ids = [str(s.get("id")) for s in (data or {}).get("steps") or [] if isinstance(s, dict)]
    order = [str(o) for o in order]
    if sorted(order) != sorted(ids) or len(set(order)) != len(order):
        raise ValueError(f"the order must name every step once: {', '.join(ids)}")
    parts = _blocks(text)
    if parts is not None and [i for i, _ in parts[1]] == ids:
        head, items, tail = parts
        by = dict(items)
        body = [by[o] for o in order]
        for block in body[:-1]:  # every item but the last ends its line
            if not block[-1].endswith("\n"):
                block[-1] += "\n"
        return head + "".join("".join(b) for b in body) + tail
    by_id = {str(s.get("id")): s for s in data["steps"]}
    data["steps"] = [by_id[o] for o in order]
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
