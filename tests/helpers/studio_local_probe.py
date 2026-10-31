"""tests.helpers.studio_local_probe -- Studio's Local tab, the battery (Halo 3.3.6.0 R1), in headless Chrome: real
clicks through tests/helpers/studio_local.LocalDriver's session (R1's seeded home; `box` a fake Ollama on
127.0.0.1:0 whose qwen3.5:9b answers the probes like a full agent and qwen3-coder:30b like a model with no tool
calling, tests/helpers/mock_ollama_battery.py). No provider request, no model call, nothing sent but to the fake:

`probe`: Models -> a row not probed yet (its mark, its card's blocks all expected), Probe (its title is the cost
line and the `halo models probe` line), the progress strip while it runs (the cost line, a step), then the row read
again: "probed <date> · re-probe", the placement chip verified, the card's four blocks verified; the no-tools model:
"bulk worker · non-agentic" and "not interactive".
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.studio_local import PAGE, LocalDriver, page  # noqa: E402
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_settings import press  # noqa: E402


def _row(model: str, inner: str = "") -> str:
    return q(f'[data-testid=local-model-row][data-host=box][data-model="{model}"] {inner}'.strip())


def _marks(c, model: str) -> list:
    sel = f'[data-testid=local-model-row][data-host=box][data-model="{model}"] [data-testid=model-card-item]'
    return c.js(f"[...new Set({qa(sel)}.map((li) => li.dataset.mark))]")


def _blocks(c, model: str) -> list:
    sel = f'[data-testid=local-model-row][data-host=box][data-model="{model}"] [data-testid=model-card-block]'
    return c.js(f"{qa(sel)}.map((b) => b.dataset.block)")


def probe(c, url, ctx) -> dict:
    from tests.helpers import mock_ollama_battery as MB
    mock = ctx["mock"]
    mock.scenarios["qwen3.5:9b"] = MB.scenario("bt-coder:30b")
    mock.scenarios["qwen3-coder:30b"] = MB.scenario("bt-mute:24b")
    mock.load_delay_s["qwen3.5:9b"] = 0.35  # every probe takes a moment: the strip is seen running
    c.go(f"{ctx['base']}?mode=local&page=models&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'models'", 40)
    page(c, "models")
    c.wait(f"!!{_row('qwen3.5:9b')}", 20)
    out = {"mark_before": c.js(f"{_row('qwen3.5:9b', '[data-testid=local-model-probed]')}.dataset.probed"),
           "marks_before": _marks(c, "qwen3.5:9b"),
           "sits_before": c.js(f"{_row('qwen3.5:9b', '[data-testid=model-card-sits]')}?.dataset.mark || ''")}
    btn = _row("qwen3.5:9b", "[data-testid=local-model-probe]")
    out["title"] = c.js(f"{btn}.title")
    out["label_before"] = c.js(f"{btn}.textContent")
    strip = _row("qwen3.5:9b", "[data-testid=local-probe-strip]")
    press(c, btn, f"!!{strip}")
    out["running"] = c.wait(f"{strip} && !{strip}.dataset.done && {strip}.querySelector('[data-testid=local-probe-cost]') "
                            f"&& {strip}.querySelector('[data-testid=local-probe-step]').textContent.includes('/7 ') "
                            f"&& [{strip}.querySelector('[data-testid=local-probe-cost]').textContent, "
                            f"{strip}.querySelector('[data-testid=local-probe-step]').textContent]", 20)
    out["done"] = c.wait(f"{strip}?.dataset.done && [{strip}.dataset.ok || '', {strip}.querySelector('[data-testid=local-probe-step]').textContent]", 60)
    mark = _row("qwen3.5:9b", "[data-testid=local-model-probed]")
    out["mark_after"] = c.wait(f"{mark}?.dataset.probed === 'yes' && {mark}.textContent", 30)
    chip = _row("qwen3.5:9b", ".lc-model-top [data-testid=model-card-sits] [data-chip]")
    out["chip"] = c.wait(f"{chip} && [{chip}.dataset.chip, {chip}.dataset.mark]", 20)
    out["blocks"] = _blocks(c, "qwen3.5:9b")
    out["marks_after"] = _marks(c, "qwen3.5:9b")
    out["label_after"] = c.js(f"{btn}.textContent")
    out["fit_word"] = c.js(f"{_row('qwen3.5:9b', '.lc-model-top [data-testid=fit-meter] .fit-meter-word')}?.textContent || ''")
    press(c, _row("qwen3-coder:30b", "[data-testid=local-model-probe]"),
          f"{_row('qwen3-coder:30b', '[data-testid=local-model-probed]')}?.dataset.probed === 'yes'")
    chips = _row("qwen3-coder:30b", ".lc-model-top [data-testid=model-card-sits]")
    out["mute_chips"] = c.wait(f"{chips} && {chips}.querySelectorAll('[data-chip]').length >= 2 && "
                               f"[...{chips}.querySelectorAll('[data-chip]')].map((x) => x.dataset.chip)", 20)
    roles = qa('[data-testid=local-model-row][data-host=box][data-model="qwen3-coder:30b"] [data-testid=model-card-roles] [data-role]')
    out["mute_roles"] = c.js(f"{roles}.map((r) => [r.dataset.role, !!r.dataset.ok, r.dataset.mark])")
    return out


class ProbeDriver(LocalDriver):
    @contextmanager
    def session(self, c):
        with super().session(c) as steps:
            yield ((probe, steps[0][1]),)


if __name__ == "__main__":
    sys.exit(ProbeDriver(sys.argv[1:]).main())
