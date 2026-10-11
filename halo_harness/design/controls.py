"""halo_harness.design.controls -- apply a knob to an artboard without a model
call (Halo 3.0.1.0 round D3). A `css:--name` control target is a CSS custom
property on `:root` in the artboard's index.html; moving the knob rewrites
that one declaration in place (adding it to the first `:root` block, or a new
`<style>` block, when the page does not declare it yet) and leaves every other
declaration untouched.
"""

from __future__ import annotations

import re

_ROOT = re.compile(r"(:root\s*\{)([^}]*)(\})", re.I)
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_UNIT = re.compile(r"^-?[\d.]+\s*([a-zA-Z%]*)\s*$")


def _name(var: str) -> str:
    return "--" + str(var).strip().lstrip("-")


def _decl(name: str) -> "re.Pattern":
    return re.compile(r"(?<![\w-])" + re.escape(name) + r"(\s*:\s*)([^;}]*)")


def read_css_var(html: str, var: str) -> str:
    """The value the first `:root` block gives `var`, or ''."""
    decl = _decl(_name(var))
    for m in _ROOT.finditer(html):
        hit = decl.search(m.group(2))
        if hit:
            return hit.group(2).strip()
    return ""


def css_value(html: str, var: str, value, unit: str = "") -> str:
    """The text to write for `value`: a bare number takes `unit`, or the unit
    the page already uses for that variable (16px -> 24 becomes 24px)."""
    text = ("%g" % value) if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value).strip()
    if _NUMBER.match(text):
        if unit:
            return text + unit
        old = _UNIT.match(read_css_var(html, var))
        return text + (old.group(1) if old else "")
    return text


def apply_css_control(html: str, var: str, value) -> str:
    """Return `html` with `var` set to `value` in its `:root` block(s)."""
    value = str(value).strip()
    if not value or re.search(r"[;{}<>]", value):
        raise ValueError(f"{value!r} is not a usable CSS value (no ; {{ }} < >)")
    name = _name(var)
    decl = _decl(name)
    hit = False

    def fix(m: "re.Match") -> str:
        nonlocal hit
        if not decl.search(m.group(2)):
            return m.group(0)
        hit = True
        return m.group(1) + decl.sub(lambda d: name + d.group(1) + value + d.group(2)[len(d.group(2).rstrip()):], m.group(2)) + m.group(3)

    out = _ROOT.sub(fix, html)
    if hit:
        return out
    m = _ROOT.search(out)
    if m:
        body = m.group(2).rstrip()
        sep = "" if (not body or body.endswith(";")) else ";"
        return out[:m.start()] + m.group(1) + body + sep + f"{name}:{value};" + m.group(3) + out[m.end():]
    block = f"<style>:root{{{name}:{value};}}</style>"
    head = re.search(r"</head>", out, re.I)
    if head:
        return out[:head.start()] + block + out[head.start():]
    return block + out
