"""halo_harness.media.comfy_ui -- UI-format ComfyUI graphs (what the editor
saves under user/default/workflows) to API format (what `POST /prompt`
takes), the way the frontend does on Run: links resolved, each node's
`widgets_values` mapped onto its class's widget inputs in `/object_info`
order (a seed's control_after_generate value and an upload button's slot
skipped, dynamic combos expanded to `name.sub` keys), notes and reroutes
dropped, muted nodes left out, bypassed nodes passed through, and
subgraphs flattened to `<outer id>:<inner id>` nodes. Every node keeps its
title in `_meta.title` so `set` can address it by name.
"""

from __future__ import annotations

SKIP_TYPES = {"MarkdownNote", "Note", "PrimitiveNode", "Reroute"}
WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", "COMFY_DYNAMICCOMBO_V3"}
SOCKET_TYPES = {"IMAGE", "LATENT", "MASK", "VIDEO", "AUDIO", "MODEL", "CLIP", "VAE", "CONDITIONING"}
MUTED, BYPASSED = 2, 4


class ComfyGraphError(ValueError):
    pass


def _opts(spec) -> dict:
    return spec[1] if isinstance(spec, (list, tuple)) and len(spec) > 1 and isinstance(spec[1], dict) else {}


def _is_widget(spec) -> bool:
    o = _opts(spec)
    if o.get("forceInput") or o.get("rawLink"):
        return False
    t = spec[0] if isinstance(spec, (list, tuple)) and spec else None
    return isinstance(t, list) or t in WIDGET_TYPES


def _ordered_inputs(cls_spec: dict) -> list:
    out = []
    for sec in ("required", "optional"):
        block = (cls_spec.get("input") or {}).get(sec)
        if isinstance(block, dict):
            out.extend(block.items())
    return out


def map_widgets(class_type: str, values, info: dict) -> dict:
    """{input name: value} for a node's widget values, in the class's order."""
    spec = info.get(class_type)
    if spec is None:
        raise ComfyGraphError(f"class {class_type!r} is not on this ComfyUI server (no /object_info entry)")
    if isinstance(values, dict):  # some custom nodes save widgets by name
        names = {n for n, _ in _ordered_inputs(spec)}
        return {k: v for k, v in values.items() if k in names}
    vals, out, i = list(values or []), {}, 0

    def take():
        nonlocal i
        v = vals[i] if i < len(vals) else None
        i += 1
        return v

    for name, s in _ordered_inputs(spec):
        if not _is_widget(s):
            continue
        if i >= len(vals):
            break
        o = _opts(s)
        val = take()
        out[name] = val
        if s[0] == "COMFY_DYNAMICCOMBO_V3":
            chosen = next((x for x in o.get("options", []) if x.get("key") == val), None)
            for sec in ("required", "optional"):
                for sub, ss in ((chosen or {}).get("inputs", {}).get(sec) or {}).items():
                    if _is_widget(ss) and i < len(vals):
                        out[f"{name}.{sub}"] = take()
                        if _opts(ss).get("control_after_generate"):
                            take()
        if o.get("control_after_generate"):
            take()
        if o.get("image_upload") or o.get("video_upload") or o.get("audio_upload") or o.get("upload"):
            take()
    return out


def _title(node: dict, info: dict) -> str:
    spec = info.get(node.get("type")) or {}
    return str(node.get("title") or spec.get("display_name") or node.get("type") or "")


