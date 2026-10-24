"""halo_harness.packs.studio_keys -- the keys of a pack's `contributes.studio`
that are not panels (Halo 3.2.0.0 R3; packs/studio_rules.py checks the ids
and the panels, then calls `check`): `config_form` (needs `config.schema`
and a section: the form is the first section's Settings panel), a section's
own panel list, `panels[].section` (a core section), `palette` (an id, a
label, an action: `route:<section>[/<panel>]`, `url:<address>` or `config`),
`events` (kinds among `contributes.events`, each with its `line`) and
`attention` (row kinds, each with a label and its keys). One line per
problem through studio_rules' line finder (`pack.yaml line N: <key> ...`).
"""

from __future__ import annotations

import re

from halo_harness.packs import studio_rules as R

ROW_KIND_RE = re.compile(r"^[a-z][a-z0-9_.-]*$")


def _config_and_sections(L, manifest, studio: dict, own: dict) -> None:
    has_schema = isinstance((manifest.get("config") or {}).get("schema"), dict)
    if studio.get("config_form") is True:
        if not has_schema:
            L.add("contributes.studio.config_form", ": true, but pack.yaml has no config.schema (the form's fields)")
        if not own:
            L.add("contributes.studio.config_form", ": the form is the Settings panel of the pack's first section; "
                  "declare a section under sections:")
    for i, s in enumerate(R._list(studio, "sections")):
        if isinstance(s, dict) and not R._list(s, "panels") and not (i == 0 and studio.get("config_form") is True):
            L.add(f"contributes.studio.sections[{i}].panels", ": a section shows its panels; it lists none", "id", s.get("id"))
    for j, p in enumerate(R._list(studio, "panels")):
        if isinstance(p, dict) and p.get("section") not in R.CORE_SECTIONS:
            L.add(f"contributes.studio.panels[{j}].section", f" {p.get('section')!r} is not a core section "
                  f"({', '.join(R.CORE_SECTIONS)}); the pack's own sections are under sections:", "section", p.get("section"))


def _palette(L, manifest, studio: dict, own: dict) -> None:
    form = studio.get("config_form") is True or any(p.get("kind") == "form" for _k, _s, p in R.panels_of(manifest))
    for i, e in enumerate(R._list(studio, "palette")):
        key = f"contributes.studio.palette[{i}]"
        if not isinstance(e, dict):
            continue
        if not R.is_id(e.get("id")):
            L.add(f"{key}.id", f" {e.get('id')!r} is not an id (letters, digits, - and _, no '--')", "id", e.get("id"))
        if not str(e.get("label") or "").strip():
            L.add(f"{key}.label", ": required (the palette's line)", "id", e.get("id"))
        act = str(e.get("action") or "")
        if act.startswith("route:"):
            if R.route_problem(act[6:], own):
                L.add(f"{key}.action", R.route_problem(act[6:], own), "action", act)
        elif act.startswith("url:"):
            if not R.URL_RE.match(act[4:]):
                L.add(f"{key}.action", f" {act!r}: url: takes an http(s) or mailto address", "action", act)
        elif act == "config":
            if not form:
                L.add(f"{key}.action", ": config opens the settings form; the pack declares none (config_form: true)", "action", act)
        else:
            L.add(f"{key}.action", f" {act!r} is not route:<section>[/<panel>], url:<address> or config", "action", act or None)


def _events_and_rows(L, manifest, studio: dict) -> None:
    declared = set(R._list(manifest.get("contributes") or {}, "events"))
    for kind, ev in (studio.get("events") or {}).items() if isinstance(studio.get("events"), dict) else ():
        if kind not in declared:
            L.add(f"contributes.studio.events.{kind}", ": not one of contributes.events "
                  f"({', '.join(sorted(declared)) or 'none declared'})", kind)
        elif not isinstance(ev, dict) or not str(ev.get("line") or "").strip():
            L.add(f"contributes.studio.events.{kind}.line", ": required (the line's template, {field} from the frame's data)", kind)
    for kind, at in (studio.get("attention") or {}).items() if isinstance(studio.get("attention"), dict) else ():
        key = f"contributes.studio.attention.{kind}"
        if not ROW_KIND_RE.match(str(kind)):
            L.add(key, ": not a row kind (lower-case, digits, . _ -)", str(kind))
        elif not isinstance(at, dict) or not str(at.get("label") or "").strip():
            L.add(f"{key}.label", ": required (the row's kind chip)", str(kind))
        elif not isinstance(at.get("keys"), dict) or not any(str(at["keys"].get(k) or "").strip() for k in R.ANSWER_KEYS):
            L.add(f"{key}.keys", ": name the row's answers (a, r, s, o: each a label)", str(kind))


def check(L, manifest, own: dict) -> None:
    studio = R.studio_of(manifest)
    _config_and_sections(L, manifest, studio, own)
    _palette(L, manifest, studio, own)
    _events_and_rows(L, manifest, studio)
