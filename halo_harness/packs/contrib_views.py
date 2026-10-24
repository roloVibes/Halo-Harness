"""halo_harness.packs.contrib_views -- the "contributes" block of `halo pack
inspect` and the fleet rows of `halo pack doctor` (Halo 3.2.0.0 R4).

    contributes(pack, granted, running=, cwd=, state_dir=) -> {"studio": {...} | None, "fleet": {...} | None}
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


def contributes(pack, granted, *, running: bool, cwd=None, state_dir=None) -> dict:
    return {"studio": _studio(pack), "fleet": _fleet(pack, granted, running=running, cwd=cwd, state_dir=state_dir)}


def contributes_lines(d: dict) -> "list[str]":
    st, fl = (d or {}).get("studio"), (d or {}).get("fleet")
    if not st and not fl:
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
