"""halo_harness.config.claude_md_imports -- which `@import` a CLAUDE.md may pull in (Halo 3.4.1.2, ENGINE-2).

Before 3.4.1.2 an untrusted repo's CLAUDE.md could `@~/.claude/.credentials.json` (or `settings.json`, or another
project's transcript under `projects/`): the import was refused only when it was outside BOTH the cwd and the Claude
config dir, and no Read deny rule was asked. The rule now (`refused` answers '' or the warning line the owner sees):

1. Under the Claude config dir only `*.md` is imported, never `.credentials.json`, `settings*.json`, `projects/`,
   `history.jsonl`, `sessions/`, `todos/`, `shell-snapshots/` or any other file Claude Code keeps there.
2. In a folder that is not trusted, an import comes only from inside the cwd -- except that the person's own files
   (under the config dir or the managed dir) may still import `*.md` from the config dir as before.
3. Every import passes the session's Read deny rules (the settings' `permissions.deny`, as the Read tool decides).

    use(settings, cwd)         -> the deny engine for this discovery (discover_instructions sets it per call)
    refused(target, importer, *, cwd, trusted) -> '' | the line
"""

from __future__ import annotations

import contextvars
from pathlib import Path

_ENGINE: "contextvars.ContextVar" = contextvars.ContextVar("claude_md_import_engine", default=None)
_NEVER_DIRS = ("projects", "sessions", "todos", "shell-snapshots", "statsig", "ide", "plugins", "local", "debug")


def use(settings, cwd) -> None:
    """The Read deny rules of this discovery's settings, as an engine (None: no rules, or they did not parse)."""
    engine = None
    try:
        from halo_harness.permissions import PermissionEngine, build_rules_from_settings
        deny, _ask, _allow = build_rules_from_settings(settings, cwd=Path(cwd))
        if deny:
            engine = PermissionEngine(deny_rules=deny, mode="auto", cwd=Path(cwd))
    except Exception:
        engine = None
    _ENGINE.set(engine)


def _within(path: Path, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (OSError, ValueError):
        return False


def config_dir_problem(target: Path, cfg: Path) -> str:
    """'' for a file under the Claude config dir that may be imported (a `*.md` outside Claude Code's own folders)."""
    try:
        rel = Path(target).resolve().relative_to(Path(cfg).resolve())
    except (OSError, ValueError):
        return ""
    parts = [p.lower() for p in rel.parts]
    if parts and parts[0] in _NEVER_DIRS:
        return f"it is under {parts[0]}/, where Claude Code keeps its own files"
    if not parts or not parts[-1].endswith(".md"):
        return "only *.md files under the Claude config folder are imported (never credentials, settings or logs)"
    return ""


def _config_dirs() -> list:
    from halo_harness.config.paths import claude_config_dir, home
    return list(dict.fromkeys([claude_config_dir(), home() / ".claude"]))  # CLAUDE_CONFIG_DIR, and ~/.claude itself


def refused(target: Path, importer: Path, *, cwd: Path, trusted: bool) -> str:
    from halo_harness.config.paths import managed_dir
    cfgs = _config_dirs()
    why = next((w for w in (config_dir_problem(target, c) for c in cfgs) if w), "")
    if why:
        return f"import refused: {target} ({why}) (from {importer})"
    if not trusted and not _within(target, cwd):
        own = any(_within(importer, c) for c in cfgs) or _within(importer, managed_dir())
        if not (own and any(_within(target, c) for c in cfgs)):
            return (f"import not approved (this folder is not trusted: its files import only from inside it): {target} "
                    f"(from {importer})")
    engine = _ENGINE.get()
    if engine is not None:
        try:
            d = engine.decide("Read", {"file_path": str(target)})
        except Exception:
            d = None
        if d is not None and d.action == "deny":
            return f"import refused by your Read deny rule ({d.reason}): {target} (from {importer})"
    return ""


_NOTICED: set = set()


def notice(bundle, *, file=None) -> "list[str]":
    """Print each import refusal of `bundle` once per process (the owner sees what was not imported, and why)."""
    import sys
    lines = [w for w in getattr(bundle, "warnings", None) or [] if w.startswith(("import refused", "import not approved"))]
    for line in lines:
        if line not in _NOTICED:
            _NOTICED.add(line)
            print(f"halo: CLAUDE.md {line}", file=file or sys.stderr)
    return lines
