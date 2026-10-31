"""tests.test_studio_steer_image -- Halo 3.3.6.0 R6: Studio takes an image into a session's steer, in a real browser
(headless Chrome through tests/helpers/studio_steer_image.py; skipped without one), plus the routes without a
browser (studio/session_eyes_api.py):

1. a base64 PNG pasted into the Live steer becomes the chip (name, w x h, size); Send puts it in the session's
   log as an image block with `image_path` and no base64 (the TUI's paste's LOG shape);
2. the Screenshot button attaches the harness's own capture (the seam's fixture), its title says whose screen;
3. a model that cannot see: the chip shows the offer's line and three buttons (the lane's disabled with no visual
   lane set); "Text only" is the pick that rides with the steer (tests/test_eyes_offer.py runs each choice);
4. the routes: the 5 MB rule (413), a bad media type (422), an image_path outside the session's folder (422),
   the screenshot command's answer, GET sessions/<sid>/eyes.
Run: python -m tests.test_studio_steer_image
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "tests" / "fixtures" / "vision" / "shot.png"
_RUN: dict = {}


def _driver():
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the steer's image needs headless Chrome)")
    if not _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_steer_image", "steer"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"], _RUN["info"] = r, info
    r, info = _RUN["r"], _RUN["info"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    return r, info


def _ran(ctx: Ctx, r, got) -> None:
    ctx.check(f"the driver ran, got {r.returncode} {got.get('failed')!r} {r.stderr[-800:]!r}", r.returncode == 0 and "failed" not in got)


@test
def test_a_pasted_png_becomes_the_chip_and_the_logs_image_block(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    chip = got.get("chip") or {}
    ctx.check(f"the chip: name, 4 x 3, size, got {chip}", chip.get("name") == "clip.png" and (chip.get("w"), chip.get("h")) == ("4", "3")
              and "4 x 3" in str(chip.get("text")) and "KB" in str(chip.get("text")))
    logged = (got.get("logged") or [{}])[0]
    ctx.check(f"the log's image block has image_path and no base64, got {logged}", logged.get("type") == "image"
              and "attachments" in str(logged.get("image_path")) and "source" not in logged and "data" not in json.dumps(logged))
    ctx.check(f"it lands at the steer's safe point, got {got.get('kinds')}", "steer_image" in (got.get("kinds") or []))
    ctx.check("the chip clears once sent", got.get("chip_cleared") == "gone")


@test
def test_the_screenshot_button_and_the_offer_on_the_chip(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    ctx.check(f"the button says whose screen, got {got.get('button_title')!r}", "this PC's screen" in str(got.get("button_title")))
    shot = got.get("shot_chip") or {}
    ctx.check(f"the capture is the chip, got {shot}", shot.get("from") == "screenshot" and str(shot.get("name", "")).startswith("shot-"))
    ctx.check(f"the offer's line, got {got.get('offer_line')!r}", "cannot see images" in str(got.get("offer_line")))
    ids = [b[0] for b in got.get("offer_buttons") or []]
    ctx.check(f"three buttons, got {got.get('offer_buttons')}", ids == ["session-steer-eyes-lane", "session-steer-eyes-describe",
                                                                      "session-steer-eyes-send"])
    ctx.check("no visual lane here: that button is disabled", (got.get("offer_buttons") or [[None, None]])[0][1] is True)
    ctx.check(f"Text only is picked, got {got.get('picked')}", got.get("picked") == "send")
    ctx.check("the chip's remove button", got.get("removed") == "gone")


def _req(body, sid="s-eyes", **query):
    return SimpleNamespace(body=body, params={"sid": sid}, query=query)


@test
def test_the_routes_without_a_browser(ctx: Ctx):
    from halo_harness.studio import session_eyes_api as E
    saved = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="ey-eyes-api-")
    try:
        b64 = base64.b64encode(FIXTURE.read_bytes()).decode("ascii")
        st, f = E.image_fields("s-eyes", {"image": {"media_type": "image/png", "data_b64": b64}, "eyes": "describe"})
        ctx.check(f"a PNG is written to the session's folder, got {st} {f}", st == 200 and Path(f["image_path"]).is_file()
                  and Path(f["image_path"]).parent.name == "s-eyes" and f["eyes_choice"] == "describe")
        big = "A" * (E.MAX_B64 + 8)
        ctx.check("over the 5 MB rule: 413", E.image_fields("s-eyes", {"image": {"media_type": "image/png", "data_b64": big}})[0] == 413)
        ctx.check("a bad media type: 422", E.image_fields("s-eyes", {"image": {"media_type": "text/plain", "data_b64": b64}})[0] == 422)
        ctx.check("a path outside the folder: 422", E.image_fields("s-eyes", {"image_path": str(FIXTURE)})[0] == 422)
        ctx.check("no image: nothing added", E.image_fields("s-eyes", {"text": "hi"}) == (200, {}))
        os.environ["HALO_SCREENSHOT_FIXTURE"] = str(FIXTURE)
        try:
            st, shot = E.screenshot("s-eyes", {"target": "screen"})
        finally:
            os.environ.pop("HALO_SCREENSHOT_FIXTURE", None)
        res = shot.get("result") or {}
        ctx.check(f"the screenshot command, got {st} {res}", st == 200 and res.get("name") == "shot-1.png" and (res["width"], res["height"]) == (4, 3))
        ctx.check("its path is accepted for the steer", E.image_fields("s-eyes", {"image_path": res["path"]})[0] == 200)
        st, eyes = E.get_eyes(_req({}, model="or:mock/no-such-vision-model"))
        ctx.check(f"GET eyes: the offer for a model with no vision, got {st} {eyes.get('offer')} {[c['id'] for c in eyes.get('choices') or []]}",
                  st == 200 and eyes["offer"] is True and [c["id"] for c in eyes["choices"]] == ["lane", "describe", "send"])
        ctx.check("GET eyes needs the model", E.get_eyes(_req({}))[0] == 422)
    finally:
        if saved is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
