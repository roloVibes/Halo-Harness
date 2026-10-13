"""halo_harness.tui.edit_guard -- the editors never replace a template or an
org file that exists but does not load (review 3 item 149, prior finding 22).

`load_role_template` and `load_org` return None both for "no such file" and
for "a file that does not parse or validate". Opening the form editor on the
second case used to show an empty template, and its ctrl+s wrote that empty
one over the user's file. Every editor entry point (`/roles edit`, the
external-editor path, `/org edit`, the wizard's Edit org...) asks
`unloadable_path` first and refuses with `refusal_text` when it answers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def file_state(kind: str, name: str, state_dir=None) -> "tuple[str, Path]":
    """('missing' | 'ok' | 'unloadable', path) for a role template
    (`kind="role"`) or an org (`kind="org"`)."""
    if kind == "role":
        from halo_harness.roles import load_role_template, role_templates_dir
        path, loaded = role_templates_dir(state_dir) / f"{name}.json", load_role_template(name, state_dir)
    else:
        from halo_harness.orgs import load_org, orgs_dir
        loaded = load_org(name, state_dir)
        path = orgs_dir(state_dir) / f"{name}.json"
    if loaded is not None:
        return "ok", path
    return ("unloadable" if path.exists() else "missing"), path


def unloadable_path(kind: str, name: str, state_dir=None) -> Optional[Path]:
    state, path = file_state(kind, name, state_dir)
    return path if state == "unloadable" else None


def refusal_text(kind: str, name: str, path: Path) -> str:
    what = "Template" if kind == "role" else "Organization"
    return (f"{what} {name!r} exists at {path} but cannot be loaded (invalid JSON or schema); "
            "fix or remove the file first -- the editor will not overwrite it.")
