"""halo_harness.packs.contrib_slash -- a pack's own slash command run by its Python (Halo 3.4.0.0 B; docs/EXTENSION_API.md
"CLI verbs, slash commands, doctor rows and settings rows", draft in API 1.3).

    contributes:
      slash: [{name: start, module: cli/slash.py, help: "the guided first run's card"}]

The module exposes `run(args_text, facade) -> str`: `/<name> ...` in the terminal (and every surface that runs a
slash command) calls it and shows what it returns. It runs only while the pack is enabled and granted `cli:<name>`,
the grant its CLI verb of the same name takes (one grant: "its verb runs"). A core command always keeps its name. A
word that left the core (halo_harness/left.py) that no enabled pack answers is a command of its own that says its one
line, so `/start` with the first-run pack off is one line, not an unknown command.

    entries(manifest)          the `slash` entries
    lines(data, root)          one line per problem, each naming the entry
    register(reg, cwd)         the commands, added to a commands registry where nothing else took the name
"""

from __future__ import annotations

from halo_harness.packs.contrib_cli import GRANT_PREFIX, VERB, entries as _entries, grant_line, load, module_problem, rows

KEYS = ("name", "module", "help")


def entries(manifest) -> "list[dict]":
    return _entries(manifest, "slash")


def needs(data) -> "list[tuple[str, str]]":
    return [(GRANT_PREFIX + str(e.get("name")), f"slash command /{e.get('name')}") for e in entries(data) if e.get("name")]


def lines(data, root=None) -> "list[str]":
    c = data.get("contributes") if isinstance(data, dict) else None
    raw = c.get("slash") if isinstance(c, dict) else None
    if raw is None:
        return []
    if not isinstance(raw, list):
        return ["contributes.slash: a list of {name, module, help}"]
    out, seen = [], set()
    for i, e in enumerate(raw):
        where = f"contributes.slash[{i}]"
        if not isinstance(e, dict):
            out.append(f"{where}: a mapping {{name, module, help}}")
            continue
        out += [f"{where}: unknown key {k!r} (name, module, help)" for k in e if k not in KEYS]
        name = e.get("name")
        if not isinstance(name, str) or not VERB.match(name):
            out.append(f"{where}.name: {name!r} is not a command name (lower-case letters, digits and -)")
        elif name in seen:
            out.append(f"{where}.name: {name!r} is used twice")
        seen.add(name)
        line = module_problem(where, e.get("module"), root)
        out += [line] if line else []
    return out


def _runner(row: dict):
    def _run(args_text: str, facade) -> str:
        if not row["granted"]:
            return f"/{row['name']}: {grant_line(row['pack'], row['name'])}"
        try:
            mod = load(row["pack"], row["root"], str(row["module"]))
            return str(mod.run(args_text or "", facade) or "")
        except Exception as e:  # the pack's own code: one line, never the session's failure
            return f"/{row['name']}: the {row['pack']} pack's {row['module']} failed: {type(e).__name__}: {e}"
    return _run


def register(reg, cwd=None, state_dir=None) -> None:
    from halo_harness.commands.registry import SlashCommand
    from halo_harness.left import LEFT, PACKED, line
    for row in rows(cwd, state_dir, key="slash", name="name"):
        if reg.resolve(row["name"]) is None:
            reg.add(SlashCommand(name=row["name"], description=row["help"] or f"from pack {row['pack']}", kind="core",
                                 source="custom", run=_runner(row)))
    for word in list(LEFT) + list(PACKED):
        if reg.resolve(word) is None:
            reg.add(SlashCommand(name=word, description="left the core in 3.4.0.0: says where it went", kind="core",
                                 source="builtin", run=lambda _a, _f, w=word: f"/{w}: {line(w)}"))
