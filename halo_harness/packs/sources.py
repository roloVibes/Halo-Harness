"""halo_harness.packs.sources -- where `halo pack install <id>` looks, and what
each place holds (Halo 3.2.0.0 R6: `halo pack sources`, `halo pack list
--available`, the Pack Manager's Sources panel).

    search()                    config `packs.sources` (folders and git urls), then the shipped
                                folder halo_harness/templates/packs/ (the reference pack), last
    listing(cwd=, state_dir=)   [{source, kind: folder | url | shipped, configured, exists, problem,
                                  packs: [{id, name, version, description, path, installed, problems}]}]
    available(cwd=, state_dir=) the packs of every source not installed here, one per id, first source first
    add(source) / remove(source) -> (ok, lines)   packs.sources in ~/.halo/config.json

A folder source holds packs (`<source>/<id>/pack.yaml`) or is one; a git url
is one pack, named by its last path part, and is cloned only when it is
installed (a listing fetches nothing).
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.packs.fetch import configured_sources
from halo_harness.packs.names import is_url

URL_LINE = "a git url: Install clones it"


def shipped_dir() -> Path:
    """The packs Halo ships (halo_harness/templates/packs/): the last place a bare id is looked for."""
    return Path(__file__).resolve().parent.parent / "templates" / "packs"


def search() -> "list[str]":
    return configured_sources() + [str(shipped_dir())]


def url_id(url: str) -> str:
    """The pack id a git url names: its last path part without `.git`."""
    return url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")


def _folders(base: Path) -> "list[Path]":
    if (base / "pack.yaml").is_file():
        return [base]
    try:
        return sorted(d for d in base.iterdir() if d.is_dir() and not d.name.startswith(".") and (d / "pack.yaml").is_file())
    except OSError:
        return []


def _installed(cwd, state_dir) -> "set[str]":
    from halo_harness.packs.registry import snapshot
    return {p.id for p in snapshot(cwd=cwd, state_dir=state_dir).packs}


def _row(src: str, *, configured: bool, have: "set[str]") -> dict:
    from halo_harness.packs.discover import read_pack
    kind = "url" if is_url(src) else ("folder" if configured else "shipped")
    out = {"source": src, "kind": kind, "configured": configured, "exists": True, "problem": "", "packs": []}
    if kind == "url":
        pid = url_id(src)
        out["packs"] = [{"id": pid, "name": pid, "version": "", "description": URL_LINE, "path": src,
                         "installed": pid in have, "problems": []}]
        return out
    base = Path(src).expanduser()
    if not base.is_dir():
        out.update(exists=False, problem=f"packs.sources: {src} is not a folder")
        return out
    for folder in _folders(base):
        pack = read_pack(folder, "source", folder_is_id=False)
        out["packs"].append({"id": pack.id, "name": pack.name, "version": pack.version, "description": pack.description,
                             "path": str(folder), "installed": pack.id in have, "problems": list(pack.problems)})
    return out


def listing(*, cwd=None, state_dir=None) -> "list[dict]":
    have = _installed(cwd, state_dir)
    rows = [_row(s, configured=True, have=have) for s in configured_sources()]
    return rows + [_row(str(shipped_dir()), configured=False, have=have)]


def available(*, cwd=None, state_dir=None) -> "list[dict]":
    """`[{id, name, version, description, path, source}]`: what `halo pack install <id>` would install."""
    seen, out = set(), []
    for row in listing(cwd=cwd, state_dir=state_dir):
        for p in row["packs"]:
            if p["id"] in seen or p["installed"]:
                seen.add(p["id"])
                continue
            seen.add(p["id"])
            out.append({**{k: p[k] for k in ("id", "name", "version", "description", "path")}, "source": row["source"]})
    return out


def _write(values: "list[str]") -> "list[str]":
    from halo_harness.theme import set_config_value
    try:
        set_config_value("packs.sources", values)
    except Exception as e:  # CorruptConfigError: config.json does not parse
        return [str(e)]
    return []


def add(source: str) -> "tuple[bool, list[str]]":
    src = str(source or "").strip()
    if not src:
        return False, ["give a folder of packs, a pack's folder or a git url"]
    if not is_url(src) and not Path(src).expanduser().is_dir():
        return False, [f"{src} is neither a folder nor a git url"]
    have = configured_sources()
    if src in have:
        return True, [f"{src} is already in packs.sources"]
    problems = _write(have + [src])
    if problems:
        return False, problems
    if is_url(src):
        return True, [f"added {src} to packs.sources (a git url: halo pack install {url_id(src)} clones it)"]
    names = sorted(p.name for p in _folders(Path(src).expanduser()))
    return True, [f"added {src} to packs.sources" + (f" (it holds {', '.join(names)})" if names else " (it holds no pack yet)")]


def remove(source: str) -> "tuple[bool, list[str]]":
    src = str(source or "").strip()
    have = configured_sources()
    if src not in have:
        if src and Path(src).expanduser().resolve() == shipped_dir():
            return False, ["the packs Halo ships are always looked in last; they are not in packs.sources"]
        return False, [f"{src or '(nothing)'} is not in packs.sources (halo pack sources lists them)"]
    problems = _write([s for s in have if s != src])
    return (False, problems) if problems else (True, [f"removed {src} from packs.sources; the packs installed from it stay"])
