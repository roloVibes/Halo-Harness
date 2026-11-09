"""The design pack's tests/test_studio_design.py (was tests/test_studio_design.py in Halo's core) -- Studio's Design mode backend (Halo 3.0.1.0
round D3) over the in-process server and a fake turn runner: projects, a live
turn polled to its end, comments, knobs applied in place, direct text edits,
versions, the design system, exports, the handoff, the raw artboard file
route and its sandbox headers, the token guard, one turn at a time; plus the
`design.controls` unit checks (the Design page in headless Chrome is Halo's tests/test_pack_design_ui.py).
Since the pack (3.3.13.0 R2) over `testing.studio` (tests/rig.py): the routes are the pack's, the files its `_files/`.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

from tests.run import Ctx, main, mod, new_registry, scratch  # noqa: E402

scratch()

from tests.rig import _fake_runner, _Studio  # noqa: E402

test, TESTS = new_registry()


@test
def test_projects_models_and_the_guard(ctx: Ctx):
    with _Studio() as s:
        status, r = s.call("POST", "/api/design/projects", {"name": "Launch Page", "model": "or:v/eyes"})
        ctx.check("a project is created (201 with a slug)", status == 201 and r["slug"] == "launch-page")
        ctx.check("a blank name is a 422 with the reason", s.call("POST", "/api/design/projects", {"name": " "})[0] == 422)
        status, r = s.call("GET", "/api/design/projects")
        ctx.check("the list has it with its model", status == 200 and any(x["slug"] == "launch-page" and x["model"] == "or:v/eyes" for x in r["projects"]))
        status, r = s.call("GET", "/api/design/launch-page")
        ctx.check("the detail carries meta, artboards, comments, system, history and no live turn",
                  status == 200 and r["meta"]["name"] == "Launch Page" and r["artboards"] == [] and r["comments"] == [] and r["live_turn"] is None and "history" in r and "system" in r)
        ctx.check("an unknown slug is a 404 with an error", s.call("GET", "/api/design/nope")[0] == 404 and s.call("GET", "/api/design/..")[0] == 404)
        status, r = s.call("PUT", "/api/design/launch-page/model", {"model": "or:v/other"})  # 3.1.4.0 R4: the Projects panel's model select
        ctx.check("PUT <slug>/model changes the project's model", status == 200 and r["model"] == "or:v/other"
                  and s.call("GET", "/api/design/launch-page")[1]["meta"]["model"] == "or:v/other")
        ctx.check("an empty model is the default model again", s.call("PUT", "/api/design/launch-page/model", {"model": ""})[1]["model"] == ""
                  and any(x["slug"] == "launch-page" and x["model"] == "" for x in s.call("GET", "/api/design/projects")[1]["projects"]))
        ctx.check("a model that is not a string is a 422", s.call("PUT", "/api/design/launch-page/model", {"model": 3})[0] == 422)
        s.call("PUT", "/api/design/launch-page/model", {"model": "or:v/eyes"})
        status, r = s.call("GET", "/api/design/models")
        ctx.check("the design ranking is a list of at most 12 rows", status == 200 and isinstance(r, list) and len(r) <= 12)
        ctx.check("a wrong token is a 401", s.call("GET", "/api/design/projects", token="wrong")[0] == 401)


@test
def test_turn_streams_in_order_and_versions_the_artboard(ctx: Ctx):
    with _Studio() as s:
        slug = s.call("POST", "/api/design/projects", {"name": "Turny"})[1]["slug"]
        seen, p = s.run_turn(slug, "A hero section")
        ctx.check("events arrive in order", [e.get("type") for e in seen] == ["system", "assistant", "result", "halo_design"])
        ctx.check("the result has the cost and the new version", p["done"] and p["result"]["cost"] == 0.02 and p["result"]["versions"] == [["hero", 1]])
        _, d = s.call("GET", f"/api/design/{slug}")
        ctx.check("the artboard is registered with v1, its knobs and its render", d["artboards"][0]["latest"] == 1 and d["artboards"][0]["render"] == "index.html" and len(d["artboards"][0]["controls"]) == 2)
        ctx.check("the history has the prompt and cost", d["history"][-1]["prompt"] == "A hero section" and d["history"][-1]["cost"] == 0.02)
        ctx.check("an unknown turn is a 404", s.call("GET", f"/api/design/{slug}/turn/t0")[0] == 404)
        ctx.check("an empty prompt is a 422", s.call("POST", f"/api/design/{slug}/run", {"prompt": ""})[0] == 422)


@test
def test_comment_resolve_knob_text_edit_versions_restore(ctx: Ctx):
    with _Studio() as s:
        slug = s.seeded()
        status, c = s.call("POST", f"/api/design/{slug}/comment", {"artboard": "hero", "text": "bigger title", "x": 40, "y": 12, "path": "h1"})
        ctx.check("a comment is pinned on the artboard", status == 201 and c["artboard"] == "hero" and c["x"] == 40 and c["version"] == 1)
        ctx.check("a comment on an unknown artboard is a 404", s.call("POST", f"/api/design/{slug}/comment", {"artboard": "x", "text": "t"})[0] == 404)
        status, r = s.call("POST", f"/api/design/{slug}/comments/resolve", {"ids": [c["id"]]})
        ctx.check("resolve closes it", status == 200 and r["resolved"] == 1 and s.call("GET", f"/api/design/{slug}")[1]["comments"][0]["resolved"] is True)
        status, r = s.call("POST", f"/api/design/{slug}/control", {"artboard": "hero", "name": "Spacing", "value": 24})
        html = (s.root / slug / "artboards" / "hero" / "index.html").read_text(encoding="utf-8")
        ctx.check("a css knob rewrites the variable in place with the page's unit", status == 200 and "--space:24px" in html and "body{padding:var(--space)}" in html and r["value"] == "24px")
        vs = s.call("GET", f"/api/design/{slug}/artboard/hero/versions")[1]
        ctx.check("the knob made v2 with its note", [v["version"] for v in vs] == [1, 2] and vs[1]["note"] == "knob Spacing")
        ctx.check("the knob's value is saved in controls.json", s.call("GET", f"/api/design/{slug}")[1]["artboards"][0]["controls"][0]["value"] == 24)
        status, r = s.call("POST", f"/api/design/{slug}/control", {"artboard": "hero", "name": "Title size", "value": 40})
        ctx.check("a craft knob is queued for the next turn", status == 202 and r["queued"] is True)
        ctx.check("an unknown knob is a 422", s.call("POST", f"/api/design/{slug}/control", {"artboard": "hero", "name": "Nope", "value": 1})[0] == 422)
        edited = html.replace("Hello", "Hello, world") .replace("<body>", '<body contenteditable="true">').replace("</body>", "<!--halo-edit--><script>1</script><!--/halo-edit--></body>")
        status, r = s.call("POST", f"/api/design/{slug}/text-edit", {"artboard": "hero", "html": edited})
        saved = (s.root / slug / "artboards" / "hero" / "index.html").read_text(encoding="utf-8")
        ctx.check("a direct edit is saved as v3 with the helper script and contenteditable stripped",
                  status == 200 and "Hello, world" in saved and "halo-edit" not in saved and "contenteditable" not in saved and r["versions"] == [["hero", 3]])
        vs = s.call("GET", f"/api/design/{slug}/artboard/hero/versions")[1]
        ctx.check("the versions list has version, created and note", [v["version"] for v in vs] == [1, 2, 3] and vs[2]["note"] == "direct edit" and vs[0]["created"])
        status, r = s.call("POST", f"/api/design/{slug}/artboard/hero/restore", {"version": 1})
        now = (s.root / slug / "artboards" / "hero" / "index.html").read_text(encoding="utf-8")
        ctx.check("restore brings v1 back as the newest version", status == 200 and "--space:16px" in now and "Hello, world" not in now and r["versions"] == [["hero", 4]])
        ctx.check("restoring a missing version is a 404", s.call("POST", f"/api/design/{slug}/artboard/hero/restore", {"version": 99})[0] == 404)


@test
def test_system_sync_export_and_handoff(ctx: Ctx):
    with _Studio() as s:
        slug = s.seeded("Systems")
        tokens = {"tokens": {"colors": {"--accent": "#89b4fa"}}, "components": [{"name": "Button"}], "sources": ["by hand"]}
        status, r = s.call("PUT", f"/api/design/{slug}/system", {"system": tokens})
        ctx.check("PUT system saves the tokens", status == 200 and r["system"]["tokens"]["colors"]["--accent"] == "#89b4fa"
                  and s.call("GET", f"/api/design/{slug}")[1]["system"]["components"][0]["name"] == "Button")
        ctx.check("a malformed system is a 422", s.call("PUT", f"/api/design/{slug}/system", {"system": {"tokens": "no"}})[0] == 422)
        code = s.state.parent / "codebase"
        code.mkdir()
        (code / "theme.css").write_text(":root{--brand:#ff6600;--radius:8px}", encoding="utf-8")
        status, r = s.call("POST", f"/api/design/{slug}/sync", {"source": str(code)})
        ctx.check("sync reads a folder's tokens into the system", status == 200 and r["tokens"] >= 3 and "--brand" in json.dumps(r["system"]["tokens"]))
        ctx.check("sync of a missing path is a 422", s.call("POST", f"/api/design/{slug}/sync", {"source": str(code / "nope")})[0] == 422)
        status, r = s.call("POST", f"/api/design/{slug}/export", {"as": "folder"})
        folder = Path(r["lines"][0].split("folder: ", 1)[1].split(" (")[0])
        ctx.check("export folder returns a path that exists with an index", status == 200 and (folder / "index.html").is_file() and (folder / "hero" / "index.html").is_file())
        status, r = s.call("POST", f"/api/design/{slug}/export", {"as": "html", "artboard": "hero"})
        ctx.check("export html lists the artboard file", status == 200 and r["lines"][0].startswith("hero:") and Path(r["lines"][0].split(": ", 1)[1]).is_file())
        ctx.check("an unknown export kind is a 422", s.call("POST", f"/api/design/{slug}/export", {"as": "exe"})[0] == 422)
        status, r = s.call("POST", f"/api/design/{slug}/handoff", {})
        ctx.check("handoff returns a bundle with HANDOFF.md", status == 200 and (Path(r["path"]) / "HANDOFF.md").is_file())


@test
def test_raw_artboard_file_route_and_its_sandbox(ctx: Ctx):
    with _Studio() as s:
        slug = s.seeded("Raw")
        status, h, body = s.raw(f"/design-files/{slug}/hero/index.html")
        csp = h.get("Content-Security-Policy", "")
        ctx.check("index.html is served as HTML with the sandbox CSP and nosniff", status == 200 and b"--space:16px" in body and h["Content-Type"].startswith("text/html")
                  and csp == "default-src 'self' 'unsafe-inline' data: blob:; sandbox allow-scripts" and h.get("X-Content-Type-Options") == "nosniff")
        status, h, body = s.raw(f"/design-files/{slug}/hero/v1/index.html")
        ctx.check("a version's file is served too", status == 200 and b"--space:16px" in body)
        ctx.check("a path with .. is a 404", s.raw(f"/design-files/{slug}/hero/../../design.json")[0] == 404 and s.raw(f"/design-files/{slug}/hero/%2e%2e/design.json")[0] == 404)
        ctx.check("an unknown slug, artboard or file is a 404", s.raw("/design-files/nope/hero/index.html")[0] == 404 and s.raw(f"/design-files/{slug}/zzz/index.html")[0] == 404
                  and s.raw(f"/design-files/{slug}/hero/nothing.html")[0] == 404)
        status, h, body = s.raw(f"/design-files/{slug}/hero/index.html?edit=1")
        text = body.decode("utf-8")
        ctx.check("edit=1 injects the marked helper before </body>", status == 200 and "<!--halo-edit-->" in text and "halo-design-edit" in text and text.index("halo-edit-script") < text.index("</body>"))
        ctx.check("the helper is not injected into a version", b"halo-edit" not in s.raw(f"/design-files/{slug}/hero/v1/index.html?edit=1")[2])
        (s.root / slug / "artboards" / "hero" / "render.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
        ctx.check("an svg render has an image content type", s.raw(f"/design-files/{slug}/hero/render.svg")[1]["Content-Type"].startswith("image/svg+xml"))


@test
def test_one_turn_at_a_time(ctx: Ctx):
    gate = threading.Event()
    with _Studio() as s:
        s.api.RUNNER = _fake_runner(gate)
        slug = s.call("POST", "/api/design/projects", {"name": "Busy"})[1]["slug"]
        status, r = s.call("POST", f"/api/design/{slug}/run", {"prompt": "first"})
        ctx.check("the first turn starts", status == 200)
        status, r2 = s.call("POST", f"/api/design/{slug}/run", {"prompt": "second"})
        ctx.check("a second run while one is live is a 409 with a plain sentence", status == 409 and "already has a turn running" in r2["error"])
        ctx.check("the detail names the live turn", s.call("GET", f"/api/design/{slug}")[1]["live_turn"] == r["turn"])
        gate.set()
        deadline = time.time() + 10
        while time.time() < deadline and not s.call("GET", f"/api/design/{slug}/turn/{r['turn']}")[1]["done"]:
            time.sleep(0.05)
        ctx.check("after it finishes a new turn is accepted", s.call("POST", f"/api/design/{slug}/run", {"prompt": "third"})[0] == 200)
        gate.set()
        time.sleep(0.3)


@test
def test_apply_css_control_unit(ctx: Ctx):
    _m = mod("server/controls.py")
    apply_css_control, css_value, read_css_var = _m.apply_css_control, _m.css_value, _m.read_css_var
    html = "<style>:root{--space:16px;--accent:#fff}.a{--space:1px}</style>"
    out = apply_css_control(html, "--space", "24px")
    ctx.check("an existing value is replaced", ":root{--space:24px;--accent:#fff}" in out)
    ctx.check("other declarations are left alone", "--accent:#fff" in out and ".a{--space:1px}" in out)
    out = apply_css_control(html, "gap", "4px")
    ctx.check("a missing variable is added to :root", ":root{--space:16px;--accent:#fff;--gap:4px;}" in out)
    out = apply_css_control("<style>:root{ --x : 1px ; --y:2px }</style>", "--x", "9px")
    ctx.check("`--x : 1px` spacing is handled", "--x : 9px ;" in out and "--y:2px" in out)
    ctx.check("a last declaration without ; is replaced", ":root{--a:2px}" in apply_css_control(":root{--a:1px}", "--a", "2px"))
    ctx.check("a prefix name is not mistaken for the variable", ":root{--space-lg:8px;--space:3px}" in apply_css_control(":root{--space-lg:8px;--space:1px}", "--space", "3px"))
    ctx.check("no :root adds a style block in the head", "<head><style>:root{--k:1;}</style></head>" in apply_css_control("<html><head></head></html>", "--k", "1"))
    ctx.check("a unit is inferred from the page", css_value(html, "--space", 24) == "24px" and css_value(html, "--accent", "#000") == "#000" and css_value(html, "--space", 2, "rem") == "2rem")
    ctx.check("read_css_var reads the root value", read_css_var(html, "space") == "16px")
    try:
        apply_css_control(html, "--space", "1px;}body{display:none")
        bad = False
    except ValueError:
        bad = True
    ctx.check("a value that would break out of the declaration is rejected", bad)




if __name__ == "__main__":
    sys.exit(main(TESTS))
