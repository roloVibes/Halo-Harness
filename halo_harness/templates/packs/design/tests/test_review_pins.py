"""The design pack's tests/test_review_pins.py -- the 3.0.2.0 review fix pass's Design pins (were in Halo's core
tests/test_review3_c.py and test_review3_c2.py), over the pack's routes in a live Studio (tests/rig.py):

  * item 7    file-derived numbers reach the page as numbers; no page source writes HTML from data
  * item 34   an artboard file answers only its own Host (a rebound name, another port or no port is a 403)
  * item 35   a symlinked artboard folder is never served nor discovered
  * item 112  HTML and SVG are sandboxed, a render image is not
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
from pathlib import Path

from tests.run import PACK, Ctx, SkipTest, main, mod, new_registry, scratch  # noqa: E402

scratch()

from tests.rig import _Studio  # noqa: E402

test, TESTS = new_registry()
IFRAME = '<iframe src="_files/probe/hero/index.html"></iframe>'


def _project(s, name):
    p = mod("server/store.py").Project.create(name, state_dir=s.root.parent)
    board = p.artboard_dir("hero")
    board.mkdir(parents=True)
    (board / "index.html").write_text("<!doctype html><body>hero</body>", encoding="utf-8")
    (board / "render.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (board / "render.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    return p


def _get(s, path, host):
    port = s.srv.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.putrequest("GET", s.path(path) + "?t=" + s.token, skip_host=True)
    conn.putheader("Host", host.replace("PORT", str(port)))
    conn.endheaders()
    r = conn.getresponse()
    out = (r.status, r.read())
    conn.close()
    return out


@test
def test_item34_an_artboard_file_answers_only_its_own_host(ctx: Ctx):
    with _Studio() as s:
        p = _project(s, "Host Lab")
        path = f"/design-files/{p.slug}/hero/index.html"
        port = s.srv.server_address[1]
        for label, host in (("the own Host", "127.0.0.1:PORT"), ("localhost on the own port", "localhost:PORT")):
            ctx.check(f"{label} answers", _get(s, path, host)[0] == 200)
        for label, host in (("a rebound name", "evil.example:PORT"), ("a rebound name with no port", "evil.example"),
                            ("loopback on another port", f"127.0.0.1:{port + 1}"), ("a missing port", "127.0.0.1")):
            status, body = _get(s, path, host)
            ctx.check(f"{label} is a 403 with no body of the file, got {status}", status == 403 and b"hero" not in body)


@test
def test_item35_a_symlinked_artboard_folder_is_not_served(ctx: Ctx):
    with _Studio() as s:
        p = _project(s, "Link Lab")
        outside = Path(tempfile.mkdtemp(prefix="halo-outside-"))
        (outside / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
        try:
            os.symlink(outside, p.artboard_dir("esc"), target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError):
            raise SkipTest("this host cannot create symlinks")
        status, _h, body = s.raw(f"/design-files/{p.slug}/esc/secret.txt")
        ctx.check(f"the file behind the link is a 404, got {status}", status == 404 and b"TOP SECRET" not in body)
        ctx.check("a real artboard in the same project still serves", s.raw(f"/design-files/{p.slug}/hero/index.html")[0] == 200)
        ctx.check("discovery skips the symlinked folder", "esc" not in [a["id"] for a in p.discover_artboards()])
        ctx.check("the snapshot does not copy it", "esc" not in [a for a, _v in p.snapshot()])


@test
def test_item112_html_and_svg_are_sandboxed_renders_are_not(ctx: Ctx):
    files = mod("server/files.py")
    with _Studio() as s:
        p = _project(s, "Csp Lab")
        base = f"/design-files/{p.slug}/hero/"
        csp = lambda name: s.raw(base + name)[1].get("Content-Security-Policy", "")  # noqa: E731
        ctx.check("index.html: sandbox allow-scripts", csp("index.html").endswith("; sandbox allow-scripts") and csp("index.html").startswith(files.CSP))
        ctx.check("svg: sandbox allow-scripts", csp("render.svg").endswith("; sandbox allow-scripts"))
        ctx.check("png keeps the plain policy", csp("render.png") == files.CSP)
        ctx.check("the ?edit=1 page is sandboxed too", csp("index.html?edit=1").endswith("sandbox allow-scripts"))
        ctx.check("csp_for ignores a charset suffix", files.csp_for("text/html; charset=utf-8").endswith("sandbox allow-scripts")
                  and files.csp_for("application/pdf") == files.CSP and files.csp_for("video/mp4") == files.CSP)


@test
def test_item7_file_derived_values_are_numbers_and_escaped(ctx: Ctx):
    with _Studio() as s:
        p = _project(s, "Xss Lab")
        (p.path / "history.jsonl").write_text(json.dumps({"ts": "t", "prompt": "p", "tool_calls": IFRAME, "elapsed": "x", "cost": IFRAME}) + "\n"
                                              + json.dumps({"ts": "t2", "prompt": "q", "tool_calls": 3, "elapsed": 1.5, "cost": 0.02}) + "\n", encoding="utf-8")
        (p.path / "comments.json").write_text(json.dumps([
            {"id": "c1", "artboard": "hero", "version": IFRAME, "x": '0"><iframe src=x><b x="', "y": IFRAME, "text": "t", "resolved": False},
            {"id": "c2", "artboard": "hero", "version": 2, "x": 12.5, "y": 40, "text": "t", "resolved": False}, "junk"]), encoding="utf-8")
        status, data = s.call("GET", f"/api/design/{p.slug}")
        c1, c2 = data["comments"][0], data["comments"][1]
        ctx.check("markup in x / y / version becomes numbers", status == 200 and (c1["x"], c1["y"], c1["version"]) == (0.0, 0.0, 0)
                  and (c2["x"], c2["y"], c2["version"]) == (12.5, 40, 2))
        ctx.check("a non-object comment row is dropped", len(data["comments"]) == 2)
        h1, h2 = data["history"]
        ctx.check("markup in tool_calls / elapsed / cost is dropped", h1["tool_calls"] is None and h1["elapsed"] is None and h1["cost"] is None)
        ctx.check("real numbers are kept", (h2["tool_calls"], h2["elapsed"], h2["cost"]) == (3, 1.5, 0.02))
        ctx.check("no iframe markup reaches the project payload", "<iframe" not in json.dumps({"c": data["comments"], "h": data["history"]}))
    src = {f.name: f.read_text(encoding="utf-8") for f in (PACK / "studio" / "src").glob("*.ts*")}
    ctx.check("the page has its sources", len(src) >= 10)
    ctx.check(f"no page source writes HTML from data, got {[n for n, t in src.items() if 'dangerouslySetInnerHTML' in t or '.innerHTML' in t]}",
              not any("dangerouslySetInnerHTML" in t or ".innerHTML" in t for t in src.values()))
    ctx.check("the pins are drawn as React elements", any('data-testid="design-pin"' in t for t in src.values()))


if __name__ == "__main__":
    sys.exit(main(TESTS))
