"""tests.helpers.studio_textboxes -- Halo 3.3.15.0 R3 "text boxes fit their text" in headless Chrome on the driver base
(tests/helpers/chrome_driver.Driver), over tests/helpers/prompt_rig.py (a scripted fake session behind the real
Controller, an in-process Studio). tests/test_studio_textboxes.py runs it as a subprocess:

    python -m tests.helpers.studio_textboxes      on Session's Prompt panel (`?prompt=1`), Orchestra's goal form (the
                                                  Start view) and Roles' Lineup tab (`?edit=lineup:halo-dev-cycle`),
                                                  every textarea: its height empty, with four lines, with twenty; its
                                                  line height, padding and borders; whether it scrolls; whether its
                                                  placeholder fits (a mirror at its width: no word wider than the box,
                                                  the number of lines it takes); on the Prompt panel, whether the box
                                                  takes the free height while the feed is short, and with a feed
                                                  taller than the panel is its own size again while the feed scrolls
                                                  then (owner feedback 2026-11-09, the strips) Fleet and Session with
                                                  every panel collapsed: each strip's height, its bar centred, the gaps;
                                                  one panel opened: its title bar and its body's padding
                                                  (tests/helpers/studio_strips.py)
    python -m tests.helpers.studio_textboxes DIR  the same, and a capture of each page into DIR

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called; the boxes' text is put
back as it was (nothing is sent or saved)."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

# one textarea's numbers; `__tb(el)` runs in the page (MEASURE defines it once per page)
MEASURE = r"""
window.__tbSet = (el, v) => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(el, v);
  el.dispatchEvent(new Event('input', {bubbles: true})); };
