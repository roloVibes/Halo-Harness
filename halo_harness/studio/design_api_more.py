"""halo_harness.studio.design_api_more -- the "plus more" handlers of Studio's
Design mode (Halo 3.0.1.0 round D5): the variants prompt for `run`, the
critique turn (read-only, pins as comments), the contrast check and the
assets folder; 3.0.7.0 R3: rename and delete an artboard, cancel a turn.
Routed from design_api.py.
"""

from __future__ import annotations

import re

from halo_harness.design import assets as A
from halo_harness.design import contrast as K
from halo_harness.design import critique as Q
from halo_harness.design.jsonio import project_lock
from halo_harness.studio import design_api_turns as turns
from halo_harness.studio.design_api_io import _artboard, _bad, _project

_BASE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def variants_of(prompt: str, body: dict):
    """(prompt, None) or (None, error response) for a run body's optional variants / base."""
    if body.get("variants") in (None, "", 0, 1):
        return prompt, None
    try:
        n = int(body["variants"])
    except (TypeError, ValueError):
        return None, _bad("variants is a number from 2 to %d" % Q.MAX_VARIANTS)
    if not 2 <= n <= Q.MAX_VARIANTS:
        return None, _bad("variants is a number from 2 to %d" % Q.MAX_VARIANTS)
    base = str(body.get("base") or "design")
    if not _BASE.match(base):
        return None, _bad("base is an artboard id: lower-case letters, digits and hyphens")
    return Q.variants_prompt(prompt, n, base), None


def critique(req):
    """POST critique {artboard, model?, wait?}: a Read,Glob turn; the pins are in the finished turn's result.
    `wait: true` answers {turn, pins, note} once the turn has ended."""
    from halo_harness.studio import design_api as D
    p, err = _project(req)
    if err:
        return err
    a, err = _artboard(req, p)
    if err:
        return err

    def pin(result: dict) -> dict:
        pins, note = Q.add_pins(p, a["id"], result.get("text") or "", version=a["latest"]) if result.get("code") == 0 else ([], "The critique turn did not finish, so no pins were added.")
        return {"pins": pins, "note": note}
    turn = turns.start(p, Q.critique_prompt(p, a["id"]), model=str(req.body.get("model") or ""), runner=D.RUNNER, registered=D.REGISTERED,
                       after=pin, tools_override="Read,Glob", entries={}, max_turns=6, publish=D.feed_of(req))
    if turn is None:
        return 409, {"error": "this project already has a turn running: wait for it to finish", "turn": turns.live_turn(p.slug)}
    if req.body.get("wait"):
        turn["thread"].join(timeout=1800)
        r = turn["result"] or {}
        return 200, {"turn": turn["id"], "pins": r.get("pins", []), "note": r.get("note", "")}
    return 200, {"turn": turn["id"]}


def contrast(req):
    p, err = _project(req)
    if err:
        return err
    a, err = _artboard(req, p)
    if err:
        return err
    return 200, K.check_artboard(p, a["id"])


def assets_list(req):
    p, err = _project(req)
    return err or (200, {"assets": A.list_assets(p)})


def assets_post(req):
    p, err = _project(req)
    if err:
        return err
    if not str(req.body.get("name") or "").strip():
        return _bad("an asset needs a name")
    try:
        row = A.save_asset(p, str(req.body["name"]), req.body.get("data_base64"))
    except A.TooBig as e:
        return 413, {"error": str(e), "problems": [str(e)]}
    except ValueError as e:
        return _bad(str(e))
    return 201, row


def artboard_rename(req):
    """POST artboard/<aid>/rename {name}: the artboard's title (its id, folder and versions stay)."""
    p, err = _project(req)
    if err:
        return err
    a, err = _artboard(req, p)
    if err:
        return err
    name = " ".join(str(req.body.get("name") or "").split())[:80]
    if not name:
        return _bad("an artboard needs a name")
    with project_lock(p.path):
        meta = p._meta_for_write()
        for row in meta.get("artboards") or []:
            if row.get("id") == a["id"]:
                row["title"] = name
        p.save_meta(meta)
    return 200, {"id": a["id"], "title": name}


def artboard_delete(req):
    """DELETE artboard/<aid>: the artboard, its files and versions; its open pins are resolved."""
    p, err = _project(req)
    if err:
        return err
    a, err = _artboard(req, p)
    if err:
        return err
    if turns.live_turn(p.slug):
        return 409, {"error": "a turn is running in this project: delete the artboard when it has finished"}
    pins = [c["id"] for c in p.comments() if c.get("artboard") == a["id"] and not c.get("resolved")]
    if pins:
        p.resolve_comments(pins)
    p.remove_artboard(a["id"])
    return 200, {"deleted": a["id"], "resolved": len(pins)}


def turn_cancel(req):
    """POST turn/<tid>/cancel: stop the running turn."""
    return turns.cancel(req.params["slug"], req.params["tid"])
