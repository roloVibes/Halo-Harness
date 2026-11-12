"""tests.helpers.studio_write_routes -- every route Studio's server answers, as the code says it (Halo 3.4.1.2,
SERVERS-2: "a test enumerates every POST/PUT/PATCH/DELETE handler").

Routes live in many shapes: `ROUTES` lists of (method, pattern, fn), dicts keyed by (method, path) or by path with
(method, fn) or {method: fn}, and dispatch functions that compare `path` / `req.path` with literals or match a module's
compiled pattern. `harvest()` imports every studio/*.py module and the shipped packs' server/*.py, reads the tables at
run time (f-string patterns are evaluated there) and reads the dispatch functions' literals and patterns from the AST:

    rows = harvest()     # [{"key": "<method> <pattern>", "method": "POST" | "*", "path": "<a concrete path>", ...}]

`method` "*" is a candidate whose method the code decides inside the handler (sent as POST, PUT and DELETE).
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STUDIO = REPO / "halo_harness" / "studio"
PACKS = REPO / "halo_harness" / "templates" / "packs"
WRITES = ("POST", "PUT", "PATCH", "DELETE")
SAMPLE = {"sid": "s-1", "hid": "local", "aid": "main", "name": "x", "id": "nopack", "mid": "m-20260101-abcd",
          "pid": "1", "role": "main", "rid": "r-1", "run": "r-1", "cid": "c-1", "block": "b", "act": "pull",
          "verb": "on", "what": "x", "path": "x", "tid": "t-1", "slug": "s", "aid2": "a"}
_GROUP = re.compile(r"\(\?P<(\w+)>(?:[^()]|\([^()]*\))*\)")


def sample(pattern: str) -> str:
    """A concrete path a pattern matches (named groups filled from SAMPLE), or the literal itself."""
    p = _GROUP.sub(lambda m: SAMPLE.get(m.group(1), "x"), pattern.strip("^$"))
    p = re.sub(r"\(\?:([^()|]*)(\|[^()]*)?\)\??", r"\1", p)  # (?:a|b)? -> a
    p = re.sub(r"\(([a-z-]+)(\|[a-z|-]+)?\)", r"\1", p)  # (enable|grant) -> enable
    p = p.replace("\\.", ".").replace("[^/]+", "x").replace(".+", "x").replace("\\d{1,3}", "1").replace("\\d+", "1")
    return p


def _modules():
    for f in sorted(STUDIO.glob("*.py")):
        yield f, "halo_harness.studio." + f.stem
    for f in sorted(PACKS.glob("*/server/*.py")):
        pack = f.parts[-3]
        if pack.replace("-", "_") == pack:
            yield f, f"halo_harness.templates.packs.{pack}.server.{f.stem}"


def _table_rows(mod, origin: str):
    for attr, val in vars(mod).items():
        if attr.startswith("__"):
            continue
        items = []
        if isinstance(val, list):
            items = [(m, p) for m, p, *_ in (t for t in val if isinstance(t, tuple) and len(t) >= 3)
                     if isinstance(m, str) and isinstance(p, str)]
        elif isinstance(val, dict):
            for k, v in val.items():
                if isinstance(k, tuple) and len(k) == 2 and all(isinstance(x, str) for x in k):
                    items.append(k)
                elif isinstance(k, str) and isinstance(v, tuple) and v and isinstance(v[0], str):
                    items.append((v[0], k))
                elif isinstance(k, str) and isinstance(v, dict):
                    items += [(m, k) for m in v if isinstance(m, str)]
        for method, pattern in items:
            if method.upper() in WRITES:
                yield {"key": f"{method} {pattern}", "method": method, "path": sample(pattern), "origin": origin,
                       "fn": val[(method, pattern)] if isinstance(val, dict) and (method, pattern) in val else None}


def _literals(source: str):
    """Paths a dispatch function compares `path` with, and the patterns a module compiles at its top."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, (ast.Name, ast.Attribute)):
            name = node.left.id if isinstance(node.left, ast.Name) else node.left.attr
            if name != "path":
                continue
            for comp in node.comparators:
                vals = [comp] if isinstance(comp, ast.Constant) else list(getattr(comp, "elts", []))
                yield from (v.value for v in vals if isinstance(v, ast.Constant) and isinstance(v.value, str))
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and getattr(node.value.func, "attr", "") == "compile":
            yield ("re", node.targets[0].id if isinstance(node.targets[0], ast.Name) else "")


def harvest() -> list:
    rows, seen = [], set()
    for f, name in _modules():
        mod = importlib.import_module(name)
        origin = str(f.relative_to(REPO)).replace("\\", "/")
        for row in _table_rows(mod, origin):
            if row["key"] not in seen:
                seen.add(row["key"])
                rows.append(row)
        if not name.startswith("halo_harness.studio."):
            continue
        for lit in _literals(f.read_text(encoding="utf-8")):
            if isinstance(lit, tuple):
                pat = getattr(getattr(mod, lit[1], None), "pattern", None)
                if not isinstance(pat, str) or not pat.startswith("^") or "/" not in pat:
                    continue
                pattern = pat
            else:
                pattern = lit
            if not re.match(r"^\^?[a-z][a-z0-9-]*", pattern) or " " in pattern:
                continue
            key = f"* {pattern}"
            if key not in seen and not any(r["key"].endswith(" " + pattern) for r in rows):
                seen.add(key)
                rows.append({"key": key, "method": "*", "path": sample(pattern), "origin": origin, "fn": None})
    return rows
