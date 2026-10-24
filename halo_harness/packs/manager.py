"""halo_harness.packs.manager -- what Studio's Pack Manager shows (Halo
3.2.0.0 R6; `GET /api/pack/manager`, studio/packs_manager_api.py;
docs/STUDIO-packs.md). One read of everything, in the words the CLI prints:

    payload(cwd=, state_dir=) -> {"version": 1, "halo", "halo_api",
                                  "packs":   [row]  every pack here (installed, or found in place),
                                  "sources": [source]  packs/sources.py's listing, each pack of a folder
                                             source with its row (`details`) while it is not installed,
                                  "problems": [doctor row]  the ones of no pack (sources, conflicts)}

A row is `halo pack list`'s row and `halo pack inspect`'s payload (cli_views)
plus: `health` (halo pack doctor's rows for it), `compat` (the lines that
keep it from running here, in the doctor's words: the extension API or Halo
range, a dependency, a fleet capability not available here), `requires`
with `met`, `granted` / `requested`, `contributes_lines` (the block `halo
pack inspect` prints), `workflows` (each with its inputs, for "Run"),
`sections` (its Studio sections, qualified) and `has_settings`.
"""

from __future__ import annotations

from pathlib import Path


def _workflows(pack) -> "list[dict]":
    from halo_harness.packs.workflow_rules import read_workflow, workflow_files
    out = []
    for name, path in workflow_files(pack.manifest, pack.root).items():
        data, _t = read_workflow(path)
        data = data if isinstance(data, dict) else {}
        inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
        out.append({"ref": f"{pack.id}/{name}", "name": name, "description": str(data.get("description") or ""),
                    "stages": [str(s.get("id")) for s in data.get("stages") or [] if isinstance(s, dict)],
                    "inputs": [{"name": k, "type": str((v or {}).get("type") or "text"), "required": bool((v or {}).get("required")),
                                "default": (v or {}).get("default"), "description": str((v or {}).get("description") or "")}
                               for k, v in inputs.items() if isinstance(v, (dict, type(None)))]})
    return out


def _requires(pack, snap) -> "list[dict]":
    from halo_harness.packs import semver as V
    from halo_harness.packs.manifest import requirement_range
    out = []
    for req in pack.manifest.get("requires") or []:
        if not isinstance(req, dict) or not isinstance(req.get("pack"), str):
            continue
        dep, rng = snap.pack(req["pack"]), requirement_range(req) or {}
        met = bool(dep is not None and dep.id in snap.order and (not rng or V.in_range(dep.version, rng)))
        out.append({"pack": req["pack"], "version": V.describe(rng) if rng else "any", "met": met,
                    "have": dep.version if dep is not None else "", "running": bool(dep is not None and dep.id in snap.order)})
    return out


def _compat(pack, snap, granted, *, cwd, state_dir) -> "list[str]":
    """What keeps it from running here, as the doctor words it: resolve's lines as if it were enabled (the API and
    Halo ranges, each dependency) and each fleet capability not available here."""
    from halo_harness.packs import contrib_views as CW
    from halo_harness.packs.resolve import compat_lines, resolve
    if pack.scope == "source":
        lines = compat_lines(pack)
    else:
        _order, problems = resolve(snap.packs, enabled=sorted(set(snap.enabled) | {pack.id}))
        lines = [ln for ln in problems.get(pack.id, []) if ": pack.yaml: " not in ln]
    try:
        lines += [r["text"] for r in CW.doctor_rows(pack, granted, cwd=cwd, state_dir=state_dir)]
    except Exception:  # an unreadable catalog cache: the doctor itself says so
        pass
    return list(dict.fromkeys(lines))


