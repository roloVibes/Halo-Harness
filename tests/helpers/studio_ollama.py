"""tests.helpers.studio_ollama -- Fleet's Ollama panel, Settings -> Ollama and Setup's steward line (Halo 3.3.4.0 R5),
real clicks in headless Chrome through the driver base, over a scratch home (capture_studio's seeded_home) with the
steward fixture of tests/helpers/ollama_panel_seed.py (two hosts, a local server, the ledger, an event, a note,
review mode; the cards and the catalog through studio/ollama_hosts_view.READERS); no provider request, no model call:

1. the quiet Fleet: nothing opens, the panel is not in the layout; the "+" menu's Ollama row adds it;
2. `open=all`: the steward's attention row, O opens the panel;
3. the host picker (pc, samus, the local server); the model rows' numbers, the eye, the VRAM share;
4. the timeline draws (a bucket a minute, the hour's calls, a trim and a cut marked);
5. a finding's Apply (config.json's ollama.profiles has it, the row says applied); Dismiss (gone, and still gone
   after a reload); Copy on the KV hint (the exact env line);
6. Settings -> Ollama: the block's model picker writes ollama.steward.model, its mode writes apply;
7. Setup -> Providers: the Ollama card's steward line and its link to the panel.
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
from tests.helpers.studio_header_menus import close_menus, plus, plus_rows  # noqa: E402
from tests.helpers.studio_packs_steps import CUR, q, qa  # noqa: E402
from tests.helpers.studio_settings import press, set_field  # noqa: E402

DETAIL = q("[data-testid=fleet-ollama-detail]")
HOST = f"({DETAIL}?.dataset.host || '')"
ROWS = qa("[data-testid=fleet-ollama-detail] [data-testid=ollama-model-row]")
FIND = "[data-testid=fleet-ollama-detail] [data-testid=ollama-finding]"
NUMS = ".map((r) => [r.dataset.model, +r.dataset.calls, +r.dataset.trims, +r.dataset.cuts, +r.dataset.errors])"


def finding(rule: str, inner: str = "") -> str:
    return q(f'{FIND}[data-rule="{rule}"] {inner}'.strip())


def by_id(fid: str, inner: str = "") -> str:
    return q(f'{FIND}[data-id="{fid}"] {inner}'.strip())


def config(ctx) -> dict:
    return json.loads((ctx["state"] / "config.json").read_text(encoding="utf-8"))


def load(c, ctx, query: str, done: str) -> None:
    c.go("about:blank")  # the same address again would be a fragment hop, not a load
    c.go(f"{ctx['base']}?{query}&tour=off&feed=off#{ctx['frag']}")
    c.wait(done, 40)


def quiet_plus(c, url, ctx) -> dict:
    load(c, ctx, "mode=fleet&view=workspace", f"{CUR}.startsWith('Fleet') && !!{q('[data-section=fleet] [data-panel]')}")
    time.sleep(1.5)
    out = {"quiet_open": c.js("[!!document.querySelector('[data-testid=section-help]'), document.querySelectorAll('[role=dialog]').length]"),
           "quiet_has_panel": c.js(f"!!{q('[data-panel=fleet-ollama]')}")}
    rows = {r[0]: r[1] for r in plus_rows(c)}
    out["plus_word"] = rows.get("fleet-ollama")
    close_menus(c)
    plus(c, "fleet-ollama")
    out["plus_opened"] = c.wait(f"!!{DETAIL} && {HOST}", 30)
    c.js("localStorage.removeItem('halo.studio.layout.fleet'); 1")  # the next load starts without it again
    return out


def attention(c, url, ctx) -> dict:
    load(c, ctx, "mode=fleet&view=workspace&open=all", f"!!{q('[data-panel=fleet-attention]')}")
    row = q("[data-testid=fleet-attn-row][data-kind=ollama_steward]")
    out = {"attn_row": c.wait(f"!!{row} && {row}.querySelector('.fat-what').textContent", 40),
           "attn_before": c.js(f"!!{DETAIL}")}
    c.js(f"{row}.scrollIntoView({{block: 'center'}}); 1")
    c.click_on(f"{row}.querySelector('.fat-what')")  # the row selected, then its one key (Attention's J / K / A / O)
    c.wait(f"{row}?.getAttribute('aria-selected') === 'true'", 10)
    c.key("o")
    out["attn_opened"] = c.wait(f"!!{DETAIL} && {HOST}", 30)
    return out


def hosts(c, url, ctx) -> dict:
    pick = q("[data-testid=ollama-host]")
    out = {"hosts": c.wait(f"!!{pick} && [...{pick}.options].map((o) => o.value)", 20)}
    set_field(c, pick, "samus", "change")
    out["samus_rows"] = c.wait(f"{HOST} === 'samus' && {ROWS}.length && {ROWS}{NUMS}", 15)
    set_field(c, pick, "llama-box", "change")
    out["local_rows"] = c.wait(f"{HOST} === 'llama-box' && {ROWS}.length && {ROWS}{NUMS}", 15)
    out["local_label"] = c.js(f"!!{q('[data-testid=fleet-ollama-detail] .oll-next')}")
    set_field(c, pick, "pc", "change")
    out["pc_rows"] = c.wait(f"{HOST} === 'pc' && {ROWS}.length === 2 && {ROWS}{NUMS}", 15)
    out["eye"] = c.js(f"{ROWS}.map((r) => [r.dataset.model, !!r.querySelector('[data-testid=ollama-vision]')])")
    out["vram"] = c.js(f"{ROWS}.map((r) => r.querySelector('[data-testid=ollama-vram]')?.textContent || '')")
    out["card"] = c.js(f"{q('[data-testid=ollama-card]')}.textContent")
    return out


def timeline(c, url, ctx) -> dict:
    svg = q("[data-testid=fleet-ollama-detail] [data-testid=ollama-timeline]")
    out = {"tl": c.wait(f"!!{svg} && [+{svg}.dataset.buckets, +{svg}.dataset.calls]", 20)}
    out["tl_marks"] = c.js(qa("[data-testid=fleet-ollama-detail] [data-testid=ollama-mark]") + ".map((m) => m.dataset.kind).sort()")
    out["tl_line"] = c.js(f"({svg}.querySelector('polyline')?.getAttribute('points') || '').split(' ').length")
    return out


def apply_dismiss(c, url, ctx) -> dict:
    out = {"review_apply": c.wait(f"!!{finding('window-small', '[data-testid=ollama-apply]')}", 20)}
    fid = c.js(f"{finding('window-small')}.dataset.id")
    applied = q(f'{FIND}[data-applied][data-id="{fid}"]')
    press(c, finding("window-small", "[data-testid=ollama-apply]"), f"!!{applied}")
    out["applied_row"] = c.wait(f"{by_id(fid, '[data-testid=ollama-applied]')}?.textContent", 15)
    out["applied_config"] = ((config(ctx).get("ollama") or {}).get("profiles") or {}).get("pc|qwen3.8:27b")
    out["profile_cell"] = c.wait(f"{ROWS}.find((r) => r.dataset.model === 'qwen3.8:27b')?.querySelector('[data-testid=ollama-profile]')?.textContent", 15)
    cut = c.js(f"{finding('reply-cut')}?.dataset.id")
    press(c, finding("reply-cut", "[data-testid=ollama-dismiss]"), f"!{by_id(cut)}")
    out["dismissed"] = cut
    out["dismiss_gone"] = c.js(f"!{by_id(cut)}")
    load(c, ctx, "mode=fleet&view=workspace&open=all", f"!!{DETAIL} && {qa(FIND)}.length > 0")
    out["dismiss_after_reload"] = c.js(f"!{by_id(cut)}")
    return out


def copy(c, url, ctx) -> dict:
    kv = q("[data-testid=fleet-ollama-detail] [data-testid=ollama-option][data-kind=kv-q8_0]")
    c.wait(f"!!{kv}", 20)
    out = {"hint_line": c.js(f"{kv}.querySelector('[data-testid=ollama-hint-line]').textContent")}
    press(c, f"{kv}.querySelector('[data-testid=ollama-copy-hint]')", f"!!{kv}.querySelector('[data-copied]')")
    out["copied"] = c.js(f"{kv}.querySelector('[data-testid=ollama-copy-hint]').dataset.copied")
    out["plan_chosen"] = c.js(q("[data-testid=ollama-option][data-chosen]") + "?.dataset.kind")
    return out


def settings(c, url, ctx) -> dict:
    load(c, ctx, "mode=settings&group=ollama", f"!!{q('[data-testid=settings-ollama-block]')}")
    block = "[data-testid=settings-ollama-block]"
    out = {"settings_status": c.wait(f"{q(block + ' [data-testid=settings-ollama-status]')}.textContent.includes('steward job') && "
                                     f"{q(block + ' [data-testid=settings-ollama-status]')}.textContent", 20),
           "settings_first": c.js(f"{q('[data-testid=settings-group-page] .st-rows')}.firstElementChild.dataset.testid"),
           "settings_models": c.js(f"[...{q('[data-testid=settings-ollama-model]')}.options].map((o) => o.value)")}
    set_field(c, q("[data-testid=settings-ollama-model]"), "none", "change")
    for _ in range(50):
        if ((config(ctx).get("ollama") or {}).get("steward") or {}).get("model") == "none":
            break
        time.sleep(0.2)
    out["model_config"] = ((config(ctx).get("ollama") or {}).get("steward") or {}).get("model")
    set_field(c, q("[data-testid=settings-ollama-mode]"), "auto", "change")
    for _ in range(50):
        if ((config(ctx).get("ollama") or {}).get("steward") or {}).get("apply") == "auto":
            break
        time.sleep(0.2)
    out["mode_config"] = ((config(ctx).get("ollama") or {}).get("steward") or {}).get("apply")
    out["model_says"] = c.wait(f"{q(block + ' [data-testid=settings-ollama-status]')}.textContent.includes('none') && "
                               f"{q(block + ' [data-testid=settings-ollama-status]')}.textContent", 20)
    press(c, q("[data-testid=settings-ollama-open]"), f"!!{DETAIL}")
    out["settings_open"] = c.wait(f"{CUR}.startsWith('Fleet') && !!{DETAIL}", 20)
    return out


def setup(c, url, ctx) -> dict:
    load(c, ctx, "mode=setup&block=providers", f"!!{q('[data-testid=setup-steward-text]')}")
    text = q("[data-testid=setup-steward-text]")
    out = {"setup_line": c.wait(f"!{text}.textContent.endsWith('reading...') && {text}.textContent", 20)}
    press(c, q("[data-testid=setup-steward-open]"), f"!!{DETAIL}")
    out["setup_open"] = c.wait(f"{CUR}.startsWith('Fleet') && !!{DETAIL}", 20)
    return out


class OllamaDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.studio import ollama_hosts_view as V
        from tests.helpers import ollama_panel_seed as S
        state = seeded_home()
        S.seed(state)
        V.reset_cache()
        V.READERS.update(S.readers())
        srv, url = serve(state, True)
        base, frag = url.split("?", 1)[0], url.split("#", 1)[1]
        ctx = {"state": state, "srv": srv, "base": base, "frag": frag}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (quiet_plus, attention, hosts, timeline, apply_dismiss, copy, settings, setup))
        finally:
            V.READERS.clear()
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(OllamaDriver(sys.argv[1:]).main())
