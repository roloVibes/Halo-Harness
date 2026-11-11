"""scripts/prepush_tree.py -- the two things scripts/prepush.py settles before its tiers (Halo 3.4.0.0 D).

    prune(repo)        remove every directory under halo_harness/ and tests/ that holds nothing but __pycache__ (a
                       package a round removed, left importable by its .pyc files: test_core_focus failed on one three
                       times); returns the removed paths, relative to the repo, deepest first
    bash_fix(env)      (prefix, line): on Windows, when the `bash` on PATH is WSL's (C:\\Windows\\System32\\bash.exe,
                       what PowerShell finds first) and Git's bash is installed, `prefix` is Git's bin folders for the
                       suites' PATH and `line` says so; when Git's bash cannot be found, `prefix` is None and `line`
                       is the fix (the gate stops); elsewhere ("", "")
    dist_digest(repo)  the digest of Studio's static/dist (the build must not change it)
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

SKIP = {"node_modules", ".git", "dist", ".venv"}


def _only_cache(d: Path, gone: set) -> bool:
    try:
        kids = list(d.iterdir())
    except OSError:
        return False
    return bool(kids) and all(k.is_dir() and (k.name == "__pycache__" or k in gone) for k in kids)


def prune(repo: Path) -> "list[str]":
    out, gone = [], set()
    for top in ("halo_harness", "tests"):
        root, seen = repo / top, []
        for here, dirs, _files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in SKIP and x != "__pycache__"]  # never into node_modules
            seen.append(Path(here))
        for d in reversed(seen):  # deepest first, so a parent of a removed folder can go too
            if d != root and _only_cache(d, gone):
                shutil.rmtree(d, ignore_errors=True)
                if not d.exists():
                    gone.add(d)
                    out.append(d.relative_to(repo).as_posix())
    return out


def _is_wsl(path: str) -> bool:
    p = path.replace("/", "\\").lower()
    return p.endswith("\\system32\\bash.exe") or "\\windowsapps\\" in p


def git_bash() -> "Path | None":
    git = shutil.which("git")
    if not git:
        return None
    for base in (Path(git).resolve().parent.parent, Path(git).resolve().parent.parent.parent):
        if (base / "bin" / "bash.exe").is_file():
            return base / "bin" / "bash.exe"
    return None


def bash_fix(env: "dict | None" = None) -> "tuple[str | None, str]":
    if os.name != "nt":
        return "", ""
    found = shutil.which("bash", path=(env or os.environ).get("PATH"))
    if not found or not _is_wsl(found):
        return "", ""
    gb = git_bash()
    if gb is None:
        return None, (f"prepush: `bash` here is WSL's ({found}) and Git's bash was not found: run the gate from Git "
                      "Bash, or put Git's bin folder first on PATH")
    root = gb.parent.parent
    prefix = os.pathsep.join(str(p) for p in (root / "bin", root / "usr" / "bin"))
    return prefix, f"prepush: `bash` here is WSL's ({found}); the suites use Git's bash ({gb}) instead"


def dist_digest(repo: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    for f in sorted((repo / "halo_harness" / "studio" / "static" / "dist").rglob("*")):
        if f.is_file():
            h.update(f.name.encode() + b"/" + f.read_bytes())
    return h.hexdigest()
