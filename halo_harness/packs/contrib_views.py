"""halo_harness.packs.contrib_views -- the "contributes" block of `halo pack
inspect` and the fleet rows of `halo pack doctor` (Halo 3.2.0.0 R4).

    contributes(pack, granted, running=, cwd=, state_dir=) -> {"studio": {...} | None, "fleet": {...} | None,
                                                                "typed": {workflows, artifacts, events} | None (3.2.0.0 R5)}
    contributes_lines(d)       the text block under "contributes:" (Studio's sections, panels, palette lines,
                               the settings form, event lines, attention rows; the fleet capabilities, each
                               available here or not and why, the inspector lines, the mission metadata)
    doctor_rows(pack, granted, cwd=, state_dir=) -> one "fleet-capability" row per capability not available

Availability is checked against this harness's capabilities catalog as
cached (packs/fleet_registry.host_catalog: any age, else a light look at the
hardware, PATH and the repos now), so inspect and doctor start no MCP server.
"""

from __future__ import annotations

from pathlib import Path


def _studio(pack) -> "dict | None":
    from halo_harness.packs import studio_rules as R
    st = R.studio_of(pack.manifest)
    if not st:
        return None
    sections = [{"id": s.get("id"), "title": s.get("title") or s.get("id"),
                 "panels": [f"{p.get('id')} ({p.get('kind')})" for p in s.get("panels") or [] if isinstance(p, dict)]}
                for s in R.sections_of(pack.manifest)]
    panels = [f"{p.get('section')}: {p.get('id')} ({p.get('kind')})" for _k, s, p in R.panels_of(pack.manifest) if s is None]
    return {"sections": sections, "panels": panels,
            "palette": [str(e.get("label") or e.get("id")) for e in st.get("palette") or [] if isinstance(e, dict)],
            "config_form": st.get("config_form") is True,
            "events": sorted((st.get("events") or {}).keys()) if isinstance(st.get("events"), dict) else [],
            "attention": sorted((st.get("attention") or {}).keys()) if isinstance(st.get("attention"), dict) else []}


def _fleet(pack, granted, *, running: bool, cwd=None, state_dir=None) -> "dict | None":
    from halo_harness.packs.fleet_registry import host_catalog, pack_entry
    from halo_harness.packs.fleet_rules import fleet_of
    if not fleet_of(pack.manifest):
        return None
    try:
        cat = host_catalog(state_dir, cwd)
    except Exception:  # an unreadable cache: every check reads as not met, never a crash
        cat = {}
    got = pack_entry(pack, granted, cat, running=running, cwd=cwd, state_dir=state_dir)
    return {k: got[k] for k in ("capabilities", "inspector", "metadata")}


def _typed(pack) -> "dict | None":
    """3.2.0.0 R5: the pack's workflows (stages, inputs, outputs), artifact schemas and event schemas."""
    from halo_harness.packs.typed import artifact_names, artifact_schema, event_entries, event_schema, view_of
    from halo_harness.packs.workflow_rules import read_workflow, workflow_files
    flows = []
    for name, path in workflow_files(pack.manifest, pack.root).items():
        data, _t = read_workflow(path)
        data = data if isinstance(data, dict) else {}
        flows.append({"name": name, "stages": [str(x.get("id")) for x in data.get("stages") or [] if isinstance(x, dict)],
                      "inputs": list((data.get("inputs") or {}).keys()) if isinstance(data.get("inputs"), dict) else [],
                      "outputs": {k: str((v or {}).get("type")) for k, v in (data.get("outputs") or {}).items()}
                      if isinstance(data.get("outputs"), dict) else {}})
    arts = [{"name": a, "view": view_of(artifact_schema(pack.root, a))} for a in artifact_names(pack.manifest)]
    evs = [{"kind": e["kind"], "schema": event_schema(pack.root, pack.manifest, e["kind"]) is not None}
           for e in event_entries(pack.manifest)]
    return {"workflows": flows, "artifacts": arts, "events": evs} if flows or arts or any(e["schema"] for e in evs) else None


def contributes(pack, granted, *, running: bool, cwd=None, state_dir=None) -> dict:
    return {"studio": _studio(pack), "fleet": _fleet(pack, granted, running=running, cwd=cwd, state_dir=state_dir),
            "typed": _typed(pack)}


def contributes_lines(d: dict) -> "list[str]":
    st, fl, ty = (d or {}).get("studio"), (d or {}).get("fleet"), (d or {}).get("typed")
    if not st and not fl and not ty:
        return []
    out = ["contributes:"]
    if st:
        for s in st["sections"]:
            out.append(f"  Studio section {s['id']} ({s['title']}): " + (", ".join(s["panels"]) or "no panels"))
        out += [f"  Studio panel in {p}" for p in st["panels"]]
        if st["palette"]:
            out.append("  palette: " + ", ".join(st["palette"]))
        if st["config_form"]:
            out.append("  the settings form (its first section's Settings panel)")
        if st["events"]:
            out.append("  event lines: " + ", ".join(st["events"]))
        if st["attention"]:
            out.append("  attention rows: " + ", ".join(st["attention"]))
    if fl:
        for c in fl["capabilities"]:
            state = "available here" if c["available"] else "not available here"
            par = (c.get("capacity") or {}).get("parallel")
            out.append(f"  fleet capability {c['name']}: {state} ({c['why']})" + (f"; {par} at once" if par else ""))
            if c.get("description"):
                out.append(f"    {c['description']}")
        out += [f"  mission inspector line: {x['label']} ({x['source']})" for x in fl["inspector"]]
        if fl["metadata"]:
            out.append("  mission metadata: " + ", ".join(f"{k}={v}" for k, v in fl["metadata"].items()))
    for w in (ty or {}).get("workflows") or []:  # 3.2.0.0 R5
        out.append(f"  workflow {w['name']}: stages {', '.join(w['stages'])}; inputs {', '.join(w['inputs']) or '-'}; outputs "
                   + (", ".join(f"{k} ({v})" for k, v in w["outputs"].items()) or "-"))
    if (ty or {}).get("artifacts"):
        out.append("  artifact schemas: " + ", ".join(f"{a['name']} ({a['view']})" for a in ty["artifacts"]))
    typed_events = [e["kind"] for e in (ty or {}).get("events") or [] if e["schema"]]
    if typed_events:
        out.append("  event schemas: " + ", ".join(typed_events))
    return out


def doctor_rows(pack, granted, *, cwd=None, state_dir=None) -> "list[dict]":
    """`[{severity, check, text, fix, path}]`: a running pack's fleet capabilities that are not available here."""
    fl = _fleet(pack, granted, running=True, cwd=cwd, state_dir=state_dir)
    out = []
    for c in (fl or {}).get("capabilities") or []:
        if c["available"]:
            continue
        grants = [x for x in c.get("checks") or [] if x["key"] == "grants" and not x["ok"]]
        fix = f"halo pack enable {pack.id} " + " ".join(f"--grant {x['line'].split()[0]}" for x in grants) if grants else \
            "the fleet sends parts needing it to a harness that has it"
        out.append({"severity": "warns", "check": "fleet-capability", "fix": fix, "path": str(Path(pack.root) / "pack.yaml"),
                    "text": f"{pack.id}: fleet capability {c['name']} is not available here: {c['why']}"})
    return out
