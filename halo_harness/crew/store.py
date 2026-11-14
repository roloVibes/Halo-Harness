"""halo_harness.crew.store -- where the crew files live and how they are read and written (Halo 3.6.0.0 R1).

    <state>/crew/{agents,workflows,maps}/<name>.yaml     yours (~/.halo/crew/)
    <repo>/.halo/crew/{agents,workflows,maps}/           this project's, read in a trusted folder only
    halo_harness/templates/crew/{agents,workflows,maps}/ the shipped starters: read-only, Copy makes yours

`find(kind, name)` answers the file a name means (the project's, then yours, then a starter's); `rows(kind)` every
file of a kind with its scope; `used_by(name)` the workflows and maps that name an agent; `write` / `remove` touch
only yours (or the project's, when asked). Nothing here reads the old lineups, bios or squares.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import yaml

from halo_harness.crew.formats import AGENT_KEYS, PROBLEMS

KINDS = {"agent": "agents", "workflow": "workflows", "map": "maps"}
SHIPPED = Path(__file__).resolve().parent.parent / "templates" / "crew"
NEW_S = 24 * 3600.0


def state_dir_of(state_dir=None) -> Path:
    if state_dir is not None:
        return Path(state_dir)
    from halo_harness.providers.config import default_state_dir
    return Path(default_state_dir())


def repo_of(cwd) -> Path:
    from halo_harness.config.paths import find_git_root
    try:
        return Path(find_git_root(Path(cwd)) or cwd)
    except Exception:
        return Path(cwd)


def folders(kind: str, *, cwd=None, state_dir=None) -> "list[tuple[Path, str]]":
    """(folder, scope) nearest first: project (trusted only), yours, starter."""
    sub = KINDS[kind]
    out: list = []
    if cwd is not None:
        from halo_harness.project_gate import trusted
        if trusted(cwd):
            out.append((repo_of(cwd) / ".halo" / "crew" / sub, "project"))
    out.append((state_dir_of(state_dir) / "crew" / sub, "yours"))
    out.append((SHIPPED / sub, "starter"))
    return out


def own_folder(kind: str, *, cwd=None, state_dir=None, project: bool = False) -> Path:
    if project and cwd is not None:
        return repo_of(cwd) / ".halo" / "crew" / KINDS[kind]
    return state_dir_of(state_dir) / "crew" / KINDS[kind]


def read(path: Path) -> Optional[dict]:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def find(kind: str, name: str, *, cwd=None, state_dir=None, scope: str = "") -> "Optional[tuple[Path, str]]":
    for folder, sc in folders(kind, cwd=cwd, state_dir=state_dir):
        if scope and sc != scope:
            continue
        p = folder / f"{name}.yaml"
        if p.is_file():
            return p, sc
    return None


def load(kind: str, name: str, *, cwd=None, state_dir=None, scope: str = "") -> Optional[dict]:
    got = find(kind, name, cwd=cwd, state_dir=state_dir, scope=scope)
    if got is None:
        return None
    data = read(got[0])
    if data is None:
        return None
    return {**data, "_scope": got[1], "_path": str(got[0])}


def rows(kind: str, *, cwd=None, state_dir=None) -> "list[dict]":
    """Every file of `kind`, one row each (a name in two scopes: two rows), yours and the project's first."""
    out: list = []
    for folder, scope in folders(kind, cwd=cwd, state_dir=state_dir):
        try:
            files = sorted(p for p in folder.glob("*.yaml") if p.is_file())
        except OSError:
            continue
        for p in files:
            data = read(p) or {}
            probs = PROBLEMS[kind](data, name=p.stem) if data else ["the file is not YAML Halo can read"]
            try:
                age = time.time() - p.stat().st_mtime
            except OSError:
                age = NEW_S
            out.append({**data, "name": p.stem, "_scope": scope, "_path": str(p), "_problems": probs,
                        "_new": scope != "starter" and age < NEW_S})
    return out


def used_by(agent: str, *, cwd=None, state_dir=None) -> "list[str]":
    """The workflows (`workflow <name>`) and maps (`map <name>`) of yours and the project's that name `agent`."""
    out: list = []
    for wf in rows("workflow", cwd=cwd, state_dir=state_dir):
        if wf["_scope"] != "starter" and any(agent in (s.get("agents") or []) for s in wf.get("steps") or [] if isinstance(s, dict)):
            out.append(f"workflow {wf['name']}")
    for mp in rows("map", cwd=cwd, state_dir=state_dir):
        if mp["_scope"] == "starter":
            continue
        for b in mp.get("boxes") or []:
            ref = b.get("agent") if isinstance(b, dict) else None
            if agent == ref or (isinstance(ref, list) and agent in ref):
                out.append(f"map {mp['name']}")
                break
    return out


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper, value: str):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str)


def clean(raw: dict) -> dict:
    """The file's own fields in their order, Halo's bookkeeping (`_scope`, `_path` ...) and empty optional ones dropped."""
    data = {k: v for k, v in raw.items() if not str(k).startswith("_")}
    if data.get("format") == "agent/1":
        more = {k: v for k, v in (data.get("more") or {}).items() if v not in (None, "", [], {})}
        data["more"] = more
        order = [k for k in AGENT_KEYS if k in data] + [k for k in data if k not in AGENT_KEYS]
        data = {k: data[k] for k in order if not (k in ("instructions", "more", "needs") and data[k] in (None, "", [], {}))}
    return data


def dump(raw: dict) -> str:
    return yaml.dump(clean(raw), Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=110)


def write_text(path: Path, text: Optional[str]) -> None:
    """Write `text` atomically (None: remove the file)."""
    path = Path(path)
    if text is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    for i in range(200):  # Windows refuses the swap while a reader holds the file open (a page polling a run's record)
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if i == 199:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.01)


def path_for(kind: str, name: str, *, cwd=None, state_dir=None, project: bool = False) -> Path:
    return own_folder(kind, cwd=cwd, state_dir=state_dir, project=project) / f"{name}.yaml"
