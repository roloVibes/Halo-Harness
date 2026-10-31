"""tests.test_fleet_capture -- Halo 3.3.7.0 R4: a hub's capture on a member's display (fleet/control_capture.py,
fleet/control.py's `capture`, studio/fleet_hub_api.py's screenshot for a member), with the capture seam's fixture PNG
(HALO_SCREENSHOT_FIXTURE under the test flag) -- never a real capture of this desktop:

1. the member runs capture_for itself: the file lands in its own attachments folder and the answer is {path, bytes,
   w, h} with no image; with the member's fleet.share_captures on, the image comes with it;
2. under fleet.allow_control: none it is refused like a steer; a bad target is refused in one line;
3. Studio's screenshot for a member's session goes to the hub as `capture` with the target; an image for a member is
   still its own (422).
Run: python -m tests.test_fleet_capture
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "vision" / "shot.png"


class Handle:
    session_id, controller, kind = "sess-m1", None, "tui"

    def __init__(self):
        from types import SimpleNamespace
        self.session, self.notes = SimpleNamespace(log=None), []

    def status(self):
        return {"session_id": self.session_id}

    def _note(self, text):
        self.notes.append(text)


class Member:
    def __enter__(self):
        import tempfile
        self.saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "HALO_SCREENSHOT_FIXTURE", "BRIDGE_STATE_DIR")}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        self.root = Path(tempfile.mkdtemp(prefix="hg_member-"))
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), HALO_SCREENSHOT_FIXTURE=str(FIXTURE))
        from halo_harness.config.paths import bridge_home
        self.state = bridge_home()
        self.state.mkdir(parents=True, exist_ok=True)
        self.config({})
        return self

    def config(self, fleet: dict) -> None:
        from halo_harness.fleet import identity
        (self.state / "config.json").write_text(json.dumps({"fleet": {"name": "mac@lab", **fleet}}), encoding="utf-8")
        identity.forget_cache()

    def __exit__(self, *exc):
        from halo_harness.fleet import identity
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        identity.forget_cache()


def _run(fields, level="all"):
    from halo_harness.fleet.control import run
    return run(Handle(), {"cmd": "capture", "fields": fields, "by": "bob", "hub": "pc-hub", "cid": "c1"},
               {"share": "full", "allow_control": level, "allow_answers": False})


@test
def test_the_member_keeps_the_file(ctx: Ctx):
    with Member() as m:
        got = _run({"target": "screen"})
        res = got.get("result") or {}
        ctx.check(f"done with the path and the size, no image, got {got}", got["state"] == "done" and res.get("ok")
                  and Path(res["path"]).is_file() and str(m.root) in res["path"] and "attachments" in res["path"]
                  and res["bytes"] > 0 and res["w"] and res["h"] and "image" not in res and res["shared"] is False
                  and "fleet.share_captures is off" in res["say"])
        m.config({"share_captures": True})
        shared = _run({"target": "screen"})["result"]
        ctx.check("with share_captures on there, the image comes with it", shared["shared"] and len(shared["image"]) > 10)
        m.config({"allow_control": "none"})
        none = _run({"target": "screen"}, level="none")
        ctx.check(f"allow_control none refuses it, got {none}", none["state"] == "refused" and "allow_control: none" in none["error"])
        bad = _run({"target": "elsewhere"})
        ctx.check(f"a bad target is one line, got {bad}", bad["state"] == "error" and "target is one of" in bad["error"])


@test
def test_studio_sends_a_members_screenshot_as_capture(ctx: Ctx):
    from halo_harness.studio import fleet_hub_api as F
    sent = []
    saved_send, saved_local = F._send, F._local
    F._send = lambda req, hid, sid, cmd, fields: sent.append((hid, sid, cmd, fields)) or (200, {"state": "done"})
    F._local = lambda req, hid: False
    try:
        from types import SimpleNamespace
        req = SimpleNamespace(params={"hid": "member-1", "sid": "sess-m1"}, body={"cmd": "screenshot", "target": "window",
                                                                                   "title": "Live"})
        st, _ = F.post_session_command(req)
        img = F.post_session_command(SimpleNamespace(params={"hid": "member-1", "sid": "s"}, body={"cmd": "steer",
                                                                                                    "image": "x"}))
    finally:
        F._send, F._local = saved_send, saved_local
    ctx.check(f"the hub sends `capture` with the target, got {sent}", st == 200 and sent == [
        ("member-1", "sess-m1", "capture", {"target": "window", "title": "Live"})])
    ctx.check(f"an image for a member is still its own, got {img}", img[0] == 422 and "files are its own" in img[1]["error"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
