"""tests.helpers.studio_roles_model -- the Roles model checks of
tests/test_studio_roles_model.py (Halo 3.1.4.0 R4 "the model is where you
look"), real clicks in headless Chrome through the driver base, over a fresh
home with the shipped lineups (halo-dev-cycle active) and NO provider set up:

1. the Inspector's MODEL strip, nothing selected: the main card's model, the
   select still lists the refs already in use (not verified), and with no live
   list it says why and offers Refresh;
2. Refresh, over two stand-in providers (studio/models_refresh.jobs_for): one
   answers with two fake models, one runs past the 1.5 s box: one outcome line
   each, and the select lists the two models;
3. a card clicked: the strip names what it runs on; a model picked in the strip
   is saved (`GET lineup` reads the card's `models.preference`) and the card's
   pill follows; Test shows the stubbed probe's answer;
4. another card's pill clicked: that card selected, the strip's select focused;
   Enter on a selected card does the same;
5. "change the bio's model": the bio form opens with MODELS first and the
   picker table folded until "more...".

No model is called (`model_probe.probe_model` is stubbed). The last stdout line
is the JSON of what it saw (exit 2: no Chrome)."""
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

PROBE = {"ok": True, "latency_ms": 42, "error": "", "cost_line": "stub", "reply": "ok"}
FAKE = {"fakeco/alpha-1": (0.5, 2.0, 200000), "fakeco/beta-2": (3.0, 15.0, 400000)}
STRIP = "document.querySelector('[data-testid=\"roles-model-strip\"]')"
SEL = f"{STRIP}?.querySelector('[data-testid=\"model-select\"]')"
TOKEN = "{headers: {Authorization: 'Bearer ' + sessionStorage.getItem('halo-studio-token')}}"


def card(agent: str) -> str:
    return f"[...document.querySelectorAll('[data-testid=\"roles-card\"]')].find((n) => n.dataset.agent === '{agent}')"


def stand_ins(state: Path):
    """The two providers Refresh asks here: one answers (two fake models in OpenRouter's cache), one never in time."""
    def answers(state_dir, env):
        from halo_harness.theme import set_config_value
        rows = {k: {"context_length": c, "pricing": {"prompt": f"{i / 1e6:.10f}", "completion": f"{o / 1e6:.10f}"}} for k, (i, o, c) in FAKE.items()}
        (Path(state_dir) / "models.json").write_text(json.dumps(rows), encoding="utf-8")
        set_config_value("providers.openrouter.enabled", True)
        return True, len(rows), ""

    def slow(state_dir, env):
        time.sleep(4)
        return True, 1, ""
    return lambda state_dir, env, local=True: [("FakeRouter", "openrouter", answers), ("Slowpoke", "slowpoke", slow)]


def pick(c, expr: str, ref: str) -> None:
    """Choose `ref` in the <select> `expr` the way a user's choice reaches React (a change event)."""
    c.js(f"""(() => {{ const s = {expr}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
      set.call(s, {json.dumps(ref)}); s.dispatchEvent(new Event('change', {{bubbles: true}})); return 1; }})()""")


