"""tests.test_studio_design_more -- Studio's Design "plus more" (Halo 3.0.1.0
round D5) over the in-process server and a recording fake runner: variants in
`run` and the CLI, the critique turn (Read,Glob only, no MCP servers, pins as
comments), the contrast route, assets (upload, list, sanitised names, the cap),
the history line's tool calls and seconds, and the page's new files.
"""

from __future__ import annotations

import base64
import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_studio_design import HERO, _Studio  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
PINS = ('Two notes.\n```json\n[{"x": 40, "y": 12, "text": "The headline and sub-line share a weight.", "severity": "high"},'
        ' {"x": 150, "y": -3, "text": "The buttons sit tight to the copy.", "severity": "low"}]\n```\n')


def _recording(seen: dict, text: str = "ok", tools: int = 0):
    def runner(cmd, cwd, env, on_line):
        seen["cmd"] = list(cmd)
        if "--mcp-config" in cmd:
            seen["mcp"] = json.loads(Path(cmd[cmd.index("--mcp-config") + 1]).read_text(encoding="utf-8"))
        d = Path(cwd) / "artboards" / "hero"
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(HERO, encoding="utf-8")
        for i in range(tools):
            on_line(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"i": i}}]}}))
        on_line(json.dumps({"type": "result", "result": text, "total_cost_usd": 0.03}))
        return 0
    return runner


def _arg(cmd, flag):
    return cmd[cmd.index(flag) + 1]


@test
def test_variants_wrap_the_prompt_in_run_and_in_the_cli(ctx: Ctx):
    with _Studio() as s:
        seen = {}
        s.api.RUNNER = _recording(seen)
        slug = s.call("POST", "/api/design/projects", {"name": "Dirs"})[1]["slug"]
        status, r = s.call("POST", f"/api/design/{slug}/run", {"prompt": "a pricing page", "variants": 3, "base": "pricing"})
        ctx.check("run with variants starts one turn", status == 200 and r["turn"])
        import time
        for _ in range(100):
            if s.call("GET", f"/api/design/{slug}/turn/{r['turn']}")[1]["done"]:
                break
            time.sleep(0.05)
        prompt = _arg(seen["cmd"], "-p")
        ctx.check("the prompt names the directions pricing-a, -b, -c and keeps the design system",
                  prompt.startswith("Make 3 directions of: a pricing page.") and "pricing-a, pricing-b, pricing-c (same kind)" in prompt
                  and "clearly different in layout, type and colour, all keeping the design system." in prompt)
        ctx.check("the history logs the wrapped prompt", s.call("GET", f"/api/design/{slug}")[1]["history"][-1]["prompt"] == prompt)
        ctx.check("variants out of range or a bad base is a 422",
                  s.call("POST", f"/api/design/{slug}/run", {"prompt": "x", "variants": 9})[0] == 422
                  and s.call("POST", f"/api/design/{slug}/run", {"prompt": "x", "variants": 3, "base": "Bad Base!"})[0] == 422)
        seen.clear()
        s.run_turn(slug, "plain prompt")
        ctx.check("no variants leaves the prompt alone", _arg(seen["cmd"], "-p") == "plain prompt")
        from halo_harness.design import cli, session
        got = {}
        orig = session.run_turn
        session.run_turn = lambda p, prompt, **kw: got.update(prompt=prompt) or {"code": 0, "cost": None, "text": "", "versions": [], "events": []}
        try:
            with redirect_stdout(io.StringIO()):
                code = cli.cmd_design(["run", slug, "a hero", "--variants", "3", "--base", "hero"])
        finally:
            session.run_turn = orig
        ctx.check("halo design run --variants 3 --base hero builds the same prompt", code == 0 and got["prompt"] == "Make 3 directions of: a hero. Each is its own artboard named hero-a, hero-b, hero-c (same kind), clearly different in layout, type and colour, all keeping the design system.")


