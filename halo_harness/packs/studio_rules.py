"""halo_harness.packs.studio_rules -- what a pack's `contributes.studio` may
say (Halo 3.2.0.0 R3, docs/EXTENSION_API.md "Studio contributions").

The shape is schemas/pack_yaml.py `studio()`; these are the meanings, checked
with the manifest (`manifest.validate_manifest`), one line each naming the key
and, with a root, `pack.yaml line N`:

- every id (a section, a panel, a palette entry) is a name with no `--`
  (Studio qualifies it as `<pack id>--<id>`), unique in the pack;
- a panel's `kind` is one of `KINDS`; `markdown`, `table` and `bundle` name a
  `source`: a file inside the pack's folder (never outside it), or for a
  table `data:<path>` in the pack's data folder; a bundle is an ES module
  (`.js` / `.mjs`) and needs the `studio-script` permission requested; an
  `artifact` panel (3.2.0.0 R5) names a `schema` of `contributes.artifacts` and
  reads `latest` (the newest run's artifact, its default), a JSON file of the
  pack or `data:<path>`;
- `w` is 4..24 columns, `h` 8..200 rows; `columns` is a table's, `links` a
  links panel's (each `{label, route}` or `{label, url}`);
- a panel under `panels:` names the core section it sits in;
- a palette `action` is `route:<section>[/<panel>]`, `url:<address>` or
  `config`; a route names a core section or one of the pack's own;
- `config_form: true` (and a `form` panel) needs `config.schema`; the form is
  its first section's Settings panel, so it needs a section;
- `events` kinds are among `contributes.events`; `attention` kinds are event
  names, each with a label and its keys (a, r, s, o).

The keys that are not panels (config_form, sections' lists, palette, events,
attention) are packs/studio_keys.py's.

    studio_lines(manifest, root)   # [] when the contribution is fine
    studio_of(manifest)            # contributes.studio as a dict ({} when absent)
    panels_of(manifest)            # [(key, section or None, panel)] every declared panel
    bundle_ids(manifest)           # the ids of the bundle panels
"""

from __future__ import annotations

import re
from pathlib import Path

from halo_harness.packs import names as N

CORE_SECTIONS = ("session", "team", "roles", "fleet", "design", "orchestra")
KINDS = ("markdown", "table", "form", "links", "events", "bundle", "artifact")  # artifact: 3.2.0.0 R5
NEED_SOURCE = ("markdown", "table", "bundle", "artifact")
SUFFIXES = {"markdown": (".md", ".markdown", ".txt"), "table": (".json",), "bundle": (".js", ".mjs"), "artifact": (".json",)}
LATEST = "latest"  # an artifact panel's default source: the newest run's artifact of its schema
SCRIPT = "studio-script"
SETTINGS = "settings"  # config_form's panel id in the first section
DATA_PREFIX = "data:"
ANSWER_KEYS = ("a", "r", "s", "o")
URL_RE = re.compile(r"^(https?://\S+|mailto:\S+)$", re.I)
W_RANGE, H_RANGE = (4, 24), (8, 200)


def is_id(value) -> bool:
    return N.is_valid_name(value) and N.SEP not in value and not value.endswith("-")


def studio_of(manifest) -> dict:
    contributes = manifest.get("contributes") if isinstance(manifest, dict) else None
    studio = contributes.get("studio") if isinstance(contributes, dict) else None
    return studio if isinstance(studio, dict) else {}


def _list(d: dict, key: str) -> list:
    v = d.get(key)
    return v if isinstance(v, list) else []


def sections_of(manifest) -> list:
    return [s for s in _list(studio_of(manifest), "sections") if isinstance(s, dict)]


def panels_of(manifest) -> "list[tuple[str, object, dict]]":
    out = []
    for i, s in enumerate(_list(studio_of(manifest), "sections")):
        if isinstance(s, dict):
            out += [(f"contributes.studio.sections[{i}].panels[{j}]", s, p) for j, p in enumerate(_list(s, "panels"))
                    if isinstance(p, dict)]
    out += [(f"contributes.studio.panels[{j}]", None, p) for j, p in enumerate(_list(studio_of(manifest), "panels"))
            if isinstance(p, dict)]
    return out