def _uses(d: dict, manifest: dict) -> "dict[str, list[str]]":
    """Who else needs each permission: a bio's `tools.needs`, a fleet capability's `requires.grants`."""
    out: "dict[str, list[str]]" = {}
    for b in d.get("bios") or []:
        for n in b.get("needs") or []:
            out.setdefault(n["need"], []).append(f"bio {b['name']}")
    fleet = (manifest.get("contributes") or {}).get("fleet") if isinstance(manifest.get("contributes"), dict) else None
    for c in (fleet or {}).get("capabilities") or [] if isinstance(fleet, dict) else []:
        grants = ((c or {}).get("requires") or {}).get("grants") if isinstance(c, dict) else None
        for g in grants if isinstance(grants, list) else []:
            out.setdefault(str(g), []).append(f"fleet capability {c.get('name')}")
    return out


def row(pack, snap, *, listed: "dict | None" = None, health=(), cwd=None, state_dir=None) -> dict:
    from halo_harness import __version__
    from halo_harness.ext import API_VERSION
    from halo_harness.packs import contrib_views as CW
    from halo_harness.packs import cli_views as CV
    from halo_harness.packs import manifest as MF
    from halo_harness.packs import semver as V
    from halo_harness.packs import settings as ST
    from halo_harness.packs import state as S
    from halo_harness.packs import studio_rules as R
    from halo_harness.packs.names import qualify
    d = CV.inspect_payload(pack, snap, cwd=cwd)
    granted = sorted(S.granted(pack.id, snap.state)) if pack.id in snap.enabled else []
    out = {**(listed or {"id": pack.id, "name": pack.name, "version": pack.version, "state": d["state"], "enabled": False,
                          "running": False, "scope": pack.scope, "root": str(pack.root), "source": "", "offers": d["offers"]}),
           **{k: d[k] for k in ("description", "author", "license", "capabilities", "permissions", "settings",
                                "settings_problems", "contributes", "bios", "lineups", "migrations")}}
    uses = _uses(d, pack.manifest)
    out["permissions"] = [{**p, "needed_by": list(p["needed_by"]) + [u for u in uses.get(p["name"], []) if u not in p["needed_by"]]}
                          for p in d["permissions"]]
    out.update(installed=pack.scope != "source", problems=list(d["problems"]), granted=granted,
               requested=MF.requested(pack.manifest), halo_api=V.describe(d["halo_api"]), halo=V.describe(d["halo"]),
               this_api=API_VERSION, this_halo=__version__, requires=_requires(pack, snap),
               health=[h for h in health if h.get("pack") == pack.id],
               compat=_compat(pack, snap, granted, cwd=cwd, state_dir=state_dir),
               contributes_lines=CW.contributes_lines(d["contributes"]), workflows=_workflows(pack),
               sections=[{"id": qualify(pack.id, str(s.get("id"))), "title": str(s.get("title") or s.get("id"))}
                         for s in R.sections_of(pack.manifest)],
               has_settings=ST.schema_of(pack.manifest) is not None)
    return out


def payload(*, cwd=None, state_dir=None) -> dict:
    from halo_harness import __version__
    from halo_harness.ext import API_VERSION
    from halo_harness.packs import cli_views as CV
    from halo_harness.packs import sources as SRC
    from halo_harness.packs.discover import read_pack
    from halo_harness.packs.doctor import problems
    from halo_harness.packs.registry import snapshot
    snap = snapshot(cwd=cwd, state_dir=state_dir)
    health = problems(cwd=cwd, state_dir=state_dir)
    listed = {r["id"]: r for r in CV.list_rows(snap)}
    packs = [row(p, snap, listed=listed.get(p.id), health=health, cwd=cwd, state_dir=state_dir) for p in snap.packs]
    sources = SRC.listing(cwd=cwd, state_dir=state_dir)
    for src in sources:
        for p in src["packs"]:
            if src["kind"] != "url" and not p["installed"] and not p["problems"]:
                p["details"] = row(read_pack(Path(p["path"]), "source", folder_is_id=False), snap, cwd=cwd, state_dir=state_dir)
    return {"version": 1, "halo": __version__, "halo_api": API_VERSION, "packs": packs, "sources": sources,
            "problems": [h for h in health if not h.get("pack")]}
