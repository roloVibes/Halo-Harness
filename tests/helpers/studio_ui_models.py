"""tests.helpers.studio_ui_models -- the "best at" checks of
tests/test_studio_models_ui.py (Halo 3.1.9.0 R1, "what each model is good
at"): real clicks in headless Chrome through the driver base, over a fresh
home with the shipped lineups and a fixture catalog in every provider's
cache (tests/helpers/catalog_facts_seed.py; no network, no model call):

1. the Models panel: Analyze (`POST models/analyze`) shows how many models
   it analyzed and the count per kind, each kind's strongest model;
2. the bio form's picker table (a card, "change the bio's model", more...):
   the "best at" column header, a row's kinds as chips and its one line
   ("vision+pdf in, tools, reasoning; no audio" for or:v/eyes), the full line
   on hover;
3. the "best" sort puts the model good at the most kinds first; a search by
   a line's words ("pdf in") finds the rows that say it.

The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

STRIP = "document.querySelector('[data-testid=\"roles-model-strip\"]')"
FORM = "document.querySelector('[data-testid=\"bio-form\"][data-bio=\"implementer\"]')"
ROWS = f"[...{FORM}.querySelectorAll('[data-testid=\"model-row\"]')]"


def card(agent: str) -> str:
    return f"[...document.querySelectorAll('[data-testid=\"roles-card\"]')].find((n) => n.dataset.agent === '{agent}')"


def models(c, url: str, state: Path) -> dict:
    out: dict = {}
    c.go(url)
    count = "document.querySelector('[data-testid=\"roles-models-count\"]')"
    out["count"] = c.wait(f"+({count}?.textContent || 0) > 0 && +{count}.textContent", 30)
    c.click_on("document.querySelector('[data-testid=\"roles-models-analyze\"]')")
    out["analysis"] = c.wait("document.querySelector('[data-testid=\"roles-models-analysis\"]')?.textContent", 20)
    out["analysis_kinds"] = c.js("[...document.querySelectorAll('[data-testid=\"roles-models-analysis\"] [data-kind]')]"
                                 ".map((n) => n.dataset.kind)")
    # the canvas draws its cards after the Models panel has its catalog: on the Linux runner the card was not there
    # yet when the click came (518f1c7), so wait for it and bring it into view first
    c.wait(f"!!{card('implementer')}", 30)
    c.js(f"{card('implementer')}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(card("implementer"), 0.5, 0.2)
    c.wait(f"{STRIP}?.dataset.card && !{STRIP}.dataset.main", 15)
    c.click_on(f"{STRIP}.querySelector('[data-testid=\"roles-model-bio-link\"]')")
    c.wait(f"!!{FORM}", 15)
    more = f"{FORM}.querySelector('[data-testid=\"bio-model\"] [data-testid=\"model-select-more\"]')"
    c.js(f"{more}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(more)
    out["rows"] = c.wait(f"{ROWS}.length", 15)
    out["head"] = c.js(f"{FORM}.querySelector('.rm-head')?.textContent")
    eyes = f"{ROWS}.find((r) => r.dataset.ref === 'or:v/eyes')"
    out["eyes_kinds"] = c.js(f"[...{eyes}.querySelectorAll('[data-testid=\"model-best-at\"] .og-chip')].map((n) => n.textContent)")
    out["eyes_line"] = c.js(f"{eyes}.querySelector('[data-testid=\"model-best-line\"]')?.textContent")
    out["eyes_title"] = c.js(f"{eyes}.querySelector('[data-testid=\"model-best-at\"]')?.title")
    sort_best = f"{FORM}.querySelector('[data-testid=\"model-sort-best\"]')"
    c.js(f"{sort_best}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(sort_best)
    out["best_first"] = c.wait(f"{FORM}.querySelector('[data-testid=\"model-sort-best\"]').getAttribute('aria-pressed') === 'true' && "
                               f"{ROWS}.slice(0, 3).map((r) => [r.dataset.ref, r.querySelectorAll('.og-chip').length])", 10)
    out["max_chips"] = c.js(f"Math.max(...{ROWS}.map((r) => r.querySelectorAll('.og-chip').length))")
    search = f"{FORM}.querySelector('[data-testid=\"model-search\"]')"
    c.js(f"""(() => {{ const s = {search}; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      set.call(s, 'pdf in'); s.dispatchEvent(new Event('input', {{bubbles: true}})); return 1; }})()""")
    out["pdf_search"] = c.wait(f"{ROWS}.length && {ROWS}.map((r) => r.dataset.ref)", 10)
    out["dialogs"] = c.js("document.querySelectorAll('[role=dialog]').length")
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
        try:
            yield ((models, (c, url.replace("mode=orchestra", "mode=roles").replace("feed=off", "feed=off&tour=off&view=workspace"),
                             state)),)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(ModelsUiDriver(sys.argv[1:]).main())