def bundle_ids(manifest) -> "list[str]":
    return [str(p.get("id")) for _k, _s, p in panels_of(manifest) if p.get("kind") == "bundle"]


class _Lines:
    """Problem lines, each prefixed `pack.yaml line N:` when the key's line is found in the file's text."""

    def __init__(self, text: str):
        self.text, self.out = text, []

    def add(self, key: str, msg: str, name: str = "", value=None) -> None:
        from halo_harness.packs.bio_rules import _line_of
        n = _line_of(self.text, name or key.rsplit(".", 1)[-1].split("[")[0], value) if self.text else 0
        self.out.append(f"pack.yaml line {n}: {key}{msg}" if n else f"{key}{msg}")


def _source(L: _Lines, key: str, p: dict, root) -> None:
    kind, src = p.get("kind"), p.get("source")
    if kind not in NEED_SOURCE:
        if src is not None:
            L.add(f"{key}.source", f": a {kind} panel takes no source", "source", src)
        return
    if kind == "artifact" and src in (None, LATEST):
        return
    if not isinstance(src, str) or not src.strip():
        L.add(f"{key}.source", f": required for a {kind} panel", "kind", kind)
        return
    data = kind in ("table", "artifact") and src.startswith(DATA_PREFIX)
    rel = Path(src[len(DATA_PREFIX):] if data else src)
    if rel.is_absolute() or ".." in rel.parts or src.startswith(("/", "\\")) or ":" in rel.as_posix().split("/")[0]:
        L.add(f"{key}.source", f" {src!r} is outside the pack's folder (a path inside it"
              f"{', or data:<path> in its data folder' if kind == 'table' else ''})", "source", src)
        return
    if rel.suffix.lower() not in SUFFIXES[kind]:
        L.add(f"{key}.source", f" {src!r}: a {kind} panel's source is a {' or '.join(SUFFIXES[kind])} file", "source", src)
        return
    if data or root is None:
        return
    base = Path(root).resolve()
    target = (base / rel).resolve()
    if base not in target.parents:
        L.add(f"{key}.source", f" {src!r} is outside the pack's folder", "source", src)
    elif not target.is_file():
        L.add(f"{key}.source", f" {src} is not in the pack", "source", src)


def route_problem(route, own: dict) -> str:
    """'' when `route` (`<section>[/<panel>]`) names a core section or the pack's own section (and its panel)."""
    sec, _, pan = str(route or "").partition("/")
    if sec in CORE_SECTIONS and not pan:
        return ""
    if sec in own and (not pan or pan in own[sec]):
        return ""
    return (f" {route!r} is not a route: a core section ({', '.join(CORE_SECTIONS)}) or the pack's own "
            f"section[/panel] ({', '.join(own) or 'none declared'})")


