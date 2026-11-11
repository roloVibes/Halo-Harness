"""halo_harness.packs.contrib_doctor -- a pack's own rows in `halo doctor` (Halo 3.4.0.0 B; docs/EXTENSION_API.md "CLI
verbs, slash commands, doctor rows and settings rows", draft in API 1.3).

    contributes:
      doctor: [{id: library, module: doctor.py, help: "the coach library's folder"}]

The module exposes `rows(ctx) -> list`: each row a string (an OK line) or `{"ok": bool, "text": str, "fix": str}`;
`ctx` carries `pack_id`, `cwd`, `state_dir` and `data_dir`. They run while the pack is enabled and granted `doctor`
("its doctor check runs in halo doctor"); a module that raises is one red row naming it, never the doctor's failure.

    entries(manifest)       the `doctor` entries
    needs(data)             [("doctor", "doctor rows <id>")]
    lines(data, root)       one line per problem
    rows(cwd, state_dir)    every enabled pack's rows as `[ok]` / `[!!]` lines, the pack's id first
"""

from __future__ import annotations

from types import SimpleNamespace

from halo_harness.packs.contrib_cli import VERB, entries as _entries, load, module_problem

KEYS = ("id", "module", "help")
GRANT = "doctor"


def entries(manifest) -> "list[dict]":
    return _entries(manifest, "doctor")


def needs(data) -> "list[tuple[str, str]]":
    return [(GRANT, f"doctor rows {e.get('id')}") for e in entries(data) if e.get("id")]


def lines(data, root=None) -> "list[str]":
    c = data.get("contributes") if isinstance(data, dict) else None
    raw = c.get("doctor") if isinstance(c, dict) else None
    if raw is None:
        return []
    if not isinstance(raw, list):
        return ["contributes.doctor: a list of {id, module, help}"]
    out = []
    for i, e in enumerate(raw):
        where = f"contributes.doctor[{i}]"
        if not isinstance(e, dict):
            out.append(f"{where}: a mapping {{id, module, help}}")
            continue
        out += [f"{where}: unknown key {k!r} (id, module, help)" for k in e if k not in KEYS]
        if not isinstance(e.get("id"), str) or not VERB.match(e["id"]):
            out.append(f"{where}.id: {e.get('id')!r} is not an id (lower-case letters, digits and -)")
        line = module_problem(where, e.get("module"), root)
        out += [line] if line else []
    return out


def _row(r) -> str:
    if isinstance(r, str):
        return f"[ok] {r}"
    if isinstance(r, dict):
        ok, text, fix = bool(r.get("ok")), str(r.get("text") or ""), str(r.get("fix") or "")
        return f"[{'ok' if ok else '!!'}] {text}" + (f" -- fix: {fix}" if fix and not ok else "")
    return f"[!!] {r!r}"


def rows(cwd=None, state_dir=None) -> "list[str]":
    try:
        from halo_harness.ext.files import data_dir
        from halo_harness.packs import registry, state as S
        snap = registry.snapshot(cwd=cwd, state_dir=state_dir)
        data = snap.state or S.load(state_dir)
    except Exception:
        return []
    out = []
    for p in snap.active:
        granted = GRANT in S.granted(p.id, data)
        for e in entries(p.manifest):
            if not granted:
                out.append(f"[!!] {p.id}: doctor rows {e.get('id')} wait for the grant: halo pack enable {p.id} --grant doctor")
                continue
            ctx = SimpleNamespace(pack_id=p.id, cwd=cwd, state_dir=state_dir, data_dir=data_dir(p.id))
            try:
                got = load(p.id, p.root, str(e.get("module"))).rows(ctx) or []
                out += [f"{p.id}: {_row(r)}" for r in got]
            except Exception as ex:
                out.append(f"[!!] {p.id}: {e.get('module')} raised {type(ex).__name__}: {ex}")
    return out
