"""halo_harness.where.rows -- the row every `halo config where` group builds,
and the one precedence pass every group shares.

A row:

    {"kind":   "config" | "env" | "settings" | "mcp" | "lineup" | "lineups" |
               "bios" | "team" | "team-preset" | "flows",
     "file":   "~/.halo/config.json"      (home as ~, this folder as ./, the package as <halo>/),
     "path":   absolute path, "scope": "home" | "repo" | "env" | "shipped",
     "exists": bool, "read": bool (False: Halo never reads this file),
     "sets":   [top-level keys, or the lineup / bio / team / flow / server
               / variable names the file holds -- never a value],
     "rank":   1 = the resolver looks here first in its group,
     "wins":   [keys this file sets that another file sets too, and this one wins],
     "loses":  [{"key", "to", "to_path"}: keys another file (or a flag /
               variable) decides; "to_path" is the winning file when there is one],
     "note":   one sentence, "files": [the files a directory row covers]}

`settle(rows, winner_of)` fills `wins` / `loses`: for every key two or more
rows set, `winner_of(key)` answers the winning path the way the group's own
resolver finds it (`find_team_template_path`, `find_agent_bio_path`,
`find_flow`, `find_team_file`, the settings merge, the MCP resolver), so the
column is what the code does, not a table kept by hand.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Optional


def display(path, *, cwd=None) -> str:
    """`<halo>/...` inside the installed package (the shipped templates), `./...`
    under `cwd`, `~/...` under the home, else the absolute path (always `/`)."""
    from halo_harness.config.paths import home
    p = Path(path)
    package = Path(__file__).resolve().parent.parent
    for base, prefix in ((package, "<halo>/"), (Path(cwd).resolve() if cwd is not None else None, "./"),
                         (home(), "~/")):
        if base is None:
            continue
        try:
            rel = p.resolve().relative_to(Path(base).resolve())
        except (ValueError, OSError):
            continue
        return prefix + rel.as_posix() if str(rel) != "." else prefix.rstrip("/")
    return p.as_posix()


def make(kind: str, path, scope: str, *, cwd=None, sets: Iterable = (), read: bool = True, rank: int = 1,
         note: str = "", files: Optional[list] = None, label: Optional[str] = None) -> dict:
    p = Path(path)
    try:
        exists = p.exists()
    except OSError:
        exists = False
    return {"kind": kind, "file": label or display(p, cwd=cwd), "path": str(p), "scope": scope, "exists": exists,
            "read": read, "sets": [str(s) for s in sets], "rank": rank, "wins": [], "loses": [], "note": note,
            "files": [str(f) for f in (files if files is not None else ([p] if exists and p.is_file() else []))]}


def settle(rows: list, winner_of: Callable[[str], Optional[str]], *, cwd=None) -> list:
    """Fill each row's `wins` / `loses` for the keys two or more rows set.
    `winner_of(key)` answers the winning path (or a plain label such as
    "HALO_MODEL"); None leaves that key alone."""
    counts: dict = {}
    for r in rows:
        for key in dict.fromkeys(r["sets"]):
            counts[key] = counts.get(key, 0) + 1
    for key, n in counts.items():
        if n < 2:
            continue
        winner = winner_of(key)
        if not winner:
            continue
        for r in rows:
            if key not in r["sets"]:
                continue
            if _same(r["path"], winner) or any(_same(f, winner) for f in r["files"]):
                r["wins"].append(key)
            else:
                r["loses"].append({"key": key, "to": _label(winner, rows, cwd), "to_path": winner})
    return rows


def lose(row: dict, key: str, to: str, to_path: str = "") -> None:
    """One key of `row` decided elsewhere (a flag, a variable, another file)."""
    if not any(entry["key"] == key for entry in row["loses"]):
        row["loses"].append({"key": key, "to": to, "to_path": to_path})


def _same(a: str, b: str) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except (OSError, ValueError):
        return str(a) == str(b)


def _label(winner: str, rows: list, cwd) -> str:
    for r in rows:
        if _same(r["path"], winner):
            return r["file"]
    p = Path(winner)
    return display(p, cwd=cwd) if p.is_absolute() else winner


def scope_of(source: str) -> str:
    """The loaders' own source labels -> a row scope."""
    return {"project": "repo", "repo": "repo", "user": "home", "template": "shipped"}.get(source, source)


def yaml_keys(path) -> "tuple[list, str]":
    """`(top-level keys, problem)` of a YAML file; problem is "" when it parsed."""
    import yaml
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except OSError as e:
        return [], f"cannot read it: {e}"
    except yaml.YAMLError as e:
        return [], f"not valid YAML: {str(e).splitlines()[0]}"
    if data is None:
        return [], ""
    if not isinstance(data, dict):
        return [], "not a mapping"
    return [str(k) for k in data], ""


def json_keys(path) -> "tuple[list, str]":
    import json
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except OSError as e:
        return [], f"cannot read it: {e}"
    except ValueError as e:
        return [], f"not valid JSON: {e}"
    if not isinstance(data, dict):
        return [], "not a JSON object"
    return [str(k) for k in data], ""
