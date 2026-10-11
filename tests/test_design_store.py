"""tests.test_design_store -- the design project on disk (Halo 3.0.1.0
round D2): create/open/list, artboards registered and discovered, versions
only when files change, restore, comments, knobs, the design system from a
codebase scan and a captured page, the folder/html/png exports with an
index page, and the handoff bundle. Scoped home, no network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_projects_artboards_versions_and_restore(ctx: Ctx):
    from halo_harness.design.store import Project
    p = Project.create("Store Launch Page", model="or:v/eyes")
    ctx.check("a project is a folder with design.json under ~/.halo/design", p.slug == "store-launch-page" and (p.path / "design.json").is_file())
    ctx.check("open and list find it", Project.open("store-launch-page") is not None and any(r["slug"] == "store-launch-page" for r in Project.list()))
    ctx.check("a second project with the same name gets a numbered slug", Project.create("Store Launch Page").slug == "store-launch-page-2")
    a = p.add_artboard("Hero", "prototype")
    (p.artboard_dir(a["id"]) / "index.html").write_text("<h1>v1</h1>", encoding="utf-8")
    ctx.check("the first snapshot makes v1", p.snapshot("first") == [("hero", 1)])
    ctx.check("an unchanged artboard is not versioned again", p.snapshot("again") == [])
    (p.artboard_dir("hero") / "index.html").write_text("<h1>v2</h1>", encoding="utf-8")
    ctx.check("a change makes v2", p.snapshot("second") == [("hero", 2)] and p.artboards()[0]["latest"] == 2)
    ctx.check("restore brings v1 back", p.restore("hero", 1) and (p.artboard_dir("hero") / "index.html").read_text(encoding="utf-8") == "<h1>v1</h1>")
    ctx.check("restoring a missing version fails cleanly", p.restore("hero", 9) is False)
    d = p.path / "artboards" / "logo-mark"
    d.mkdir()
    (d / "render.svg").write_text("<svg/>", encoding="utf-8")
    (d / "source.json").write_text(json.dumps({"app": "vectorcraft", "kind": "vector", "title": "Logo mark"}), encoding="utf-8")
    found = p.discover_artboards()
    ctx.check("a folder the model created is discovered with its kind and app", found and found[0]["id"] == "logo-mark" and found[0]["kind"] == "vector" and found[0]["app"] == "vectorcraft")
    boards = {b["id"]: b for b in p.artboards()}
    ctx.check("artboards report their render file", boards["logo-mark"]["render"] == "render.svg" and boards["hero"]["render"] == "index.html")
    ctx.check("remove drops the artboard and its folder", p.remove_artboard("logo-mark") and not d.exists())


@test
def test_comments_controls_system_and_history(ctx: Ctx):
    from halo_harness.design.store import Project
    p = Project.create("Deck")
    p.add_artboard("Cover", "deck", app="designcraft")
    c = p.add_comment("cover", "make the title bigger", x=40, y=12)
    ctx.check("a comment is a pin with a position", p.comments()[0]["text"] == "make the title bigger" and p.comments()[0]["x"] == 40)
    ctx.check("resolve marks it", p.resolve_comments([c["id"]]) == 1 and p.comments()[0]["resolved"] is True)
    (p.artboard_dir("cover") / "controls.json").write_text(json.dumps([{"name": "Spacing", "kind": "range", "target": "css:--space", "min": 0, "max": 64, "value": 16}]), encoding="utf-8")
    ctx.check("a knob can be moved", p.set_control("cover", "Spacing", 24)["value"] == 24 and p.controls("cover")[0]["value"] == 24)
    ctx.check("an unknown knob is None", p.set_control("cover", "Nope", 1) is None)
    p.save_system({"tokens": {"colors": {"--accent": "#89b4fa"}}})
    ctx.check("the system round-trips", p.system()["tokens"]["colors"]["--accent"] == "#89b4fa")
    p.log_turn({"prompt": "hi", "cost": 0.01})
    ctx.check("history is one line per turn", p.history()[-1]["prompt"] == "hi")


@test
def test_design_system_sync(ctx: Ctx):
    from halo_harness.design.store import Project
    from halo_harness.design.sync import capture_url, scan_codebase, tokens_from_json, tokens_from_tailwind, write_system
    from halo_harness.providers.config import default_state_dir
    root = Path(default_state_dir()).parent / "fake-codebase"
    (root / "src" / "components").mkdir(parents=True, exist_ok=True)
    (root / "src" / "theme.css").write_text(":root{--color-accent:#1e66f5;--space-4:16px;--radius-md:8px;--font-sans:Inter,sans-serif;} body{font-family: Inter, sans-serif;}", encoding="utf-8")
    (root / "tailwind.config.js").write_text("module.exports={theme:{extend:{colors:{brand:'#ff0066',ink:'#111111'},borderRadius:{xl:'20px'}}}}", encoding="utf-8")
    (root / "tokens.json").write_text(json.dumps({"color": {"primary": {"value": "#123456"}}, "space": {"sm": {"value": "4px"}}}), encoding="utf-8")
    (root / "src" / "components" / "Button.tsx").write_text("export const Button = () => null", encoding="utf-8")
    (root / "node_modules").mkdir(exist_ok=True)
    (root / "node_modules" / "x.css").write_text(":root{--junk:1}", encoding="utf-8")
    sysd = scan_codebase(root)
    tok = sysd["tokens"]
    ctx.check("CSS custom properties are grouped", tok["colors"]["--color-accent"] == "#1e66f5" and tok["spacing"]["--space-4"] == "16px" and tok["radii"]["--radius-md"] == "8px")
    ctx.check("font families are read", "Inter" in tok["typography"].get("font-families", "") or "--font-sans" in tok["typography"])
    ctx.check("a tailwind config contributes literal colours", tokens_from_tailwind((root / "tailwind.config.js").read_text())["colors"]["brand"] == "#ff0066" and tok["colors"].get("brand") == "#ff0066")
    ctx.check("W3C tokens are read", tokens_from_json({"color": {"primary": {"value": "#123456"}}})["colors"]["color.primary"] == "#123456" and tok["colors"].get("color.primary") == "#123456")
    ctx.check("components are listed and node_modules is skipped", any(c["name"] == "Button" for c in sysd["components"]) and "--junk" not in tok.get("other", {}))
    page = capture_url("https://example.test/", fetch=lambda u: "<style>:root{--brand:#abcdef}</style><link rel='stylesheet' href='/a.css'>" if u.endswith("/") else ":root{--from-sheet:#000}")
    ctx.check("a URL capture reads inline and linked stylesheets", page["tokens"]["other"].get("--brand") == "#abcdef" and page["tokens"]["other"].get("--from-sheet") == "#000" and page["sources"] == ["url:https://example.test/"])
    p = Project.create("Synced")
    merged = write_system(p, sysd)
    write_system(p, page)
    ctx.check("write_system merges with provenance", "brand" in p.system()["tokens"]["colors"] and any(s.startswith("url:") for s in p.system()["sources"]) and merged["name"] == "default")


@test
def test_exports_and_handoff(ctx: Ctx):
    from halo_harness.design.export import export_project, handoff_bundle
    from halo_harness.design.store import Project
    p = Project.create("Export Me")
    p.add_artboard("Hero", "prototype")
    (p.artboard_dir("hero") / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")
    p.add_artboard("Mark", "vector", app="vectorcraft")
    (p.artboard_dir("mark") / "render.svg").write_text("<svg/>", encoding="utf-8")
    (p.artboard_dir("mark") / "render.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    p.snapshot()
    lines = export_project(p, "folder")
    out = Path(lines[0].split("folder: ")[1].split(" (")[0])
    ctx.check("a folder export has an index page and every artboard", (out / "index.html").is_file() and (out / "hero" / "index.html").is_file() and (out / "mark" / "render.svg").is_file())
    ctx.check("versions are not copied into the export", not (out / "hero" / "v1").exists())
    html = export_project(p, "html")
    ctx.check("html exports the prototypes", any("hero.html" in l for l in html))
    png = export_project(p, "png")
    ctx.check("png exports the raster renders", any("mark.png" in l for l in png) and any("nothing to export" in l for l in png))
    pdf = export_project(p, "pdf")
    ctx.check("a missing pdf says how to get one", any("no render.pdf yet" in l for l in pdf))
    bundle = handoff_bundle(p)
    text = (bundle / "HANDOFF.md").read_text(encoding="utf-8")
    ctx.check("the handoff bundle carries the artboards and a HANDOFF.md naming them", (bundle / "artboards" / "hero" / "index.html").is_file() and "artboards/hero/" in text and "artboards/mark/" in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="design store tests"))
