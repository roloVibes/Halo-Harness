"""tests.test_studio_design_live -- Halo 3.0.7.0 round R3: a Design turn on
Studio's live feed and its Cancel. Over the in-process server and fake
runners (tests/test_studio_design.py, no model call): every step of a turn is
a `design_turn` frame on /api/events (started, each event by index with a
tool call's input cut to one line, done with the result); the history keeps
the model's reply text; `POST turn/<id>/cancel` stops a running turn (code
130, `cancelled`), a finished turn answers 409 and an unknown one 404; the
pump kills a real child when the cancel event is set; the Assets panel's
download route `/design-files/<slug>/_assets/<name>` serves the project's
assets and nothing outside them.

Run: python -m tests.test_studio_design_live
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.orchestra_studio_rig import Reader  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_studio_design import HERO, _Studio  # noqa: E402

test, TESTS = new_registry()


def _tooling_runner():
    def runner(cmd, cwd, env, on_line, stdin=""):
        d = Path(cwd) / "artboards" / "hero"
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(HERO, encoding="utf-8")
        big = {"file_path": "artboards/hero/index.html", "content": "x" * 5000}
        on_line(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "## Making it"}, {"type": "tool_use", "name": "Write", "input": big}]}}))
        on_line(json.dumps({"type": "result", "result": "Made **hero**.", "total_cost_usd": 0.01}))
        return 0
    return runner


def _waiting_runner(seen: dict):
    def runner(cmd, cwd, env, on_line, stdin="", cancel=None):
        seen["cancel"] = cancel
        on_line(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Starting."}]}}))
        stopped = cancel.wait(10) if cancel is not None else False
        return 130 if stopped else 0
    return runner


def _wait_done(s, slug, tid, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        _, p = s.call("GET", f"/api/design/{slug}/turn/{tid}")
        if p.get("done"):
            return p
        time.sleep(0.05)
    return None


@test
def test_turn_steps_are_design_turn_frames_on_the_live_feed(ctx: Ctx):
    with _Studio() as s:
        s.api.RUNNER = _tooling_runner()
        slug = s.call("POST", "/api/design/projects", {"name": "Feed"})[1]["slug"]
        rd = Reader(f"{s.base}/api/events?t={s.srv.token}&sessions=all")
        try:
            time.sleep(0.3)
            status, r = s.call("POST", f"/api/design/{slug}/run", {"prompt": "A hero"})
            ctx.check("the turn starts", status == 200)
            got = []
            done = rd.wait(lambda k, f: k == "design_turn" and (got.append(f) or f["data"].get("state") == "done"), 15)
            ctx.check(f"a done frame with the result, got {done}", done is not None and done["data"]["result"]["code"] == 0
                      and done["data"]["result"]["versions"] == [["hero", 1]] and done["session_id"] == f"design:{slug}")
            states = [f["data"]["state"] for f in got]
            ctx.check(f"started, the events, done in order, got {states}", states[0] == "started" and states[-1] == "done" and states.count("event") == 3)
            ctx.check("every frame names the project and the turn", all(f["data"]["slug"] == slug and f["data"]["turn"] == r["turn"] for f in got))
            ns = [f["data"]["n"] for f in got if f["data"]["state"] == "event"]
            ctx.check(f"events carry their index, got {ns}", ns == [0, 1, 2])
            tool = got[1]["data"]["event"]["message"]["content"][1]
            ctx.check(f"a tool call's input is one short line on the feed, got {str(tool)[:120]}",
                      tool["name"] == "Write" and "input" not in tool and len(tool["input_line"]) <= 160 and "artboards/hero" in tool["input_line"])
            _, p = s.call("GET", f"/api/design/{slug}/turn/{r['turn']}")
            ctx.check("the poll still has the full event", p["events"][0]["message"]["content"][1]["input"]["content"] == "x" * 5000)
        finally:
            rd.close()
        row = s.call("GET", f"/api/design/{slug}")[1]["history"][-1]
        ctx.check(f"the history keeps the model's reply text, got {row.get('text')!r}", row.get("text") == "Made **hero**.")


@test
def test_cancel_stops_a_running_turn(ctx: Ctx):
    seen = {}
    with _Studio() as s:
        s.api.RUNNER = _waiting_runner(seen)
        slug = s.call("POST", "/api/design/projects", {"name": "Stop me"})[1]["slug"]
        tid = s.call("POST", f"/api/design/{slug}/run", {"prompt": "long work"})[1]["turn"]
        end = time.time() + 5
        while time.time() < end and "cancel" not in seen:
            time.sleep(0.02)
        ctx.check("the runner got the cancel event", isinstance(seen.get("cancel"), threading.Event))
        status, r = s.call("POST", f"/api/design/{slug}/turn/{tid}/cancel", {})
        ctx.check(f"cancel answers 200, got {status} {r}", status == 200 and r == {"cancelled": True, "turn": tid})
        p = _wait_done(s, slug, tid)
        ctx.check(f"the turn ends with code 130 and cancelled, got {p and p['result']}", p is not None and p["result"]["code"] == 130 and p["result"]["cancelled"] is True)
        status, r = s.call("POST", f"/api/design/{slug}/turn/{tid}/cancel", {})
        ctx.check(f"a finished turn answers 409, got {status}", status == 409 and "already finished" in r["error"])
        ctx.check("an unknown turn is a 404", s.call("POST", f"/api/design/{slug}/turn/t0/cancel", {})[0] == 404)
        row = s.call("GET", f"/api/design/{slug}")[1]["history"][-1]
        ctx.check(f"the history marks it cancelled, got {row}", row.get("cancelled") is True and row.get("code") == 130)
        ctx.check("a new turn is accepted after it", s.call("POST", f"/api/design/{slug}/run", {"prompt": "again"})[0] == 200)
        seen["cancel"].set()
        time.sleep(0.2)


@test
def test_the_pump_kills_a_real_child_on_cancel(ctx: Ctx):
    from halo_harness.design.session import _pump
    proc = subprocess.Popen([sys.executable, "-c", "import time; print('up', flush=True); time.sleep(60)"], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
    cancel = threading.Event()
    lines = []
    threading.Timer(0.6, cancel.set).start()
    t0 = time.monotonic()
    code = _pump(proc, lines.append, 30, cancel)
    took = time.monotonic() - t0
    ctx.check(f"the child is killed with 130 within a few seconds, got {code} after {took:.1f} s", code == 130 and took < 6 and proc.poll() is not None)
    ctx.check(f"its output before the cancel was read, got {lines}", any("up" in line for line in lines))


@test
def test_assets_download_route(ctx: Ctx):
    with _Studio() as s:
        slug = s.call("POST", "/api/design/projects", {"name": "Files"})[1]["slug"]
        data = b"\x89PNG\r\n\x1a\nfake"
        status, row = s.call("POST", f"/api/design/{slug}/assets", {"name": "logo.png", "data_base64": base64.b64encode(data).decode()})
        ctx.check("the asset is uploaded", status == 201 and row["path"] == "assets/logo.png")
        status, headers, body = s.raw(f"/design-files/{slug}/_assets/logo.png")
        ctx.check(f"the download route serves it as an image, got {status} {headers.get('Content-Type')}", status == 200 and body == data and headers["Content-Type"].startswith("image/png"))
        ctx.check("a traversal out of assets/ is a 404", s.raw(f"/design-files/{slug}/_assets/..%2Fdesign.json")[0] == 404
                  and s.raw(f"/design-files/{slug}/_assets/../design.json")[0] == 404)
        ctx.check("a missing asset is a 404", s.raw(f"/design-files/{slug}/_assets/nope.png")[0] == 404)
        ctx.check("a path under _assets/ is a 404 (one name only)", s.raw(f"/design-files/{slug}/_assets/a/b.png")[0] == 404)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio design live tests"))