def roles(c, url: str, state: Path) -> dict:
    out: dict = {}
    c.go(url)
    out["cards"] = c.wait("document.querySelectorAll('[data-testid=\"roles-card\"]').length", 30)
    out["main_strip"] = c.wait(f"{STRIP}?.dataset.main && {STRIP}.dataset.card", 15)
    out["empty_why"] = c.wait(f"(({STRIP}?.querySelector('[data-testid=\"model-select-why\"]')?.textContent || '').includes('Looked at') && "
                              f"{STRIP}.querySelector('[data-testid=\"model-select-why\"]').textContent)", 15)
    out["looked"] = c.wait("document.querySelector('[data-testid=\"roles-models-why\"]')?.textContent", 15)  # the Models panel: every provider's line
    out["empty_refresh"] = c.js(f"!!{STRIP}.querySelector('[data-testid=\"model-select-refresh\"]')")
    out["empty_options"] = c.wait(f"{SEL}?.querySelectorAll('option').length > 1 && {SEL}.querySelectorAll('option').length", 15)
    out["empty_unverified"] = c.js(f"[...{SEL}.querySelectorAll('option')].some((o) => o.textContent.includes('not verified'))")
    c.click_on(f"{STRIP}.querySelector('[data-testid=\"model-select-refresh\"]')")
    out["outcomes"] = c.wait(f"(() => {{ const l = [...{STRIP}.querySelectorAll('[data-testid=\"model-outcome\"]')]"
                             f".map((e) => e.textContent); return l.length >= 2 && l; }})()", 20)
    out["live_options"] = c.wait(f"[...({SEL}?.querySelectorAll('optgroup') || [])].filter((g) => !g.label.includes('not verified'))"
                                 f".flatMap((g) => [...g.querySelectorAll('option')].map((o) => o.value))", 15)
    out["refreshed"] = c.js(f"{STRIP}.querySelector('[data-testid=\"model-refreshed\"]')?.textContent")
    c.click_on(card("implementer"), 0.5, 0.2)
    impl = c.wait(f"{STRIP}?.dataset.main ? '' : {STRIP}?.dataset.card", 10)
    graph = f"(await (await fetch('/api/lineup/' + document.querySelector('[data-testid=\"roles-canvas\"]').dataset.lineup, {TOKEN})).json())"
    out["runs_on"] = c.js(f"{STRIP}.querySelector('[data-testid=\"roles-model-runs-on\"]').dataset.ref")
    out["graph_model"] = c.js(f"(async () => {graph}.graph.nodes.find((n) => n.id === {json.dumps(impl)}).model)()")
    pick(c, SEL, "or:fakeco/beta-2")
    out["saved_pref"] = c.wait(f"""(async () => {{ const p = {graph}; const n = p.graph.nodes.find((x) => x.agent === 'implementer');
      const e = p.raw.agents[n.index]; return (e.models || {{}}).preference || ''; }})()""", 15)
    out["pill_after"] = c.wait(f"{card('implementer')}.querySelector('[data-testid=\"roles-model-pill\"]').textContent.includes('beta-2') && "
                               f"{card('implementer')}.querySelector('[data-testid=\"roles-model-pill\"]').textContent", 10)
    c.click_on(f"{STRIP}.querySelector('[data-testid=\"model-select-test\"]')")
    out["probe"] = c.wait(f"{STRIP}.querySelector('[data-testid=\"model-select-result\"]')?.textContent", 10)
    pill = f"{card('reviewer')}.querySelector('[data-testid=\"roles-model-pill\"]')"
    out["pill_title"] = c.js(f"{pill}.title")
    c.click_on(pill)
    out["pill_focus"] = c.wait(f"document.activeElement === {SEL} && {STRIP}.dataset.card", 10)
    out["pill_card"] = c.js(f"{card('reviewer')}.dataset.id")
    c.js("document.activeElement.blur(); 1")
    c.click_on(card("implementer"), 0.5, 0.2)
    c.wait(f"{STRIP}.dataset.card === {json.dumps(impl)}", 10)
    c.key("Enter")
    out["enter_focus"] = c.wait(f"document.activeElement === {SEL} && {STRIP}.dataset.card", 10)
    c.click_on(f"{STRIP}.querySelector('[data-testid=\"roles-model-bio-link\"]')")
    form = "document.querySelector('[data-testid=\"bio-form\"][data-bio=\"implementer\"]')"
    c.wait(f"!!{form}", 15)
    out["bio_first_section"] = c.js(f"{form}.querySelector('.rb-sec')?.textContent")
    out["models_before_description"] = c.js(f"""(() => {{ const m = {form}.querySelector('[data-testid="bio-model"]'), d = {form}.querySelector('[data-testid="bio-description"]');
      return !!(m && d && (m.compareDocumentPosition(d) & Node.DOCUMENT_POSITION_FOLLOWING)); }})()""")
    out["bio_focus"] = c.wait(f"!!document.activeElement?.closest('[data-testid=\"bio-model\"]')", 10)
    out["picker_folded"] = c.js(f"{form}.querySelectorAll('[data-testid=\"model-picker\"]').length")
    more = f"{form}.querySelector('[data-testid=\"bio-model\"] [data-testid=\"model-select-more\"]')"
    c.js(f"{more}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(more)
    out["picker_rows"] = c.wait(f"{form}.querySelectorAll('[data-testid=\"model-row\"]').length", 10)
    out["dialogs"] = c.js("document.querySelectorAll('[role=dialog]').length")
    return out


class RolesModelDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        import halo_harness.model_probe as probe
        from halo_harness.studio import models_refresh as MR
        probe.probe_model = lambda ref, **_kw: {**PROBE, "ref": ref}
        state = seeded_home()
        from halo_harness.theme import set_config_value
        # 3.1.4.0: every shipped bio says `default`, so the "in use" fallback (the refs the home itself
        # names) needs refs of its own here: the session model and one role, both unverifiable fakes.
        set_config_value("model", "or:demo/atlas-pro")
        set_config_value("roles.coder", "or:demo/coder-9b")
        MR.BOX_S = 1.5  # this process serves Studio: Refresh boxes each provider at 1.5 s
        MR.jobs_for = stand_ins(state)
        srv, url = serve(state, True)
        from tests.helpers.studio_full import full
        url = full(url)  # 3.3.2.0 R3: every panel open, the arrangement this driver works in
        try:
            yield ((roles, (c, url.replace("mode=orchestra", "mode=roles").replace("feed=off", "feed=off&tour=off&view=workspace"), state)),)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(RolesModelDriver(sys.argv[1:]).main())
