"""halo_harness.design.export -- exports and the handoff bundle (Halo
3.0.1.0 round D2). `folder` copies every artboard's current files into one
static folder with an index page (shareable as is); `html` the prototypes;
`png` / `svg` / `pdf` the renders (a PDF of an HTML artboard goes through
PdfCraft when its server is registered, otherwise the export says so). The
handoff bundle is a folder with the artboards' sources, system.json and a
HANDOFF.md the next Halo or Claude Code session starts from.
"""

from __future__ import annotations

import html
import shutil
import time
import urllib.parse
from pathlib import Path
from typing import Optional

from halo_harness.design.store import Project


def _target(project: Project, out: Optional[Path], suffix: str) -> Path:
    if out is None:
        out = project.path / "exports" / f"{time.strftime('%Y%m%d-%H%M%S')}-{suffix}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _e(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _url(path: str) -> str:
    """A relative path as an attribute-safe URL: each segment percent-encoded."""
    return _e("/".join(urllib.parse.quote(part) for part in str(path).split("/")))


def _thumb(item: dict) -> str:
    return f'<img src="{_url(item["thumb"])}">' if item.get("thumb") else "<span>html</span>"


def _index_html(project: Project, items: list) -> str:
    meta = project.meta()
    name = _e(meta.get("name", project.slug))
    cards = "\n".join(
        f'<a class="card" href="{_url(i["href"])}"><div class="thumb">{_thumb(i)}</div>'
        f'<b>{_e(i["title"])}</b><small>{_e(i["kind"])} · v{_e(i["version"])}</small></a>' for i in items)
    return f"""<!doctype html><meta charset="utf-8"><title>{name}</title>
<style>body{{font:15px system-ui;margin:0;background:#15161c;color:#e6e6ef}}header{{padding:28px 32px 8px}}h1{{margin:0;font-size:22px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;padding:16px 32px 40px}}
.card{{display:block;color:inherit;text-decoration:none;border:1px solid #2a2c38;border-radius:12px;overflow:hidden;background:#1d1f29}}
.thumb{{aspect-ratio:16/10;background:#0f1016;display:grid;place-items:center;color:#777}}.thumb img{{width:100%;height:100%;object-fit:cover}}
.card b{{display:block;padding:10px 12px 0}}.card small{{display:block;padding:2px 12px 12px;color:#9a9db0}}</style>
<header><h1>{name}</h1><small>exported by Halo Design</small></header><div class="grid">{cards}</div>"""


def export_project(project: Project, kind: str, out: Optional[Path] = None, *, artboard: str = "") -> list:
    boards = [a for a in project.artboards() if not artboard or a["id"] == artboard]
    lines = []
    if kind == "folder":
        target = _target(project, out, "site")
        items = []
        for a in boards:
            dst = target / a["id"]
            replaced = dst.exists()
            shutil.copytree(project.artboard_dir(a["id"]), dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("v*", "version.json"))
            if replaced:
                lines.append(f"{a['id']}: overwrote the files in the existing {dst}")
            href = f"{a['id']}/index.html" if "index.html" in a["files"] else (f"{a['id']}/{a['render']}" if a.get("render") else f"{a['id']}/")
            thumb = f"{a['id']}/{a['render']}" if a.get("render") and a["render"] != "index.html" and not a["render"].endswith((".pdf", ".mp4")) else ""
            items.append({"href": href, "thumb": thumb, "title": a["title"], "kind": a["kind"], "version": a["latest"]})
        (target / "index.html").write_text(_index_html(project, items), encoding="utf-8")
        lines.append(f"folder: {target} ({len(items)} artboard(s); open index.html)")
        return lines
    target = _target(project, out, kind)
    for a in boards:
        d = project.artboard_dir(a["id"])
        if kind == "html" and (d / "index.html").is_file():
            shutil.copy2(d / "index.html", target / f"{a['id']}.html")
            lines.append(f"{a['id']}: {target / (a['id'] + '.html')}")
        elif kind in ("png", "svg") and (d / f"render.{kind}").is_file():
            shutil.copy2(d / f"render.{kind}", target / f"{a['id']}.{kind}")
            lines.append(f"{a['id']}: {target / (a['id'] + '.' + kind)}")
        elif kind == "pdf":
            if (d / "render.pdf").is_file():
                shutil.copy2(d / "render.pdf", target / f"{a['id']}.pdf")
                lines.append(f"{a['id']}: {target / (a['id'] + '.pdf')}")
            else:
                lines.append(f"{a['id']}: no render.pdf yet -- ask for one in a turn (\"export {a['id']} as a PDF through PdfCraft\")")
        else:
            lines.append(f"{a['id']}: nothing to export as {kind}")
    return lines


def handoff_bundle(project: Project, out: Optional[Path] = None) -> Path:
    target = _target(project, out, "handoff")
    meta = project.meta()
    for a in project.artboards():
        shutil.copytree(project.artboard_dir(a["id"]), target / "artboards" / a["id"], dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("v*", "version.json"))
    if (project.path / "system.json").is_file():
        shutil.copy2(project.path / "system.json", target / "system.json")
    if (project.path / "assets").is_dir():
        shutil.copytree(project.path / "assets", target / "assets", dirs_exist_ok=True)
    boards = "\n".join(f"- `artboards/{a['id']}/` ({a['kind']}{', ' + a['app'] if a.get('app') else ''}): {a['title']}" for a in project.artboards())
    pins = [c for c in project.comments() if not c.get("resolved")]
    hist = project.history()
    text = f"""# Handoff: {meta.get('name', project.slug)}

This folder is a Halo Design handoff bundle. Continue the work here: the artboards are
the designs (an `index.html` is a self-contained prototype; `render.*` plus `source.json`
is a craft-app deliverable), `system.json` is the design system to keep to, `assets/`
the inputs.

## Artboards
{boards or '- (none yet)'}

## Open comments
{chr(10).join('- ' + c['artboard'] + ': ' + c['text'] for c in pins) or '- none'}

## What was asked so far
{chr(10).join('- ' + (h.get('prompt') or '')[:140] for h in hist[-12:]) or '- nothing yet'}

## How to continue
Build the real thing from these artboards: keep the tokens in `system.json`, keep every
artboard's intent, and when you change a design update its folder here so the bundle stays
the source of truth. `halo design` made this on {time.strftime('%Y-%m-%d')}.
"""
    (target / "HANDOFF.md").write_text(text, encoding="utf-8")
    return target
