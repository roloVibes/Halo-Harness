"""tests.test_studio_media_sessions -- Halo 3.0.4.0 round R5: Studio's
ComfyUI routes (`/api/media/...`) over tests/helpers/fake_comfy.py -- status
(reachable, version, GPU, cache age; an unreachable server answers within
the wait cap), models after a scan, workflows (starters + saved), a
workflow's inputs, a render -> 202 with `media_render` frames on
/api/events and the artboard in the design project, `.mp4` served as
video/mp4 without the sandbox -- and the sessions routes over a real
ControlServer and the fake session (tests/helpers/remote_rig.py): the list
(public fields, a status, never a token), an approval card answered with
`POST sessions/<sid>/command`, the 404, 422 and 502 answers.

Run: python tests/test_studio_media_sessions.py
"""

from __future__ import annotations

import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.media_studio_rig import MediaStudio, Reader, wait_for  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_media_status_models_workflows_inputs(ctx: Ctx):
    from halo_harness.studio import media_api
    with MediaStudio() as s:
        status, st = s.get("media/status")
        ctx.check(f"status: reachable, version, the GPU, got {status} {st}", status == 200 and st["reachable"] is True
                  and st["version"] == "0.37.0" and st["gpus"][0]["name"] == "cuda:0 Fake GPU"
                  and st["url"] == s.comfy.url and "registered" in st and st["cache"]["scanned"] is None)
        ctx.check(f"models before a scan are empty, got {s.get('media/models')}", s.get("media/models")[1]["rows"] == [])
        status, sc = s.post("media/scan")
        ctx.check(f"scan reads the server into the cache, got {status} {sc}", status == 200 and sc["rows"] > 0
                  and "Fixture UI workflow.json" in sc["workflows"])
        status, rows = s.get("media/models?kind=image-gen")
        ctx.check(f"image-gen rows only, got {[r.get('kind') for r in rows['rows']]}", status == 200 and rows["rows"]
                  and all(r["kind"] == "image-gen" for r in rows["rows"]) and rows["scanned"])
        ctx.check("all rows >= image-gen rows", len(s.get("media/models?kind=all")[1]["rows"]) >= len(rows["rows"]))
        ctx.check("audio-gen is a kind", s.get("media/models?kind=audio-gen")[0] == 200)
        ctx.check("an unknown kind is a 422", s.get("media/models?kind=smell")[0] == 422)
        status, st2 = s.get("media/status")
        ctx.check(f"status now reports the cache age, got {st2['cache']}", st2["cache"]["scanned"] and st2["cache"]["rows"] > 0)
        status, wf = s.get("media/workflows")
        names = {(w["name"], w["source"]) for w in wf.get("workflows") or []}
        ctx.check(f"starters and saved workflows, got {names}", status == 200 and wf["reachable"]
                  and ("text-to-image-qwen", "starter") in names and ("Fixture UI workflow", "saved") in names)
        status, inp = s.get("media/workflows/text-to-image-qwen/inputs")
        node4 = next((n for n in inp.get("nodes") or [] if n["node"] == "4"), {})
        ctx.check(f"a starter's inputs, got {status} {node4}", status == 200 and inp["source"] == "starter"
                  and "prompt" in node4.get("inputs", {}))
        status, inp = s.get("media/workflows/Fixture%20UI%20workflow/inputs")
        ctx.check(f"a saved workflow's inputs (UI format converted), got {status}", status == 200
                  and inp["source"] == "saved" and inp["nodes"])
        ctx.check("an unknown workflow is a 404", s.get("media/workflows/nope/inputs")[0] == 404)
        media_api.URL = "http://127.0.0.1:1"
        t0 = time.monotonic()
        status, st3 = s.get("media/status")
        took = time.monotonic() - t0
        ctx.check(f"an unreachable server answers within the wait cap ({took:.2f} s), got {st3}",
                  status == 200 and took < media_api.STATUS_WAIT_S + 1.5 and st3["reachable"] in (False, None))
        status, wf = s.get("media/workflows")
        ctx.check("workflows fall back to the cache when the server is down", status == 200 and not wf["reachable"]
                  and any(w["source"] == "saved" for w in wf["workflows"]))
        media_api.URL = s.comfy.url


