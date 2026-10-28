"""tests.helpers.studio_model_card -- the page checks of
tests/test_studio_model_card.py (Halo 3.3.5.0 R0b): real clicks in headless
Chrome through the driver base over a seeded home (capture_studio's
seeded_home) whose Ollama host `pc` (a placeholder address, never asked) has
the fixture catalog and hardware card in this process's caches
(tests/helpers/model_card_fixtures.py): the picker rows are the real
`row_view` of those (studio/model_card_api.py), no provider request, no
model call:

1. Roles: the bio form's picker rows carry the card's chips and the fit
   meter; the picked row unfolds the card (`model-card`);
2. Setup -> Default model: the rows' chips and meters; the coder picked shows
   its card, the main-model line and the offer; the offer's button writes the
   lineup (active) and sets `model` to the orchestrator;
3. Settings: the `model` row shows the saved model's card (no offer: it can
   orchestrate) and its list rows carry the chips and the meter;
4. Session's Cost header: the effort word is a control; on a thinking local
   model it lists think on / off / default and a pick writes `models.think`.

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
from tests.helpers.studio_packs_steps import CUR, q, qa  # noqa: E402
from tests.helpers.studio_setup_pages import goto  # noqa: E402

LOCAL = ("qwen3-coder:30b", "qwen3.8:27b", "qwen3.5:9b")
SID = "m1cardsession000000000000000001"
FORM = "document.querySelector('[data-testid=\"bio-form\"][data-bio=\"implementer\"]')"
STRIP = "document.querySelector('[data-testid=\"roles-model-strip\"]')"


def rows(state) -> list:
    from halo_harness.providers.effort_on import row_word
    from halo_harness.studio.model_card_api import row_view
    out = []
    for name in LOCAL:
        ref = f"ol:{name}"
        out.append({"ref": ref, "provider": "ollama", "group": "Ollama (pc)", "detail": name, "price": "free", "context": "?",
                    "context_tokens": None, "price_in": 0, "price_out": 0, "chips": "text", "local": True,
                    "best_at": {"line": "", "kinds": []}, "learned": {}, "effort_word": row_word(ref, None),
                    **row_view(ref, None, state)})
    return out


def _levels(sel: str) -> str:
    return f"{qa(sel + ' [data-testid=fit-meter]')}.map((m) => m.dataset.level)"


def roles_picker(c, url, ctx) -> dict:
    card = "[...document.querySelectorAll('[data-testid=\"roles-card\"]')].find((n) => n.dataset.agent === 'implementer')"
    c.go(url)
    c.wait(f"!!{card}", 40)
    c.js(f"{card}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(card, 0.5, 0.2)
    c.wait(f"{STRIP}?.dataset.card && !{STRIP}.dataset.main", 15)
    c.click_on(f"{STRIP}.querySelector('[data-testid=\"roles-model-bio-link\"]')")
    c.wait(f"!!{FORM}", 15)
    more = f"{FORM}.querySelector('[data-testid=\"bio-model\"] [data-testid=\"model-select-more\"]')"
    c.js(f"{more}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(more)
    picker = f"{FORM}.querySelector('[data-testid=\"model-picker\"]')"
    c.wait(f"{picker}?.querySelectorAll('[data-testid=\"model-row\"]').length === {len(LOCAL)}", 20)
    out = {"picker_chips": c.js(f"[...{picker}.querySelectorAll('[data-testid=\"model-row\"]')].map((r) => "
                                "[...r.querySelectorAll('[data-chip]')].map((x) => x.textContent).join(' '))"),
           "picker_levels": c.js(f"[...{picker}.querySelectorAll('[data-testid=\"model-row\"] [data-testid=\"fit-meter\"]')]"
                                 ".map((m) => m.dataset.level)")}
    row = f"{picker}.querySelector('[data-testid=\"model-row\"][data-ref=\"ol:qwen3-coder:30b\"]')"
    c.js(f"{row}.click(); 1")  # the pick folds the table away; opened again, the picked row unfolds its card
    time.sleep(0.4)
    if not c.js(f"!!{picker}"):
        c.js(f"{more}.click(); 1")
    c.wait(f"!!{picker}", 15)
    detail = f"{picker}.querySelector('[data-testid=\"model-card\"][data-ref=\"ol:qwen3-coder:30b\"]')"
    c.wait(f"!!{detail}", 15)
    c.js(f"{detail}.open = true; 1")
    out["picker_detail"] = c.js(f"[...{detail}.querySelectorAll('li')].map((l) => l.textContent)")
    return out


def setup_default(c, url, ctx) -> dict:
    c.go("about:blank")
    c.go(url.replace("mode=roles", "mode=setup"))
    goto(c, "model")
    sel = "[data-testid=setup-model-row]"
    c.wait(f"{qa(sel)}.length === {len(LOCAL)}", 20)
    out = {"setup_chips": c.js(f"{qa(sel)}.map((r) => [...r.querySelectorAll('[data-chip]')].map((x) => x.textContent).join(' '))"),
           "setup_levels": c.js(_levels(sel))}
    pick = q("[data-testid=setup-model-input][data-ref='ol:qwen3-coder:30b']")
    c.js(f"{pick}.click(); 1")
    line = q("[data-testid=model-card-panel][data-ref='ol:qwen3-coder:30b'] [data-testid=model-check-line]")
    out["setup_line"] = c.wait(f"{line}?.textContent", 20)
    btn = q("[data-testid=model-offer-lane]")
    out["setup_offer"] = c.js(f"{btn}?.textContent")
    c.js(f"{btn}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.2)
    c.click_on(btn)
    said = q("[data-testid=model-offer-said]")
    try:
        c.wait(f"!!{said}", 6)
    except TimeoutError:
        c.js(f"{btn}?.click(); 1")
    out["setup_said"] = c.wait(f"{said}?.textContent", 20)
    from halo_harness.theme import get_config_value
    out["team"], out["model"] = get_config_value("team", None), get_config_value("model", None)
    out["coder_role"] = get_config_value("roles.coder", None)
    return out


def settings_row(c, url, ctx) -> dict:
    from tests.helpers.studio_settings import group, row
    c.go("about:blank")
    c.go(url.replace("mode=roles", "mode=settings"))
    c.wait(f"{CUR}.startsWith('Settings') && {qa('[data-testid=settings-row]')}.length > 0", 40)
    group(c, "general")
    panel = row("model", "[data-testid=model-card-panel]")
    out = {"settings_panel": c.wait(f"{panel}?.dataset.ref", 20)}
    time.sleep(0.5)
    out["settings_offer"] = c.js(f"!!{row('model', '[data-testid=model-offer-lane]')}")
    c.js(f"{row('model', '[data-testid=settings-model-open]')}.click(); 1")
    rows_sel = '[data-testid=settings-row][data-key="model"] [data-testid=settings-model-row]'
    c.wait(f"{qa(rows_sel)}.length === {len(LOCAL)}", 20)
    out["settings_levels"] = c.js(_levels(rows_sel))
    out["settings_chips"] = c.js(f"{qa(rows_sel)}.map((r) => r.querySelectorAll('[data-chip]').length)")
    return out


def header_effort(c, url, ctx) -> dict:
    c.go("about:blank")
    c.go(url.replace("mode=roles", f"mode=session&session={SID}"))
    word = q("[data-testid=session-cost-effort]")
    out = {"effort_word": c.wait(f"{word}?.textContent", 40)}
    c.js(f"{word}.click(); 1")
    opts = "[data-testid=session-effort-option]"
    out["effort_options"] = c.wait(f"{qa(opts)}.length === 3 && {qa(opts)}.map((b) => b.dataset.value)", 20)
    c.js(f"{q(opts + '[data-value=off]')}.click(); 1")
    out["effort_after"] = c.wait(f"{word}?.textContent === 'think off' && 'think off'", 20)
    from halo_harness.providers.effort_on import think_choice_for
    out["effort_saved"] = think_choice_for("ol:qwen3.8:27b")
    return out


def _session_rows(_live=None) -> list:
    return [{"session_id": SID, "title": "card check", "cwd": str(REPO), "started": time.time() - 60, "pid": 1,
             "harness": "local", "mode": "tui", "kind": "main", "status": "idle", "busy": False, "pending": None,
             "model": "ol:qwen3.8:27b", "effort": "think default", "cost_usd": 0.0, "cost_complete": True,
             "cost_unknown": [], "remote_attached": 0, "agents_live": 1, "turns": 1, "tokens_in": 10, "tokens_out": 5,
             "context_tokens": 100, "context_limit": 65536,
             "agents": [{"agent_id": "main", "name": "main", "state": "running", "role": "main", "model": "ol:qwen3.8:27b"}]}]


class ModelCardDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.fleet import local_view
        from halo_harness.providers import ollama as O
        from halo_harness.studio import model as M
        from halo_harness.studio import ollama_hosts_view as V
        from halo_harness.theme import set_config_value
        from tests.helpers.model_card_fixtures import ROWS, host_card, write_probes
        state = seeded_home()
        set_config_value("ollama.hosts", [{"name": "pc", "url": "http://192.0.2.10:11434", "default": True}])
        set_config_value("model", "ol:qwen3.8:27b")
        write_probes(state)
        host = O.resolve_ollama_host("pc")
        with O._CATALOG_LOCK:
            O._CATALOG_CACHE[host.url] = (time.monotonic() + 3600, {"models": [dict(ROWS[n]) for n in LOCAL]})
        with V._LOCK:
            V._CACHE[("card", host.url)] = (time.monotonic() + 3600, host_card())
        saved = (M.model_rows, M.catalog_rows, local_view.sessions)
        M.model_rows = lambda *_a, **_k: rows(state)
        M.catalog_rows = lambda *_a, **_k: [{"ref": f"ol:{n}", "local": True} for n in LOCAL]
        local_view.sessions = _session_rows
        local_view.forget()
        srv, url = serve(state, True)
        from tests.helpers.studio_full import full
        url = full(url).replace("mode=orchestra&feed=off", "mode=roles&tour=off&view=workspace&feed=off")
        ctx = {"state": state}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (roles_picker, setup_default, settings_row, header_effort))
        finally:
            M.model_rows, M.catalog_rows, local_view.sessions = saved
            O.reset_catalog_cache()
            V.reset_cache()
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(ModelCardDriver(sys.argv[1:]).main())
