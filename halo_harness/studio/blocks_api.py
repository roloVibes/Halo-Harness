"""halo_harness.studio.blocks_api -- the composing routes of Agents -> Cast's blocks (Halo 3.3.16.3, docs/STUDIO-blocks.md).
Every write goes through the square files of yours, the lineup's file or config (when_store.py, members.py, blocks.py);
a shipped or a pack's file is never written.

    PUT  workflows/when      {ref, when, lineup?}        {ok, line}: the block's "when" (when.py; {} = the plain rule)
    PUT  workflows/members   {ref, add | remove, lineup?} {ok, line, ref, copied_from}: who is inside a square
    POST workflows/swap      {from, to, lineup?}         {ok, line}: the board's `from` becomes `to` (an Undo of a copy)
    GET  workflows/templates                             {templates: [summary + problems]}: blocks you can start from
    POST workflows/templates/add    {template, as?, lineup?}   {ok, line, ref}: a square template written and wired
    POST workflows/templates/merge  {template, raw}            {ok, raw, tier}: a tier template merged into the
                                                               lineup mapping the canvas holds (it saves through
                                                               PUT lineup, so Undo walks it back)
    POST workflows/templates/remove {ref, lineup?}       {ok, line}: a square template's add undone
"""

from __future__ import annotations


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def _answer(ok: bool, line: str, **more):
    return (200, {"ok": True, "line": line, **more}) if ok else (422, {"ok": False, "error": line, "line": line})


def put_when(req):
    from halo_harness.workflows.when_store import set_rule
    b = _body(req)
    ref = str(b.get("ref") or "").strip()
    if not ref:
        return 400, {"error": "ref is required"}
    raw = b.get("when") if isinstance(b.get("when"), dict) else {}
    return _answer(*set_rule(ref, raw, b.get("lineup") or None, cwd=req.cwd))


def put_members(req):
    from halo_harness.workflows.members import change
    b = _body(req)
    ok, line, info = change(str(b.get("ref") or ""), add=str(b.get("add") or ""), remove=str(b.get("remove") or ""),
                            lineup=b.get("lineup") or None, cwd=req.cwd)
    return _answer(ok, line, **info)


def post_swap(req):
    from halo_harness.workflows.members import swap
    b = _body(req)
    return _answer(*swap(str(b.get("from") or ""), str(b.get("to") or ""), b.get("lineup") or None, cwd=req.cwd))


def get_templates(req):
    from halo_harness.workflows import blocks as B
    out = []
    for name in B.names():
        t, _why = B.load(name)
        if t is not None:
            out.append(dict(B.summary(t), problems=B.problems(t, cwd=req.cwd)))
    return 200, {"templates": out}


def post_template(req, verb: str):
    from halo_harness.workflows import blocks as B
    b = _body(req)
    if verb == "remove":
        return _answer(*B.remove(str(b.get("ref") or ""), b.get("lineup") or None, cwd=req.cwd))
    if verb == "merge":
        from halo_harness.workflows.blocks_tier import merge
        t, why = B.load(str(b.get("template") or ""))
        if t is None or t.get("kind") != "tier":
            return 422, {"ok": False, "error": why or "not a tier template"}
        raw, name = merge(b.get("raw") if isinstance(b.get("raw"), dict) else {}, t)
        return (200, {"ok": True, "raw": raw, "tier": name}) if raw is not None else (422, {"ok": False, "error": name})
    ok, line, info = B.add(str(b.get("template") or ""), b.get("as") or None, b.get("lineup") or None, cwd=req.cwd)
    return _answer(ok, line, **info)


def dispatch_blocks(req):
    path, method = req.path, req.method
    if path == "workflows/when" and method == "PUT":
        return put_when(req)
    if path == "workflows/members" and method == "PUT":
        return put_members(req)
    if path == "workflows/swap" and method == "POST":
        return post_swap(req)
    if path == "workflows/templates" and method == "GET":
        return get_templates(req)
    if path.startswith("workflows/templates/") and method == "POST" and path.rsplit("/", 1)[1] in ("add", "merge", "remove"):
        return post_template(req, path.rsplit("/", 1)[1])
    return None