window.__tbPh = (el) => {
  if (!el.placeholder) return {lines: 0, fits: true};
  const cs = getComputedStyle(el), m = document.createElement('div');
  for (const p of ['fontFamily', 'fontSize', 'fontWeight', 'letterSpacing', 'wordSpacing', 'lineHeight', 'paddingLeft', 'paddingRight'])
    m.style[p] = cs[p];
  Object.assign(m.style, {position: 'absolute', visibility: 'hidden', left: '0', top: '0', boxSizing: 'border-box',
    width: el.clientWidth + 'px', whiteSpace: 'pre-wrap', overflowWrap: 'normal', wordBreak: 'normal'});
  m.textContent = el.placeholder; document.body.appendChild(m);
  const out = {lines: Math.round(m.scrollHeight / parseFloat(cs.lineHeight)), fits: m.scrollWidth <= m.clientWidth, text: el.placeholder};
  m.remove(); return out;
};
window.__tb = async (el) => {
  const cs = getComputedStyle(el), lh = parseFloat(cs.lineHeight), h = () => el.getBoundingClientRect().height;
  const tick = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const was = el.value, lines = (n) => Array.from({length: n}, (_, i) => 'line ' + (i + 1)).join('\n');
  __tbSet(el, ''); await tick();
  const out = {testid: el.dataset.testid || el.getAttribute('aria-label') || el.id, fill: !!el.dataset.fill, lh,
    pad: parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom), border: parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth),
    resize: cs.resize, width: el.clientWidth, h0: h(), ph: __tbPh(el), textbox: el.classList.contains('textbox')};
  __tbSet(el, lines(4)); await tick(); out.h4 = h();
  __tbSet(el, lines(20)); await tick(); out.h20 = h(); out.scrolls = el.scrollHeight > el.clientHeight + 1;
  __tbSet(el, was); await tick();
  return out;
};
1
"""


def boxes(c, scope: str) -> list:
    """Every visible textarea under `scope`, measured."""
    c.js(MEASURE)
    return c.js(f"""(async () => {{ const out = [];
      for (const el of document.querySelectorAll({scope!r})) if (el.offsetParent) {{ el.scrollIntoView({{block: 'center'}}); out.push(await __tb(el)); }}
      return out; }})()""")


def prompt(c, rig) -> dict:
    c.go(rig.url(f"&session={rig.sid}&prompt=1"))
    c.wait(f"document.querySelector('[data-testid=\"prompt-detail\"]')?.dataset.session === {rig.sid!r} && 'ok'", 40)
    c.wait("!!document.querySelector('[data-testid=\"prompt-input\"]')", 10)
    room = c.js("""(() => { const box = document.querySelector('[data-testid="prompt-input"]').getBoundingClientRect(),
        foot = document.querySelector('.spp-foot').getBoundingClientRect(), feed = document.querySelector('.spp-body'),
        panel = document.querySelector('[data-testid="prompt-detail"]').getBoundingClientRect();
      return {box_h: box.height, box_bottom_gap: foot.bottom - box.bottom, panel_h: panel.height,
              feed_h: feed.getBoundingClientRect().height, feed_content: feed.firstElementChild ? feed.firstElementChild.scrollHeight : 0}; })()""")
    shot(c, "prompt-short-feed")
    return {"prompt": boxes(c, "[data-testid=\"prompt-detail\"] textarea"), "prompt_room": room}


def prompt_long(c, rig) -> dict:
    """A turn sent (the fake session replies), then a feed taller than the panel (a 2000 px block put in it): the box
    is its own size again (three lines, grows, twelve at the most) and the feed scrolls."""
    from tests.helpers.studio_prompt import enter, typed
    c.wait("document.querySelector('[data-testid=\"prompt-state\"]')?.textContent === 'idle'", 20)  # a send while busy asks first
    typed(c, "hello from the text box test")
    c.wait("document.querySelector('[data-testid=\"prompt-input\"]').value === 'hello from the text box test'", 10)
    enter(c)
    c.wait("!!document.querySelector('[data-testid=\"prompt-feed\"] [data-testid=\"prompt-turn\"]')", 30)
    c.js("(() => { const d = document.createElement('div'); d.id = '__tb_tall'; d.style.height = '2000px';"
         " document.querySelector('[data-testid=\"prompt-feed\"]').appendChild(d); return 1; })()")
    c.wait("document.querySelector('[data-testid=\"prompt-feed\"]').scrollHeight > 1900", 5)
    got = boxes(c, "[data-testid=\"prompt-detail\"] textarea")
    feed = c.js("(() => { const f = document.querySelector('[data-testid=\"prompt-feed\"]'); return [f.clientHeight, f.scrollHeight]; })()")
    shot(c, "prompt-long-feed")
    c.js("document.getElementById('__tb_tall')?.remove(); 1")
    return {"prompt_long": got, "prompt_long_feed": feed}


SHOTS: list = []


def shot(c, name: str) -> None:
    """With a folder as the driver's argument, a capture of the page into it (the hand-back's pictures)."""
    if SHOTS:  # no device-metrics override (cdp.Chrome.shot's): a resize would fold the Prompt panel back to its strip
        import base64
        data = c.call("Page.captureScreenshot", format="png")["data"]
        (Path(SHOTS[0]) / f"{name}.png").write_bytes(base64.b64decode(data))


def orchestra(c, rig) -> dict:
    from halo_harness.studio.server import url_for
    c.go("about:blank")
    c.go(url_for(rig.server, "orchestra").replace("#t=", "&tour=off&view=start#t="))
    c.wait("document.querySelectorAll('[data-testid=\"orchestra-goal-form\"] textarea').length >= 3", 30)
    shot(c, "orchestra-goal")
    return {"orchestra": boxes(c, "[data-testid=\"orchestra-goal-form\"] textarea")}


def roles(c, rig) -> dict:
    from halo_harness.studio.server import url_for
    c.go("about:blank")
    c.go(url_for(rig.server, edit="lineup:halo-dev-cycle").replace("#t=", "&tour=off#t="))
    c.wait("document.querySelector('[data-testid=\"roles-lineup-tab\"]')?.dataset.lineup === 'halo-dev-cycle' && "
           "document.querySelectorAll('[data-testid=\"roles-lineup-tab\"] textarea').length >= 2", 30)
    # the tab's help block lands after the form (Linux shard 2 on 91f5d090 read it before it was there): wait for its rows
    c.wait("(document.querySelector('[data-testid=\"roles-lineup-help\"]')?.querySelectorAll('dt').length || 0) > 0", 20)
    help_ = c.js("""(() => { const h = document.querySelector('[data-testid="roles-lineup-help"]');
      return {help: !!h, help_lines: h ? h.querySelectorAll('dt').length : 0,
              hints_under_fields: document.querySelectorAll('[data-testid="roles-lineup-tab"] .field-hint').length}; })()""")
    shot(c, "roles-lineup")
    return {"roles": boxes(c, "[data-testid=\"roles-lineup-tab\"] textarea"), "roles_help": help_}


def fleet_strips(c, rig) -> dict:
    """3.3.15.0 R3, owner feedback 2026-11-09 (the strips): Fleet with every panel collapsed, then People opened."""
    from halo_harness.studio.server import url_for
    from tests.helpers.studio_strips import strips
    url = url_for(rig.server, "fleet").replace("#t=", "&tour=off#t=")
    return {"fleet_strips": strips(c, url, "!!document.querySelector('.workspace .ws-cell')", "fleet-people", shot, "fleet")}


def session_strips(c, rig) -> dict:
    """The same on Session, then Cost opened."""
    from tests.helpers.studio_strips import strips
    url = rig.url(f"&session={rig.sid}")
    return {"session_strips": strips(c, url, "!!document.querySelector('.workspace .ws-cell[data-panel=session-cost]')",
                                     "session-cost", shot, "session")}


class TextBoxDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1440, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.prompt_rig import PromptRig
        with PromptRig() as rig:
            SHOTS[:] = self.argv[:1]
            yield ((prompt, (c, rig)), (prompt_long, (c, rig)), (orchestra, (c, rig)), (roles, (c, rig)),
                   (fleet_strips, (c, rig)), (session_strips, (c, rig)))


if __name__ == "__main__":
    sys.exit(TextBoxDriver(sys.argv[1:]).main())
