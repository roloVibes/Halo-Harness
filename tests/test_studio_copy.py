"""tests.test_studio_copy -- copying out of Session in a real browser (Halo 3.6.0.6 C, the owner's point 33 of
2026-11-20: "Copying from the session barely works!", "copying from the harness just sucks and doesn't work"), headless
Chrome through tests/helpers/studio_copy.py (skipped without one), over this harness's real session with extra agents
and scripted feed frames:

1. a drag from one Live row's words into the next row's selects the rows' own words, one row a line: no clock, no
   kind label, no agent tag, no "why?", no Copy, nothing of the Steer box;
2. a drag inside a row does not change who is steered; a plain click on a row still chooses it;
3. a reply's Copy shows on hover in room that was there from the first draw (no rect moves), is a tab stop, shows on
   keyboard focus, puts the reply's SOURCE on the clipboard, reads "Copied" for two seconds, then "Copy";
4. a code block's Copy puts the code only (indentation and line breaks kept);
5. the same two buttons in the Prompt panel's feed;
6. a refused clipboard reads "Select and copy it yourself" and selects the reply for him; the page had no errors.
Run: python -m tests.test_studio_copy
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}


def _driver() -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (copying in Session needs headless Chrome)")
    if not _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_copy", "copy"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"], _RUN["info"] = r, info
    r, info = _RUN["r"], _RUN["info"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    return info


def _ran(ctx: Ctx, got: dict) -> None:
    r = _RUN["r"]
    ctx.check(f"the driver ran, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in got)


def _copied(ctx: Ctx, got: dict, prefix: str, want: str) -> None:
    clip = got.get(f"{prefix}_clip") or {}
    ctx.check(f"{prefix}: the button is there, got {got.get(f'{prefix}_btn')!r}", got.get(f"{prefix}_btn") is True)
    ctx.check(f"{prefix}: the clipboard holds it, read back {clip.get('read')!r}", clip.get("read") == want)
    ctx.check(f"{prefix}: the page wrote it, got {clip.get('hook')!r}", clip.get("hook") == want)
    ctx.check(f"{prefix}: Copied, then Copy again, got {got.get(f'{prefix}_said')!r} -> {got.get(f'{prefix}_back')!r}",
              got.get(f"{prefix}_said") == "Copied" and got.get(f"{prefix}_back") == "Copy")
    hov = got.get(f"{prefix}_hover") or {}
    ctx.check(f"{prefix}: hidden, then shown on hover, got {hov.get('opacity')}", hov.get("opacity") == ["0", "1"])
    ctx.check(f"{prefix}: nothing moved (the row and the button), got {hov.get('before')} -> {hov.get('after')} -> {got.get(f'{prefix}_after_rect')}",
              bool(hov.get("before")) and hov.get("before") == hov.get("after") == got.get(f"{prefix}_after_rect"))
    ctx.check(f"{prefix}: a tab stop that reads Copy, got {hov.get('tabindex')} {hov.get('label')!r}", hov.get("tabindex") == 0 and hov.get("label") == "Copy")


@test
def test_a_drag_across_live_rows_selects_only_what_the_agents_said(ctx: Ctx):
    from tests.helpers.studio_copy import ALPHA
    got = _driver()
    _ran(ctx, got)
    sel = str(got.get("across") or "")
    lines = [x.strip() for x in sel.splitlines() if x.strip()]
    ctx.check(f"the two rows' words, one row a line, got {sel!r}", lines == [ALPHA, "BRAVO-ROW"])
    ctx.check(f"no clock, no kind, no tag, no why?, no Copy, no Steer box, got {sel!r}",
              re.search(r"\d\d:\d\d:\d\d|TEXT|why\?|Copy|Steering|steer ▸|tester|docs", sel) is None)


@test
def test_a_drag_inside_a_row_does_not_move_the_steer_target(ctx: Ctx):
    got = _driver()
    _ran(ctx, got)
    keys = got.get("keys") or {}
    ctx.check(f"the drag selected the words, got {got.get('inside_sel')!r}", str(got.get("inside_sel")) == "second agent words")
    ctx.check(f"the target did not move, got {got.get('target_before')!r} -> {got.get('target_after_drag')!r}",
              got.get("target_after_drag") == got.get("target_before") and got.get("target_before") != keys.get("docs"))
    ctx.check(f"a plain click on the row's words chooses it, got {got.get('target_after_click')!r}", got.get("target_after_click") == keys.get("docs"))
    ctx.check(f"a click on another row's clock chooses that row, got {got.get('target_after_clock')!r}", got.get("target_after_clock") == keys.get("tester"))


@test
def test_a_replys_copy_in_live_puts_its_source_on_the_clipboard(ctx: Ctx):
    from tests.helpers.studio_copy import REPLY
    got = _driver()
    _ran(ctx, got)
    _copied(ctx, got, "live_reply", REPLY)
    ctx.check(f"keyboard focus shows it, got {got.get('focus_shows')!r}", got.get("focus_shows") == "1")


@test
def test_a_code_blocks_copy_in_live_puts_the_code_only(ctx: Ctx):
    from tests.helpers.studio_copy import CODE
    got = _driver()
    _ran(ctx, got)
    _copied(ctx, got, "live_code", CODE)


@test
def test_the_prompt_feed_has_the_same_buttons(ctx: Ctx):
    from tests.helpers.studio_copy import CODE, REPLY
    got = _driver()
    _ran(ctx, got)
    _copied(ctx, got, "feed_reply", REPLY)
    _copied(ctx, got, "feed_code", CODE)


@test
def test_a_refused_clipboard_says_so_and_selects_the_reply(ctx: Ctx):
    got = _driver()
    _ran(ctx, got)
    ctx.check(f"the button says what to do, got {got.get('refused_said')!r}", got.get("refused_said") == "refused")
    sel = str(got.get("refused_sel") or "")
    ctx.check(f"the reply is selected for him (and no button word), got {sel!r}",
              "COPY-REPLY here is the fix:" in sel and "i.price for i in items" in sel and "Then run it." in sel and "Copy" not in sel)
    ctx.check(f"the clipboard permission was granted through DevTools, got {got.get('granted')!r}", got.get("granted") is True)
    ctx.check(f"the page had no errors, got {got.get('errors')!r}", got.get("errors") == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
