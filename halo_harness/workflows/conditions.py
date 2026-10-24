"""halo_harness.workflows.conditions -- a stage's `when` (Halo 3.2.0.0 R5,
docs/WORKFLOWS.md "Conditions").

    when: {input: style, equals: long}             resolved at compile time from the inputs
    when: {output: judge.verdict, not-empty: true} resolved when the stage's lane starts, from what
                                                   its upstream lanes gave (orchestra/handoff.py `gave`)
    when: {output: judge.report, key: verdict, equals: fix}   a key of an artifact's JSON

`exists` is whether the value is there at all (`exists: false` asks for its
absence), `not-empty` whether it holds something (text that is not blank, a
list or mapping with items), `equals` compares the text (stripped) or the
JSON value as written. Each answers `(ok, why)`: `why` is the line a skipped
stage shows ("skipped: when input style equals long is false (it is short)").
"""

from __future__ import annotations

import json
from pathlib import Path

CONDITIONS = ("exists", "equals", "not-empty")


def describe(when: dict) -> str:
    what = f"input {when['input']}" if "input" in when else f"output {when.get('output')}"
    what += f" key {when['key']}" if when.get("key") else ""
    if "equals" in when:
        return f"{what} equals {when['equals']!r}"
    if "not-empty" in when:
        return f"{what} is {'not empty' if when['not-empty'] else 'empty'}"
    return f"{what} {'exists' if when.get('exists', True) else 'does not exist'}"


def _key(value, key):
    for part in str(key or "").split(".") if key else []:
        value = value.get(part) if isinstance(value, dict) else None
    return value


def _holds(when: dict, values: list) -> bool:
    """`values`: what the input or the output holds ([] = it is not there)."""
    if "equals" in when:
        want = when["equals"]
        return any(v == want or (isinstance(v, str) and v.strip() == str(want)) for v in values)
    if "not-empty" in when:
        full = any(v not in (None, "", [], {}) and not (isinstance(v, str) and not v.strip()) for v in values)
        return full if when["not-empty"] else not full
    return bool(values) if when.get("exists", True) else not values


def _say(when: dict, ok: bool, seen: list) -> str:
    if ok:
        return ""
    shown = "nothing" if not seen else ", ".join(repr(v if not isinstance(v, str) else v.strip()[:40]) for v in seen[:3])
    return f"when {describe(when)} is false (it is {shown})"


def on_input(when, values: dict) -> "tuple[bool, str]":
    if not isinstance(when, dict) or "input" not in when:
        return True, ""
    name = when["input"]
    got = [_key(values[name], when.get("key")) if when.get("key") else values[name]] if name in values else []
    got = [g for g in got if g is not None]
    ok = _holds(when, got)
    return ok, _say(when, ok, got)


def output_values(run_dir, rows: list, key=None) -> list:
    """What `gave` rows hold: each file's text, or the value of `key` in its JSON."""
    out = []
    for row in rows:
        path = Path(run_dir) / str(row.get("path") or "")
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if key:
            try:
                value = _key(json.loads(text), key)
            except ValueError:
                value = None
            if value is not None:
                out.append(value)
        else:
            out.append(text)
    return out


def on_output(when, run_dir, upstream_lanes: list) -> "tuple[bool, str]":
    """`upstream_lanes`: the lanes of the stage `when.output` names (a skipped one gave nothing)."""
    if not isinstance(when, dict) or "output" not in when:
        return True, ""
    _stage, _, give = str(when["output"]).partition(".")
    rows = []
    for lane in upstream_lanes:
        data = lane.data()
        if data.get("skipped"):
            continue
        rows += [g for g in data.get("gave") or [] if g.get("name") == give
                 or (give == "summary" and g.get("kind") == "summary")]
    got = output_values(run_dir, rows, when.get("key"))
    ok = _holds(when, got)
    return ok, _say(when, ok, got)