def _panel(L: _Lines, key: str, p: dict, root, manifest, own: dict) -> None:
    kind = p.get("kind")
    if kind not in KINDS:
        L.add(f"{key}.kind", f" {kind!r} is not one of {', '.join(KINDS)}", "kind", kind)
        return
    if not isinstance(p.get("title"), str) or not p["title"].strip():
        L.add(f"{key}.title", ": required (the panel's title bar)", "id", p.get("id"))
    _source(L, key, p, root)
    for dim, (lo, hi) in (("w", W_RANGE), ("h", H_RANGE)):
        v = p.get(dim)
        if v is not None and (not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi):
            L.add(f"{key}.{dim}", f" {v!r} is not {lo}..{hi}", dim, v)
    if p.get("columns") is not None and kind != "table":
        L.add(f"{key}.columns", ": columns are a table panel's", "columns")
    links = _list(p, "links")
    if kind == "links" and not links:
        L.add(f"{key}.links", ": a links panel lists {label, route} or {label, url} entries", "kind", kind)
    elif kind != "links" and p.get("links") is not None:
        L.add(f"{key}.links", ": links are a links panel's", "links")
    for i, ln in enumerate(links):
        lk = f"{key}.links[{i}]"
        if not isinstance(ln, dict) or not str(ln.get("label") or "").strip():
            L.add(lk, ": a link has a label", "label")
        elif ("route" in ln) == ("url" in ln):
            L.add(lk, ": a link has a route or a url (one of them)", "label", ln.get("label"))
        elif "url" in ln and not URL_RE.match(str(ln["url"])):
            L.add(f"{lk}.url", f" {ln['url']!r} is not an http(s) or mailto address", "url", ln["url"])
        elif "route" in ln and route_problem(ln["route"], own):
            L.add(f"{lk}.route", route_problem(ln["route"], own), "route", ln["route"])
    if kind == "bundle" and SCRIPT not in _list(manifest, "permissions"):
        L.add(key, f": a bundle panel runs the pack's script, which needs the {SCRIPT!r} permission in pack.yaml's "
              "permissions (you grant it with halo pack enable <id> --grant studio-script)", "kind", "bundle")
    if kind == "form" and not isinstance((manifest.get("config") or {}).get("schema"), dict):
        L.add(key, ": a form panel is the pack's settings form; pack.yaml has no config.schema", "kind", "form")
    from halo_harness.packs.typed import artifact_names  # 3.2.0.0 R5: an artifact panel names one of its schemas
    if kind == "artifact" and p.get("schema") not in artifact_names(manifest):
        L.add(f"{key}.schema", f" {p.get('schema')!r} is not one of contributes.artifacts "
              f"({', '.join(artifact_names(manifest)) or 'none declared'})", "schema", p.get("schema"))
    elif kind != "artifact" and p.get("schema") is not None:
        L.add(f"{key}.schema", ": a schema is an artifact panel's", "schema")
    if kind == "events" and not _list(manifest.get("contributes") or {}, "events"):
        L.add(key, ": an events panel lists the pack's own frames; contributes.events declares none", "kind", "events")


def _ids(L: _Lines, manifest) -> dict:
    """`{section id: {panel ids}}` of the pack's own sections; every id checked once."""
    seen: "dict[str, str]" = {}
    own: "dict[str, set]" = {}

    def one(key: str, value) -> bool:
        if not is_id(value):
            L.add(f"{key}.id", f" {value!r} is not an id (letters, digits, - and _, no '--')", "id", value)
            return False
        if value in seen:
            L.add(f"{key}.id", f" {value!r} is used twice ({seen[value]} has it)", "id", value)
            return False
        seen[value] = key
        return True

    for i, s in enumerate(_list(studio_of(manifest), "sections")):
        key = f"contributes.studio.sections[{i}]"
        if not isinstance(s, dict):
            continue
        if one(key, s.get("id")):
            own[s["id"]] = set()
        if not isinstance(s.get("title"), str) or not s["title"].strip():
            L.add(f"{key}.title", ": required (the section's tab)", "id", s.get("id"))
    for key, s, p in panels_of(manifest):
        if one(key, p.get("id")) and s is not None and s.get("id") in own:
            own[s["id"]].add(p["id"])
    first = sections_of(manifest)[0].get("id") if sections_of(manifest) else None
    if studio_of(manifest).get("config_form") is True and first in own:
        own[first].add(SETTINGS)  # the form's panel (packs/studio_registry.py adds it)
    return own


def studio_lines(manifest, root=None) -> "list[str]":
    if not studio_of(manifest):
        return []
    text = ""
    if root is not None:
        try:
            text = (Path(root) / "pack.yaml").read_text(encoding="utf-8")
        except OSError:
            text = ""
    L = _Lines(text)
    own = _ids(L, manifest)
    for key, _s, p in panels_of(manifest):
        _panel(L, key, p, root, manifest, own)
    from halo_harness.packs.studio_keys import check  # config_form, sections, palette, events, attention
    check(L, manifest, own)
    return L.out
