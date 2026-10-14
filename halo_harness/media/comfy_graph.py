"""halo_harness.media.comfy_graph -- working with ComfyUI API-format graphs:
the UI-to-API conversion (comfy_ui.ui_to_api), `set` overrides addressed by
node id or node title, `only` pruning to what feeds the chosen output
nodes, and the input listing `inspect` prints.

`set` keys:
  "<node id>.<input>"     e.g. "6.text", "459:452.prompt" (subgraph nodes)
  "<node title>.<input>"  e.g. "Positive.text" -- every node with that title
  "<key>"                 a key a node declares in `_meta.keys` (the starter
                          workflows declare prompt, negative, width, height,
                          seed, steps, image, length), else the one node that
                          has a literal input of that name
A seed of "random" or -1 becomes a fresh random seed.
"""

from __future__ import annotations

import copy
import random
from typing import Iterable

from halo_harness.media.comfy_ui import ComfyGraphError, ui_to_api  # noqa: F401  (re-exported)

SEED_INPUTS = ("seed", "noise_seed")


def is_api_format(graph) -> bool:
    if not isinstance(graph, dict) or not graph or "nodes" in graph:
        return False
    nodes = [v for k, v in graph.items() if not str(k).startswith("_")]
    return bool(nodes) and all(isinstance(v, dict) and "class_type" in v and isinstance(v.get("inputs", {}), dict) for v in nodes)


def to_api(graph: dict, object_info) -> dict:
    """An API graph (copied) from either format; `object_info` is the
    server's dict or a zero-argument callable that fetches it."""
    if is_api_format(graph):
        return {str(k): copy.deepcopy(v) for k, v in graph.items() if not str(k).startswith("_")}
    info = object_info() if callable(object_info) else object_info
    return ui_to_api(graph, info or {})


def _title(node: dict) -> str:
    return str(((node.get("_meta") or {}).get("title")) or "")


def _is_link(v) -> bool:
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], int)


def _sort_key(nid: str):
    return [int(p) if p.isdigit() else 0 for p in str(nid).split(":")] + [str(nid)]


def _by_title(g: dict, title: str) -> list:
    t = title.strip().lower()
    return [nid for nid, n in g.items() if _title(n).strip().lower() == t]


def resolve_key(g: dict, key: str) -> list:
    """[(node id, input name)] a `set` key addresses."""
    key = str(key)
    for i, ch in enumerate(key):
        if ch != ".":
            continue
        head, rest = key[:i], key[i + 1:]
        if not rest:
            continue
        if head in g:
            return [(head, rest)]
        hits = _by_title(g, head)
        if hits:
            return [(nid, rest) for nid in hits]
    aliased = [(nid, (n.get("_meta") or {}).get("keys", {})[key]) for nid, n in g.items()
               if isinstance((n.get("_meta") or {}).get("keys"), dict) and key in n["_meta"]["keys"]]
    if aliased:
        return aliased
    plain = [nid for nid, n in g.items() if key in (n.get("inputs") or {}) and not _is_link(n["inputs"][key])]
    if len(plain) == 1:
        return [(plain[0], key)]
    if len(plain) > 1:
        names = ", ".join(f"{nid} ({g[nid].get('class_type')}{', ' + repr(_title(g[nid])) if _title(g[nid]) else ''})" for nid in sorted(plain, key=_sort_key))
        raise ComfyGraphError(f"set {key!r}: several nodes have that input ({names}); use '<node id>.{key}'")
    titles = sorted({_title(n) for n in g.values() if _title(n)})
    raise ComfyGraphError(f"set {key!r}: no node id, title or input matches. Node ids: {', '.join(sorted(g, key=_sort_key)[:40])}; "
                          f"titles: {', '.join(titles[:40]) or '(none)'}")


def _coerce(old, new, name: str):
    if name in SEED_INPUTS and (new == -1 or str(new).lower() == "random"):
        return random.randint(1, 2**48)
    if isinstance(new, str) and isinstance(old, (int, float)) and not isinstance(old, bool):
        try:
            return int(new) if isinstance(old, int) and new.strip().lstrip("-").isdigit() else float(new)
        except ValueError:
            return new
    return new


