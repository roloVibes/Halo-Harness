"""tests.test_studio_textboxes -- Halo 3.3.15.0 R3 "text boxes fit their text" (the owner, 2026-11-09: "These chat prompt
boxes or all boxes that have text in them need to be bigger ... I can't ever see the example text fully"). Unit pins over
the source, then headless Chrome through tests/helpers/studio_textboxes.py (skipped without one) over the Prompt
panel's rig (tests/helpers/prompt_rig.py); no provider request, no model call:

1. one primitive: `lib/ui/TextBox.tsx` is the only `<textarea` in `ui/src`; styles/textbox.css makes it three lines at
   the least, `--tb-max` (12) at the most, no resize handle, `field-sizing: content` (a measured fallback in the
   component), imported after every section's sheet; `Field` offers it as `multiline`; lib/ui exports it;
2. placeholders fit: the composer's is "Type a turn, or / for a command" and its keys are in the panel's `?`;
3. Chrome: on Session's Prompt panel, Orchestra's goal form and Roles' Lineup tab every textarea is >= 3 lines tall
   empty, grows with four lines, stops at twelve and scrolls, and its placeholder takes at most two lines with no word
   wider than the box; the composer takes the panel's free height while the feed is short, and with a feed taller than
   the panel it is its own size again while the feed scrolls; the Lineup tab's field hints are in its `?`;
4. the bar breathes (owner feedback 2026-11-09 on the strips; 3.6.0.0 R0a: the strips became the view bar's buttons):
   on Agents -> Live and Session with every drawer closed the bar is 44 px, each button >= 32 px, 8 px apart and from
   the bar's ends, its name centred; an open drawer's bar is >= 36 px and its body pads >= 12 px.
Run: python -m tests.test_studio_textboxes
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
_RUN: dict = {}
TOUCHED = ["lib/ui/TextBox.tsx", "lib/ui/Field.tsx", "lib/ui/index.ts", "styles/textbox.css", "styles/prompt.css", "main.tsx",
           "routes/session/PromptComposer.tsx", "routes/session/Prompt.tsx", "routes/orchestra/GoalForm.tsx", "routes/roles/controls.tsx",
           "routes/roles/TabHelp.tsx", "routes/roles/LineupTab.tsx", "routes/roles/Assignment.tsx", "routes/fleet/Steer.tsx",
           "styles/workspace.css", "lib/workspace/types.ts"]


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_textboxes", why="the text boxes' sizes need headless Chrome", cache=_RUN,
                      timeout=420, tail=600, what="the text box driver")


def _lines(b: dict, n: int) -> float:
    return n * b["lh"] + b["pad"] + b["border"]


@test
def test_textbox_is_the_only_textarea(ctx: Ctx):
    hits = [str(p.relative_to(UI)).replace("\\", "/") for p in UI.rglob("*.ts*") if "<textarea" in p.read_text(encoding="utf-8")]
    ctx.check(f"only lib/ui/TextBox.tsx draws a <textarea, got {hits}", hits == ["lib/ui/TextBox.tsx"])
    users = [p for p in UI.rglob("*.tsx") if "<TextBox" in p.read_text(encoding="utf-8")]
    ctx.check(f"the boxes use it (at least ten files), got {len(users)}", len(users) >= 10)


@test
def test_the_rule_is_in_one_place(ctx: Ctx):
    css = (UI / "styles" / "textbox.css").read_text(encoding="utf-8")
    for bit in ("--tb-min: calc(3 * var(--tb-line)", "--tb-cap: calc(var(--tb-max, 12) * var(--tb-line)", "resize: none",
                "field-sizing: content", "min-height: var(--tb-min)", "max-height: var(--tb-cap)", "content: attr(data-mirror)"):
        ctx.check(f"textbox.css says {bit}", bit in css)
    box = (UI / "lib" / "ui" / "TextBox.tsx").read_text(encoding="utf-8")
    ctx.check("TextBox: maxRows 12 by default, the measured fallback, fill, rows fixed at 3",
              "maxRows = 12" in box and 'CSS.supports("field-sizing", "content")' in box and "scrollHeight" in box
              and "fill" in box and "rows={3}" in box)
    ctx.check("lib/ui exports it", "export { TextBox" in (UI / "lib" / "ui" / "index.ts").read_text(encoding="utf-8"))
    ctx.check("Field offers it as multiline", "multiline ? <TextBox" in (UI / "lib" / "ui" / "Field.tsx").read_text(encoding="utf-8"))
    imports = re.findall(r'import "\./styles/([\w-]+)\.css"', (UI / "main.tsx").read_text(encoding="utf-8"))
    ctx.check(f"textbox.css is imported after every section's sheet, got {imports[-3:]}", imports and imports[-1] == "textbox")
    for rel in TOUCHED:
        text = (UI / rel).read_text(encoding="utf-8")
        n = len(text.splitlines())
        raw = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", re.sub(r"/\*.*?\*/", "", text, flags=re.S)) if rel.endswith(".css") else []
        ctx.check(f"{rel}: {n} lines <= 250, no colour literal {raw}", n <= 250 and not raw)


@test
def test_the_composer_placeholder_is_one_line_and_its_keys_are_in_help(ctx: Ctx):
    src = (UI / "routes" / "session" / "PromptComposer.tsx").read_text(encoding="utf-8")
    ctx.check("the placeholder is 'Type a turn, or / for a command'", 'placeholder={off || "Type a turn, or / for a command"}' in src)
    ctx.check("the composer fills its panel", "<TextBox ref={box} fill mono" in src)
    helps = (UI / "routes" / "help-session.ts").read_text(encoding="utf-8")
    ctx.check("the panel's ? has Enter, Shift+Enter and the history", all(k in helps for k in ("Enter sends", "Shift+Enter is a new line", "history")))


def _sizes(ctx: Ctx, where: str, rows: list) -> None:
    ctx.check(f"{where}: the boxes are there, got {[b.get('testid') for b in rows]}", bool(rows))
    for b in rows:
        name = f"{where} {b['testid']}"
        ctx.check(f"{name}: a TextBox, no resize handle, got {b['textbox']} {b['resize']}", b["textbox"] and b["resize"] == "none")
        ctx.check(f"{name}: three lines empty, got {b['h0']} for {_lines(b, 3)}", b["h0"] >= _lines(b, 3) - 0.5)
        ctx.check(f"{name}: grows with four lines, got {b['h4']} for {_lines(b, 4)}", b["h4"] >= _lines(b, 4) - 0.5 and b["h4"] > b["h0"])
        ctx.check(f"{name}: twelve lines at the most, then it scrolls, got {b['h20']} for {_lines(b, 12)} {b['scrolls']}",
                  abs(b["h20"] - _lines(b, 12)) <= 1.5 and b["scrolls"])


def _placeholders(ctx: Ctx, where: str, rows: list) -> None:
    for b in rows:
        ph = b.get("ph") or {}
        ctx.check(f"{where} {b['testid']}: its placeholder fits, at most two lines, got {ph}", ph.get("fits") and ph.get("lines", 0) <= 2)


@test
def test_the_prompt_box_fills_the_panel_while_the_feed_is_short(ctx: Ctx):
    got = _got(ctx)
    rows, room = got.get("prompt") or [], got.get("prompt_room") or {}
    ctx.check(f"one box, with fill, got {[(b.get('testid'), b.get('fill')) for b in rows]}", [(b.get("testid"), b.get("fill")) for b in rows]
              == [("prompt-input", True)])
    b = rows[0] if rows else {"h0": 0, "h4": 0, "lh": 1, "pad": 0, "border": 0}
    ctx.check(f"three lines at the least, got {b['h0']}", b["h0"] >= _lines(b, 3) - 0.5 and b["h4"] >= b["h0"] - 0.5)
    ctx.check(f"it reaches the foot, the feed is no taller than it holds, got {room}", room.get("box_bottom_gap", 99) <= 12
              and room.get("feed_h", 999) <= room.get("feed_content", 0) + 2 and room.get("box_h", 0) > _lines(b, 6))
    _placeholders(ctx, "the composer", rows)


@test
def test_the_prompt_box_under_a_long_feed(ctx: Ctx):
    got = _got(ctx)
    _sizes(ctx, "the composer under a long feed", got.get("prompt_long") or [])
    feed = got.get("prompt_long_feed") or [0, 0]
    ctx.check(f"the feed scrolls on its own, got {feed}", 0 < feed[0] < feed[1])


@test
def test_the_orchestra_goal_boxes(ctx: Ctx):
    rows = _got(ctx).get("orchestra") or []
    ctx.check(f"WHAT YOU WANT, DONE WHEN, STOP WHEN, got {len(rows)}", len(rows) == 3)
    _sizes(ctx, "the goal form", rows)
    _placeholders(ctx, "the goal form", rows)


@test
def test_the_lineup_tab_boxes_and_its_help(ctx: Ctx):
    got = _got(ctx)
    rows = got.get("roles") or []
    ctx.check(f"Description and How the pieces work together, got {[b.get('testid') for b in rows]}",
              [b.get("testid") for b in rows] == ["roles-description", "roles-about"])
    _sizes(ctx, "the Lineup tab", rows)
    _placeholders(ctx, "the Lineup tab", rows)
    h = got.get("roles_help") or {}
    # 3.3.16.0 R1b: the tab opens on its summary (no box); the Description page's ? lists its three fields only
    ctx.check(f"the fields' hints are in the page's ?, none under a field, the summary has no box, got {h}", h.get("help")
              and h.get("help_lines", 0) >= 3 and h.get("hints_under_fields") == 0 and h.get("summary_boxes") == 0)


@test
def test_the_strips_breathe(ctx: Ctx):
    """Owner feedback 2026-11-09 (a photo of Fleet: the strips "squished and too small"); 3.6.0.0 R0a: no strips, the
    view bar's buttons instead -- the bar 44 px, each button >= 32 px with its name centred and 12 px at its sides, 8 px
    between buttons and to the bar's ends; an open drawer's title bar is >= 36 px and its body pads >= 12 px."""
    got = _got(ctx)
    for where in ("fleet_strips", "session_strips"):
        m = got.get(where) or {}
        ctx.check(f"{where}: the bar 44 px, its buttons drawn, each >= 32 px, got {m.get('bar')} {m.get('heights')}",
                  m.get("bar") == 44 and m.get("n", 0) >= 5 and min(m.get("heights") or [0]) >= 32)
        ctx.check(f"{where}: >= 8 px between them, got {m.get('hgap')}", m.get("hgap", 0) >= 8)
        ctx.check(f"{where}: >= 8 px to the bar's ends, 12 px side padding, the name centred, got {m.get('edge')} "
                  f"{m.get('pad')} {m.get('off')}", m.get("edge", 0) >= 8 and m.get("pad", 0) >= 12 and m.get("off", 99) <= 2)
        f = m.get("frame") or {}
        ctx.check(f"{where}: an open drawer's bar >= 36 px, its body pads >= 12 px, got {f}", f.get("bar", 0) >= 36 and f.get("body_pad", 0) >= 12)
    src = (UI / "lib" / "workspace" / "types.ts").read_text(encoding="utf-8")
    ctx.check("no strip rows any more (3.6.0.0 R0a)", "STRIP_ROWS" not in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