@test
def test_critique_turn_pins_comments(ctx: Ctx):
    with _Studio() as s:
        slug = s.seeded("Crit Lab")
        seen = {}
        s.api.RUNNER = _recording(seen, PINS)
        status, r = s.call("POST", f"/api/design/{slug}/critique", {"artboard": "hero", "model": "or:v/critic", "wait": True})
        cmd = seen["cmd"]
        ctx.check("the critique turn has only Read,Glob, no MCP servers, six turns and the chosen model",
                  status == 200 and _arg(cmd, "--tools") == "Read,Glob" and seen["mcp"] == {"mcpServers": {}} and _arg(cmd, "--max-turns") == "6" and _arg(cmd, "--model") == "or:v/critic")
        ctx.check("the prompt asks for the checklist and one fenced json list", all(w in _arg(cmd, "-p") for w in ("hierarchy", "spacing rhythm", "type scale", "contrast", "tokens", "copy", "accessibility", "```json")) and "artboards/hero/index.html" in _arg(cmd, "-p"))
        ctx.check("the response is {turn, pins} with both pins", r["turn"] and len(r["pins"]) == 2)
        _, d = s.call("GET", f"/api/design/{slug}")
        crit = [c for c in d["comments"] if c.get("source") == "critique"]
        ctx.check("the pins are comments with the source and the severity prefix", [c["text"].split("]")[0] for c in crit] == ["[high", "[low"] and crit[0]["text"] == "[high] The headline and sub-line share a weight.")
        ctx.check("coordinates are clamped to 0-100 and the pin is on the artboard's version", crit[1]["x"] == 100.0 and crit[1]["y"] == 0.0 and crit[0]["artboard"] == "hero" and crit[0]["version"] == 1 and not crit[0]["resolved"])
        seen.clear()
        s.api.RUNNER = _recording(seen, "I would change nothing.")
        status, r = s.call("POST", f"/api/design/{slug}/critique", {"artboard": "hero", "wait": True})
        ctx.check("no json block adds no pins and says so in one sentence", status == 200 and r["pins"] == [] and r["note"] == "The critique came back without a pin list, so no pins were added."
                  and len([c for c in s.call("GET", f"/api/design/{slug}")[1]["comments"] if c.get("source") == "critique"]) == 2)
        ctx.check("the project's model is used when none is given", _arg(seen["cmd"], "--model") == "or:v/eyes")
        s.api.RUNNER = _recording(seen, PINS)
        status, r = s.call("POST", f"/api/design/{slug}/critique", {"artboard": "hero"})
        import time
        for _ in range(100):
            _, p = s.call("GET", f"/api/design/{slug}/turn/{r['turn']}")
            if p["done"]:
                break
            time.sleep(0.05)
        ctx.check("without wait the turn polls like any turn and its result carries the pins", status == 200 and len(p["result"]["pins"]) == 2 and "2 critique pin(s)" in p["result"]["note"])
        ctx.check("an unknown artboard is a 404", s.call("POST", f"/api/design/{slug}/critique", {"artboard": "zzz"})[0] == 404)
        from halo_harness.design import cli, session
        orig = session.run_turn
        session.run_turn = lambda p, prompt, **kw: {"code": 0, "cost": None, "text": PINS, "versions": [], "events": [], "kw": kw}
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                code = cli.cmd_design(["critique", slug, "hero", "--model", "m"])
        finally:
            session.run_turn = orig
        ctx.check("halo design critique prints the pins", code == 0 and "[high] The headline" in buf.getvalue() and "2 critique pin(s) added" in buf.getvalue())


@test
def test_contrast_route(ctx: Ctx):
    with _Studio() as s:
        slug = s.seeded("Contrast Route")
        page = s.state / "design" / slug / "artboards" / "hero" / "index.html"
        page.write_text("<style>:root{--text:#777;--bg:#fff;--accent:#000}</style>", encoding="utf-8")
        status, r = s.call("GET", f"/api/design/{slug}/artboard/hero/contrast")
        ctx.check("the route returns pairs (failing first) and a note", status == 200 and r["pairs"][0]["ratio"] == 4.48 and r["pairs"][0]["aa"] is False and r["pairs"][1]["ratio"] == 21.0 and "below AA" in r["note"])
        ctx.check("an unknown artboard or project is a 404", s.call("GET", f"/api/design/{slug}/artboard/zzz/contrast")[0] == 404 and s.call("GET", "/api/design/nope/artboard/hero/contrast")[0] == 404)


