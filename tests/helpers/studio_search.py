"""tests.helpers.studio_search -- Studio's Local -> Library search (Halo 3.3.6.0 R2) in headless Chrome: real clicks
through tests/helpers/studio_local.LocalDriver's session (R1's seeded home; `box` a fake Ollama on 127.0.0.1:0 with
its 24 GB card through the panel's READERS seam) with the library's fixture sources. Seeded here: a battery profile
of qwen3.5:9b on box (its tools verified), a crash of qwen3-coder:30b on box (a CUDA illegal memory access after a
load at 65,536), and qwen3:8b pullable on the fake, answering the battery like a full agent
(tests/helpers/mock_ollama_battery.py). No provider request, no model call, nothing pulled but from the fake:

`search`: the strip pinned (box, usable / free VRAM, resident); the Coder preset and its bundle; the window moving
re-reads every row against the strip; the three marks on a row; the cost line; Exclude crashed greys the crashed row
and puts it last; Verifier, then Download and verify on qwen3:8b through its two stages to the role offer, Assign;
Save as role template. The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.studio_local import PAGE, LocalDriver, page  # noqa: E402
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_settings import press, set_field  # noqa: E402

ROWS = "[data-testid=local-library-row]"
GIB = 2 ** 30


def _row(name: str, inner: str = "") -> str:
    return q(f'{ROWS}[data-name="{name}"] {inner}'.strip())


def _seed(ctx) -> None:
    from halo_harness.ollama_steward import resources as R
    from halo_harness.ollama_steward.server_events import record_events
    from halo_harness.providers.ollama import resolve_ollama_host
    from halo_harness.providers.ollama_capability import save_profile
    from halo_harness.studio.ollama_hosts_view import card_of
    from tests.helpers import mock_ollama_battery as MB
    from tests.helpers.search_rig import profile
    R.stop_all()  # the sampler's fake nvidia-smi would count 18 GB "not Ollama" on box
    R.SAMPLER_SEAMS.clear()
    R.STORE.clear()
    save_profile(ctx["state"], profile("qwen3.5:9b", size_gb=6.6, speed={"tok_s": 120.0, "cold_load_s": 8.0, "at_window": 32768}))
    card_of(resolve_ollama_host("box"))
    record_events(ctx["state"], [{"kind": "loaded", "severity": "info", "say": "", "evidence": "", "at": None, "model": "qwen3-coder:30b",
                                  "data": {"size": 20 * GIB, "size_vram": 17 * GIB, "context_length": 65536}}], host="box")
    record_events(ctx["state"], [{"kind": "gpu-memory", "severity": "error", "say": "", "at": None, "model": None, "data": {},
                                  "evidence": "CUDA error: an illegal memory access was encountered"}], host="box")
    mock = ctx["mock"]
    show = {"modelfile": "", "parameters": "", "template": "", "capabilities": ["completion", "tools"],
            "details": MB.row("bt-coder:30b")["details"], "model_info": MB.KINDS["bt-coder:30b"]["info"]}
    mock.pullable = {"qwen3:8b": show}
    mock.scenarios["qwen3:8b"] = MB.scenario("bt-coder:30b")
    mock.version_response = {"version": "0.40.6"}
    mock.pull_delay_s = 0.15  # each stage is on the page long enough to be seen
    mock.load_delay_s["qwen3:8b"] = 0.3


def search(c, url, ctx) -> dict:
    _seed(ctx)
    c.go(f"{ctx['base']}?mode=local&page=library&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'library'", 40)
    page(c, "library")
    c.wait(f"{qa(ROWS)}.length >= 50", 30)
    set_field(c, q("[data-testid=local-library-host]"), "box", "change")
    strip = q("[data-testid=local-resource-strip]")
    out = {"strip": c.wait(f"{strip}?.dataset.host === 'box' && [{strip}.dataset.card, {strip}.textContent]", 20)}
    press(c, q("[data-testid=local-preset][data-preset=coder]"), f"{q('[data-testid=local-preset-bundle]')}?.dataset.preset === 'coder'")
    needs = qa("[data-testid=local-bundle-need]")
    out["bundle"] = c.wait(f"{needs}.length >= 2 && {needs}.map((n) => [n.dataset.cap, n.dataset.floor])", 15)
    out["coder_rows"] = c.wait(f"{qa(ROWS)}.length > 0 && {qa(ROWS)}.every((r) => r.querySelector('[data-cap=coder]')) && {qa(ROWS)}.length", 20)
    out["fit_8k"] = c.js(f"{qa(ROWS)}.map((r) => r.dataset.fit)")
    set_field(c, q("[data-testid=local-library-window]"), "131072", "change")
    out["win_strip"] = c.wait(f"{strip}?.dataset.window === '131072' && {strip}.dataset.window", 20)
    out["fit_128k"] = c.wait(f"{qa(ROWS)}.length > 0 && {qa(ROWS)}.length !== {out['coder_rows']} && {qa(ROWS)}.map((r) => r.dataset.fit)", 20)
    press(c, q("[data-testid=local-preset][data-preset=coder]"), f"!{q('[data-testid=local-preset-bundle]')}")
    set_field(c, q("[data-testid=local-library-window]"), "32768", "change")
    c.click_on(q("[data-testid=local-library-search]"))
    c.type_text("qwen3")
    q9 = _row("qwen3.5:9b")
    c.wait(f"!!{q9} && {qa(ROWS)}.every((r) => r.dataset.name.toLowerCase().includes('qwen3'))", 20)
    out["marks"] = c.js(f"[...{q9}.querySelectorAll('[data-testid=local-library-cap-chip]')].map((x) => [x.dataset.cap, x.dataset.truth, "
                        f"x.querySelector('.ls-glyph').textContent])")
    out["mark_title"] = c.js(f"{_row('qwen3.5:9b', '[data-cap=tools]')}.title")
    out["verdicts"] = c.js(f"{_row('qwen3.5:9b', '[data-testid=local-library-verdicts]')}.textContent")
    out["cost"] = c.js(f"[{_row('qwen3-coder:30b', '[data-testid=local-library-cost]')}.textContent, "
                       f"{_row('qwen3-coder:30b', '[data-testid=local-library-cost]')}.title]")
    out["crash_line"] = c.js(f"{_row('qwen3-coder:30b', '[data-testid=local-library-crashed]')}?.textContent || ''")
    press(c, q("[data-testid=local-library-more] summary"), f"{q('[data-testid=local-library-more]')}.open")
    out["groups"] = c.js(f"{qa('[data-testid=local-filter-group]')}.map((g) => g.dataset.group)")
    press(c, q("[data-testid=local-exclude-crashed]"), f"!!{_row('qwen3-coder:30b')}?.dataset.greyed")
    out["greyed"] = c.js(f"[{_row('qwen3-coder:30b')}.dataset.greyed, {qa(ROWS)}.at(-1).dataset.name]")
    press(c, q("[data-testid=local-exclude-crashed]"), f"!{_row('qwen3-coder:30b')}?.dataset.greyed")
    press(c, q("[data-testid=local-preset][data-preset=verifier]"), f"{q('[data-testid=local-preset-bundle]')}?.dataset.preset === 'verifier'")
    v8 = _row("qwen3:8b", "[data-testid=local-library-verify]")
    c.wait(f"!!{v8}", 20)
    out["verify_title"] = c.js(f"{v8}.title")
    press(c, v8, f"!!{qa('[data-testid=local-verify-row]')}.length")
    stage = q('[data-testid=local-verify-row][data-name="qwen3:8b"]')
    out["first_stage"] = c.wait(f"{stage}?.dataset.stage", 20)
    out["offer"] = c.wait(f"(() => {{ const s = {stage}?.dataset.stage; window.__st = (window.__st || []).concat(s); "
                          f"const o = {_row('qwen3:8b', '[data-testid=local-library-offer]')}; return o && o.textContent; }})()", 90)
    out["stages"] = c.js("[...new Set(window.__st || [])]")
    out["pull_bar"] = c.js(f"{qa('[data-testid=local-verify-stage]')}.map((s) => [s.dataset.step, s.dataset.state])")
    press(c, _row("qwen3:8b", "[data-testid=local-library-assign]"), f"!!{_row('qwen3:8b', '[data-testid=local-library-assigned]')}")
    out["assigned"] = c.js(f"{_row('qwen3:8b', '[data-testid=local-library-assigned]')}.textContent")
    press(c, q("[data-testid=local-save-template]"), f"!!{q('[data-testid=local-save-template-said]')}")
    out["template"] = c.js(f"{q('[data-testid=local-save-template-said]')}.textContent")
    out["pulled"] = list(ctx["mock"].pulled)
    return out


class SearchDriver(LocalDriver):
    @contextmanager
    def session(self, c):
        with super().session(c) as steps:
            yield ((search, steps[0][1]),)


if __name__ == "__main__":
    sys.exit(SearchDriver(sys.argv[1:]).main())
