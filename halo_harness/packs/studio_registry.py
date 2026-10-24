"""halo_harness.packs.studio_registry -- what the active packs add to Studio,
as the one registry the shell reads (Halo 3.2.0.0 R3; `GET /api/pack/registry`,
studio/packs_studio_api.py; docs/EXTENSION_API.md "Studio contributions").

    registry(cwd=..., state_dir=...) -> {"version": 1, "core": [...], "packs": [entry, ...]}

Only packs that run (enabled, no problem) are in it, so nothing of a
disabled pack shows. Every id is qualified `<pack id>--<id>` (sections,
panels, palette entries); titles stay as written. A route (`docs/checks`,
`roles`) becomes `{section, panel?}` with the qualified ids; `config_form`
adds the Settings panel (kind form) to the pack's first section. A bundle
panel carries `script: granted | not granted`, the grant line, and (granted)
the module's path.
"""

from __future__ import annotations

from halo_harness.packs import names as N
from halo_harness.packs import studio_rules as R

API = "api/pack/{id}/{where}/{path}"
DEFAULT_W, DEFAULT_H = 12, 24
FORM_HELP = ("The pack's settings: each field is a key of its config.schema.\n"
             "Save writes packs.settings.<id> in ~/.halo/config.json, checked against the schema first.")


def grant_line(pack_id: str) -> str:
    return f"halo pack enable {pack_id} --grant {R.SCRIPT}"


def _route(pack_id: str, route) -> dict:
    sec, _, pan = str(route or "").partition("/")
    if sec in R.CORE_SECTIONS:
        return {"section": sec}
    out = {"section": N.qualify(pack_id, sec)}
    if pan:
        out["panel"] = N.qualify(pack_id, pan)
    return out


def _file(pack_id: str, source: str) -> str:
    if source.startswith(R.DATA_PREFIX):
        return API.format(id=pack_id, where="data", path=source[len(R.DATA_PREFIX):])
    return API.format(id=pack_id, where="file", path=source)


def _panel(pack, p: dict, section: str, *, core: bool, granted: bool) -> dict:
    kind = p.get("kind")
    out = {"id": N.qualify(pack.id, p["id"]), "name": p["id"], "pack": pack.id, "section": section,
           "title": p.get("title") or p["id"], "kind": kind, "w": p.get("w") or DEFAULT_W, "h": p.get("h") or DEFAULT_H,
           "help": str(p.get("help") or ""), "about": f"from pack {pack.id}", "collapsed": core}
    if kind in R.NEED_SOURCE:
        out["source"] = p["source"]
        out["file"] = _file(pack.id, p["source"])
    if kind == "table":
        out["columns"] = [str(c) for c in p.get("columns") or []]
    if kind == "links":
        out["links"] = [{"label": ln["label"], **({"url": ln["url"]} if "url" in ln else {"route": _route(pack.id, ln["route"])})}
                        for ln in p.get("links") or [] if isinstance(ln, dict)]
    if kind == "bundle":
        out["script"] = "granted" if granted else "not granted"
        out["grant"] = grant_line(pack.id)
        if not granted:
            out.pop("file")
    return out


def _settings(pack) -> dict:
    return {"id": R.SETTINGS, "title": "Settings", "kind": "form", "w": DEFAULT_W, "h": DEFAULT_H, "help": FORM_HELP}


def entry(pack, granted) -> dict:
    """One pack's contribution with its ids qualified and its routes resolved."""
    studio = R.studio_of(pack.manifest)
    script = R.SCRIPT in set(granted or [])
    sections = []
    for i, s in enumerate(R.sections_of(pack.manifest)):
        sid = N.qualify(pack.id, s["id"])
        raw = [p for p in s.get("panels") or [] if isinstance(p, dict)]
        if i == 0 and studio.get("config_form") is True and not any(p.get("kind") == "form" for p in raw):
            raw = raw + [_settings(pack)]
        sections.append({"id": sid, "name": s["id"], "pack": pack.id, "title": s.get("title") or s["id"],
                         "blurb": str(s.get("blurb") or f"from pack {pack.id}"), "help": str(s.get("help") or ""),
                         "panels": [_panel(pack, p, sid, core=False, granted=script) for p in raw]})
    panels = [_panel(pack, p, p["section"], core=True, granted=script)
              for p in studio.get("panels") or [] if isinstance(p, dict) and p.get("section") in R.CORE_SECTIONS]
    forms = [p for s in sections for p in s["panels"] if p["kind"] == "form"] + [p for p in panels if p["kind"] == "form"]
    palette = []
    for e in studio.get("palette") or []:
        if not isinstance(e, dict):
            continue
        act = str(e.get("action") or "")
        if act.startswith("route:"):
            action = {"kind": "route", **_route(pack.id, act[len("route:"):])}
        elif act.startswith("url:"):
            action = {"kind": "url", "url": act[len("url:"):]}
        else:
            action = {"kind": "route", "section": forms[0]["section"], "panel": forms[0]["id"]} if forms else {"kind": "none"}
        palette.append({"id": N.qualify(pack.id, str(e.get("id"))), "label": str(e.get("label") or ""),
                        "group": f"pack {pack.id}", "action": action})
    if forms and not any(p["action"].get("panel") == forms[0]["id"] for p in palette):
        palette.append({"id": N.qualify(pack.id, "settings"), "label": f"Settings: {pack.name}", "group": f"pack {pack.id}",
                        "action": {"kind": "route", "section": forms[0]["section"], "panel": forms[0]["id"]}})
    bundles = R.bundle_ids(pack.manifest)
    return {"id": pack.id, "name": pack.name, "version": pack.version, "scope": pack.scope,
            "script": ("granted" if script else "not granted") if bundles else "none", "grant": grant_line(pack.id),
            "sections": sections, "panels": panels, "palette": palette, "config_form": studio.get("config_form") is True,
            "events": {k: {"label": str(v.get("label") or k), "line": str(v.get("line") or "")}
                       for k, v in (studio.get("events") or {}).items() if isinstance(v, dict)},
            "attention": {k: {"label": str(v.get("label") or k),
                              "keys": {a: str(v["keys"][a]) for a in R.ANSWER_KEYS if (v.get("keys") or {}).get(a)}}
                          for k, v in (studio.get("attention") or {}).items() if isinstance(v, dict)}}


def registry(*, cwd=None, state_dir=None) -> dict:
    from halo_harness.packs import state as S
    from halo_harness.packs.contribute import _active
    data = S.load(state_dir)
    packs = [entry(p, S.granted(p.id, data)) for p in _active(cwd, state_dir) if R.studio_of(p.manifest)]
    return {"version": 1, "core": list(R.CORE_SECTIONS), "packs": packs}


def active_pack(pack_id: str, *, cwd=None, state_dir=None):
    """The running pack `pack_id`, or None (not installed here, disabled, or with a problem)."""
    from halo_harness.packs.contribute import _active
    return next((p for p in _active(cwd, state_dir) if p.id == pack_id), None)
