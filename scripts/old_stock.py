"""scripts/old_stock.py -- write halo_harness/crew/old_stock.txt from git history (Halo 3.6.0.0 R5c).

Halo copied its shipped lineups, bios and workflow squares into ~/.halo/{teams,agents,workflows} once and never
overwrote them, so a long-time user's home holds the version of the day it was copied. old_stock.txt names every
version of every one of those files that ever shipped -- `<kind>/<file name> <sha256 of its bytes, LF line ends>` --
so crew/old_files.py never counts Halo's own copy as the user's.

    python scripts/old_stock.py           write the file (from the history of the checkout it runs in)
    python scripts/old_stock.py --check   exit 1 when the file misses a version the history has

Read: every blob any commit ever had under halo_harness/templates/{teams,agents,workflows}/ (all refs).
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "halo_harness" / "crew" / "old_stock.txt"
FOLDERS = {"halo_harness/templates/teams/": "teams", "halo_harness/templates/agents/": "agents",
           "halo_harness/templates/workflows/": "workflows"}
SUFFIXES = (".yaml", ".yml", ".md", ".json")
HEAD = """# 3.6.0.0 R5c: every version of every lineup, bio and square Halo ever shipped (and copied into ~/.halo), by name
# and the sha256 of its bytes (LF line ends): a file in the old folders with one of these is Halo's own copy, never
# named as the user's (crew/old_files.py). Written by scripts/old_stock.py from git history; do not edit by hand.
"""


def _git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(REPO), *args], check=True, capture_output=True).stdout


def blobs() -> "set[tuple[str, str]]":
    """{(kind/file name, blob id)} of every version under the template folders, on every ref."""
    out: set = set()
    raw = _git("log", "--all", "--no-renames", "--pretty=format:", "--raw", "--no-abbrev", "--", *FOLDERS)
    for line in raw.decode("utf-8", "replace").splitlines():
        if not line.startswith(":") or "\t" not in line:
            continue
        meta, path = line.split("\t", 1)
        new = meta.split()[3]
        kind = next((k for f, k in FOLDERS.items() if path.startswith(f) and "/" not in path[len(f):]), None)
        if kind and path.endswith(SUFFIXES) and set(new) != {"0"}:
            out.add((f"{kind}/{path.rsplit('/', 1)[-1]}", new))
    return out


def lines() -> "list[str]":
    out = set()
    for name, blob in blobs():
        data = _git("cat-file", "blob", blob).replace(b"\r\n", b"\n")
        out.add(f"{name} {hashlib.sha256(data).hexdigest()}")
    return sorted(out)


def main(argv) -> int:
    want = lines()
    if "--check" in argv:
        have = set(ln.strip() for ln in OUT.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#"))
        missing = [w for w in want if w not in have]
        print(f"{len(want)} versions in history, {len(missing)} missing from {OUT.name}")
        for m in missing[:20]:
            print(f"  {m}")
        return 1 if missing else 0
    OUT.write_text(HEAD + "\n".join(want) + "\n", encoding="utf-8", newline="\n")
    print(f"{OUT.relative_to(REPO).as_posix()}: {len(want)} versions")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
