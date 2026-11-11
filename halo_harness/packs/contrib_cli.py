"""halo_harness.packs.contrib_cli -- a pack's own top-level CLI verb (Halo 3.4.0.0 B; docs/EXTENSION_API.md
"CLI verbs, slash commands, doctor rows and settings rows", draft in API 1.3).

    contributes:
      cli: [{verb: start, module: cli/start.py, help: "the guided first run"}]

The module exposes `main(argv) -> int`. `halo <verb> ...` imports it through the pack's folder (the package
`halo_packs.<id>`, as Studio imports a pack's routes: studio/packs_routes.ensure_package) and calls it with the words
after the verb. It runs only while the pack is enabled and granted `cli:<verb>` (the pack requests it in
`permissions`); a core verb always wins over a pack's. A verb that left the core (halo_harness/left.py) says its one
line when no enabled pack contributes it.

    entries(manifest)              the `cli` entries (mappings only)
    needs(data)                    [("cli:<verb>", "CLI verb <verb>")] -- the grant each verb needs
    lines(data, root)              one line per problem, each naming the entry
    rows(cwd, state_dir)           [{verb, pack, help, granted}] for the packs that run here
    load(pack, rel)                the module, imported through the pack's folder
    dispatch(argv)                 the exit code when the verb is a pack's (or one that left), else None
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Optional

KEYS = ("verb", "module", "help")
GRANT_PREFIX = "cli:"
VERB = re.compile(r"^[a-z][a-z0-9-]*$")


def _contributes(manifest) -> dict:
    c = manifest.get("contributes") if isinstance(manifest, dict) else None
    return c if isinstance(c, dict) else {}


def entries(manifest, key: str = "cli") -> "list[dict]":
    raw = _contributes(manifest).get(key)
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def needs(data) -> "list[tuple[str, str]]":
    return [(GRANT_PREFIX + str(e.get("verb")), f"CLI verb {e.get('verb')}") for e in entries(data) if e.get("verb")]


def module_problem(where: str, rel, root) -> str:
    """'' when `rel` is a .py file inside the pack (checked on disk with a root), else the one line."""
    if not isinstance(rel, str) or not rel.endswith(".py"):
        return f"{where}.module: {rel!r} is not a .py file of the pack"
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        return f"{where}.module: {rel!r} is outside the pack"
    if root is not None and not (Path(root) / p).is_file():
        return f"{where}.module: {rel} is not in the pack"
    return ""


def lines(data, root=None) -> "list[str]":
    raw = _contributes(data).get("cli")
    if raw is None:
        return []
    if not isinstance(raw, list):
        return ["contributes.cli: a list of {verb, module, help}"]
    out, seen = [], set()
    for i, e in enumerate(raw):
        where = f"contributes.cli[{i}]"
        if not isinstance(e, dict):
            out.append(f"{where}: a mapping {{verb, module, help}}")
            continue
        out += [f"{where}: unknown key {k!r} (verb, module, help)" for k in e if k not in KEYS]
        verb = e.get("verb")
        if not isinstance(verb, str) or not VERB.match(verb):
            out.append(f"{where}.verb: {verb!r} is not a verb (lower-case letters, digits and -)")
        elif verb in seen:
            out.append(f"{where}.verb: {verb!r} is used twice")
        seen.add(verb)
        line = module_problem(where, e.get("module"), root)
        out += [line] if line else []
        if e.get("help") is not None and not isinstance(e.get("help"), str):
            out.append(f"{where}.help: one line of text")
    return out


def _running(cwd=None, state_dir=None):
    from halo_harness.packs import registry, state as S
    snap = registry.snapshot(cwd=cwd, state_dir=state_dir)
    return snap.active, snap.state or S.load(state_dir)


def rows(cwd=None, state_dir=None, key: str = "cli", name: str = "verb") -> "list[dict]":
    """Every entry of `key` the packs that run here contribute: {<name>, pack, help, module, root, granted}."""
    from halo_harness.packs import state as S
    try:
        packs, data = _running(cwd, state_dir)
    except Exception:
        return []
    out = []
    for p in packs:
        have = set(S.granted(p.id, data))
        for e in entries(p.manifest, key):
            word = str(e.get(name) or "")
            out.append({name: word, "pack": p.id, "help": str(e.get("help") or ""), "module": e.get("module"),
                        "root": p.root, "granted": GRANT_PREFIX + word in have})
    return out


def load(pack_id: str, root, rel: str):
    """The pack's module `rel`, imported through its folder as `halo_packs.<id>.<path>`."""
    from halo_harness.studio.packs_routes import ensure_package
    name = ensure_package(pack_id, root)
    return importlib.import_module(name + "." + ".".join(Path(rel).with_suffix("").parts))


def grant_line(pack_id: str, verb: str) -> str:
    return f"the {pack_id} pack's verb {verb} is not granted: halo pack enable {pack_id} --grant cli:{verb}"


def dispatch(argv: list, *, cwd=None, state_dir=None) -> Optional[int]:
    """`halo <verb> ...` for a verb no core command took: a pack's verb runs; a verb that left says its line."""
    from halo_harness.left import LEFT, line
    verb = str(argv[0]) if argv else ""
    if verb in LEFT:
        print(f"halo {verb}: {LEFT[verb]}", file=sys.stderr)
        return 2
    row = next((r for r in rows(cwd, state_dir) if r["verb"] == verb), None)
    if row is None:
        moved = line(verb)
        if moved:
            print(f"halo {verb}: {moved}", file=sys.stderr)
            return 2
        return None
    if not row["granted"]:
        print(f"halo {verb}: {grant_line(row['pack'], verb)}", file=sys.stderr)
        return 2
    try:
        mod = load(row["pack"], row["root"], str(row["module"]))
    except Exception as e:
        print(f"halo {verb}: the {row['pack']} pack's {row['module']} did not import: {type(e).__name__}: {e}",
              file=sys.stderr)
        return 1
    rc = mod.main(list(argv[1:]))
    return int(rc or 0)


def pack_call(pack_id: str, rel: str, attr: str, error=LookupError, cwd=None, state_dir=None):
    """`attr` of an enabled pack's module `rel` (3.4.0.0 B2: the fleet's coach_library command answers through the
    coach pack); with the pack off, a callable that raises `error` with the one line of `left.py`."""
    from halo_harness.left import line
    from halo_harness.packs import registry
    try:
        pack = next((p for p in registry.active(cwd=cwd, state_dir=state_dir) if p.id == pack_id), None)
        if pack is not None:
            return getattr(load(pack.id, pack.root, rel), attr)
    except Exception:
        pass

    def _off(*_a, **_k):
        raise error(line(pack_id) or f"the {pack_id} pack is not enabled here")
    return _off
