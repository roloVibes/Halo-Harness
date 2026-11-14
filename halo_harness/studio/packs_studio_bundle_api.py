"""halo_harness.studio.packs_studio_bundle_api -- the routes behind a bundle panel's `api` (Halo 3.3.10.0 R3;
docs/EXTENSION_API.md "Studio contributions", the `api` table). studio/packs_studio_api.py `dispatch_pack` asks
`dispatch` first; the loopback / origin / token guard is every Studio route's.

    POST pack/<id>/publish {kind, data}        -> 200 {ok, kind, published, problems?}
                                                  422 {error}: the line ext.events.publish_event raises, or a kind
                                                      the pack's contributes.events does not declare
                                                  429 {error, rate: {limit, window_s}, retry_after}
    POST pack/<id>/attention {row, kind, what, detail?}
                                               -> 200 {ok, row, kind, file}: attention/<row>.json in the pack's data
                                                  folder (fleet/pack_attention.py reads it); 422 a kind
                                                  contributes.studio.attention does not declare, or a bad row name
    GET  pack/<id>/mode                        -> {pack, mode, label, since, by, armed, modes: [{id, label}]}

Each answers 403 naming the grant (`halo pack enable <id> --grant studio-script`) until studio-script is granted:
the bundle that calls them is loaded only then, and a page that is not the bundle gets the same answer. `publish`
and `attention` share one rate per pack: RATE writes per WINDOW_S seconds (a sliding window in this process); a
write past it is 429 and nothing is written. A pack that does not run here is 404, as on every pack/<id>/ route.
"""

from __future__ import annotations

import collections
import json
import re
import threading
import time

RATE = 20       # writes (publish + attention) per pack in WINDOW_S seconds
WINDOW_S = 10.0
_ROUTE = re.compile(r"^pack/(?P<id>[a-z][a-z0-9-]*)/(?P<what>publish|attention|mode)$")
_METHOD = {"publish": "POST", "attention": "POST", "mode": "GET"}
_hits: "dict[tuple, collections.deque]" = {}
_lock = threading.Lock()
_now = time.monotonic  # the tests' seam


def _granted(req, pack) -> str:
    """'' when studio-script is granted to the pack, else the 403 line naming the grant."""
    from halo_harness.packs import state as S
    from halo_harness.packs import studio_rules as R
    from halo_harness.packs.studio_registry import grant_line
    if R.SCRIPT in S.granted(pack.id, S.load(req.state_dir)):
        return ""
    return f"{pack.id}'s bundle panel calls this once you grant studio-script: {grant_line(pack.id)}"


def _rate(req, pack_id: str) -> "float | None":
    """None when the write may go; else the seconds until it may (nothing counted)."""
    key = (id(req.server), pack_id)
    now = _now()
    with _lock:
        q = _hits.setdefault(key, collections.deque())
        while q and now - q[0] >= WINDOW_S:
            q.popleft()
        if len(q) >= RATE:
            return max(0.1, round(WINDOW_S - (now - q[0]), 1))
        q.append(now)
    return None


def _too_fast(pack_id: str, wait: float):
    return 429, {"error": f"{pack_id}'s bundle panel wrote {RATE} times in the last {WINDOW_S:g} s (its rate: {RATE} "
                          f"per {WINDOW_S:g} s); nothing was written, try again in {wait:g} s",
                 "rate": {"limit": RATE, "window_s": WINDOW_S}, "retry_after": wait}


def _bridge(req):
    if req.server is None:
        return None
    from halo_harness.studio.events import bridge_for
    return bridge_for(req.server)


