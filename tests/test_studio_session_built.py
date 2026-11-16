"""tests.test_studio_session_built -- the owner's sentence, in a real browser (Halo 3.6.0.2 "Session map", design
section 11, the VM browser test; headless Chrome through tests/helpers/studio_session_built.py, skipped without one).

Over this harness's real session (open, on starter, two agents mid-work) the workflow review and the map review-flow
are written as an applied Builder card writes them, new sessions are switched to review-flow, and the `builder_done`
frame arrives on the page. Then, as a person sees it:

2. within 10 s the word `new` on Session's Live button, in a slot that was already there; nothing moved, opened or
   popped up;
3. a press on Live shows the pair "Running: starter | Just built: review-flow", the map drawn down, the new box
   marked, every text at least 12 px, no box cut, and the truth block S13 with New session;
6. the rig's turn ends and two more turns come and go: the drawer stays exactly as it was;
4. Alt+2 opens Agents on its fourth view Live (starter, nothing amber); 3 · Map shows review-flow with L2.

All under 60 s from the frame. Seen red on the base first (P2, P3 and P4 make it green).
Run: python -m tests.test_studio_session_built   (the Linux VM; browser modules never run on the PC)
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUNS: dict = {}


def _driver(*argv: str) -> "tuple[subprocess.CompletedProcess, dict]":
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Session drawing needs headless Chrome)")
    if argv not in _RUNS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_session_built", *argv], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=300, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUNS[argv] = (r, info)
    r, info = _RUNS[argv]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    return r, info


@test
def test_his_sentence_built_shown_down_marked_agents_opens(ctx: Ctx):
    from tests.helpers.studio_session_built import STEPS_S, verdicts
    r, got = _driver()
    ctx.check(f"the driver ran, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in got)
    ctx.check(f"the page was reached with the rig's session row and its feed open, got {got.get('reached')!r} {got.get('feed_open')!r}",
              got.get("reached") is True and got.get("feed_open") is True)
    ctx.check("the builder_done frame was sent", got.get("frame_sent") is True)
    ctx.check(f"from the frame to the last step under {STEPS_S:.0f} s, got {got.get('steps_s')}", (got.get("steps_s") or 1e9) < STEPS_S)
    red = verdicts(got)
    ctx.check("built, shown at once, drawn down and marked, held across turns, Agents opens on Live: " + " | ".join(red), not red)


# what the driver returns when the page is as the design says, and as the base shows it (tests/helpers'
# verdicts must pass the first and name each assert of the second for its own reason)
_BOX = {"x": 20, "w": 200}
GREEN = {
    "word": {"seconds": 0.8, "name": "Live", "title": "Open Live (was Map): ...", "pressed": "false", "drawer": False,
             "sections_shown": ["session"], "dialogs": 0, "toasts": 0, "slot_before": True, "moved": []},
    "drawn": {"pair": "Running: starter | Just built: review-flow", "built_pressed": "true", "map": "review-flow", "dir": "down",
              "zoom": 1.0, "small_px": [], "ellipsis": [], "more_below": "", "new_session": True, "drawer": "",
              "truth": "This session keeps running on starter (the default), as it started. Start a new session to run on "
                       "review-flow. New session",
              "scroll": {"x": 0, "y": 100, "w": 455, "h": 600},
              "boxes": [{"box": "main", "y": 110, "h": 60, "new": False, "text": "main", "all": "main", **_BOX},
                        {"box": "review", "y": 200, "h": 120, "new": True, "text": "workflow review",
                         "all": "workflow review code coder review reviewer", **_BOX}],
              "s0": {"truth": "S13 ...", "truth_h": 64, "map": "review-flow", "top": 100, "main_top": 110}},
    "rig_turn": {"ended": True, "seconds": 2.0},
    "agents": {"view": "live", "live_tab": {"selected": "true", "text": "4 · Live"},
               "tabs": ["1 · Agents", "2 · Workflows", "3 · Map", "4 · Live"], "live_map": "starter", "amber": 0,
               "map_value": "review-flow", "watch_button": True,
               "topline": "This session runs on starter (the default), as it started; new sessions run on this map. Watch it in Live"},
}
GREEN["turns"] = [dict(GREEN["drawn"]["s0"], when=w) for w in ("idle after the rig's turn", "during 2", "after 2", "during 3", "after 3")]
BASE = {
    "word": {"seconds": None, "name": "Map", "title": "Open Map: The map this session runs on", "pressed": "false",
             "drawer": False, "sections_shown": ["session"], "dialogs": 0, "toasts": 0, "slot_before": False, "moved": []},
    "drawn": {"pair": "", "built_pressed": "", "map": "starter", "dir": "", "truth": "", "new_session": False,
              "drawer": "MAP drawer 455 px", "s0": {"truth": None, "truth_h": None, "map": "starter", "top": 120, "main_top": 130}},
    "turns": [{"when": "idle after the rig's turn", "truth": None, "truth_h": None, "map": None, "top": None, "main_top": None,
               "shows": "MAP drawer No session is running here"}],
    "rig_turn": {"ended": True, "seconds": 2.0},
    "agents": {"view": "crew", "live_tab": None, "tabs": ["1 · Agents", "2 · Workflows", "3 · Map"], "live_map": "", "amber": 0,
               "map_value": "starter", "topline": "Nothing is running on it now.", "watch_button": False},
}


@test
def test_the_verdicts_pass_the_designed_page_and_name_each_red_assert(ctx: Ctx):
    """Runs anywhere (no browser): the reading of the driver's JSON."""
    import copy
    from tests.helpers.studio_session_built import verdicts
    ctx.check(f"the page as the design says: nothing red, got {verdicts(GREEN)}", verdicts(GREEN) == [])
    red = verdicts(BASE)
    want = [("(2)", "no word new"), ("(3)", "not the map review-flow"), ("(6)", "No session is running here"), ("(4)", "it has no Live view")]
    ctx.check(f"the base: each of (2) (3) (6) (4) red for its own reason, got {red}",
              len(red) == 4 and all(line.startswith(n) and why in line for line, (n, why) in zip(red, want)))
    for path, value, n in ((("word", "moved"), ["session-cost"], "(2)"), (("drawn", "dir"), "", "(3)"),
                           (("agents", "amber"), 1, "(4)")):
        g = copy.deepcopy(GREEN)
        g[path[0]][path[1]] = value
        ctx.check(f"one fault alone ({path}) is red as {n} only, got {verdicts(g)}", [x[:3] for x in verdicts(g)] == [n])
    g = copy.deepcopy(GREEN)
    g["turns"][3]["truth_h"] = 80
    ctx.check(f"a truth block that grows during turn 3 is red as (6), got {verdicts(g)}",
              len(verdicts(g)) == 1 and verdicts(g)[0].startswith("(6) during 3"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
