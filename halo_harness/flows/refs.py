"""halo_harness.flows.refs -- the `$.<step id>.<path>` references a flow's
`inputs` and `set` values use, a small jsonpath subset:

    $.intake.brief                          a key
    $.marketing.positions.Copywriter.text   nested keys
    $.marketing.positions['Art Director']   a quoted key (spaces, dots)
    $.approve.accepted[0]                   a list index

`parse_ref(text)` -> `[step id, key or index, ...]` (ValueError on a bad
path), `resolve_ref(text, outputs)` reads it out of `{step id: output}`
(KeyError when the step or a key is missing), `resolve_value(value, outputs)`
walks a dict/list/str and replaces every ref string, `refs_in(value)` lists
the ref strings a value holds (validation reads it).
"""

from __future__ import annotations

import re

_NAME = re.compile(r"[A-Za-z0-9_\-]+")


def is_ref(value) -> bool:
    return isinstance(value, str) and value.startswith("$.")


def parse_ref(text: str) -> list:
    if not is_ref(text):
        raise ValueError(f"{text!r} is not a $.<step>.<path> reference")
    s, i, parts = text, 2, []
    while i < len(s):
        ch = s[i]
        if ch == ".":
            i += 1
            continue
        if ch == "[":
            end = s.find("]", i)
            if end < 0:
                raise ValueError(f"{text!r}: an unclosed [ at {i}")
            inner = s[i + 1:end].strip()
            if len(inner) >= 2 and inner[0] == inner[-1] and inner[0] in "'\"":
                parts.append(inner[1:-1])
            elif inner.lstrip("-").isdigit():
                parts.append(int(inner))
            else:
                raise ValueError(f"{text!r}: [{inner}] is neither a quoted key nor an index")
            i = end + 1
            continue
        m = _NAME.match(s, i)
        if not m:
            raise ValueError(f"{text!r}: unexpected {ch!r} at {i}")
        parts.append(m.group(0))
        i = m.end()
    if not parts or not isinstance(parts[0], str):
        raise ValueError(f"{text!r}: the reference names no step")
    return parts


def ref_step(text: str) -> str:
    return parse_ref(text)[0]


def resolve_ref(text: str, outputs: dict):
    parts = parse_ref(text)
    if parts[0] not in outputs:
        raise KeyError(f"{text}: step {parts[0]!r} has no output yet")
    cur = outputs[parts[0]]
    walked = "$." + parts[0]
    for p in parts[1:]:
        if isinstance(p, int):
            if not isinstance(cur, list) or not -len(cur) <= p < len(cur):
                raise KeyError(f"{text}: {walked} has no item [{p}]")
            cur = cur[p]
            walked += f"[{p}]"
        else:
            if not isinstance(cur, dict) or p not in cur:
                have = ", ".join(sorted(map(str, cur))) if isinstance(cur, dict) else type(cur).__name__
                raise KeyError(f"{text}: {walked} has no key {p!r} (has: {have or 'nothing'})")
            cur = cur[p]
            walked += f".{p}" if _NAME.fullmatch(p) else f"['{p}']"
    return cur


def resolve_value(value, outputs: dict):
    if is_ref(value):
        return resolve_ref(value, outputs)
    if isinstance(value, dict):
        return {k: resolve_value(v, outputs) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_value(v, outputs) for v in value]
    return value


def refs_in(value) -> list:
    if is_ref(value):
        return [value]
    if isinstance(value, dict):
        return [r for v in value.values() for r in refs_in(v)]
    if isinstance(value, list):
        return [r for v in value for r in refs_in(v)]
    return []
