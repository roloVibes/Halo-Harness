"""tests.helpers.capture_source -- the Studio capture tools' source, parsed
(Halo 3.1.7.0 R2; tests/test_capture_identity.py): which call serves Studio,
which counts or shoots a page, which guards it, and whether one call runs on
every path before another inside one function (`dominates`: the lowest block
holding both decides; a call under an `if`, a loop or an `except` below that
block does not run on every path)."""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOLS = ("capture_studio", "capture_orchestra", "capture_roles", "capture_design", "capture_fleet", "capture_team",
         "capture_start", "capture_session_anim", "capture_packs", "capture_setup",
         "capture_settings", "capture_ollama")  # capture_packs: 3.2.0.0 R7; capture_setup: 3.3.0.0 R4; capture_settings: 3.3.3.0 R2; capture_ollama: 3.3.4.0 R5
SERVES = {"serve", "start_server", "StudioFleetRig", "PlanRig", "CoachRig", "StudioTeamRig"}
READS = {"shot", "crop_shot", "write_gif", "film", "counts", "shell_counts"}  # a picture, or the DOM's counts
GUARDS = {"guard", "guard_page", "checked_dump"}
PRIMITIVES = {"serve", "frame", *READS}  # the definitions themselves; their callers are what is checked
BRANCHES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler)


def calls(fn) -> list:
    """[(name, call node)] in `fn`; a `chrome([... --screenshot ...])` run is named `shot`."""
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            if name in ("chrome", "one_shot") and "--screenshot" in ast.unparse(node):
                name = "shot"
            out.append((name, node))
    return out


def parents_of(fn) -> dict:
    return {c: p for p in ast.walk(fn) for c in ast.iter_child_nodes(p)}


def _blocks(node, parents: dict) -> list:
    """[(block id, index, under a branch, statement)] for each statement above `node`, innermost first."""
    out, cond, child = [], False, node
    while child in parents:
        p = parents[child]
        if isinstance(child, ast.stmt):
            for field in ("body", "orelse", "finalbody"):
                block = getattr(p, field, None)
                if isinstance(block, list) and any(s is child for s in block):
                    out.append((id(block), next(i for i, s in enumerate(block) if s is child), cond, child))
                    break
        cond = cond or isinstance(p, BRANCHES)
        child = p
    return out


def dominates(g, r, parents: dict) -> bool:
    """Whether call `g` runs on every path before call `r`."""
    seen = {b: i for b, i, _c, _s in _blocks(r, parents)}
    for b, i, cond, _s in _blocks(g, parents):
        if b in seen:
            j = seen[b]
            if cond or i > j:
                return False
            return i < j or any(n is g for n in ast.walk(r)) or (g.lineno, g.col_offset) < (r.lineno, r.col_offset)
    return False


def unguarded(fn) -> "tuple[list, int]":
    """([(name, line)] of the counts and pictures no guard runs before, how many there are)."""
    parents, cs = parents_of(fn), calls(fn)
    guards = [n for name, n in cs if name in GUARDS]
    reads = [(name, n) for name, n in cs if name in READS]
    return [(name, n.lineno) for name, n in reads if not any(dominates(g, n, parents) for g in guards)], len(reads)


def missing_first(fn, first: str, later: set) -> list:
    """[(name, line)] of the `later` calls no `first` call runs before."""
    parents, cs = parents_of(fn), calls(fn)
    before = [n for name, n in cs if name == first]
    return [(name, n.lineno) for name, n in cs if name in later and not any(dominates(b, n, parents) for b in before)]


def functions(mod: str) -> list:
    """Every function of tools/<mod>.py but the primitives."""
    tree = ast.parse((REPO / "tools" / f"{mod}.py").read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name not in PRIMITIVES]
