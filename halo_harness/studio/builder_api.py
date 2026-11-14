"""halo_harness.studio.builder_api -- the builder's routes (Halo 3.6.0.0 R1; docs/STUDIO-builder.md).

    GET  builder                       {model, model_from, typical, spent_usd, cap_usd, reached}
    POST builder/ask {tab, selection, text, conversation_id, history}
                                       {reply, question?, changes: [{id, kind, target, summary, widen, ticked, fill?}],
                                        cost_usd, meta}; 429 with the one line when today's cap is reached
    POST builder/apply {conversation_id, change_ids}
                                       {undo_id, wrote, removed, skipped, filled}: only the ids sent are written -- a
                                       widening line is written only when the person ticked it in this request
    POST builder/undo {undo_id}        {restored}: every file the apply touched, as it was before

All three writes are owner-only; the cap is checked here, before the model is called.
"""

from __future__ import annotations

import re

from halo_harness.crew import builder, builder_cap, changes
from halo_harness.studio.crew_api import dispatch_table
from halo_harness.studio.owner_proof import owner_only

_CID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
TABS = ("agents",)


def get_meta(req):
    return 200, builder_cap.meta(req.state_dir)


def post_ask(req):
    b = req.body or {}
    cid, text, tab = str(b.get("conversation_id") or ""), str(b.get("text") or "").strip(), str(b.get("tab") or "agents")
    if not _CID.match(cid) or not text:
        return 400, {"error": "the body needs a conversation_id (letters, digits, - and _) and the text"}
    if tab not in TABS:
        return 422, {"error": f"the builder works on the Agents tab in this version, not {tab!r}"}
    if builder_cap.left(req.state_dir) <= 0:
        line = builder_cap.reached_line(req.state_dir)
        return 429, {"error": line, "reply": line, "capped": True, "changes": [], "meta": builder_cap.meta(req.state_dir)}
    sel = b.get("selection") if isinstance(b.get("selection"), dict) else {}
    hist = b.get("history") if isinstance(b.get("history"), list) else []
    return 200, builder.turn(req.state_dir, req.cwd, tab, sel, text[:4000], cid, hist)


def post_apply(req):
    b = req.body or {}
    cid = str(b.get("conversation_id") or "")
    ids = b.get("change_ids")
    if not _CID.match(cid) or not isinstance(ids, list):
        return 400, {"error": "the body needs the conversation_id and change_ids (the lines ticked)"}
    rows = builder.pending(req.state_dir, cid)
    if not rows:
        return 409, {"error": "nothing to apply: the preview is gone (ask again)"}
    known = {r["id"] for r in rows}
    unknown = [i for i in ids if i not in known]
    if unknown:
        return 422, {"error": f"not in this preview: {', '.join(map(str, unknown[:5]))}"}
    got = changes.apply(rows, ids, cwd=req.cwd, state_dir=req.state_dir)
    if not got["ok"]:
        return 422, {"error": got["problems"][0], **got}
    builder.forget(req.state_dir, cid)
    return 200, got


def post_undo(req):
    got = changes.undo(str((req.body or {}).get("undo_id") or ""), state_dir=req.state_dir)
    return (200, got) if got.get("ok") else (404, got)


ROUTES: list = [
    ("GET", r"^builder$", get_meta),
    ("POST", r"^builder/ask$", owner_only(post_ask)),
    ("POST", r"^builder/apply$", owner_only(post_apply)),
    ("POST", r"^builder/undo$", owner_only(post_undo)),
]


def dispatch_builder(req):
    return dispatch_table(req, ROUTES)
