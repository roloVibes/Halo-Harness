"""halo_harness.studio.workflows_api -- the Workflows board's routes (Halo 3.3.16.0 R3, docs/STUDIO-agents.md "Workflows").

    GET  workflows                     {lineup, where, enabled: [ref], squares: [row]} -- a row: ref, group (yours |
                                       packs | shipped), origin, enabled, writable, line, path and the contract
                                       (does, takes, gives, covers, lead, engine, band, cap_usd, depth, turns,
                                       wall_s, costs, limits); the same rows as `halo workflows list --json`
    POST workflows/enable  {ref, lineup?}   {ok, line}: on for the active lineup (the auto lineup: config workflows.enabled)
    POST workflows/disable {ref, lineup?}   {ok, line}
    GET  workflows/yaml?ref=<ref>      {ref, path, text, writable}
    PUT  workflows/contract {ref, budget: {band, cap_usd}, limits: {depth, turns, wall_s}}
                                       {ok, line}: written into a square of yours or the project's; a shipped or a
                                       pack's square answers 422 with how to copy it to yours
"""

from __future__ import annotations

from pathlib import Path


def _rows(req) -> list:
    from halo_harness.workflows.squares_cli import rows
    out = rows(Path(req.cwd))
    for r in out:
        r["writable"] = r.get("origin") in ("yours", "project")
    return out


def get_board(req):
    from halo_harness.workflows import registry
    lineup = registry.active_lineup()
    where = "the auto lineup" if registry.uses_config(lineup) else f"lineup {lineup}"
    return 200, {"lineup": lineup, "where": where, "enabled": registry.enabled_refs(lineup, cwd=req.cwd),
                 "squares": _rows(req)}


def _flip(req, on: bool):
    from halo_harness.workflows import registry
    ref = str((req.body or {}).get("ref") or "").strip()
    if not ref:
        return 400, {"error": "ref is required"}
    lineup = (req.body or {}).get("lineup") or None
    ok, line = (registry.enable if on else registry.disable)(ref, lineup, cwd=req.cwd)
    return (200, {"ok": True, "line": line}) if ok else (422, {"ok": False, "error": line, "line": line})


def get_yaml(req):
    from halo_harness.workflows.spec import find
    ref = str((req.query or {}).get("ref") or "")
    wf, why = find(ref, cwd=req.cwd)
    if wf is None:
        return 404, {"error": why}
    try:
        text = Path(wf.path).read_text(encoding="utf-8")
    except OSError as e:
        return 404, {"error": str(e)}
    return 200, {"ref": wf.ref, "path": str(wf.path), "text": text, "writable": wf.origin in ("yours", "project")}


def _merge(data: dict, key: str, given, keys: tuple) -> None:
    if not isinstance(given, dict):
        return
    cur = dict(data.get(key) or {}) if isinstance(data.get(key), dict) else {}
    for k in keys:
        if k in given:
            if given[k] in (None, ""):
                cur.pop(k, None)
            else:
                cur[k] = given[k]
    if cur:
        data[key] = cur
    else:
        data.pop(key, None)


def put_contract(req):
    from halo_harness.agents_yaml import _read_yaml_file, _write_yaml_file
    from halo_harness.workflows.contract import problems
    from halo_harness.workflows.spec import find
    body = req.body or {}
    wf, why = find(str(body.get("ref") or ""), cwd=req.cwd)
    if wf is None:
        return 404, {"error": why}
    if wf.origin not in ("yours", "project"):
        line = (f"{wf.ref} is {wf.origin} and read-only: copy it to yours first "
                f"(halo workflows new my-{wf.name} --from {wf.ref}), then edit the copy")
        return 422, {"ok": False, "error": line, "line": line}
    data = _read_yaml_file(Path(wf.path)) or {}
    _merge(data, "budget", body.get("budget"), ("band", "cap_usd"))
    _merge(data, "limits", body.get("limits"), ("depth", "turns", "wall_s"))
    bad = problems(data)
    if bad:
        return 422, {"ok": False, "error": bad[0], "problems": bad}
    wrote = _write_yaml_file(Path(wf.path), data)
    if wrote:
        return 422, {"ok": False, "error": wrote[0]}
    return 200, {"ok": True, "line": f"{wf.ref}: budget and limits saved to {wf.path}"}


def dispatch_workflows(req):
    path, method = req.path, req.method
    if path == "workflows" and method == "GET":
        return get_board(req)
    if path in ("workflows/enable", "workflows/disable") and method == "POST":
        return _flip(req, path.endswith("enable") and not path.endswith("disable"))
    if path == "workflows/yaml" and method == "GET":
        return get_yaml(req)
    if path == "workflows/contract" and method == "PUT":
        return put_contract(req)
    if path.startswith("workflows"):
        return 404, {"error": f"no route for {method} /api/{path}"}
    return None
