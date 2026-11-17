"""tests.helpers.studio_agents_live -- Agents -> 4 · Live (Halo 3.6.0.2 R52), in headless Chrome as a first-time user,
over tests/helpers/studio_session_rig.py (this harness's real session: main, an implementer and a researcher mid-work)
and tests/helpers/studio_live_rig.py (the session row's `map` and `map_next`, as tests/helpers/studio_map_live.py uses
them). No model is called.

    doors     the old `?mode=agents&view=live` door opens Live (its tab pressed); the four tabs' words; the Live part
              holds the shell (the T-state line, the status line, the frame) in its own workspace `agents-live`; the
              dot on 4 · Live while a session runs, not on 3 · Map; keys C -> Map, L -> Live, 3 -> Map, 4 -> Live; Live
              remembered as the tab used last; the palette's `Agents: 4 · Live` line, its key, Enter lands on Live

    python -m tests.helpers.studio_agents_live
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_agents import key  # noqa: E402

VIEW = "document.querySelector('[data-testid=agents]')?.dataset.view"
P = "[data-part=live]"


def q(sel: str) -> str:
    return f"document.querySelector('{sel}')"


def doors(c, rig, lv) -> dict:
    out: dict = {}
    c.go(rig.url("agents", "&view=live"))
    out["door"] = c.wait(f"{VIEW} === 'live' && {VIEW}", 40)
    tab = q(f"{P} [data-testid=agents-view-live]")
    out["pressed"] = c.wait(f"{tab}?.getAttribute('aria-pressed')", 20)
    out["switch"] = c.js(f"[...document.querySelectorAll('{P} [data-testid=agents-views] button')].map((b) => b.textContent)")
    out["shown"] = c.js(f"!{q(P)}.hidden && !!{q(P + ' [data-testid=agents-live]')}")
    out["workspace"] = c.js(f"{q(P + ' .workspace')}?.dataset.section || ''")
    truth = q(f"{P} [data-testid=live-truth]")
    out["truth"] = c.wait(f"{truth}?.dataset.state === 'T1' && [{truth}.dataset.state, {truth}.textContent]", 30)
    out["status"] = c.js(f"!!{q(P + ' [data-testid=live-status]')}")
    out["frame"] = c.js(f"!!{q(P + ' [data-testid=live-frame]')}")
    lv.refresh(busy=True)
    out["dot"] = c.wait(f"{tab}?.dataset.running === '1' && [{tab}.dataset.running, {tab}.textContent]", 30)
    out["map_dot"] = c.js(f"{q(P + ' [data-testid=agents-view-map]')}?.dataset.running || ''")
    c.js("document.activeElement?.blur(); 1")
    for ch, want in (("c", "map"), ("l", "live"), ("3", "map"), ("4", "live")):
        key(c, ch)
        out[f"key_{ch}"] = c.wait(f"{VIEW} === '{want}' && {VIEW}", 20)
    out["remembered"] = c.js("(() => { try { return localStorage.getItem('halo.studio.agents-view'); } catch { return 'unreadable'; } })()")
    key(c, "3")
    c.wait(f"{VIEW} === 'map'", 20)
    c.click_on(q(".palette-btn"))
    c.wait("document.activeElement?.classList.contains('palette-input')", 10)
    c.type_text("Agents: 4")
    rows = "[...document.querySelectorAll('[data-testid=palette] .palette-item')]"
    out["palette"] = c.wait(f"(() => {{ const r = {rows}.filter((x) => x.querySelector('.palette-label').textContent.startsWith('Agents: 4'));"
                            f" return r.length && r.map((x) => [x.querySelector('.palette-label').textContent,"
                            f" (x.querySelector('kbd')?.textContent || '').trim()]); }})()", 15)
    out["palette_first"] = c.js(f"{rows}[0]?.querySelector('.palette-label').textContent || ''")
    c.key("Enter")
    out["palette_to"] = c.wait(f"!document.querySelector('[data-testid=palette]') && {VIEW}", 15)
    return out


class AgentsLiveDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            lv = Live(rig)
            lv.refresh(map="shop", map_next="shop")
            try:
                yield ((doors, (c, rig, lv)),)
            finally:
                lv.close()


if __name__ == "__main__":
    sys.exit(AgentsLiveDriver(sys.argv[1:]).main())
