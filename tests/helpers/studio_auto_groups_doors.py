"""tests.helpers.studio_auto_groups_doors -- an ask's door on Auto (Halo 3.6.0.5 b/batch06 entry 3, the owner's point 24), in
headless Chrome over the rig of tests/helpers/studio_doors.py (this harness's real session, tests/helpers/studio_live_rig.py's
agents), the session's row refreshed to Auto (`map: auto`, `map_plain: true`): the tester's row and the reviewer's (the one
that asks) each in a group of its own task, numbered as the engine numbers them (halo_harness/crew/groups.py): after the
real session's own group of main's first reply (n 1), in start order, so the tester's is n 2 and the reviewer's n 3
(r/batch04 entry 4: this rig once wrote n 1 for the tester beside the real n 1). No model is called.

    ask_live     Agents -> 3 · Map, the alert's click on the reviewer's ask: Agents -> 4 · Live shows group 3 selected
                 (`data-selected`) with the card open, its title the asker's who and the ask's choices
    ask_session  Session, its Attention drawer: the same row's O lands on Session's Live drawer, group 3 selected, the card
                 the same

    python -m tests.helpers.studio_auto_groups_doors
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_doors import SESSION, VIEW, alert_click, alert_ready, alerts_on, asked  # noqa: E402

LIVE_GROUP = "document.querySelector('[data-part=live] [data-testid=live-group][data-group=\"3\"]')"
LIVE_CARD = "document.querySelector('[data-part=live] [data-testid=map-step-in]')"
S_GROUP = "document.querySelector('.section-view[data-section=session] [data-testid=session-map-group][data-group=\"3\"]')"
S_CARD = "document.querySelector('.section-view[data-section=session] .mp-down [data-testid=map-step-in]')"


def seen(group: str, card: str) -> str:
    """[selected, the card's target, its title, how many ask keys] once the group is selected and its card is open."""
    return (f"(() => {{ const g = {group}, c = {card}; return !!g && g.hasAttribute('data-selected') && !!c && "
            f"[c.dataset.target, c.querySelector('[data-testid=map-step-in-title]')?.textContent || '', "
            f"c.querySelectorAll('[data-testid=map-step-in-ask-key]').length]; }})()")


def ask_live(c, rig, lv) -> dict:
    c.go(rig.url("agents", "&view=map"))
    c.wait(f"{VIEW} === 'map'", 40)
    n0 = alert_ready(c)
    asked(lv)
    alert_click(c, n0)  # 3.6.0.5 r: the alert's click, the door that stays in Agents
    try:
        return {"ask_live": c.wait(f"{VIEW} === 'live' && {seen(LIVE_GROUP, LIVE_CARD)}", 8)}
    except TimeoutError:
        return {"ask_live": f"not landed: view {c.js(VIEW)}, groups "
                            f"{c.js('[...document.querySelectorAll(`[data-part=live] [data-testid=live-group]`)].map((g) => g.dataset.group)')}"}


def ask_session(c, rig, lv) -> dict:
    c.go(rig.url("session"))
    c.wait(f"!!{SESSION} && !{SESSION}.hidden", 40)
    btn = "document.querySelector('[data-testid=viewbar-btn][data-panel=session-attention]')"
    c.wait(f"!!{btn}", 30)
    c.click_on(btn)
    row = "document.querySelector('[data-panel=session-attention] [data-testid=fleet-attn-row][data-kind=waiting]')"
    c.wait(f"!!{row}", 30)
    c.click_on(f"{row}.querySelector('[data-testid=fleet-attn-key][data-key=o]')")
    try:
        return {"ask_session": c.wait(seen(S_GROUP, S_CARD), 8)}
    except TimeoutError:
        return {"ask_session": f"not landed: groups "
                               f"{c.js('[...document.querySelectorAll(`[data-testid=session-map-group]`)].map((g) => g.dataset.group)')}"}


def _group(lv, aid: str, task: str) -> int:
    """The extra row `aid` in a group of its own `task`, with the number the engine would give it: the next after every
    group of the session so far (the real rows' and this rig's), as crew/groups.py numbers keys in the order it meets them."""
    rows = [*lv.rig.agents(), *lv.rows.values()]
    n = 1 + max([int(((r.get("spawn") or {}).get("group") or {}).get("n") or 0) for r in rows] or [0])
    lv.rows[aid]["spawn"] = {"step": str(n), "description": task, "task": task, "group": {"key": f"task:{task}", "n": n, "by": "task"}}
    return n


class AutoDoorsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            lv = Live(rig)
            ns = (_group(lv, "t7e5s1t0", "run the basket suite"), _group(lv, "r3v1e2w0", "review the basket diff"))
            if ns != (2, 3):  # the selectors name the reviewer's group 3: the real session's own groups changed
                raise RuntimeError(f"the rig's groups got the numbers {ns}, not (2, 3)")
            lv.refresh(map="auto", map_plain=True)
            alerts_on(c)
            try:
                yield tuple((fn, (c, rig, lv)) for fn in (ask_live, ask_session))
            finally:
                lv.close()


if __name__ == "__main__":
    sys.exit(AutoDoorsDriver(sys.argv[1:]).main())
