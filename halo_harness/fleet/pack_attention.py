"""halo_harness.fleet.pack_attention -- a pack's own rows in the attention
queue (Halo 3.2.0.0 R3; fleet/attention.py builds the queue,
studio/fleet_answer.py routes the keys; docs/EXTENSION_API.md "Studio
contributions").

A pack declares its row kinds in pack.yaml under
`contributes.studio.attention` (`{<kind>: {label, keys: {a, r, s, o}}}`).
Its code raises a row by writing one JSON file in its data folder with the
stable surface (`ext.write_private(pack_id, "attention/<row>.json", text)`):

    {"kind": "review.ask", "what": "README.md: 3 findings wait for you", "detail": "two broken links"}

The row's kind is `pack:<id>:<kind>`, its chip the pack's label, its keys
the pack's labels. A, R or S answers it: Studio writes
`answers/<row>.json` (`{row, kind, key, answer, text, by, ts}`) beside it
and removes the row file, so the pack's code reads the answer; O opens the
pack's first section. A row of a disabled pack, or of a kind it does not
declare, is not listed.
"""

from __future__ import annotations

import json
import time

ROWS, ANSWERS = "attention", "answers"
PREFIX = "pack:"
MAX_ROWS = 50  # per pack


def _folder(state_dir, pack_id: str):
    from halo_harness.packs.discover import user_packs_dir
    return user_packs_dir(state_dir) / ".data" / pack_id


def pending(cwd, state_dir) -> list:
    """`[{pack, name, kind, row, what, detail, since, label, keys, section}]`: each row file of a running pack."""
    from halo_harness.packs import names as N
    from halo_harness.packs import studio_rules as R
    from halo_harness.packs.contribute import _active
    out = []
    for p in _active(cwd, state_dir):
        declared = R.studio_of(p.manifest).get("attention")
        if not isinstance(declared, dict) or not declared:
            continue
        secs = R.sections_of(p.manifest)
        section = N.qualify(p.id, secs[0]["id"]) if secs else ""
        try:
            files = sorted((_folder(state_dir, p.id) / ROWS).glob("*.json"))[:MAX_ROWS]
        except OSError:
            continue
        for f in files:
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
                since = f.stat().st_mtime
            except (OSError, ValueError):
                continue
            kind = raw.get("kind") if isinstance(raw, dict) else None
            decl = declared.get(kind) if isinstance(kind, str) else None
            if not N.is_valid_name(f.stem) or not isinstance(decl, dict):
                continue
            keys = {k: str(decl["keys"][k]) for k in R.ANSWER_KEYS if isinstance(decl.get("keys"), dict) and decl["keys"].get(k)}
            out.append({"pack": p.id, "name": p.name, "kind": kind, "row": f.stem, "what": str(raw.get("what") or kind),
                        "detail": str(raw.get("detail") or ""), "since": float(raw.get("since") or since),
                        "label": str(decl.get("label") or kind), "keys": keys, "section": section})
    return out


def rows(items: list, local: dict, seen: dict, now: float) -> list:
    from halo_harness.remote.bridge_cards import one_line
    out = []
    for it in items:
        kind = f"{PREFIX}{it['pack']}:{it['kind']}"
        rid = f"{kind}:{local.get('id') or '-'}:-:{it['row']}"
        out.append({"id": rid, "kind": kind, "harness": local.get("id"), "local": True,
                    "harness_name": local.get("name") or str(local.get("id") or "")[:8],
                    "session_id": None, "session": "", "agent_id": None, "agent": f"pack {it['pack']}",
                    "what": one_line(it["what"], 240), "detail": one_line(it["detail"], 240),
                    "since": seen.setdefault(rid, min(now, it["since"])), "keys": dict(it["keys"]), "remote_attached": 0,
                    "text_for": None, "label": it["label"],
                    "target": {"pack": it["pack"], "row": it["row"], "kind": it["kind"], "section": it["section"]}})
    return out


def answer(req, row: dict, key: str, text: str):
    """`(status, body, label)`: the answer file written, the row file removed."""
    from halo_harness.packs import names as N
    from halo_harness.privateio import write_private_atomic
    from halo_harness.studio.fleet_watch_sources import by
    t, label = row.get("target") or {}, row["keys"][key]
    pack_id, rid = str(t.get("pack") or ""), str(t.get("row") or "")
    if not N.is_valid_pack_id(pack_id) or not N.is_valid_name(rid):
        return 422, {"error": f"{row.get('id')!r} names no pack row"}, label
    base = _folder(req.state_dir, pack_id)
    note = {"row": rid, "kind": t.get("kind"), "key": key, "answer": label, "text": text, "by": by(req.state_dir),
            "ts": time.time()}
    try:
        write_private_atomic(base / ANSWERS / f"{rid}.json", json.dumps(note, ensure_ascii=False))
    except OSError as e:
        return 500, {"error": f"cannot write the answer for {pack_id}: {e}"}, label
    try:
        (base / ROWS / f"{rid}.json").unlink()
    except OSError:
        pass
    return 200, {"answered": True, "pack": pack_id, "row": rid, "file": f"{ANSWERS}/{rid}.json"}, label


def open_target(row: dict) -> dict:
    t = row.get("target") or {}
    return {"section": t.get("section") or "fleet", "panel": "" if t.get("section") else "fleet-attention"}
