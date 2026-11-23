"""tests.helpers.studio_ui_models -- the "best at" checks of
tests/test_studio_models_ui.py (Halo 3.1.9.0 R1, "what each model is good
at"): real clicks in headless Chrome through the driver base, over a fresh
home with the shipped lineups and a fixture catalog in every provider's
cache (tests/helpers/catalog_facts_seed.py; no network, no model call):

1. (3.6.0.0 R5: the Models panel's Analyze went with Roles' panels.)
2. an agent's form (Agents -> 1 · Agents, its MODEL picker; the bio form's before):
   3.3.15.0 R2: the "takes" column header, a row's takes as tags, and for the
   focused row its one line ("vision+pdf in, tools, reasoning; no audio" for
   or:v/eyes) and the kinds it is best at on the detail line under the list,
   the line on the tags' hover too;
3. the "best" sort puts the model good at the most kinds first; a search by
   a line's words ("pdf in") finds the rows that say it;
4. (3.6.0.0 R5c) the picker's bar holds still while the rows under it change (bar_holds);
5. (3.6.0.0 R5e) the keyboard walks every row while the pointer rests over the list (resting_pointer), and a row
   focused, Best pressed or a filter typed while the picker's answers are on their way survives them (early).

The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

FORM = "document.querySelector('[data-part=crew] [data-testid=\"crew-form\"]')"
ROWS = "[...document.querySelectorAll('[data-testid=\"model-row\"]')]"
Q = "document.querySelector"


BAR = "[...document.querySelectorAll('[data-testid=\"model-picker\"] .rm-bar input, [data-testid=\"model-picker\"] .rm-bar button')]"
BAR_RECTS = f"{BAR}.map((e) => {{ const r = e.getBoundingClientRect(); return [e.dataset.testid, Math.round(r.left), Math.round(r.top)]; }})"


def bar_holds(c) -> list:
    """3.6.0.0 R5c: the picker's bar (the search, the sorts) stays where it is while the rows under it change: pointing
    at a row of another detail line, and a filter that leaves fewer rows. Centred, the dialog moved with its content and
    Best moved out from under a click on a slow Windows runner. The moves seen ([] when none)."""
    first = c.js(BAR_RECTS)
    moved = []
    rows = f"{ROWS}"
    for i in c.js(f"[0, Math.floor({rows}.length / 2), {rows}.length - 1]"):
        c.js(f"{rows}[{i}]?.focus(); 1")
        time.sleep(0.15)
        now = c.js(BAR_RECTS)
        if now != first:
            moved.append(f"focus row {i}: {first} -> {now}")
    search = f"{Q}('[data-testid=\"model-search\"]')"
    for text in ("eyes", ""):
        c.js(f"""(() => {{ const s = {search}; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
          set.call(s, {text!r}); s.dispatchEvent(new Event('input', {{bubbles: true}})); return 1; }})()""")
        time.sleep(0.15)
        now = c.js(BAR_RECTS)
        if now != first:
            moved.append(f"filter {text!r}: {first} -> {now}")
    return moved


def models(c, url: str, state: Path) -> dict:
    out: dict = {}
    c.go(url)
    c.wait(f"{FORM}?.dataset.name === 'coder'", 30)
    more = f"{FORM}.querySelector('[data-testid=\"crew-model\"] [data-testid=\"model-select\"]')"
    c.js(f"{more}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(more)
    out["rows"] = c.wait(f"{ROWS}.length", 15)
    out["head"] = c.js(f"{Q}('.rm-head')?.textContent")
    eyes = f"{ROWS}.find((r) => r.dataset.ref === 'or:v/eyes')"
    # 3.3.15.0 R2 (owner feedback 2026-11-09): the TAKES column's tags; the line is the detail line under the list
    # for the focused row and the tag group's title; the ranked kinds sit on that line
    out["eyes_kinds"] = c.js(f"[...{eyes}.querySelectorAll('[data-testid=\"model-takes\"] [data-take]')].map((n) => n.dataset.take)")
    c.call("Emulation.setFocusEmulationEnabled", enabled=True)  # focus events fire without window focus
    out["bar_moves"] = bar_holds(c)
    c.js(f"{eyes}.focus(); 1")
    detail = f"{Q}('[data-testid=\"model-detail\"]')"
    out["eyes_line"] = c.wait(f"{detail}?.dataset.ref === 'or:v/eyes' && {detail}.querySelector('[data-testid=\"model-best-line\"]').textContent", 10)
    out["eyes_best"] = c.js(f"{detail}.querySelector('[data-testid=\"model-best-kinds\"]')?.textContent")
    out["eyes_title"] = c.js(f"{eyes}.querySelector('[data-testid=\"model-takes\"]')?.title")
    out["eyes_row_line"] = c.js(f"!!{eyes}.querySelector('[data-testid=\"model-best-line\"]')")
    sort_best = f"{Q}('[data-testid=\"model-sort-best\"]')"
    c.js(f"{sort_best}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(sort_best)
    out["best_first"] = c.wait(f"{Q}('[data-testid=\"model-sort-best\"]').getAttribute('aria-pressed') === 'true' && "
                               f"{ROWS}.slice(0, 3).map((r) => [r.dataset.ref, Number(r.dataset.kinds)])", 10)
    out["max_chips"] = c.js(f"Math.max(...{ROWS}.map((r) => Number(r.dataset.kinds)))")
    search = f"{Q}('[data-testid=\"model-search\"]')"
    c.js(f"""(() => {{ const s = {search}; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      set.call(s, 'pdf in'); s.dispatchEvent(new Event('input', {{bubbles: true}})); return 1; }})()""")
    out["pdf_search"] = c.wait(f"{ROWS}.length && {ROWS}.map((r) => r.dataset.ref)", 10)
    out["dialogs"] = c.js("[...document.querySelectorAll('[role=dialog]')].map((d) => d.dataset.testid)")
    return out


TRIG = f"{FORM}?.querySelector('[data-testid=\"crew-model\"] [data-testid=\"model-select\"]')"
DETAIL = f"{Q}('[data-testid=\"model-detail\"]')"
HOT = f"{Q}('[data-testid=\"model-row\"][data-hot]')"
SEARCH = f"{Q}('[data-testid=\"model-search\"]')"
EYES = f"{ROWS}.find((r) => r.dataset.ref === 'or:v/eyes')"
OPEN = "!!document.querySelector('[data-testid=\"model-select-dialog\"]')"


def resting_pointer(c, url: str, state: Path) -> dict:
    """3.6.0.0 R5e: the pointer rests over the list (where the click that opened the picker left it, or a row pointed at)
    while the keyboard walks the rows. Each Down scrolls the list under the resting pointer; Chrome then reports the row
    now under it as entered (a mouseover with no move), and the row took the highlight: the detail line showed that row
    and Down started again from it, so the keyboard never got past it. A pointer that has not moved takes nothing."""
    out: dict = {}
    c.go("about:blank")
    c.go(url)
    c.wait(f"!!{TRIG}", 30)
    c.click_on(TRIG)
    c.wait(f"{ROWS}.length > 10", 15)
    x, y, w, h = c.rect(f"{ROWS}[2]")
    c.mouse("mouseMoved", x + w / 2, y + h / 2)  # a person points at the third row and leaves the pointer there
    c.wait(f"{DETAIL}?.dataset.ref === {ROWS}[2].dataset.ref", 10)
    c.js(f"{SEARCH}.focus(); 1")
    last = c.js(f"{ROWS}[{ROWS}.length - 1].dataset.ref")
    walked = []
    for _ in range(c.js(f"{ROWS}.length") + 3):  # Down past the end stays on the last row
        c.key("ArrowDown")
        walked.append(c.js(f"new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r({HOT}?.dataset.ref || null))))"))
    out["rest_last"] = last
    out["rest_walked"] = walked
    out["rest_detail"] = c.js(f"{DETAIL}?.dataset.ref")
    # fx studio pass 2: the wheel scrolls the list back up under the resting pointer, off the highlighted last row.
    # Enter picked that row out of sight while the row under the pointer was painted like the highlight.
    px, py = c.pointer
    c.call("Input.dispatchMouseEvent", type="mouseWheel", x=px, y=py, deltaX=0, deltaY=-4000)
    c.js("new Promise((r) => setTimeout(() => requestAnimationFrame(() => r(1)), 700))")
    out["wheel"] = c.js(f"""(() => {{
      const list = {Q}('[data-testid=\"model-select-dialog\"] [role=listbox]'), hot = {HOT}, at = document.elementFromPoint({px}, {py})?.closest('.rm-row');
      const box = list.getBoundingClientRect(), r = hot?.getBoundingClientRect();
      const bg = (e) => e ? getComputedStyle(e).backgroundColor : null;
      return {{scrolled: list.scrollTop, hot: hot?.dataset.ref || null, hot_seen: !!r && r.bottom > box.top && r.top < box.bottom,
               under: at?.dataset.ref || null, under_hot: !!at?.hasAttribute('data-hot'), under_chosen: at?.getAttribute('aria-selected') === 'true',
               under_bg: bg(at), plain_bg: bg({ROWS}.find((e) => !e.hasAttribute('data-hot') && e.getAttribute('aria-selected') !== 'true' && e !== at))}};
    }})()""")
    return out


def _open_picker(c):
    from tests.helpers.hold_still import release_until
    c.click_on(TRIG)
    release_until(c, OPEN)


def _focus_eyes_early(c):
    """The rows' first paint, the measured cards, the providers' state, the best-at kinds and the gym still on their way."""
    from tests.helpers.hold_still import release_until
    _open_picker(c)
    release_until(c, f"!!{EYES}")
    c.js(f"{EYES}.focus(); 1")


def _best_early(c):
    from tests.helpers.hold_still import release_until
    _open_picker(c)
    release_until(c, f"!!{Q}('[data-testid=\"model-sort-best\"]')")
    c.click_on(f"{Q}('[data-testid=\"model-sort-best\"]')")


def _filter_early(c):
    _open_picker(c)
    c.js(f"{SEARCH}.focus(); 1")
    c.type_text("pdf in")  # typed, as a person types, before the catalog has landed


# name: (the choice made as soon as it can be, the expression that holds while it is in effect)
EARLY = {
    "focus": (_focus_eyes_early, f"{OPEN} && {DETAIL}?.dataset.ref === 'or:v/eyes' && {HOT}?.dataset.ref === 'or:v/eyes'"),
    "best": (_best_early, f"{OPEN} && {Q}('[data-testid=\"model-sort-best\"]')?.getAttribute('aria-pressed') === 'true'"),
    "filter": (_filter_early, f"{OPEN} && {SEARCH}?.value === 'pdf in' && !{ROWS}.some((r) => r.dataset.ref === 'or:v/cheap')"),
}


def early(c, url: str, state: Path) -> dict:
    """3.6.0.0 R5e: a choice made in the picker while its answers are on their way (hold_still.survives) is still in
    effect once every answer has landed, oldest first and newest first."""
    from tests.helpers.hold_still import survives
    out: dict = {}
    for name, (choose, holds) in EARLY.items():
        for order in ("oldest", "newest"):
            try:
                out[f"early_{name}/{order}"] = survives(c, url, f"!!{TRIG}", choose, holds, order=order)
            except Exception as e:
                out[f"early_{name}/{order}"] = {"error": f"{type(e).__name__}: {e}"[:300]}
    return out


class ModelsUiDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from tests.helpers.catalog_facts_seed import seed
        state = seeded_home()
        from tests.helpers.his_agent import his_coder
        his_coder(state)  # 3.6.0.15 O2-6: a shipped one's picker is off; this check picks on his coder
        seed(state)  # every provider's cache, the fixture keys in this (the server's) process env
        srv, url = serve(state, True)
        from tests.helpers.studio_full import full
        url = full(url)  # 3.3.2.0 R3: every panel open, the arrangement this driver works in
        try:
            page = url.replace("mode=orchestra", "mode=agents").replace("feed=off", "feed=off&tour=off&view=crew&agent=coder")
            yield ((models, (c, page, state)), (resting_pointer, (c, page, state)), (early, (c, page, state)))
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(ModelsUiDriver(sys.argv[1:]).main())
