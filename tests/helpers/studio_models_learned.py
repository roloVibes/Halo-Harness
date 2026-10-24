"""tests.helpers.studio_models_learned -- Auto learns, in Studio (Halo 3.1.9.0
R3) in headless Chrome on the driver base, over tests/helpers/
studio_fleet_rig.py with its `team:` cleared (the default `auto` lineup in
use), R1's fixture catalog in every provider's cache
(tests/helpers/catalog_facts_seed.py) and the seeded outcomes fixture
tests/fixtures/outcomes/learn-roster.jsonl (or:v/ears code 1/4 and
or:v/cheap plan 1/3 dropped, or:v/eyes code 4/4, or:v/cheap code 2/2).
tests/test_studio_models_learned.py runs it:

1. a live coder whose model the real pick chose against R2's order (over
   the seeded outcomes.jsonl): its card's pill, on hover, ends with
   "(learned: code 1/4 on or:v/ears, so or:v/eyes instead)"; the Inspector's
   Live tab line and the Session Live spawn line carry the same words;
2. the bio form's picker table (auto-coder's card, "change the bio's
   model", more...): the learned chips per task kind (muted under 3 tasks,
   struck when dropped), the "learned for" select listing the kinds; "code"
   strikes or:v/ears' row and only it, "plan" strikes or:v/cheap's, "any"
   strikes no row.

The last stdout line is a JSON object of what it saw (exit 2: no Chrome).
No model is called."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

STRIP = "document.querySelector('[data-testid=\"roles-model-strip\"]')"
FORM = "document.querySelector('[data-testid=\"bio-form\"][data-bio=\"auto-coder\"]')"
ROWS = f"[...{FORM}.querySelectorAll('[data-testid=\"model-row\"]')]"
KIND = f"{FORM}.querySelector('[data-testid=\"model-learned-kind\"]')"
LINES = "[...document.querySelectorAll('[data-testid=\"session-live-line\"]')]"
COL = "document.querySelector('[data-testid=\"session-live-detail\"]')"
PICK_ROWS = {"or:v/ears": {"kinds": ["code"], "scores": {"code": 0.9}, "facts": {"price_in_per_m": 0.3, "price_out_per_m": 2.5,
                                                                                  "tools": True, "modalities_out": ["text"]}},
             "or:v/eyes": {"kinds": ["code"], "scores": {"code": 0.8}, "facts": {"price_in_per_m": 1.0, "price_out_per_m": 2.0,
                                                                                  "tools": True, "modalities_out": ["text"]}}}


def card(agent: str) -> str:
    return f"document.querySelector('[data-testid=\"roles-card\"][data-agent=\"{agent}\"]')"


def pill(agent: str) -> str:
    return f"{card(agent)}?.querySelector('[data-testid=\"roles-model-pill\"]')"


def _row(aid: str, name: str, bio: str, model: str, why: str, task: str) -> dict:
    return {"agent_id": aid, "parent": "main", "name": name, "role": "coder", "bio": bio, "lineup": "auto", "model": model,
            "model_reason": why, "kind": "member", "task": task, "since": time.time(), "state": "running", "turns": 1,
            "cost_usd": 0.0, "current": "thinking", "last_text": "", "transcript": None}


def _choose(c, value: str) -> None:
    c.js(f"""(() => {{ const s = {KIND}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
      set.call(s, '{value}'); s.dispatchEvent(new Event('change', {{bubbles: true}})); return 1; }})()""")


def _struck(c) -> list:
    return c.js(f"{ROWS}.filter((r) => r.dataset.dropped).map((r) => [r.dataset.ref, "
                "getComputedStyle(r.querySelector('.rm-ref')).textDecorationLine])")


def pick_words(c, rig) -> dict:
    """The live coder's pill, its Live tab line and its spawn line carry what was learned."""
    from halo_harness.models_auto import pick
    from tests.helpers.studio_fleet import card_click
    from tests.helpers.studio_live_rig import Live
    chosen = pick(rig.state, rows=PICK_ROWS, needs=["tools"], band="high", main_ref="or:mock/main", kind="code", role="coder")
    out: dict = {"reason": chosen.reason, "picked": chosen.ref}
    lv = Live(rig, extra=())
    c.go(rig.url("roles"))
    c.wait("!!document.querySelector('[data-testid=\"roles-start\"]') || document.querySelectorAll('[data-testid=\"roles-card\"]').length > 0", 40)
    if c.js("!!document.querySelector('[data-testid=\"roles-start-open-default\"]')"):
        c.click_on("document.querySelector('[data-testid=\"roles-start-open-default\"]')")
    c.wait("document.querySelectorAll('[data-testid=\"roles-card\"]').length >= 8", 30)
    time.sleep(1.2)  # the canvas fits itself after its first draw
    lv.rows["c0d3a001"] = _row("c0d3a001", "coder", "auto-coder", chosen.ref, chosen.reason, "Fix the basket total")
    lv.state("coder")
    out["pill"] = c.wait(f"{pill('auto-coder')}?.dataset.picked && [{pill('auto-coder')}.textContent, {pill('auto-coder')}.title]", 15)
    card_click(c, card("auto-coder"))
    out["live_tab"] = c.wait("document.querySelector('[data-testid=\"roles-live-reason\"]')?.textContent", 15)
    c.go(rig.url("session"))
    c.wait(f"!!{COL} && document.querySelectorAll('[data-testid=\"session-map\"] [data-testid=\"fleet-node\"]').length >= 3", 40)
    time.sleep(1.0)  # the first look at the tree is silent
    lv.rows["c0d3a002"] = _row("c0d3a002", "coder-2", "auto-coder", chosen.ref, chosen.reason, "Fix the tax rounding")
    lv.state("coder-2")  # a second coder (Live finds a row by its name)
    out["spawn_line"] = c.wait(f"{LINES}.filter((l) => l.dataset.kind === 'spawn' && l.textContent.includes('learned'))"
                               ".map((l) => l.textContent).pop()", 15)
    return out


