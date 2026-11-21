"""tests.helpers.studio_copy -- copying out of Session (Halo 3.6.0.6 C, the owner's point 33 of 2026-11-20: "Copying
from the session barely works!"), through real drags, hovers and presses in headless Chrome on the driver base
(tests/helpers/chrome_driver.Driver), over tests/helpers/studio_session_rig.py (this harness's real session) with the
extra agents and scripted feed frames of tests/helpers/studio_live_rig.py. tests/test_studio_copy.py runs it:

    python -m tests.helpers.studio_copy copy   a drag from one Live row's words into the next row's: the selection is
                                               the rows' own words, one row a line (no clock, kind, tag, why?, Copy or
                                               Steer box); a drag inside a row leaves the steer target where it was, a
                                               plain click still chooses the row; a reply's Copy shows on hover in room
                                               that was there (no rect moves), a press puts the reply's source on the
                                               clipboard and reads "Copied", then "Copy" again; a code block's Copy the
                                               code only; the same in the Prompt panel's feed; a refused clipboard
                                               reads "Select and copy it yourself" with the reply selected

The clipboard is read back with `navigator.clipboard.readText()` (the permission granted through DevTools'
Browser.grantPermissions); the page's own writeText is also wrapped to record what it was given (`hook`), and both are
reported. The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import json
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_session import collect_page_errors, page_errors  # noqa: E402
from tests.helpers.studio_session_steer import COL, LINES  # noqa: E402

CODE = "def total(items):\n    return sum(\n        i.price for i in items\n    )"
REPLY = f"COPY-REPLY here is the fix:\n```python\n{CODE}\n```\nThen run it."
ALPHA = "ALPHA-ROW first agent words here."
BRAVO = "BRAVO-ROW second agent words."
FEED = "document.querySelector('[data-testid=\"prompt-feed\"]')"
HOOK = ("(() => { window.__copied = window.__copied || []; const cb = navigator.clipboard; if (!cb || cb.__wrapped) return !!cb;"
        " const w = Clipboard.prototype.writeText.bind(cb); cb.writeText = (t) => { window.__copied.push(t); return w(t); };"
        " cb.__wrapped = true; return true; })()")
# Windows' own clipboard hands text back with CRLF line ends whatever was put on it (the page wrote LF): the read is
# compared with its line ends as LF. (On Windows the page's clipboard is the system's: this module replaces what a
# person had copied; it is for CI and the Linux VM, not for a machine in use.)
READ = "navigator.clipboard.readText().then((t) => t.replace(/\\r\\n/g, '\\n'), (e) => 'READ-REFUSED: ' + e)"


def row_of(word: str) -> str:
    return f"{LINES}.find((l) => l.textContent.includes({json.dumps(word)}))"


def word_at(c, scope: str, word: str) -> list:
    """[left, middle y, right] of `word`'s first text inside `scope` (a Range over the text node, as a person aims)."""
    return c.js(f"""(() => {{ const root = ({scope}); if (!root) return null; const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      let n; while ((n = w.nextNode())) {{ const i = n.data.indexOf({json.dumps(word)}); if (i >= 0) {{
        const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + {len(word)}); const b = r.getBoundingClientRect();
        return [b.left, b.top + b.height / 2, b.right]; }} }} return null; }})()""")


def label(c, btn: str) -> str:
    return c.js(f"({btn})?.querySelector('[data-on]')?.textContent || ''")


def clipboard(c) -> dict:
    return {"read": c.js(READ), "hook": c.js("(window.__copied || []).slice(-1)[0] || ''")}


def opened(c, rig) -> dict:
    collect_page_errors(c)
    origin = f"http://127.0.0.1:{rig.server.server_address[1]}"
    try:
        c.call("Browser.grantPermissions", origin=origin, permissions=["clipboardReadWrite", "clipboardSanitizedWrite"])
        granted = True
    except Exception as e:  # noqa: BLE001 -- the hook still reports what was written
        granted = f"{type(e).__name__}: {e}"[:200]
    c.call("Emulation.setFocusEmulationEnabled", enabled=True)  # the page has the focus a person's window has
    c.go(rig.url("session", f"&session={rig.act.session_id}&prompt=1"))
    c.wait(f"!!{COL} && !!document.querySelector('[data-testid=\"prompt-detail\"]') && 1", 40)
    time.sleep(0.8)
    return {"granted": granted, "hooked": c.js(HOOK)}


def seeded(c, lv) -> dict:
    lv.say("tester", ALPHA)
    lv.say("docs", BRAVO)
    lv.say("main", REPLY)
    c.wait(f"!!{row_of('COPY-REPLY')} && !!{row_of('BRAVO-ROW')} && !!{FEED} && {FEED}.textContent.includes('COPY-REPLY') && 1", 15)
    time.sleep(0.4)
    return {"keys": {"tester": lv.key("tester"), "docs": lv.key("docs"), "main": lv.key("main")}}


