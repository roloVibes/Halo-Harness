"""halo_harness.orchestra.index -- the claimable units of a file.

Keys:

* `<relpath>`                the whole file (always the first unit);
* `<relpath>#<name>`         a Python function or class (`ast`; a nested def
                             is `outer.inner`, a method `Class.method`);
* `<relpath>#<heading-slug>` a Markdown heading: the heading line through the
                             line before the NEXT heading of any level, so
                             heading units never share a line;
* `<relpath>#<name>`         other languages: a top-level `function name(`,
                             `def name(`, `func name(` or `fn name(` at line
                             start, up to the next one.

A repeated name gets `~2`, `~3`, ... so every key is unique. Lines are
1-based and inclusive. `overlaps(a, b)` decides from the keys alone: the
same file, and one is the whole file or the same unit or a dotted parent of
the other.
"""

from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional

_MD_SUFFIXES = (".md", ".markdown", ".mdx")
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$")
_FENCE = re.compile(r"^[ \t]{0,3}(```|~~~)")
_FALLBACK = re.compile(
    r"^(?:export\s+)?(?:default\s+)?(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?"
    r"(?:function\*?|def|func|fn)\s+(?:\([^)]*\)\s*)?([A-Za-z_$][\w$]*)\s*[(<]")


@dataclass
class Unit:
    key: str
    path: str        # repo-relative, forward slashes
    kind: str        # file | function | class | heading
    name: str        # "" for the whole file
    start_line: int
    end_line: int

    def to_dict(self) -> dict:
        return asdict(self)


def relpath(path, root=None) -> str:
    """`path` relative to `root` (or the current folder) with forward slashes;
    the path as given when it is not under that root."""
    p = Path(path)
    base = Path(root) if root is not None else Path.cwd()
    try:
        rel = p.resolve().relative_to(base.resolve())
        return rel.as_posix()
    except (ValueError, OSError):
        return p.as_posix()


def split_key(key: str) -> "tuple[str, str]":
    """`("basket.py", "Basket.total")` for `basket.py#Basket.total`; name "" for a whole file."""
    path, _, name = str(key).partition("#")
    return path, name


def covers(outer: str, inner: str) -> bool:
    """True when claiming `outer` also covers `inner`: same file and `outer`
    is the whole file, the same unit, or a dotted parent of `inner`."""
    p1, n1 = split_key(outer)
    p2, n2 = split_key(inner)
    if p1 != p2:
        return False
    return n1 == "" or n1 == n2 or n2.startswith(n1 + ".")


def overlaps(key_a: str, key_b: str) -> bool:
    """Same file, and one key covers the other (whole file overlaps every unit
    of its file; a function overlaps itself, its parents and its children)."""
    return covers(key_a, key_b) or covers(key_b, key_a)


def index_text(text: str, rel: str) -> list:
    """The units of `text`, keyed under `rel`. Whole file first."""
    lines = text.splitlines()
    whole = Unit(rel, rel, "file", "", 1, max(1, len(lines)))
    lower = rel.lower()
    if lower.endswith((".py", ".pyw", ".pyi")):
        units = _python_units(text, rel)
        if units is None:
            units = _fallback_units(lines, rel)
    elif lower.endswith(_MD_SUFFIXES):
        units = _markdown_units(lines, rel)
    else:
        units = _fallback_units(lines, rel)
    return [whole] + _unique(units)


def index_file(path, root=None) -> list:
    """The units of the file at `path`, keyed relative to `root` (default:
    the current folder). A missing or unreadable file is one whole-file unit."""
    rel = relpath(path, root)
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [Unit(rel, rel, "file", "", 1, 1)]
    return index_text(text, rel)


def unit_for_line(units: list, line: int) -> Optional[Unit]:
    """The innermost unit holding `line`; the whole-file unit for a line no
    function/heading holds; None for an empty list."""
    best = None
    for u in units:
        if u.start_line <= line <= u.end_line:
            if best is None or best.kind == "file" or (u.kind != "file" and
                                                        u.end_line - u.start_line < best.end_line - best.start_line):
                best = u
    if best is None and units:
        best = next((u for u in units if u.kind == "file"), units[0])
    return best


def units_for_lines(units: list, lines: Iterable[int]) -> list:
    """The distinct innermost units of every line, in first-seen order."""
    out, seen = [], set()
    for line in lines:
        u = unit_for_line(units, line)
        if u is not None and u.key not in seen:
            seen.add(u.key)
            out.append(u)
    return out


def _python_units(text: str, rel: str) -> Optional[list]:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    out: list = []

    def walk(body, prefix: str) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}{node.name}"
                start = min([node.lineno] + [d.lineno for d in node.decorator_list])
                end = getattr(node, "end_lineno", None) or node.lineno
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                out.append(Unit(f"{rel}#{name}", rel, kind, name, start, end))
                walk(node.body, name + ".")
            elif isinstance(node, (ast.If, ast.Try, ast.With, ast.AsyncWith, ast.For, ast.While)):
                # a def under `if TYPE_CHECKING:` / `try:` keeps its own outer name
                for part in ("body", "orelse", "finalbody"):
                    walk(getattr(node, part, []) or [], prefix)
                for handler in getattr(node, "handlers", []) or []:
                    walk(handler.body, prefix)

    walk(tree.body, "")
    return out


def slugify(text: str) -> str:
    """GitHub-style heading slug: lower case, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"[`*_~\[\]()]", "", text.strip().lower())
    text = re.sub(r"[^\w\- ]", "", text)
    return re.sub(r"\s", "-", text).strip("-") or "section"


def _markdown_units(lines: list, rel: str) -> list:
    heads, fenced = [], False
    for i, line in enumerate(lines, start=1):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        m = None if fenced else _HEADING.match(line)
        if m:
            heads.append((i, slugify(m.group(2))))
    out = []
    for n, (start, slug) in enumerate(heads):
        end = heads[n + 1][0] - 1 if n + 1 < len(heads) else max(start, len(lines))
        out.append(Unit(f"{rel}#{slug}", rel, "heading", slug, start, end))
    return out


def _fallback_units(lines: list, rel: str) -> list:
    hits = []
    for i, line in enumerate(lines, start=1):
        m = _FALLBACK.match(line)
        if m:
            hits.append((i, m.group(1)))
    out = []
    for n, (start, name) in enumerate(hits):
        end = hits[n + 1][0] - 1 if n + 1 < len(hits) else max(start, len(lines))
        while end > start and not lines[end - 1].strip():
            end -= 1
        out.append(Unit(f"{rel}#{name}", rel, "function", name, start, end))
    return out


def _unique(units: list) -> list:
    """Give a repeated key `~2`, `~3`, ... (and its dotted children follow it)."""
    seen: dict = {}
    renamed: dict = {}
    for u in units:
        name = u.name
        for old, new in renamed.items():
            if name.startswith(old + "."):
                name = new + name[len(old):]
                break
        if name in seen:
            seen[name] += 1
            new_name = f"{name}~{seen[name]}"
            renamed[u.name] = new_name
            name = new_name
        else:
            seen[name] = 1
        u.name = name
        u.key = f"{u.path}#{name}"
    return units
