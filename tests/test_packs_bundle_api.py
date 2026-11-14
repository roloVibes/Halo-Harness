"""tests.test_packs_bundle_api -- the routes behind a bundle panel's `api` (Halo 3.3.10.0 R3,
studio/packs_studio_bundle_api.py; docs/EXTENSION_API.md "Studio contributions", the `api` table) over a real
server and a scratch home with the studio-bundle fixture pack:

1. `POST pack/<id>/publish`: a declared kind lands in the pack's events log and on the bridge as a `pack_event`
   frame; an undeclared kind is 422 naming contributes.events, a bad name 422 with publish_event's own line, and
   neither is written;
2. the rate: RATE writes per WINDOW_S per pack, the next is 429 with the rate in the body and nothing written;
   past the window it goes again (the module's clock seam, no sleep);
3. without studio-script every route is 403 naming the grant;
4. `GET pack/<id>/mode`: none, then the mode `halo pack mode` turned on, with its label;
5. `POST pack/<id>/attention`: a declared kind is a row file the attention queue lists, the pack named; an
   undeclared kind and a bad row name are 422;
6. the data route stays read-only: GET reads, any write method is 405 and the file is unchanged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_studio import PackStudio, next_kind, until  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
GRANT = "halo pack enable studio-bundle --grant studio-script"


def _log(s) -> list:
    path = s.packs / ".data" / "studio-bundle" / "events.jsonl"
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.is_file() else []
    return [r for r in rows if r.get("kind", "").startswith("hello.")]


@test
def test_publish_a_declared_kind(ctx: Ctx):
    with PackStudio() as s:
        s.install_pack("studio-bundle", grants=["studio-script"])
        q = s.frames()
        status, body, _ = s.call("POST", "pack/studio-bundle/publish", {"kind": "hello.said", "data": {"text": "hi"}})
        ctx.check(f"200 ok, published on this server's bridge, got {status} {body}", status == 200 and body.get("ok") is True
                  and body.get("published") is True and "problems" not in body)
        f = next_kind(q, "pack_event")
        ctx.check(f"the pack_event frame, got {f}", f is not None and f["pack"] == "studio-bundle"
                  and f["data"] == {"pack": "studio-bundle", "kind": "hello.said", "data": {"text": "hi"}})
        rows = _log(s)
        ctx.check(f"one row in the pack's events log, got {rows}", len(rows) == 1 and rows[0]["data"] == {"text": "hi"})
        status, body, _ = s.call("POST", "pack/studio-bundle/publish", {"kind": "hello.nope", "data": {}})
        ctx.check(f"an undeclared kind: 422 naming contributes.events, got {status} {body}", status == 422
                  and body["error"] == "studio-bundle declares no event hello.nope (contributes.events: hello.said): "
                                       "a bundle panel publishes its pack's own kinds")
        status, body, _ = s.call("POST", "pack/studio-bundle/publish", {"kind": "Hello Said", "data": {}})
        ctx.check(f"a bad name: publish_event's own line, got {status} {body}", status == 422
                  and body["error"] == "event kind 'Hello Said' is not an event name (lower-case, digits, . _ -)")
        ctx.check("neither was written", len(_log(s)) == 1)
        ctx.check("GET is 405", s.call("GET", "pack/studio-bundle/publish")[0] == 405)


@test
def test_the_publish_rate(ctx: Ctx):
    from halo_harness.studio import packs_studio_bundle_api as B
    clock = [5000.0]
    saved = B._now
    B._now = lambda: clock[0]
    try:
        with PackStudio() as s:
            s.install_pack("studio-bundle", grants=["studio-script"])
            codes = [s.call("POST", "pack/studio-bundle/publish", {"kind": "hello.said", "data": {"text": str(i)}})[0]
                     for i in range(B.RATE)]
            ctx.check(f"{B.RATE} in the window go, got {set(codes)}", codes == [200] * B.RATE)
            status, body, _ = s.call("POST", "pack/studio-bundle/publish", {"kind": "hello.said", "data": {"text": "x"}})
            ctx.check(f"the next is 429 with the rate, got {status} {body}", status == 429
                      and body["rate"] == {"limit": B.RATE, "window_s": B.WINDOW_S} and body["retry_after"] > 0
                      and f"its rate: {B.RATE} per {B.WINDOW_S:g} s" in body["error"])
            status, body, _ = s.call("POST", "pack/studio-bundle/attention", {"row": "r1", "kind": "hello.ask", "what": "x"})
            ctx.check(f"attention shares the rate, got {status}", status == 429)
            ctx.check("nothing past the rate was written", len(_log(s)) == B.RATE)
            clock[0] += B.WINDOW_S + 0.5
            ctx.check("past the window it goes again",
                      s.call("POST", "pack/studio-bundle/publish", {"kind": "hello.said", "data": {"text": "y"}})[0] == 200)
    finally:
        B._now = saved


@test
def test_no_grant_is_403_naming_it(ctx: Ctx):
    with PackStudio() as s:
        s.install_pack("studio-bundle")
        for method, path, body in (("POST", "publish", {"kind": "hello.said", "data": {}}), ("GET", "mode", None),
                                   ("POST", "attention", {"row": "r", "kind": "hello.ask", "what": "x"})):
            status, got, _ = s.call(method, f"pack/studio-bundle/{path}", body)
            ctx.check(f"{path}: 403 naming the grant, got {status} {got}", status == 403 and GRANT in got.get("error", ""))
        ctx.check("nothing was written", _log(s) == [] and not (s.packs / ".data" / "studio-bundle" / "attention").exists())
        ctx.check("a pack not here is 404", s.call("GET", "pack/nope/mode")[0] == 404)


@test
def test_mode_reads_the_packs_mode(ctx: Ctx):
    from halo_harness.packs.mode_state import set_mode
    with PackStudio() as s:
        s.install_pack("studio-bundle", grants=["studio-script"])
        status, body, _ = s.call("GET", "pack/studio-bundle/mode")
        ctx.check(f"none yet, the declared modes listed, got {status} {body}", status == 200 and body["mode"] is None
                  and body["label"] is None and body["modes"] == [{"id": "loud", "label": "Loud"}] and body["armed"] == [])
        ok, lines = set_mode("studio-bundle", "loud", True, by="cli", cwd=s.repo, state_dir=s.state)
        ctx.check(f"turned on, got {lines}", ok)
        status, body, _ = s.call("GET", "pack/studio-bundle/mode")
        ctx.check(f"the mode and its label, got {body}", status == 200 and body["mode"] == "loud" and body["label"] == "Loud"
                  and body["by"] == "cli" and body["since"])
        ctx.check("POST is 405", s.call("POST", "pack/studio-bundle/mode", {})[0] == 405)


@test
def test_attention_writes_a_row_the_queue_lists(ctx: Ctx):
    with PackStudio() as s:
        s.install_pack("studio-bundle", grants=["studio-script"])
        status, body, _ = s.call("POST", "pack/studio-bundle/attention", {"row": "greet", "kind": "hello.ask",
                                                                         "what": "the bundle asks you", "detail": "one"})
        ctx.check(f"200 with the file, got {status} {body}", status == 200 and body == {"ok": True, "row": "greet",
                                                                                     "kind": "hello.ask", "file": "attention/greet.json"})
        f = s.packs / ".data" / "studio-bundle" / "attention" / "greet.json"
        raw = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
        ctx.check(f"the row file, got {raw}", raw.get("kind") == "hello.ask" and raw.get("what") == "the bundle asks you")
        rows = []
        until(lambda: rows.extend(r for r in s.call("GET", "live/attention")[1]["rows"] if r["kind"].startswith("pack:")) or rows)
        row = rows[0] if rows else {}
        ctx.check(f"the queue's row, the pack named, its keys, got {row}", row.get("kind") == "pack:studio-bundle:hello.ask"
                  and row.get("agent") == "pack studio-bundle" and row.get("label") == "hello"
                  and row.get("keys") == {"a": "ok", "s": "skip"} and row.get("what") == "the bundle asks you")
        status, body, _ = s.call("POST", "pack/studio-bundle/attention", {"row": "x", "kind": "hello.other", "what": "x"})
        ctx.check(f"an undeclared kind: 422, got {status} {body}", status == 422 and "contributes.studio.attention: hello.ask" in body["error"])
        status, body, _ = s.call("POST", "pack/studio-bundle/attention", {"row": "../x", "kind": "hello.ask", "what": "x"})
        ctx.check(f"a bad row name: 422, got {status} {body}", status == 422 and "not a row name" in body["error"])
        status, body, _ = s.call("POST", "pack/studio-bundle/attention", {"row": "y", "kind": "hello.ask"})
        ctx.check(f"no what: 422, got {status}", status == 422)


@test
def test_the_data_route_stays_read_only(ctx: Ctx):
    with PackStudio() as s:
        s.install_pack("studio-bundle", grants=["studio-script"])
        data = s.packs / ".data" / "studio-bundle"
        data.mkdir(parents=True, exist_ok=True)
        (data / "note.json").write_text('{"note": "kept"}', encoding="utf-8")
        status, raw, _ = s.raw("/api/pack/studio-bundle/data/note.json")
        ctx.check(f"GET reads it, got {status} {raw!r}", status == 200 and json.loads(raw) == {"note": "kept"})
        for method in ("POST", "PUT", "DELETE"):
            status, _raw, _ = s.raw("/api/pack/studio-bundle/data/note.json", method=method, body={"note": "changed"})
            ctx.check(f"{method} is 405, got {status}", status == 405)
        ctx.check("the file is unchanged", json.loads((data / "note.json").read_text(encoding="utf-8")) == {"note": "kept"})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
