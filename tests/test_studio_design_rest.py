"""tests.test_studio_design_rest -- the server side of the Design features
the React section took over from the classic page in Halo 3.0.7.0 round R3b,
over the in-process server and a fake turn runner: the knob route as the
settings face reads it, the `?edit=pick` frame and a picked text saved
through `text-edit`, a comment pinned at a click and resolved, the token
sheet and Sync as the design-system panel reads them, "3 directions" (the
variants body of `run`, three artboards landing), and the built bundle
carrying every new testid and the device setting's key.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_studio_design import _Studio  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "halo_harness" / "studio" / "static" / "dist" / "studio.js"


def _page(s, slug):
    return (s.state / "design" / slug / "artboards" / "hero" / "index.html").read_text(encoding="utf-8")


@test
def test_knob_route_answers_what_the_settings_face_shows(ctx: Ctx):
    with _Studio() as s:
        slug = s.seeded("Knobs")
        board = s.call("GET", f"/api/design/{slug}")[1]["artboards"][0]
        ctx.check("the project's artboard carries its knobs (name, kind, target, range)",
                  [k["name"] for k in board["controls"]] == ["Spacing", "Title size"] and board["controls"][0]["target"] == "css:--space" and board["controls"][0]["max"] == 64)
        status, r = s.call("POST", f"/api/design/{slug}/control", {"artboard": "hero", "name": "Spacing", "value": 30})
        ctx.check(f"a css knob answers its value and the version it made (the chip), got {r}", status == 200 and r["value"] == "30px" and r["versions"] == [["hero", 2]])
        after = s.call("GET", f"/api/design/{slug}")[1]["artboards"][0]
        ctx.check("the card's newest version and the knob's value follow", after["latest"] == 2 and after["controls"][0]["value"] == 30)
        status, r = s.call("POST", f"/api/design/{slug}/control", {"artboard": "hero", "name": "Title size", "value": 48})
        ctx.check("any other knob is kept for the next turn (no version)", status == 202 and r == {"queued": True}
                  and s.call("GET", f"/api/design/{slug}")[1]["artboards"][0]["latest"] == 2)


@test
def test_pick_frame_and_a_picked_text_saved_as_a_version(ctx: Ctx):
    from halo_harness.studio.design_api_edit import PICK_SCRIPT, inject
    with _Studio() as s:
        slug = s.seeded("Texts")
        status, h, body = s.raw(f"/design-files/{slug}/hero/index.html?edit=pick")
        text = body.decode("utf-8")
        ctx.check("edit=pick carries the picker before </body>, inside the halo-edit markers, with the sandbox CSP",
                  status == 200 and "halo-design-pick" in text and text.index("halo-edit-script") < text.index("</body>")
                  and text.count("<!--halo-edit-->") == 1 and h["Content-Security-Policy"].endswith("sandbox allow-scripts"))
        ctx.check("the picker posts the path, the node, the text and its box; it never edits the page itself",
                  all(k in PICK_SCRIPT for k in ("path:p", "node:n", "x:box.left", "vw:innerWidth", "dblclick")) and "contentEditable" not in PICK_SCRIPT)
        ctx.check("an old version is never framed with the picker", b"halo-design-pick" not in s.raw(f"/design-files/{slug}/hero/v1/index.html?edit=pick")[2])
        ctx.check("inject puts it before </body>, or at the end without one", inject("<p>a</p></BODY>", "X") == "<p>a</p>X</BODY>" and inject("<p>a</p>", "X") == "<p>a</p>X")
        # what Studio's editor posts: the page's own source with the one text node changed
        page = _page(s, slug)
        edited = page.replace("<h1>Hello</h1>", "<h1>Hello there</h1>")
        status, r = s.call("POST", f"/api/design/{slug}/text-edit", {"artboard": "hero", "html": edited})
        ctx.check(f"text-edit saves it as v2, got {status} {r}", status == 200 and r["versions"] == [["hero", 2]] and "<h1>Hello there</h1>" in _page(s, slug))
        vs = s.call("GET", f"/api/design/{slug}/artboard/hero/versions")[1]
        ctx.check("its note is direct edit", vs[-1]["note"] == "direct edit")
        status, r = s.call("POST", f"/api/design/{slug}/text-edit", {"artboard": "hero", "html": inject(_page(s, slug).replace("there", "again"))})
        ctx.check("a page that comes back with the picker in it is saved without it", status == 200 and "halo-design-pick" not in _page(s, slug) and "Hello again" in _page(s, slug))
        ctx.check("text-edit wants a page", s.call("POST", f"/api/design/{slug}/text-edit", {"artboard": "hero", "html": "plain"})[0] == 422)


@test
def test_comment_pinned_at_a_click_and_resolved(ctx: Ctx):
    with _Studio() as s:
        slug = s.seeded("Pins")
        status, c = s.call("POST", f"/api/design/{slug}/comment", {"artboard": "hero", "text": "Thicker line", "x": 37.5, "y": 61.2, "path": ""})
        ctx.check(f"the card's comment is pinned at the click's place on the newest version, got {c}",
                  status == 201 and c["x"] == 37.5 and c["y"] == 61.2 and c["version"] == 1 and c["text"] == "Thicker line" and not c.get("resolved"))
        pins = s.call("GET", f"/api/design/{slug}")[1]["comments"]
        ctx.check("the project lists it as an open pin", len(pins) == 1 and pins[0]["id"] == c["id"])
        ctx.check("an empty comment is a 422", s.call("POST", f"/api/design/{slug}/comment", {"artboard": "hero", "text": "  ", "x": 1, "y": 1})[0] == 422)
        status, r = s.call("POST", f"/api/design/{slug}/comments/resolve", {"ids": [c["id"]]})
        ctx.check("the pin's Resolve resolves that one", status == 200 and r["resolved"] == 1 and s.call("GET", f"/api/design/{slug}")[1]["comments"][0]["resolved"] is True)


@test
def test_token_sheet_save_and_sync_as_the_panel_reads_them(ctx: Ctx):
    with _Studio() as s:
        slug = s.seeded("Tokens")
        sheet = {"name": "Pulse", "tokens": {"colors": {"--accent": "#7c5cff"}, "spacing": {"--space": "32px"}}, "components": [{"name": "Button"}], "sources": ["by hand"]}
        s.call("PUT", f"/api/design/{slug}/system", {"system": sheet})
        sheet["tokens"]["colors"]["--accent"] = "#ff3366"  # what Save tokens sends: the whole sheet, one value changed
        status, r = s.call("PUT", f"/api/design/{slug}/system", {"system": sheet})
        got = s.call("GET", f"/api/design/{slug}")[1]["system"]
        ctx.check("Save tokens keeps the components and sources", status == 200 and got["tokens"]["colors"]["--accent"] == "#ff3366"
                  and got["components"] == [{"name": "Button"}] and got["sources"][0] == "by hand")
        code = s.state.parent / "tokens-src"
        code.mkdir(exist_ok=True)
        (code / "theme.css").write_text(":root{--brand:#ff6600;--gap:12px}", encoding="utf-8")
        status, r = s.call("POST", f"/api/design/{slug}/sync", {"source": str(code)})
        groups = {g: len(v) for g, v in r["system"]["tokens"].items()}
        ctx.check(f"Sync answers the merged sheet and its token count (the result dialog), got {groups} {r.get('tokens')}",
                  status == 200 and r["tokens"] == sum(groups.values()) and r["tokens"] >= 4 and "--brand" in json.dumps(r["system"]["tokens"]))
        ctx.check("an empty source is a 422", s.call("POST", f"/api/design/{slug}/sync", {"source": " "})[0] == 422)


@test
def test_three_directions_run_and_land_as_artboards(ctx: Ctx):
    with _Studio() as s:
        seen = {}

        def runner(cmd, cwd, env, on_line, stdin=""):
            seen["prompt"] = stdin
            for name in re.findall(r"\b(pricing-[a-z])\b", stdin):
                d = Path(cwd) / "artboards" / name
                d.mkdir(parents=True, exist_ok=True)
                (d / "index.html").write_text(f"<!doctype html><html><body><h1>{name}</h1></body></html>", encoding="utf-8")
            on_line(json.dumps({"type": "result", "result": "Three directions.", "total_cost_usd": 0.01}))
            return 0
        s.api.RUNNER = runner
        slug = s.call("POST", "/api/design/projects", {"name": "Directions"})[1]["slug"]
        status, r = s.call("POST", f"/api/design/{slug}/run", {"prompt": "a pricing section", "variants": 3, "base": "pricing"})
        ctx.check("the button's body starts one turn", status == 200 and r["turn"])
        import time
        for _ in range(200):
            if s.call("GET", f"/api/design/{slug}/turn/{r['turn']}")[1]["done"]:
                break
            time.sleep(0.05)
        ctx.check("the server writes the directions prompt", seen["prompt"].startswith("Make 3 directions of: a pricing section."))
        ids = [a["id"] for a in s.call("GET", f"/api/design/{slug}")[1]["artboards"]]
        ctx.check(f"the three directions are artboards, got {ids}", ids == ["pricing-a", "pricing-b", "pricing-c"])
        ctx.check("a base that is no artboard id is a 422", s.call("POST", f"/api/design/{slug}/run", {"prompt": "x", "variants": 3, "base": "Not An Id"})[0] == 422)


@test
def test_the_bundle_carries_the_new_design_testids(ctx: Ctx):
    js = DIST.read_text(encoding="utf-8")
    want = ["design-knob", "design-knob-version", "design-knobs", "design-text-edit", "design-text-edit-input", "design-comment", "design-comment-layer",
            "design-pin-pop", "design-resolve", "design-system", "design-token", "design-sync", "design-sync-dialog", "design-tokens-save",
            "design-directions", "design-device", "design-tool-comment", "halo-design-pick", "halo.studio.design.panel.design-artboards",
            "Design: 3 directions", "Design: pin a comment", "variants:"]
    missing = [w for w in want if w not in js]
    ctx.check(f"every new testid, the pick message, the device key and the palette entries are in the built studio.js, missing {missing}", not missing)
    ctx.check("the three device sizes", all(f'w:{w},h:{h}' in js.replace(" ", "") for w, h in ((390, 844), (820, 1100), (1280, 800))))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio design rest tests"))