def apply_set(api_graph: dict, sets: "dict | None") -> dict:
    g = copy.deepcopy(api_graph)
    for key, value in (sets or {}).items():
        for nid, name in resolve_key(g, key):
            inputs = g[nid].setdefault("inputs", {})
            inputs[name] = _coerce(inputs.get(name), value, name)
    return g


def only(api_graph: dict, node_ids: "Iterable[str]") -> dict:
    """Keep the named nodes (ids or titles) and everything that feeds them."""
    wanted = []
    for x in node_ids or []:
        x = str(x)
        hits = [x] if x in api_graph else _by_title(api_graph, x)
        if not hits:
            raise ComfyGraphError(f"only: no node with id or title {x!r}")
        wanted.extend(hits)
    keep, stack = set(), list(wanted)
    while stack:
        nid = stack.pop()
        if nid in keep or nid not in api_graph:
            continue
        keep.add(nid)
        for v in (api_graph[nid].get("inputs") or {}).values():
            if _is_link(v):
                stack.append(v[0])
    return {k: copy.deepcopy(v) for k, v in api_graph.items() if k in keep}


def describe_inputs(api_graph: dict) -> list:
    rows = []
    for nid in sorted(api_graph, key=_sort_key):
        n = api_graph[nid]
        row = {"node": nid, "class_type": n.get("class_type"), "title": _title(n),
               "inputs": {k: v for k, v in (n.get("inputs") or {}).items() if not _is_link(v)}}
        keys = (n.get("_meta") or {}).get("keys")
        if isinstance(keys, dict) and keys:
            row["keys"] = dict(keys)
        rows.append(row)
    return rows


def for_queue(api_graph: dict) -> dict:
    """The graph as POST /prompt takes it: `_meta` keeps only the title."""
    out = {}
    for nid, n in api_graph.items():
        if str(nid).startswith("_"):
            continue
        node = {"class_type": n["class_type"], "inputs": copy.deepcopy(n.get("inputs") or {})}
        if _title(n):
            node["_meta"] = {"title": _title(n)}
        out[str(nid)] = node
    return out


def check_against(api_graph: dict, info: dict) -> list:
    """What this server would reject before running: a class it does not
    have, a required input left out, a choice (a model file, a sampler)
    that is not in its list. Returns readable problem lines."""
    problems = []
    for nid in sorted(api_graph, key=_sort_key):
        n = api_graph[nid]
        spec = info.get(n.get("class_type"))
        if spec is None:
            problems.append(f"node {nid}: class {n.get('class_type')} is not on this server")
            continue
        req = (spec.get("input") or {}).get("required") or {}
        opt = (spec.get("input") or {}).get("optional") or {}
        inputs = n.get("inputs") or {}
        for name, s in req.items():
            if name not in inputs and not (isinstance(s, list) and s and s[0] == "COMFY_AUTOGROW_V3"):
                problems.append(f"node {nid} ({n['class_type']}): required input {name} is missing")
        for name, v in inputs.items():
            s = req.get(name.split(".")[0]) or opt.get(name.split(".")[0])
            if not isinstance(s, list) or not s or _is_link(v) or "." in name:
                continue
            if len(s) > 1 and isinstance(s[1], dict) and s[1].get("image_upload"):
                continue  # an input image is uploaded at run time
            choices = s[0] if isinstance(s[0], list) else (s[1].get("options") if s[0] == "COMBO" and len(s) > 1 and isinstance(s[1], dict) else None)
            if isinstance(choices, list) and choices and all(isinstance(c, str) for c in choices) and v not in choices:
                problems.append(f"node {nid} ({n['class_type']}): {name} = {v!r} is not on this server")
    return problems


def dangling_links(api_graph: dict) -> list:
    """[(node, input, missing source)] -- what `only` or a muted node left behind."""
    return [(nid, k, v[0]) for nid, n in api_graph.items() for k, v in (n.get("inputs") or {}).items()
            if _is_link(v) and v[0] not in api_graph]