def post_publish(req, pack):
    from halo_harness.ext.events import publish_event
    from halo_harness.packs.events_log import check
    from halo_harness.packs.manifest import EVENT_RE
    from halo_harness.packs.typed import event_kinds
    body = req.body if isinstance(req.body, dict) else {}
    kind, data = body.get("kind"), body.get("data")
    declared = event_kinds(pack.manifest)
    if isinstance(kind, str) and EVENT_RE.match(kind) and kind not in declared:
        return 422, {"error": f"{pack.id} declares no event {kind} (contributes.events: {', '.join(declared) or 'none'}): "
                              "a bundle panel publishes its pack's own kinds"}
    wait = _rate(req, pack.id)
    if wait is not None:
        return _too_fast(pack.id, wait)
    try:
        published = publish_event(pack.id, kind, data, bridge=_bridge(req))
    except ValueError as e:
        return 422, {"error": str(e)}
    _refusal, problems = check(pack.id, kind, data, cwd=req.cwd, state_dir=req.state_dir)
    return 200, {"ok": True, "kind": kind, "published": published, **({"problems": problems} if problems else {})}


def _nudge(req) -> None:
    """The attention queue reads the new row at once (its count frame goes out), not at its next tick."""
    if req.server is None:
        return

    def run():
        try:
            from halo_harness.studio.live_watch import watcher_for
            watcher_for(req.server, req.state_dir).snapshot(0.0)
        except Exception:  # the queue picks the row up at its next tick all the same
            pass
    threading.Thread(target=run, name="pack-attention-nudge", daemon=True).start()


def post_attention(req, pack):
    from halo_harness.live.pack_attention import ROWS, _folder
    from halo_harness.packs import names as N
    from halo_harness.packs import studio_rules as R
    from halo_harness.privateio import write_private_atomic
    body = req.body if isinstance(req.body, dict) else {}
    row, kind = body.get("row"), body.get("kind")
    declared = R.studio_of(pack.manifest).get("attention")
    kinds = sorted(declared) if isinstance(declared, dict) else []
    if kind not in kinds:
        return 422, {"error": f"{pack.id} declares no attention row kind {kind!r} (contributes.studio.attention: "
                              f"{', '.join(kinds) or 'none'})"}
    if not isinstance(row, str) or not N.is_valid_name(row):
        return 422, {"error": f"row {row!r} is not a row name (letters, digits, - and _): it names the row's file"}
    what = body.get("what")
    if not isinstance(what, str) or not what.strip():
        return 422, {"error": "the row needs what: the line the attention queue shows"}
    wait = _rate(req, pack.id)
    if wait is not None:
        return _too_fast(pack.id, wait)
    note = {"kind": kind, "what": what.strip(), "detail": str(body.get("detail") or ""), "since": time.time()}
    try:
        write_private_atomic(_folder(req.state_dir, pack.id) / ROWS / f"{row}.json", json.dumps(note, ensure_ascii=False))
    except OSError as e:
        return 500, {"error": f"cannot write {pack.id}'s attention row {row}: {e}"}
    _nudge(req)
    return 200, {"ok": True, "row": row, "kind": kind, "file": f"{ROWS}/{row}.json"}


def get_mode(req, pack):
    from halo_harness.packs import manifest_policy as MP
    from halo_harness.packs import mode_state as M
    rec = M.read(pack.id, req.state_dir)
    modes = [{"id": str(m.get("id")), "label": str(m.get("label") or m.get("id"))} for m in MP.modes_of(pack.manifest)]
    label = next((m["label"] for m in modes if m["id"] == rec["mode"]), None) if rec["mode"] else None
    return 200, {"pack": pack.id, "mode": rec["mode"], "label": label, "since": rec["since"], "by": rec["by"],
                 "armed": list(rec["armed"]), "modes": modes}


def dispatch(req):
    """The answer for one of these routes, else None (packs_studio_api goes on)."""
    m = _ROUTE.match(req.path)
    if not m:
        return None
    from halo_harness.studio.packs_studio_api import _gone, _pack
    pack = _pack(req, m["id"])
    if pack is None:
        return _gone(m["id"])
    if req.method != _METHOD[m["what"]]:
        return 405, {"error": "method not allowed"}
    refused = _granted(req, pack)
    if refused:
        return 403, {"error": refused}
    return {"publish": post_publish, "attention": post_attention, "mode": get_mode}[m["what"]](req, pack)
