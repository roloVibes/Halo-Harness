"""halo_harness.design.crafts -- the craft apps as design engines (Halo
3.0.1.0 round D4). Each ArtCraft app ships an MCP server (`<app>-cli mcp`,
registered in Claude Code's user config, so every Halo session sees its
tools as `mcp__<app>__<tool>`). This module holds, per app: what it is for,
the tool recipe the Design skill teaches, the render step that turns its
document into a file the canvas can show, and the tool-name globs the
design session allows. `which_apps(registered)` keeps only the apps whose
server is actually registered, so the skill never names a tool that is
not there.
"""

from __future__ import annotations

APPS = {
    "designcraft": {
        "for": "pages, one-pagers, decks, posters, print layouts (an InDesign-class page layout app)",
        "kinds": ("page", "deck"),
        "recipe": "mcp__designcraft__new_document -> mcp__designcraft__execute frame.create {rect, content: 'text', text} / "
                  "mcp__designcraft__place_image -> mcp__designcraft__set_story_text -> mcp__designcraft__render_page (look) -> "
                  "mcp__designcraft__export_png to artboards/<id>/render.png and mcp__designcraft__save_document to artboards/<id>/source document",
        "render": "mcp__designcraft__export_png", "ext": "png",
    },
    "vectorcraft": {
        "for": "logos, icons, illustrations, diagrams, anything that must stay crisp at any size (an Illustrator-class app)",
        "kinds": ("vector",),
        "recipe": "mcp__vectorcraft__draw_shape / draw_path / add_text -> set_paint / apply_effect / transform -> "
                  "mcp__vectorcraft__screenshot (look) -> mcp__vectorcraft__export to artboards/<id>/render.svg (and .png) -> save_file",
        "render": "mcp__vectorcraft__export", "ext": "svg",
    },
    "photocraft": {
        "for": "photo compositing, retouching, raster mockups, social images (a Photoshop-class app)",
        "kinds": ("photo", "image"),
        "recipe": "mcp__photocraft__doc_new or doc_open -> mcp__photocraft__command_run / command_batch (command_list first) -> "
                  "mcp__photocraft__doc_render_preview (look) -> mcp__photocraft__doc_export to artboards/<id>/render.png -> doc_save",
        "render": "mcp__photocraft__doc_export", "ext": "png",
    },
    "lightcraft": {
        "for": "developing and batch-exporting photos, building an asset library (a Lightroom-class app)",
        "kinds": ("photo",),
        "recipe": "mcp__lightcraft__import / query_photos -> select_photos -> set_develop / apply_preset / crop -> "
                  "mcp__lightcraft__render_photo (look) -> mcp__lightcraft__export to assets/",
        "render": "mcp__lightcraft__export", "ext": "jpg",
    },
    "effectcraft": {
        "for": "motion graphics, animated logos, title cards, animated social assets (an After Effects-class compositor)",
        "kinds": ("motion",),
        "recipe": "mcp__effectcraft__execute_command comp.new -> layer.newText / layer.newSolid -> set_property / add_keyframe / "
                  "effect.apply -> mcp__effectcraft__render_frame to artboards/<id>/render.png (a still) -> save_project",
        "render": "mcp__effectcraft__render_frame", "ext": "png",
    },
    "filmcraft": {
        "for": "video cuts, trailers, product clips (a Premiere-class editor)",
        "kinds": ("video",),
        "recipe": "mcp__filmcraft__media_import -> mcp__filmcraft__command_batch (command_list first; command_run drops params) -> "
                  "mcp__filmcraft__render_frame to artboards/<id>/render.png (a poster frame) -> render_preview",
        "render": "mcp__filmcraft__render_frame", "ext": "png",
    },
    "pdfcraft": {
        "for": "assembling, annotating, signing and checking PDFs; forms; accessibility; exporting a deck to PDF",
        "kinds": ("pdf",),
        "recipe": "mcp__pdfcraft__doc_create or doc_open -> page_add_text / page_add_image / form_add_field -> "
                  "mcp__pdfcraft__page_render to artboards/<id>/render.png (page 1) -> mcp__pdfcraft__doc_save to artboards/<id>/render.pdf",
        "render": "mcp__pdfcraft__page_render", "ext": "pdf",
    },
}

CORE_TOOLS = ("Read", "Write", "Edit", "Glob", "Grep", "Bash", "WebFetch")


def which_apps(registered: "set[str] | list[str] | None") -> dict:
    """The APPS whose MCP server name is in `registered` (None = all)."""
    if registered is None:
        return dict(APPS)
    names = {str(n).lower() for n in registered}
    return {k: v for k, v in APPS.items() if k in names}


def allowed_tools(registered=None) -> str:
    """The --tools allowlist for a design turn: the core file tools and
    every tool of every present craft app."""
    apps = which_apps(registered)
    return ",".join([*CORE_TOOLS, *(f"mcp__{app}__*" for app in apps)])


def guide_lines(registered=None) -> list:
    """The part of the Design skill that says which app does what."""
    apps = which_apps(registered)
    if not apps:
        return ["No craft app is registered on this machine: make prototypes and pages as HTML/CSS/JS artboards, "
                "and SVG by writing the file yourself."]
    out = ["The craft apps on this machine, each an MCP server whose tools you already have:"]
    for app, spec in apps.items():
        out.append(f"- {app}: {spec['for']}. Recipe: {spec['recipe']}.")
    out.append("Every craft deliverable ends with its render saved INSIDE the artboard folder (render.png / render.svg / "
               "render.pdf) and a source.json naming the app, the saved document's path, the kind and a title. "
               "Look at your render (the app's own preview tool, or Read the PNG) before you stop.")
    return out


def registered_craft_servers() -> set:
    """The craft apps whose MCP server is registered for this user (the
    same user-scope config every Halo session loads)."""
    found = set()
    try:
        from halo_harness.mcp.config import discover_servers  # type: ignore
        for name in discover_servers().keys():  # pragma: no cover - depends on the local config
            if name.lower() in APPS:
                found.add(name.lower())
        return found
    except Exception:
        pass
    try:
        import json
        from pathlib import Path
        cfg = json.loads((Path.home() / ".claude.json").read_text(encoding="utf-8"))
        for name in (cfg.get("mcpServers") or {}):
            if name.lower() in APPS:
                found.add(name.lower())
    except Exception:
        pass
    return found
