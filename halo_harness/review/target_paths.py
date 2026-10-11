"""halo_harness.review.target_paths -- the "paths and globs, reviewed as they are" target form."""

from __future__ import annotations

import glob
import os
from pathlib import Path

from halo_harness.review.target_model import ReviewTarget, TargetError

_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build", ".mypy_cache"}
MAX_FILE_BYTES = 200_000
_MAX_PATH_FILES = 300


def _expand_paths(cwd: Path, tokens: "list[str]") -> "list[Path]":
    found: "list[Path]" = []
    for tok in tokens:
        pattern = tok if os.path.isabs(tok) else str(cwd / tok)
        matches = glob.glob(pattern, recursive=True) if any(c in tok for c in "*?[") else [pattern]
        for m in sorted(matches):
            p = Path(m)
            if p.is_dir():
                for root, dirs, names in os.walk(p):
                    dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS and not d.startswith("."))
                    found.extend(Path(root) / n for n in sorted(names) if not n.startswith("."))
            elif p.is_file():
                found.append(p)
    seen, out = set(), []
    for p in found:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def paths_target(cwd: Path, tokens: "list[str]") -> ReviewTarget:
    chunks: "dict[str, str]" = {}
    for p in _expand_paths(cwd, tokens):
        if len(chunks) >= _MAX_PATH_FILES:
            break
        try:
            if p.stat().st_size > MAX_FILE_BYTES:
                continue
            data = p.read_bytes()
        except OSError:
            continue
        if b"\0" in data:
            continue
        try:
            rel = p.resolve().relative_to(cwd.resolve()).as_posix()
        except ValueError:
            rel = p.as_posix()
        body = "".join(f"{i:>5}| {ln}\n" for i, ln in enumerate(data.decode("utf-8", "replace").splitlines(), 1))
        chunks[rel] = f"=== {rel} ===\n{body}"
    if not chunks:
        raise TargetError(f"nothing to review: no readable text files match {' '.join(tokens)!r}")
    label = "files: " + (", ".join(tokens) if len(tokens) <= 3 else f"{', '.join(tokens[:3])} +{len(tokens) - 3}")
    return ReviewTarget("paths", label, "".join(chunks.values()), list(chunks), cwd=str(cwd), chunks=chunks)
