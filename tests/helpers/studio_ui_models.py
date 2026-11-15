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
4. (3.6.0.0 R5c) the picker's bar holds still while the rows under it change (bar_holds).

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


class ModelsUiDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from tests.helpers.catalog_facts_seed import seed
        state = seeded_home()
        seed(state)  # every provider's cache, the fixture keys in this (the server's) process env
        srv, url = serve(state, True)
        from tests.helpers.studio_full import full
        url = full(url)  # 3.3.2.0 R3: every panel open, the arrangement this driver works in
        try:
            yield ((models, (c, url.replace("mode=orchestra", "mode=agents").replace("feed=off", "feed=off&tour=off&view=crew&agent=coder"),
                             state)),)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(ModelsUiDriver(sys.argv[1:]).main())
