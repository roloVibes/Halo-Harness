"""halo_harness.tools._gitignore -- the pure-Python Grep engine's file-set
rules, matching ripgrep's defaults as closely as a fallback can: hidden
entries (a leading dot) are skipped below the search root, and inside a git
checkout the `.gitignore` files from the repository root down to each
directory, plus `.git/info/exclude`, drop the paths they name (last matching
rule wins; `!` re-includes; a trailing `/` matches directories only; a `/`
in the pattern anchors it to its `.gitignore`'s folder). Outside a git
checkout only the hidden-entry rule applies, as with ripgrep.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


def _glob_to_regex(pat: str) -> str:
    out, i = [], 0
    while i < len(pat):
        c = pat[i]
        if c == "*":
            if pat[i:i + 3] == "**/":
                out.append("(?:.*/)?")
                i += 3
                continue
            if pat[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[":
            j = pat.find("]", i + 2)
            if j == -1:
                out.append(re.escape(c))
            else:
                body = pat[i + 1:j]
                if body[:1] == "!":
                    body = "^" + body[1:]
                out.append("[" + body.replace("\\", "\\\\") + "]")
                i = j
        elif c == "\\" and i + 1 < len(pat):
            i += 1
            out.append(re.escape(pat[i]))
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


class _Rule:
    def __init__(self, line: str, anchor: Path):
        self.negate = line.startswith("!")
        if self.negate:
            line = line[1:]
        self.dir_only = line.endswith("/")
        line = line.rstrip("/")
        self.anchored = "/" in line
        self.regex = re.compile("^" + _glob_to_regex(line.lstrip("/")) + "$")
        self.anchor = anchor

    def hits(self, path: Path, is_dir: bool) -> bool:
        if self.dir_only and not is_dir:
            return False
        try:
            rel = path.relative_to(self.anchor).as_posix()
        except ValueError:
            return False
        return bool(self.regex.match(rel if self.anchored else path.name))


def _load(file: Path, anchor: Path) -> list:
    try:
        lines = file.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rules = []
    for raw in lines:
        line = raw.rstrip() if not raw.endswith("\\ ") else raw
        if line and not line.startswith("#"):
            try:
                rules.append(_Rule(line, anchor))
            except re.error:
                continue
    return rules


def _repo_root(base: Path) -> Optional[Path]:
    for d in [base, *base.parents]:
        if (d / ".git").exists():
            return d
    return None


class Ignores:
    """Decides which entries below `base` the Python Grep engine skips."""

    def __init__(self, base: Path):
        self.base = base
        self.root = _repo_root(base)
        self._chain: dict = {}
        if self.root is not None:
            top = _load(self.root / ".git" / "info" / "exclude", self.root)
            for d in reversed([base, *base.parents][: len(base.parts) - len(self.root.parts) + 1]):
                top = top + _load(d / ".gitignore", d)
            self._chain[base] = top

    def enter(self, directory: Path) -> None:
        """Called when the walk reaches `directory` (below base): load its own .gitignore."""
        if self.root is not None and directory not in self._chain:
            self._chain[directory] = self._chain.get(directory.parent, []) + _load(directory / ".gitignore", directory)

    def skips(self, directory: Path, name: str, is_dir: bool) -> bool:
        if name.startswith("."):
            return True
        if self.root is None:
            return False
        path, verdict = directory / name, False
        for rule in self._chain.get(directory, []):
            if rule.hits(path, is_dir):
                verdict = not rule.negate
        return verdict