@test
def test_media_render_lands_an_artboard_and_streams_frames(ctx: Ctx):
    from halo_harness.design.store import Project
    with MediaStudio() as s:
        p = Project.create("media render test", state_dir=s.state)
        rd = Reader(f"{s.base}/api/events?t={s.srv.token}&sessions=all")
        try:
            ctx.check("a missing project is a 404", s.post("media/render", {"workflow": "text-to-image-qwen",
                                                                             "project": "nope"})[0] == 404)
            ctx.check("a path as workflow is a 422", s.post("media/render", {"workflow": "../x", "project": p.slug})[0] == 422)
            body = {"workflow": "text-to-image-qwen", "project": p.slug, "artboard": "hero", "poll_s": 0.01,
                    "set": {"prompt": "a lighthouse", "width": 64, "height": 64, "seed": 7}}
            status, out = s.post("media/render", body)
            pid = out.get("prompt_id", "")
            ctx.check(f"render is a 202 with the prompt id, got {status} {out}", status == 202 and pid.startswith("fake-"))
            done = rd.wait(lambda k, f: k == "media_render" and f["data"].get("state") == "done", 15)
            ctx.check(f"a done media_render frame for media:<pid>, got {done}", done is not None
                      and done["session_id"] == f"media:{pid}" and done["data"]["artboards"][0]["id"] == "hero")
            ctx.check("the prompt reached the graph", s.comfy.prompts[-1]["graph"]["4"]["inputs"]["prompt"] == "a lighthouse")
            d = p.artboard_dir("hero")
            ctx.check("render.png and source.json in the artboard", (d / "render.png").read_bytes()[:4] == b"\x89PNG"
                      and '"comfyui"' in (d / "source.json").read_text(encoding="utf-8"))
            ctx.check("the artboard is registered and versioned", any(a["id"] == "hero" and a["latest"] == 1 for a in p.artboards()))
            status, row = s.get(f"media/renders/{pid}")
            ctx.check(f"renders/<pid> keeps the last state, got {row}", status == 200 and row["state"] == "done")
            s.post("media/render", dict(body, set=dict(body["set"], prompt="__fail__")))
            err = rd.wait(lambda k, f: k == "media_render" and f["data"].get("state") == "error", 15)
            ctx.check(f"a failed render publishes an error frame, got {err and err['data']['text']}", err is not None)
        finally:
            rd.close()
        vid = p.artboard_dir("clip")
        vid.mkdir(parents=True)
        (vid / "render.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
        with urllib.request.urlopen(f"{s.base}/design-files/{p.slug}/clip/render.mp4", timeout=10) as r:
            ctx.check(f"an .mp4 is served as video/mp4 with no sandbox, got {r.headers['Content-Type']} "
                      f"{r.headers['Content-Security-Policy']}", r.headers["Content-Type"] == "video/mp4"
                      and "sandbox" not in r.headers["Content-Security-Policy"])


def _register(rig):
    from halo_harness.remote import registry
    sid = rig.server.session_id
    registry.register(registry.make_entry(session_id=sid, cwd=str(rig.cwd), endpoint=rig.server.endpoint,
                                          token=rig.server.token, title="sessions test", mode="default"))
    return sid


@test
def test_sessions_list_and_the_answer_command(ctx: Ctx):
    from tests.helpers.remote_rig import Rig
    with Rig() as rig, MediaStudio() as s:
        sid = _register(rig)
        status, rows = s.get("sessions")
        row = next((r for r in rows if r["session_id"] == sid), None) if status == 200 else None
        ctx.check(f"the live session is listed with public fields and a status, got {row}", row is not None
                  and row["title"] == "sessions test" and row["status"] == "idle" and row["kind"] == "tui"
                  and "token" not in row and "endpoint" not in row)
        status, body = s.post(f"sessions/{sid}/command", {"cmd": "submit", "text": "please ask-approval"})
        ctx.check(f"submit goes through the socket, got {status} {body}", status == 200 and body["ok"])
        waiting = wait_for(lambda: (s.get("sessions")[1] or [{}])[0].get("status") == "waiting", 10, 0.2)
        ctx.check("the open approval card shows as waiting", waiting)
        status, body = s.post(f"sessions/{sid}/command", {"cmd": "answer", "kind": "approval", "request_id": "appr_1",
                                                         "action": "accept", "instruction": "ship it"})
        ctx.check(f"the answer reaches the session's approval waiter, got {status} {body}", status == 200
                  and wait_for(lambda: "appr_1" in rig.session.answers, 5)
                  and rig.session.answers["appr_1"].get("decision") == {"action": "accept", "instruction": "ship it"})
        status, body = s.post(f"sessions/{sid}/command", {"cmd": "answer", "kind": "approval", "request_id": "appr_9",
                                                         "action": "accept"})
        ctx.check(f"no pending card is a 502 with the socket's error, got {status} {body}", status == 502
                  and "no pending approval" in body["error"])
        ctx.check("an unknown command is a 422", s.post(f"sessions/{sid}/command", {"cmd": "slash"})[0] == 422)
        ctx.check("an unknown session is a 404", s.post("sessions/nobody/command", {"cmd": "interrupt"})[0] == 404)
        ctx.check("interrupt is forwarded", s.post(f"sessions/{sid}/command", {"cmd": "interrupt"})[1].get("ok"))
        ctx.check("the token guard holds", s.get("sessions", token="wrong")[0] == 401)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio media and sessions tests"))
