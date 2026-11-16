"""halo_harness.crew.changes_map -- a map's changes, applied, and the switch `crew.map` (Halo 3.6.0.0 R3; crew/changes.py).

    {op: map_box_add,     box: {id, agent | workflow}}
    {op: map_box_remove,  id}                         the box and every line that touches it
    {op: map_line_add,    line: {from, to, when}}
    {op: map_line_set,    from, to, when}
    {op: map_line_remove, from, to}
    {op: map_set,         field: caps | main, value}

A row whose box or line is not there leaves the file as it was; crew/changes.py plan() then checks the whole file with
map_problems (a circle is refused there, named) before anything is written.

`map_use` rows target `use:crew.map` (op `{op: use, value: <map> | None}`): the file they write is config.json, whose
before-image the undo keeps like any crew file's. `config_text(value)` is that file with `crew.map` set (None: taken out).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

USE_TARGET = "use:crew.map"


def _same(ln: dict, a, b) -> bool:
    return isinstance(ln, dict) and ln.get("from") == a and ln.get("to") == b


def apply_map(body: dict, op: dict) -> dict:
    body = copy.deepcopy(body)
    boxes = [b for b in body.get("boxes") or [] if isinstance(b, dict)]
    lines = [ln for ln in body.get("lines") or [] if isinstance(ln, dict)]
    o = op.get("op")
    if o == "map_box_add" and isinstance(op.get("box"), dict) and not any(b.get("id") == op["box"].get("id") for b in boxes):
        boxes.append(dict(op["box"]))
    elif o == "map_box_remove":
        boxes = [b for b in boxes if b.get("id") != op.get("id")]
        lines = [ln for ln in lines if op.get("id") not in (ln.get("from"), ln.get("to"))]
    elif o == "map_line_add" and isinstance(op.get("line"), dict):
        ln = op["line"]
        if not any(_same(x, ln.get("from"), ln.get("to")) for x in lines):
            lines.append({"from": ln.get("from"), "to": ln.get("to"), "when": ln.get("when") or "main-decides"})
    elif o == "map_line_set":
        lines = [{**ln, "when": op.get("when") or "main-decides"} if _same(ln, op.get("from"), op.get("to")) else ln for ln in lines]
    elif o == "map_line_remove":
        lines = [ln for ln in lines if not _same(ln, op.get("from"), op.get("to"))]
    elif o == "map_set":
        if op.get("value") in (None, "", {}):
            body.pop(op.get("field"), None)
        else:
            body[op["field"]] = op["value"]
    body["boxes"], body["lines"] = boxes, lines
    return body


def config_path() -> Path:
    from halo_harness.theme import _config_path
    return _config_path()


ONE_MODEL = "one-model"  # "One model for everything": roles off and no map (studio/setup_state.py's row)


def config_text(value) -> str:
    """config.json as it would be with `crew.map` = value; the other keys as they are. 3.6.0.0 R5 fix: None or the
    shipped default map takes the key out (the default: sessions draw the starter map); ONE_MODEL ("One model for
    everything") takes it out and sets `roles.enabled` false (no map at all); any other choice turns roles back on
    when they were off."""
    from halo_harness.crew.compile import DEFAULT_MAP, _roles_on
    from halo_harness.theme import _load_config_for_write
    data = _load_config_for_write(config_path())  # 3.6.0.0 fx: CorruptConfigError, never {} written over the file
    crew = data.get("crew") if isinstance(data.get("crew"), dict) else {}
    crew = {k: v for k, v in crew.items() if k != "map"}
    if value and value not in (DEFAULT_MAP, ONE_MODEL):
        crew["map"] = value
    if crew:
        data["crew"] = crew
    else:
        data.pop("crew", None)
    if value == ONE_MODEL or not _roles_on():
        roles = data.get("roles") if isinstance(data.get("roles"), dict) else {}
        data["roles"] = {**roles, "enabled": value != ONE_MODEL}
    return json.dumps(data, indent=2) + "\n"


def write_config(text) -> None:
    """config.json written as Halo writes it (0600 from birth), or removed when `text` is None (an undo of a first write)."""
    path = config_path()
    if text is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    from halo_harness.privateio import write_private_atomic
    path.parent.mkdir(parents=True, exist_ok=True)
    write_private_atomic(path, text)
