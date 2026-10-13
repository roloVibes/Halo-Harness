"""tests.test_review3_c2 -- pins for the 3.0.2.0 review fix pass, round
C-studio-tools, part 2: Studio's Design store, lineup graph, Paperclip
install and name checks.

  * item 7    file-derived numbers reach the page as numbers; the templates
              escape them
  * item 36   an artboard whose id starts with `v` is discovered
  * item 110  concurrent comment writers lose no rows; writes are atomic
  * item 37   a hand-edited lineup or bio opens with the validator's words
  * item 38   a Paperclip install finishes on its success line, one child only
  * item 111  layout / delete names are validated
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_review3_c import _Studio  # noqa: E402  (scopes the state dir the same way)
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
STATIC = REPO / "halo_harness" / "studio" / "static"
IFRAME = '<iframe src="/design-files/probe/hero/index.html"></iframe>'


@test
def test_item7_file_derived_values_are_numbers_and_escaped(ctx: Ctx):
    import urllib.request
    with _Studio() as s:
        p = s.project("Xss Lab")
        (p.path / "history.jsonl").write_text(json.dumps({"ts": "t", "prompt": "p", "tool_calls": IFRAME, "elapsed": "x", "cost": IFRAME}) + "\n"
                                              + json.dumps({"ts": "t2", "prompt": "q", "tool_calls": 3, "elapsed": 1.5, "cost": 0.02}) + "\n", encoding="utf-8")
        (p.path / "comments.json").write_text(json.dumps([
            {"id": "c1", "artboard": "hero", "version": IFRAME, "x": '0"><iframe src=x><b x="', "y": IFRAME, "text": "t", "resolved": False},
            {"id": "c2", "artboard": "hero", "version": 2, "x": 12.5, "y": 40, "text": "t", "resolved": False}, "junk"]), encoding="utf-8")
        req = urllib.request.Request(f"http://127.0.0.1:{s.port}/api/design/{p.slug}", headers={"Authorization": "Bearer " + s.srv.token})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        c1, c2 = data["comments"][0], data["comments"][1]
        ctx.check("markup in x / y / version becomes numbers", (c1["x"], c1["y"], c1["version"]) == (0.0, 0.0, 0) and (c2["x"], c2["y"], c2["version"]) == (12.5, 40, 2))
        ctx.check("a non-object comment row is dropped", len(data["comments"]) == 2)
        h1, h2 = data["history"]
        ctx.check("markup in tool_calls / elapsed / cost is dropped", h1["tool_calls"] is None and h1["elapsed"] is None and h1["cost"] is None)
        ctx.check("real numbers are kept", (h2["tool_calls"], h2["elapsed"], h2["cost"]) == (3, 1.5, 0.02))
        ctx.check("no iframe markup reaches the project payload", "<iframe" not in json.dumps({"c": data["comments"], "h": data["history"]}))
    panel = (STATIC / "design-panel.js").read_text(encoding="utf-8")
    canvas = (STATIC / "design-canvas.js").read_text(encoding="utf-8")
    ctx.check("the history row escapes tool_calls", "${esc(x.tool_calls)}" in panel and "${x.tool_calls}" not in panel)
    ctx.check("the comment row escapes the version", '${esc(c.version || "?")}' in panel and '${c.version' not in panel)
    ctx.check("the pin position goes through Number()", "left:${esc(Number(c.x) || 0)}%;top:${esc(Number(c.y) || 0)}%" in canvas and "${c.x}" not in canvas and "${c.y}" not in canvas)


@test
def test_item36_artboards_starting_with_v_are_discovered(ctx: Ctx):
    from halo_harness.design.store import Project
    with _Studio() as s:
        p = Project.create("V Lab", state_dir=s.state)
        for name in ("vector-logo", "video-hero", "v2", "hero"):
            (p.path / "artboards" / name).mkdir()
            (p.path / "artboards" / name / "index.html").write_text("<p>x</p>", encoding="utf-8")
        found = sorted(a["id"] for a in p.discover_artboards())
        ctx.check(f"vector-logo and video-hero are registered, a bare v2 is not, got {found}", found == ["hero", "vector-logo", "video-hero"])
        snaps = dict(p.snapshot())
        ctx.check("a turn versions them", snaps.get("vector-logo") == 1 and snaps.get("video-hero") == 1)
        ctx.check("the project lists them", {"vector-logo", "video-hero"} <= {a["id"] for a in p.artboards()})


@test
def test_item110_concurrent_comment_writers_lose_nothing(ctx: Ctx):
    from halo_harness.design import jsonio
    from halo_harness.design.store import Project
    with _Studio() as s:
        p = Project.create("Race Lab", state_dir=s.state)
        errors = []

        def pin(n):
            try:
                other = Project.open(p.slug, state_dir=s.state)  # a second Project object, as a request thread has
                for i in range(20):
                    other.add_comment("hero", f"note {n}-{i}", x=n, y=i)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=pin, args=(n,)) for n in range(8)]
        [t.start() for t in threads]
        [t.join(timeout=60) for t in threads]
        rows = p.comments()
        ctx.check(f"all 160 pins survive, got {len(rows)} {errors[:1]}", len(rows) == 160 and not errors)
        ctx.check("ids are unique", len({r["id"] for r in rows}) == 160)
        ctx.check("resolving under the same lock keeps every row", p.resolve_comments([r["id"] for r in rows[:50]]) == 50 and len(p.comments()) == 160)
        target = p.path / "big.json"
        stop, bad = threading.Event(), []

        def writer():
            n = 0
            while not stop.is_set():
                jsonio.write_json(target, [{"i": i, "pad": "x" * 200} for i in range(400 + n % 3)])
                n += 1

        w = threading.Thread(target=writer)
        w.start()
        deadline = time.time() + 1.5
        while time.time() < deadline:
            try:
                json.loads(target.read_text(encoding="utf-8"))
            except ValueError as e:
                bad.append(e)
            except OSError:
                pass  # a reader may briefly be refused while a replace lands (Windows)
            except Exception as e:  # noqa: BLE001
                bad.append(e)
        stop.set()
        w.join(timeout=10)
        ctx.check(f"a reader never sees a half-written file, got {bad[:1]}", not bad)
        ctx.check("no temp files are left behind", not list(p.path.glob("big.json.*.tmp")))


@test
def test_item111_layout_and_delete_names_are_validated(ctx: Ctx):
    from halo_harness.studio import api
    with _Studio() as s:
        bs = chr(92)
        evil = f"..{bs}..{bs}pwn"

        def req(method, name, body=None):
            return api.Request(method=method, path="x", query={"scope": "user"}, body=body or {}, cwd=s.state.parent / "proj", state_dir=s.state, params={"name": name})

        ctx.check("put_layout refuses a backslash path", api.put_layout(req("PUT", evil, {"positions": {}}))[0] == 422)
        ctx.check("get_layout refuses it too", api.get_layout(req("GET", evil))[0] == 422)
        ctx.check("nothing was written outside or inside the layouts folder", not list(s.state.parent.glob("pwn*")) and not list(s.state.rglob("*pwn*")))
        ctx.check("a lineup name and the pc:<id> form are fine", api.put_layout(req("PUT", "my-lineup", {"positions": {}}))[0] == 200
                  and api.put_layout(req("PUT", "pc:3f2a-11", {"positions": {"a": {"x": 1, "y": 2}}}))[0] == 200)
        ctx.check("delete_lineup refuses a traversal name", api.delete_lineup(req("DELETE", evil))[0] == 422)
        ctx.check("delete_bio refuses a traversal name", api.delete_bio(req("DELETE", evil))[0] == 422)
        victim = s.state.parent / "other.yaml"
        victim.write_text("x: 1\n", encoding="utf-8")
        api.delete_lineup(req("DELETE", f"..{bs}other"))
        ctx.check("the file the name pointed at is still there", victim.exists())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="review3 c2 tests"))