def picker(c, rig) -> dict:
    """The bio form's picker: the learned chips, the "learned for" select, the strikes."""
    from tests.helpers.studio_fleet import card_click
    out: dict = {}
    c.go(rig.url("roles", "&view=workspace&again=1"))
    c.wait(f"!!{card('auto-coder')}", 40)
    time.sleep(1.2)
    card_click(c, card("auto-coder"))
    c.wait(f"{STRIP}?.dataset.card && !{STRIP}.dataset.main", 15)
    c.click_on(f"{STRIP}.querySelector('[data-testid=\"roles-model-bio-link\"]')")
    c.wait(f"!!{FORM}", 15)
    more = f"{FORM}.querySelector('[data-testid=\"bio-model\"] [data-testid=\"model-select-more\"]')"
    c.js(f"{more}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(more)
    out["rows"] = c.wait(f"{ROWS}.length", 15)
    chips = (f"{ROWS}.filter((r) => r.querySelector('[data-testid=\"model-learned\"]')).map((r) => [r.dataset.ref, "
             "[...r.querySelectorAll('[data-testid=\"model-learned\"]')].map((x) => [x.textContent, !!x.dataset.dropped, "
             "!!x.dataset.counted, getComputedStyle(x).textDecorationLine, x.title])])")
    out["chips"] = c.js(chips)
    out["kinds"] = c.js(f"[...{KIND}.options].map((o) => [o.value, o.textContent])")
    out["struck_any"] = _struck(c)
    _choose(c, "code")
    out["struck_code"] = c.wait(f"{ROWS}.some((r) => r.dataset.dropped) && 1", 10) and _struck(c)
    out["code_chips"] = c.js(f"{ROWS}.find((r) => r.dataset.ref === 'or:v/cheap')?.querySelectorAll('[data-testid=\"model-learned\"]').length")
    out["ears_title"] = c.js(f"{ROWS}.find((r) => r.dataset.ref === 'or:v/ears')?.title")
    _choose(c, "plan")
    out["struck_plan"] = c.wait(f"{ROWS}.find((r) => r.dataset.ref === 'or:v/cheap')?.dataset.dropped && 1", 10) and _struck(c)
    _choose(c, "")
    out["struck_none"] = c.wait(f"!{ROWS}.some((r) => r.dataset.dropped) && 1", 10) and _struck(c)
    out["dialogs"] = c.js("document.querySelectorAll('[role=dialog]').length")
    return out


class LearnedDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from halo_harness.theme import unset_config_value
        from tests.helpers.catalog_facts_seed import seed
        from tests.helpers.outcomes_rig import seed_fixture
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        with StudioFleetRig() as rig:
            unset_config_value("team")  # nothing names a lineup: the default auto lineup is in use
            seed(rig.state)  # every provider's cache, the fixture keys in this (the server's) process env
            seed_fixture(rig.state, "learn-roster")
            yield ((pick_words, (c, rig)), (picker, (c, rig)))


if __name__ == "__main__":
    sys.exit(LearnedDriver(sys.argv[1:]).main())
