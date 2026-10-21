"""halo_harness.packs.cli_views -- what `halo pack list` and `halo pack
inspect` show (Halo 3.2.0.0 R1): the rows as data (`--json` prints them) and
the text lines. Pure functions over packs/registry.py's snapshot.
"""

from __future__ import annotations

from pathlib import Path


def _state_word(pack, snap) -> str:
    if pack.id in snap.order:
        return "enabled"
    if pack.id in snap.enabled:
        return "enabled, not running"
    from halo_harness.packs import state as S
    return "disabled" if S.entry(pack.id, data=snap.state) else "not installed (found in place)"


def list_rows(snap) -> "list[dict]":
    from halo_harness.packs import state as S
    from halo_harness.packs.offers import offers
    rows = []
    for pack in snap.packs:
        rec = S.entry(pack.id, data=snap.state) or {}
        rows.append({"id": pack.id, "name": pack.name, "version": pack.version, "state": _state_word(pack, snap),
                     "enabled": pack.id in snap.enabled, "running": pack.id in snap.order, "scope": pack.scope,
                     "root": str(pack.root), "source": str(rec.get("source") or ""), "offers": offers(pack),
                     "problems": list(pack.problems) + list(snap.problems.get(pack.id, []))})
    return rows


def list_lines(rows: "list[dict]") -> "list[str]":
    from halo_harness.packs.offers import summary
    if not rows:
        return ["No packs here. A pack lives in ~/.halo/packs/<id>/ or .halo/packs/<id>/ (halo pack install <path|git url>)."]
    width = max(len(r["id"]) for r in rows)
    out = []
    for r in rows:
        source = f" from {r['source']}" if r["source"] else ""
        out.append(f"{r['id']:<{width}}  {r['version'] or '?':<8}  {r['state']:<12}  {r['scope']:<7}{source}  "
                   f"offers {summary(r['offers'])}" + (f"  ({len(r['problems'])} problem(s): halo pack doctor)"
                                                       if r["problems"] else ""))
    return out


def inspect_payload(pack, snap) -> dict:
    from halo_harness.packs import grants as G
    from halo_harness.packs import manifest as MF
    from halo_harness.packs import settings as ST
    from halo_harness.packs import state as S
    from halo_harness.packs.doctor import undeclared_lines
    from halo_harness.packs.offers import offers
    from halo_harness.packs.resolve import compat_lines
    granted = set(S.granted(pack.id, snap.state)) if pack.id in snap.enabled else set()
    needed: "dict[str, list[str]]" = {}
    for perm, why in G.needs(pack):
        needed.setdefault(perm, []).append(why)
    perms = [{"name": p, "needed_by": needed.get(p, []), "granted": p in granted} for p in MF.requested(pack.manifest)]
    m = pack.manifest
    problems = [f"pack.yaml: {line}" for line in pack.problems] + list(snap.problems.get(pack.id, []))
    if pack.scope == "source" and not pack.problems:
        problems += compat_lines(pack)
    problems += undeclared_lines(pack)
    from halo_harness.packs.roles import pack_bios, pack_lineups  # 3.2.0.0 R2: the model per bio, its needs
    return {"bios": pack_bios(pack, granted=granted), "lineups": pack_lineups(pack),
            "id": pack.id, "name": pack.name, "version": pack.version, "description": pack.description,
            "author": m.get("author"), "license": m.get("license"), "halo_api": m.get("halo_api"), "halo": m.get("halo"),
            "capabilities": m.get("capabilities") or [], "requires": m.get("requires") or [],
            "root": str(pack.root), "scope": pack.scope, "state": _state_word(pack, snap) if pack.scope != "source" else "a source folder",
            "offers": offers(pack), "permissions": perms, "settings": ST.values(pack),
            "settings_problems": ST.problems(pack), "migrations": m.get("migrations") or [], "problems": problems}


def role_lines(d: dict) -> "list[str]":
    """3.2.0.0 R2: each bio with the model it runs on and the grants it needs; each lineup with its members."""
    out = ["bios:"] if d.get("bios") else []
    for b in d.get("bios") or []:
        out.append(f"  {b['name']}: runs on {b['line']}")
        if b["needs"]:
            out.append("    needs: " + ", ".join(f"{n['need']} ({'granted' if n['granted'] else 'not granted'})"
                                             for n in b["needs"]))
        if b["namespace"]:
            out.append(f"    memory namespace: {b['namespace']}")
    out += ["lineups:"] if d.get("lineups") else []
    for t in d.get("lineups") or []:
        members = ", ".join(f"{m['agent']} ({m['role']})" for m in t["members"]) or "no members"
        extra = [f"{t['tiers']} tiers"] if t["tiers"] else []
        extra += [f"workflows {', '.join(t['workflows'])}"] if t["workflows"] else []
        extra += [f"acceptance.{k}: {str(v).lower() if isinstance(v, bool) else v}" for k, v in t["acceptance"].items()]
        out.append(f"  {t['name']}: {members}" + (f"; {'; '.join(extra)}" if extra else ""))
    return out


def inspect_lines(d: dict) -> "list[str]":
    from halo_harness.packs import semver as V
    from halo_harness.packs.offers import KINDS, LABELS
    out = [f"{d['id']} {d['version']} -- {d['name']} ({d['state']})", f"  {d['description']}".rstrip(),
           f"  folder: {Path(d['root']).as_posix()} ({d['scope']})",
           f"  works with: extension API {V.describe(d['halo_api'])}, Halo {V.describe(d['halo'])}"]
    if d["requires"]:
        out.append("  requires: " + ", ".join(f"{r.get('pack')} {r.get('version') or ''}".strip() for r in d["requires"]))
    out.append("offers:")
    for kind in KINDS:
        names = d["offers"].get(kind) or []
        if names:
            out.append(f"  {LABELS[kind][1]}: {', '.join(names)}")
    out += role_lines(d)
    out.append("permissions it requests:")
    for p in d["permissions"]:
        uses = f" ({', '.join(p['needed_by'])})" if p["needed_by"] else ""
        out.append(f"  {p['name']}{uses}: {'granted' if p['granted'] else 'not granted'}")
    if not d["permissions"]:
        out.append("  none")
    if d["settings"]:
        out.append("settings: " + ", ".join(f"{k}={v!r}" for k, v in sorted(d["settings"].items())))
    problems = d["problems"] + d["settings_problems"]
    out.append("problems:" if problems else "problems: none")
    out += [f"  {line}" for line in problems]
    return out
