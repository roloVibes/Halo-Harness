"""tests.test_studio_design -- Studio's Design mode backend (Halo 3.0.1.0
round D3) over the in-process server and a fake turn runner: projects, a live
turn polled to its end, comments, knobs applied in place, direct text edits,
versions, the design system, exports, the handoff, the raw artboard file
route and its sandbox headers, the token guard, one turn at a time; plus the
`design.controls` unit checks and the page's files.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
HERO = '<!doctype html><html><head><style>:root{--space:16px}body{padding:var(--space)}</style></head><body><h1>Hello</h1></body></html>'
KNOBS = [{"name": "Spacing", "kind": "range", "target": "css:--space", "min": 0, "max": 64, "step": 1, "value": 16},
         {"name": "Title size", "kind": "range", "target": "craft:designcraft:size", "min": 8, "max": 96, "value": 32}]


class _Studio:
    def __enter__(self):
        from halo_harness.providers.config import default_state_dir
        from halo_harness.studio import design_api
        from halo_harness.studio.server import start_server
        self.api = design_api
        design_api.RUNNER, design_api.REGISTERED = _fake_runner(), set()
        self.state = Path(default_state_dir())
        self.srv = start_server(port=0, cwd=self.state.parent / "proj", state_dir=self.state)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        return self

    def __exit__(self, *a):
        self.api.RUNNER = self.api.REGISTERED = None
        self.srv.shutdown()
        self.srv.server_close()

    def call(self, method, path, body=None, token=None):
        req = urllib.request.Request(self.base + path, method=method, data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Authorization", "Bearer " + (self.srv.token if token is None else token))
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def raw(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=10) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def run_turn(self, slug, prompt="A hero"):
        status, r = self.call("POST", f"/api/design/{slug}/run", {"prompt": prompt})
        assert status == 200, (status, r)
        seen, since, deadline = [], 0, time.time() + 15
        while time.time() < deadline:
            _, p = self.call("GET", f"/api/design/{slug}/turn/{r['turn']}?since={since}")
            seen += p["events"]
            since = p["next"]
            if p["done"]:
                return seen, p
            time.sleep(0.05)
        raise AssertionError("the turn never finished")

    def seeded(self, name="Hero Lab"):
        slug = self.call("POST", "/api/design/projects", {"name": name, "model": "or:v/eyes"})[1]["slug"]
        self.run_turn(slug)
        return slug


def _fake_runner(gate=None):
    def runner(cmd, cwd, env, on_line):
        d = Path(cwd) / "artboards" / "hero"
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(HERO, encoding="utf-8")
        (d / "controls.json").write_text(json.dumps(KNOBS), encoding="utf-8")
        on_line(json.dumps({"type": "system", "subtype": "init"}))
        if gate is not None:
            gate.wait(10)
        on_line(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Making the hero."}]}}))
        on_line(json.dumps({"type": "result", "result": "Done: hero.", "total_cost_usd": 0.02}))
        return 0
    return runner


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
        html = (s.state / "design" / slug / "artboards" / "hero" / "index.html").read_text(encoding="utf-8")
        ctx.check("a css knob rewrites the variable in place with the page's unit", status == 200 and "--space:24px" in html and "body{padding:var(--space)}" in html and r["value"] == "24px")
        vs = s.call("GET", f"/api/design/{slug}/artboard/hero/versions")[1]
        ctx.check("the knob made v2 with its note", [v["version"] for v in vs] == [1, 2] and vs[1]["note"] == "knob Spacing")
        ctx.check("the knob's value is saved in controls.json", s.call("GET", f"/api/design/{slug}")[1]["artboards"][0]["controls"][0]["value"] == 24)
        status, r = s.call("POST", f"/api/design/{slug}/control", {"artboard": "hero", "name": "Title size", "value": 40})
        ctx.check("a craft knob is queued for the next turn", status == 202 and r["queued"] is True)
        ctx.check("an unknown knob is a 422", s.call("POST", f"/api/design/{slug}/control", {"artboard": "hero", "name": "Nope", "value": 1})[0] == 422)
        edited = html.replace("Hello", "Hello, world") .replace("<body>", '<body contenteditable="true">').replace("</body>", "<!--halo-edit--><script>1</script><!--/halo-edit--></body>")
        status, r = s.call("POST", f"/api/design/{slug}/text-edit", {"artboard": "hero", "html": edited})
        saved = (s.state / "design" / slug / "artboards" / "hero" / "index.html").read_text(encoding="utf-8")
        ctx.check("a direct edit is saved as v3 with the helper script and contenteditable stripped",
                  status == 200 and "Hello, world" in saved and "halo-edit" not in saved and "contenteditable" not in saved and r["versions"] == [["hero", 3]])
        vs = s.call("GET", f"/api/design/{slug}/artboard/hero/versions")[1]
        ctx.check("the versions list has version, created and note", [v["version"] for v in vs] == [1, 2, 3] and vs[2]["note"] == "direct edit" and vs[0]["created"])
        status, r = s.call("POST", f"/api/design/{slug}/artboard/hero/restore", {"version": 1})
        now = (s.state / "design" / slug / "artboards" / "hero" / "index.html").read_text(encoding="utf-8")
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
        (s.state / "design" / slug / "artboards" / "hero" / "render.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
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
    from halo_harness.design.controls import apply_css_control, css_value, read_css_var
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


@test
def test_page_files_and_the_mode_button(ctx: Ctx):
    static = REPO / "halo_harness" / "studio" / "static"
    page = (static / "index.html").read_text(encoding="utf-8")
    ctx.check("the toggle has a Design button and the scripts are loaded", 'data-mode="design"' in page and "design.js" in page and "design-panel.js" in page and "design.css" in page)
    for name in ("design.js", "design-canvas.js", "design-panel.js", "design-panel2.js", "design.css"):
        text = (static / name).read_text(encoding="utf-8")
        ctx.check(f"{name} is under 250 lines and fetches nothing from a CDN", len(text.splitlines()) <= 250 and "//cdn" not in text and "https://" not in text)
    ctx.check("the iframes are sandboxed without allow-same-origin", 'sandbox="allow-scripts"' in (static / "design-canvas.js").read_text(encoding="utf-8")
              and "allow-same-origin" not in (static / "design-canvas.js").read_text(encoding="utf-8"))


@test
def test_design_page_boots_in_headless_chrome(ctx: Ctx):
    import os
    import subprocess
    from tests.helpers.runner import SkipTest
    sys.path.insert(0, str(REPO / "tools"))
    from capture_screens import find_chrome
    if not find_chrome(os.environ.get("HALO_CHROME", "")):
        raise SkipTest("no Chrome found (the page smoke needs headless Chrome)")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_"))}
    env["PYTHONPATH"] = str(REPO)
    env["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    r = subprocess.run([sys.executable, str(REPO / "tools" / "capture_studio.py"), "--mode", "design", "--dom"], capture_output=True, text=True, timeout=240, env=env, cwd=str(REPO))
    try:
        info = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        info = {}
    ctx.check(f"the Design page drew two artboard cards, a frame, two pins and five tabs, got {info} {r.stderr[-200:]!r}",
              info.get("cards") == 2 and info.get("frames", 0) >= 1 and info.get("pins") == 2 and info.get("tabs") == 5)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio design tests"))