def across_rows(c, lv) -> dict:
    """A real drag from the first word of one row into the next row: what the page selected."""
    c.js(f"{row_of('ALPHA-ROW')}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    a = word_at(c, row_of("ALPHA-ROW"), "ALPHA-ROW")
    b = word_at(c, row_of("BRAVO-ROW"), "BRAVO-ROW")
    c.drag(a[0] + 1, a[1], b[2] - 1, b[1])
    time.sleep(0.3)
    sel = c.js("getSelection().toString()")
    c.click(5, 5)  # a click outside the rows lets the selection go
    return {"across": sel}


def inside_row(c, lv) -> dict:
    """A drag inside the docs row leaves the steer target; a plain click on its words, or on another row's clock, chooses."""
    out: dict = {"target_before": c.js(f"{COL}.dataset.target || ''")}
    a = word_at(c, row_of("BRAVO-ROW"), "second")
    b = word_at(c, row_of("BRAVO-ROW"), "words")
    c.drag(a[0] + 1, a[1], b[2] - 1, b[1])
    time.sleep(0.5)
    out["inside_sel"] = c.js("getSelection().toString()")
    out["target_after_drag"] = c.js(f"{COL}.dataset.target || ''")
    c.click(a[0] + 4, a[1])
    out["target_after_click"] = c.wait(f"{COL}.dataset.target === {json.dumps(lv.key('docs'))} && {COL}.dataset.target", 5)
    c.click_on(f"{row_of('ALPHA-ROW')}.querySelector('[data-testid=\"session-live-time\"]')")
    out["target_after_clock"] = c.wait(f"{COL}.dataset.target === {json.dumps(lv.key('tester'))} && {COL}.dataset.target", 5)
    return out


def _press(c, scope: str, testid: str, prefix: str) -> dict:
    """Away, then hover over `scope`: the button shows where its room already was; a press copies; two seconds later
    it reads Copy again."""
    btn = f"({scope})?.querySelector('[data-testid=\"{testid}\"]')"
    out: dict = {f"{prefix}_btn": c.js(f"!!{btn}")}
    if not out[f"{prefix}_btn"]:
        return out
    c.js(f"{btn}.scrollIntoView({{block: 'center'}}); 1")  # the button's line in sight (a tall row may not fit its panel)
    c.mouse("mouseMoved", 2, 2)
    time.sleep(0.3)
    rects = f"[({scope}).getBoundingClientRect(), {btn}.getBoundingClientRect()].map((r) => [r.left, r.top, r.width, r.height].map(Math.round))"
    r0, o0 = c.js(rects), c.js(f"getComputedStyle({btn}).opacity")
    x = c.rect(scope)[0]
    bx, by, bw, bh = c.rect(btn)
    hx, hy = x + 10, by + bh / 2  # on the button's line, at the left of the row: the row hovered, not the button
    c.mouse("mouseMoved", hx, hy)
    time.sleep(0.3)
    at = (f"(() => {{ const e = document.elementFromPoint({hx}, {hy}); return e ? [e.tagName, e.className, e.dataset.testid || '', "
          f"!!{btn}.closest('.slv-line, .spp-row')?.matches(':hover')] : null; }})()")
    out[f"{prefix}_hover"] = {"before": r0, "after": c.js(rects), "opacity": [o0, c.js(f"getComputedStyle({btn}).opacity")],
                              "tabindex": c.js(f"{btn}.tabIndex"), "label": label(c, btn), "at": c.js(at),
                              "on_btn": c.js(f"(() => {{ const r = {btn}.getBoundingClientRect(); const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return !!e && {btn}.contains(e); }})()")}
    c.click_on(btn)
    out[f"{prefix}_said"] = c.wait(f"(({btn}).querySelector('[data-on]')?.textContent || '') === 'Copied' && 'Copied'", 5)
    out[f"{prefix}_clip"] = clipboard(c)
    out[f"{prefix}_after_rect"] = c.js(rects)
    time.sleep(2.4)
    out[f"{prefix}_back"] = label(c, btn)
    return out


def live_buttons(c, lv) -> dict:
    row = row_of("COPY-REPLY")
    out = _press(c, row, "copy-reply", "live_reply")
    out.update(_press(c, f"{row}.querySelector('[data-testid=\"reply-code\"]')", "copy-code", "live_code"))
    btn = f"{row}.querySelector('[data-testid=\"copy-reply\"]')"
    c.mouse("mouseMoved", 2, 2)
    out["focus_shows"] = c.js(f"(() => {{ const b = {btn}; if (!b) return null; b.focus(); const o = getComputedStyle(b).opacity; b.blur(); return o; }})()")
    return out


def feed_buttons(c, lv) -> dict:
    row = f"[...document.querySelectorAll('[data-testid=\"prompt-line\"]')].find((l) => l.textContent.includes('COPY-REPLY'))"
    out = _press(c, row, "copy-reply", "feed_reply")
    out.update(_press(c, f"{row}.querySelector('[data-testid=\"reply-code\"]')", "copy-code", "feed_code"))
    return out


def refused(c, lv) -> dict:
    """The browser refuses the clipboard: the button says so and the reply is selected for him."""
    row = row_of("COPY-REPLY")
    btn = f"{row}.querySelector('[data-testid=\"copy-reply\"]')"
    c.js("navigator.clipboard.writeText = () => Promise.reject(new DOMException('refused by the test', 'NotAllowedError')); 1")
    c.js(f"{row}.scrollIntoView({{block: 'center'}}); 1")
    c.click_on(btn)
    out = {"refused_said": c.wait(f"(({btn}).querySelector('[data-on]')?.textContent || '') === 'Select and copy it yourself' && 'refused'", 5),
           "refused_sel": c.js("getSelection().toString()")}
    c.js("delete navigator.clipboard.writeText; navigator.clipboard.__wrapped = false; 1")
    c.js(HOOK)
    out["errors"] = page_errors(c)
    return out


class CopyDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            lv = Live(rig)
            yield ((opened, (c, rig)), (seeded, (c, lv)), (across_rows, (c, lv)), (inside_row, (c, lv)), (live_buttons, (c, lv)),
                   (feed_buttons, (c, lv)), (refused, (c, lv)))


if __name__ == "__main__":
    sys.exit(CopyDriver(sys.argv[1:]).main())