@test
def test_assets_upload_list_sanitise_cap(ctx: Ctx):
    with _Studio() as s:
        slug = s.call("POST", "/api/design/projects", {"name": "Assets Lab"})[1]["slug"]
        png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()
        status, r = s.call("POST", f"/api/design/{slug}/assets", {"name": "logo.png", "data_base64": png})
        ctx.check("an upload is 201 with name, size, kind and path", status == 201 and r == {"name": "logo.png", "size": 72, "kind": "image", "path": "assets/logo.png"})
        status, r = s.call("POST", f"/api/design/{slug}/assets", {"name": "../../design.json", "data_base64": png})
        ctx.check("a path-traversal name is cut to its basename inside assets/", status == 201 and r["name"] == "design.json" and (s.state / "design" / slug / "assets" / "design.json").is_file())
        status, r = s.call("POST", f"/api/design/{slug}/assets", {"name": "..\\..\\evil.txt", "data_base64": base64.b64encode(b"hi").decode()})
        ctx.check("a backslash path is cut too", status == 201 and r["name"] == "evil.txt" and r["kind"] == "text")
        ctx.check("the project's own design.json was not overwritten", json.loads((s.state / "design" / slug / "design.json").read_text(encoding="utf-8"))["name"] == "Assets Lab")
        status, r = s.call("POST", f"/api/design/{slug}/assets", {"name": "logo.png", "data_base64": png})
        ctx.check("a name that exists gets a suffix", status == 201 and r["name"] == "logo-2.png")
        big = base64.b64encode(b"x" * 500_000).decode()
        s.call("POST", f"/api/design/{slug}/assets", {"name": "photo.jpg", "data_base64": big})
        status, r = s.call("GET", f"/api/design/{slug}/assets")
        rows = {a["name"]: a for a in r["assets"]}
        ctx.check("the list has every file with size and kind", status == 200 and set(rows) == {"logo.png", "logo-2.png", "design.json", "evil.txt", "photo.jpg"} and rows["photo.jpg"]["size"] == 500_000 and rows["evil.txt"]["kind"] == "text")
        ctx.check("a small image has a data URL thumbnail; a big image and a text file do not", rows["logo.png"]["thumb"].startswith("data:image/png;base64,") and rows["photo.jpg"]["thumb"] == "" and rows["evil.txt"]["thumb"] == "")
        ctx.check("bad base64 and a blank name are 422s", s.call("POST", f"/api/design/{slug}/assets", {"name": "a.png", "data_base64": "***"})[0] == 422 and s.call("POST", f"/api/design/{slug}/assets", {"name": " ", "data_base64": png})[0] == 422)
        ctx.check("an unknown project is a 404", s.call("GET", "/api/design/nope/assets")[0] == 404 and s.call("POST", "/api/design/nope/assets", {"name": "a", "data_base64": png})[0] == 404)
        status, r = s.call("POST", f"/api/design/{slug}/assets", {"name": "huge.bin", "data_base64": base64.b64encode(b"\0" * (15 * 1024 * 1024 + 1)).decode()})
        ctx.check("past 15 MB is a 413 and nothing is written", status == 413 and not (s.state / "design" / slug / "assets" / "huge.bin").exists())
        status, r = s.call("POST", f"/api/design/{slug}/assets", {"name": "edge.bin", "data_base64": base64.b64encode(b"\0" * (15 * 1024 * 1024)).decode()})
        ctx.check("exactly 15 MB is accepted", status == 201 and r["size"] == 15 * 1024 * 1024)


@test
def test_history_logs_tool_calls_and_seconds(ctx: Ctx):
    with _Studio() as s:
        seen = {}
        s.api.RUNNER = _recording(seen, "done", tools=3)
        slug = s.call("POST", "/api/design/projects", {"name": "Run View"})[1]["slug"]
        s.run_turn(slug, "a hero")
        row = s.call("GET", f"/api/design/{slug}")[1]["history"][-1]
        ctx.check("the history line has tool_calls and elapsed seconds", row["tool_calls"] == 3 and isinstance(row["elapsed"], float) and row["elapsed"] >= 0)
        from halo_harness.design import cli
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.cmd_design(["show", slug])
        ctx.check("halo design show prints them per turn", re.search(r"3 tool calls · [\d.]+ s · \$0\.030", buf.getvalue()) is not None)
        ctx.check("a plain turn keeps the full tool list", _arg(seen["cmd"], "--tools") != "Read,Glob" and "Write" in _arg(seen["cmd"], "--tools"))


@test
def test_page_files_shortcuts_and_the_design_tour(ctx: Ctx):
    static = REPO / "halo_harness" / "studio" / "static" / "legacy"
    page = (static / "index.html").read_text(encoding="utf-8")
    ctx.check("the new scripts are loaded", "design-more.js" in page and "design-assets.js" in page)
    for name in ("design-more.js", "design-assets.js", "design.js", "design-panel.js", "design-panel2.js", "palette.js", "design.css"):
        text = (static / name).read_text(encoding="utf-8")
        ctx.check(f"{name} is under 250 lines and fetches nothing from a CDN", len(text.splitlines()) <= 250 and "//cdn" not in text and "https://" not in text.replace("https://github.com/roloVibes", ""))
    more = (static / "design-more.js").read_text(encoding="utf-8")
    keys = re.findall(r'^\s*\["(\w)", "', more, re.M) + re.findall(r'\], \["(\w)", "', more)
    ctx.check(f"every Design command has a one-letter shortcut and none is R, O, D, A or F-clashing: {keys}", len(set(keys)) == len(keys) >= 11 and not {"r", "o", "d", "a"} & set(keys))
    ctx.check("every command shows its key in the palette and Enter in the box runs", "key.length === 1 ? key.toUpperCase() : key" in more and '"Enter", "Run a turn' in more)
    ctx.check("shortcuts are inactive while typing", "INPUT|TEXTAREA|SELECT" in more and "isContentEditable" in more)
    pal = (static / "palette.js").read_text(encoding="utf-8")
    block = pal[pal.index("const DESIGN_STEPS"):pal.index("const inDesign")]
    ctx.check("the Design tour has five steps and the Roles tour is kept", block.count('\n    ["') == 5 and "ROLES_STEPS" in pal and "inDesign(app) ? DESIGN_STEPS : ROLES_STEPS" in pal)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio design more tests"))
