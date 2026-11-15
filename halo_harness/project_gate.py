"""halo_harness.project_gate -- what a project's own `.halo/` files may do (Halo 3.4.1.2, ENGINE-1).

A cloned repo's `.halo/workflows/`, `.halo/teams/` and `.halo/agents/` are repo text. Before 3.4.1.2 they were read in
any folder and won over the shipped files of the same name, so an untrusted repo could replace the shipped `media`
square (and run its own lanes and test command) or the bio the default lineup's main runs (and its hooks with it).

- `trusted(cwd)`: the folder is trusted (config/claude_json.is_trusted); False on any error.
- `project_dir(path, cwd)`: `[(path, "project")]` in a trusted folder, else `[]` (the search lists splice it in).
- `shadows(kind, name)`: a project file of this name is not used: it is a shipped name (`workflows`, `teams`) or names
  a pack's file (`<pack>--<name>`).
- `skipped(cwd)`: one line per project file skipped here, for `halo workflows list`, `halo teams`, `halo doctor`.
"""

from __future__ import annotations

from pathlib import Path

#: the kinds whose project files may never take a shipped name (bios in a trusted folder may: like its hooks)
NO_SHIPPED_NAME = ("workflows", "teams")


_TRUSTED: dict = {}  # 3.6.0.0 R14: (folder, what the answer depends on) -> the answer
_TRUSTED_MAX = 256
_SETTLED_NS = 3_000_000_000  # a file written in the last 3 s is read again every time (agents_yaml's rule)


def _stamp(path: Path):
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size, getattr(st, "st_ino", 0), getattr(st, "st_ctime_ns", 0))


def _git_top(here: Path):
    """The nearest folder at or above `here` holding `.git` (is_trusted's walk stops there), else None."""
    cur = here
    while True:
        if (cur / ".git").exists():
            return str(cur)
        if cur.parent == cur:
            return None
        cur = cur.parent


def trusted(cwd=None) -> bool:
    """3.6.0.0 R14: the answer is kept by what it depends on -- the stamps of ~/.claude.json and ~/.halo/trust.json,
    the folder's git top and CLAUDE_CODE_SANDBOXED -- so Studio's file watcher (every 1.5 s) and each request no longer
    parse the whole ~/.claude.json (megabytes for a long-time Claude Code user) to learn the same thing. A file written
    in the last three seconds is read again every time."""
    try:
        import os
        import time
        from halo_harness.config.claude_json import is_trusted, load_claude_json
        from halo_harness.config.paths import bridge_home, claude_json_path
        here = Path(cwd if cwd is not None else Path.cwd()).absolute()
        stamps = (_stamp(claude_json_path()), _stamp(bridge_home() / "trust.json"))
        key = (str(here), stamps, _git_top(here), os.environ.get("CLAUDE_CODE_SANDBOXED") or "")
        settled = all(s is None or abs(time.time_ns() - s[0]) > _SETTLED_NS for s in stamps)
        if settled and key in _TRUSTED:
            return _TRUSTED[key]
        got = bool(is_trusted(here, load_claude_json()))
        if settled:
            if len(_TRUSTED) >= _TRUSTED_MAX:
                _TRUSTED.clear()
            _TRUSTED[key] = got
        return got
    except Exception:
        return False


def project_dir(path, cwd=None) -> "list[tuple[Path, str]]":
    return [(Path(path), "project")] if trusted(cwd) else []


def _shipped(kind: str) -> Path:
    return Path(__file__).resolve().parent / "templates" / kind


def shipped_names(kind: str) -> "set[str]":
    try:
        return {p.stem for p in _shipped(kind).glob("*.yaml") if p.is_file()}
    except OSError:
        return set()


def shadows(kind: str, name: str) -> str:
    """'' when a project file `name` of `kind` (workflows | teams | agents) may be used; else why not."""
    from halo_harness.packs import names as N
    if N.unqualify(str(name))[0]:
        return "it names a pack's file"
    if kind in NO_SHIPPED_NAME and str(name) in shipped_names(kind):
        return "it has a shipped name"
    return ""


def name_ok(source: str, kind: str, name: str) -> bool:
    """A search hit is used: anything not from the project, or a project file that shadows nothing."""
    return source != "project" or not shadows(kind, name)


_WHAT = {"workflows": "workflow", "teams": "lineup", "agents": "bio"}


def skipped(cwd=None) -> "list[str]":
    """One line per project file under `.halo/{workflows,teams,agents}` that is not used here, and why."""
    base = Path(cwd if cwd is not None else Path.cwd()) / ".halo"
    is_trusted = trusted(cwd)
    out = []
    for kind in ("workflows", "teams", "agents"):
        try:
            names = sorted(p.stem for p in (base / kind).glob("*.yaml") if p.is_file())
        except OSError:
            continue
        for name in names:
            why = "this folder is not trusted" if not is_trusted else shadows(kind, name)
            if why:
                out.append(f"project {_WHAT[kind]} .halo/{kind}/{name}.yaml is not used: {why}")
    return out


def note(kind: str, name: str, cwd=None) -> str:
    """The one line for a lookup of `name` that a project file would have answered, else ''."""
    path = Path(cwd if cwd is not None else Path.cwd()) / ".halo" / kind / f"{name}.yaml"
    if not path.is_file():
        return ""
    why = "this folder is not trusted" if not trusted(cwd) else shadows(kind, name)
    return f"project {_WHAT[kind]} .halo/{kind}/{name}.yaml is not used: {why}" if why else ""
