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
    rows(cwd, state_dir)    every enabled pack's rows as doctor lines, `[OK] From packs, <id>: <text>` or
                            `[WARN] From packs, <id>: <text> -> fix: <fix>` (3.4.0.0 B2: `halo doctor` shows them last)
    entries(cwd, state_dir) the same as (check id, line) pairs, `pack:<id>:<row id>`, for doctor.py's list
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


HEAD = "From packs"


def _row(pack_id: str, r) -> str:
    from halo_harness.doctor import OK, WARN
    if isinstance(r, str):
        return f"{OK} {HEAD}, {pack_id}: {r}"
    if isinstance(r, dict):
        ok, text, fix = bool(r.get("ok")), str(r.get("text") or ""), str(r.get("fix") or "")
        return f"{OK if ok else WARN} {HEAD}, {pack_id}: {text}" + (f" -> fix: {fix}" if fix and not ok else "")
    return f"{WARN} {HEAD}, {pack_id}: a row that is not a string or {{ok, text, fix}}: {r!r}"[:300]


def entries_of(cwd=None, state_dir=None) -> "list[tuple[str, str]]":
    """(check id, doctor line) for every enabled pack's doctor rows."""
    try:
        from halo_harness.doctor import WARN
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
            cid = f"pack:{p.id}:{e.get('id')}"
            if not granted:
                out.append((cid, f"{WARN} {HEAD}, {p.id}: its doctor rows wait for the grant -> fix: "
                                 f"halo pack enable {p.id} --grant doctor"))
                continue
            ctx = SimpleNamespace(pack_id=p.id, cwd=cwd, state_dir=state_dir, data_dir=data_dir(p.id))
            try:
                got = load(p.id, p.root, str(e.get("module"))).rows(ctx) or []
                out += [(cid, _row(p.id, r)) for r in got]
            except Exception as ex:  # the pack's own code: one row naming it, never the doctor's failure
                out.append((cid, f"{WARN} {HEAD}, {p.id}: {e.get('module')} raised {type(ex).__name__}: {ex}"[:300]))
    from halo_harness.packs.shipped_newer import stale  # 3.4.1.0 R5 (defect 30): enabled or not, once per pack
    return out + [(f"pack:{r['id']}:ships", f"{WARN} {HEAD}, {r['id']}: {r['line']}") for r in stale(state_dir)]


def rows(cwd=None, state_dir=None) -> "list[str]":
    return [line for _cid, line in entries_of(cwd, state_dir)]