def ui_to_api(wf: dict, info: dict) -> dict:
    if not isinstance(wf, dict) or not isinstance(wf.get("nodes"), list):
        raise ComfyGraphError("not a UI-format workflow (no nodes list)")
    sgs = {sg["id"]: sg for sg in (wf.get("definitions") or {}).get("subgraphs") or []}
    links = {l[0]: l for l in wf.get("links") or []}
    nodes = {n["id"]: n for n in wf["nodes"]}

    def outer_source(node, input_name):
        for inp in node.get("inputs") or []:
            if inp.get("name") == input_name and inp.get("link") is not None:
                l = links[inp["link"]]
                return resolve(l[1], l[2])
        return None

    def resolve(node_id, slot):
        n = nodes.get(node_id)
        if n is None:
            raise ComfyGraphError(f"a link points at node {node_id}, which is not in the workflow")
        mode = n.get("mode", 0)
        if mode == MUTED:
            return None
        if mode == BYPASSED:
            typ = (n.get("outputs") or [{}])[slot].get("type")
            for inp in n.get("inputs") or []:
                if inp.get("link") is not None and inp.get("type") == typ:
                    l = links[inp["link"]]
                    return resolve(l[1], l[2])
            return None
        if n["type"] in sgs:
            sg = sgs[n["type"]]
            for l in sg.get("links") or []:
                if l["target_id"] == -20 and l["target_slot"] == slot:
                    if l["origin_id"] == -10:
                        return outer_source(n, sg["inputs"][l["origin_slot"]]["name"])
                    return (f"{n['id']}:{l['origin_id']}", l["origin_slot"])
            raise ComfyGraphError(f"subgraph output {slot} of node {node_id} is not connected")
        return (str(node_id), slot)

    prompt: dict = {}
    for n in wf["nodes"]:
        if n.get("type") in SKIP_TYPES or n.get("mode", 0) in (MUTED, BYPASSED):
            continue
        if n["type"] in sgs:
            _flatten_subgraph(n, sgs, info, outer_source, prompt)
            continue
        try:
            inputs = map_widgets(n["type"], n.get("widgets_values"), info)
        except ComfyGraphError as e:
            raise ComfyGraphError(f"node {n['id']}: {e}") from None
        for inp in n.get("inputs") or []:
            if inp.get("link") is None:
                continue
            l = links.get(inp["link"])
            src = resolve(l[1], l[2]) if l else None
            if src is not None:
                inputs[inp["name"]] = [src[0], src[1]]
        prompt[str(n["id"])] = {"class_type": n["type"], "inputs": inputs, "_meta": {"title": _title(n, info)}}
    return prompt


def _flatten_subgraph(n: dict, sgs: dict, info: dict, outer_source, prompt: dict) -> None:
    sg = sgs[n["type"]]
    inner = {x["id"]: x for x in sg.get("nodes") or []}
    # Legacy promoted widgets: the subgraph node's own widgets_values feed
    # its non-socket inputs in order.
    legacy = {}
    wvals = n.get("widgets_values")
    if isinstance(wvals, list) and wvals:
        wi = [i for i in sg.get("inputs") or [] if i.get("type") not in SOCKET_TYPES]
        legacy = {inp["name"]: val for inp, val in zip(wi, wvals)}
    mapped = {}
    for x in sg.get("nodes") or []:
        if x.get("type") in SKIP_TYPES:
            continue
        if x.get("type") in sgs:
            raise ComfyGraphError(f"node {n['id']}: nested subgraphs are not supported")
        try:
            mapped[x["id"]] = map_widgets(x["type"], x.get("widgets_values"), info)
        except ComfyGraphError as e:
            raise ComfyGraphError(f"node {n['id']}:{x['id']}: {e}") from None
    # A subgraph input not wired from outside takes the value of the
    # internal widget it proxies (the frontend feeds it to every consumer).
    sg_values = {}
    for l in sg.get("links") or []:
        if l["origin_id"] != -10 or l["target_id"] not in mapped:
            continue
        sname = sg["inputs"][l["origin_slot"]]["name"]
        iname = inner[l["target_id"]]["inputs"][l["target_slot"]]["name"]
        if sname not in sg_values and iname in mapped[l["target_id"]]:
            sg_values[sname] = mapped[l["target_id"]][iname]
    for x in sg.get("nodes") or []:
        if x.get("type") in SKIP_TYPES or x.get("mode", 0) in (MUTED, BYPASSED):
            continue
        inputs = dict(mapped.get(x["id"]) or {})
        for l in sg.get("links") or []:
            if l["target_id"] != x["id"]:
                continue
            iname = x["inputs"][l["target_slot"]]["name"]
            if l["origin_id"] == -10:
                sname = sg["inputs"][l["origin_slot"]]["name"]
                src = outer_source(n, sname)
                if src is not None:
                    inputs[iname] = [src[0], src[1]]
                elif sname in legacy:
                    inputs[iname] = legacy[sname]
                elif sname in sg_values:
                    inputs[iname] = sg_values[sname]
            else:
                inputs[iname] = [f"{n['id']}:{l['origin_id']}", l["origin_slot"]]
        prompt[f"{n['id']}:{x['id']}"] = {"class_type": x["type"], "inputs": inputs, "_meta": {"title": _title(x, info)}}
