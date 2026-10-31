"""tests.helpers.studio_cards -- Studio's Local -> Models, the measured card, the dialect record and the shelf
(Halo 3.3.6.0 R4), in headless Chrome: real clicks through tests/helpers/studio_local.LocalDriver's session (R1's
seeded home; `box` a fake Ollama on 127.0.0.1:0 with ledger lines for qwen3.5:9b). No provider request, no model call,
nothing sent but to the fake:

`cards`: the Models page; qwen3.5:9b's speed chip from its measured calls; an idle model's shelf hint; the unfolded
card's Measured block and "How Halo talks to this model" with a `from` tag per field; the reply reserve edited where it
stands (blur) -> marked "you" and written to ollama.profiles["box|qwen3.5:9b"]["dialect"]; "back" undoes it; Retire
from the actions menu (the uses card, Retire) -> the delete on the fake and the model on the folded Shelf with
Re-pull. The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.studio_local import PAGE, LocalDriver, config, page  # noqa: E402
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_settings import press, set_field  # noqa: E402


def _row(model: str, inner: str = "") -> str:
    return q(f'[data-testid=local-model-row][data-host=box][data-model="{model}"] {inner}'.strip())


def cards(c, url, ctx) -> dict:
    c.go(f"{ctx['base']}?mode=local&page=models&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'models'", 40)
    page(c, "models")
    c.wait(f"!!{_row('qwen3.5:9b')}", 20)
    out = {"speed": c.wait(f"{_row('qwen3.5:9b', '[data-testid=local-model-speed]')}?.textContent || ''", 20),
           "hints": c.js(f"{qa('[data-testid=local-model-shelf-hint]')}.map((x) => x.textContent)")}
    card = _row("qwen3.5:9b", "[data-testid=model-card]")
    c.js(f"{card}.open = true; 1")
    out["blocks"] = c.wait(f"{card}.querySelectorAll('[data-testid=model-card-block]').length > 1 && "
                           f"[...{card}.querySelectorAll('[data-testid=model-card-block]')].map((b) => b.dataset.block)", 20)
    out["measured"] = c.js(f"[...{card}.querySelectorAll('[data-block=measured] [data-testid=model-card-measured]')].map((x) => x.textContent)")
    field = f"{card}.querySelector('[data-testid=dialect-field][data-field=reply_reserve]')"
    out["fields"] = c.js(f"[...{card}.querySelectorAll('[data-testid=dialect-field]')].map((x) => [x.dataset.field, x.dataset.from])")
    inp = f"{field}.querySelector('input')"
    set_field(c, inp, "4096")
    c.js(f"{inp}.blur(); 1")
    out["edited"] = c.wait(f"{field}?.dataset.from === 'user' && {card}.querySelector('[data-testid=dialect-said]')?.textContent", 20)
    prof = ((config(ctx).get("ollama") or {}).get("profiles") or {}).get("box|qwen3.5:9b") or {}
    out["stored"] = prof.get("dialect")
    press(c, f"{field}.querySelector('[data-testid=dialect-reset]')", f"{field}?.dataset.from !== 'user'")
    out["after_back"] = c.js(f"{field}.dataset.from")
    press(c, _row("nomic-embed-text", "[data-testid=local-model-acts]"), f"!!{q('[data-testid=local-act][data-act=retire]')}")
    press(c, q("[data-testid=local-act][data-act=retire]"), f"!!{q('[data-testid=local-retire]')}")
    go = q("[data-testid=local-retire-go]")
    c.wait(f"!!{go}", 20)
    out["retire_label"] = c.js(f"{go}.textContent")
    press(c, go, f"{q('[data-testid=local-act-said]')}?.dataset.ok === 'true'")
    out["retired_said"] = c.js(f"{q('[data-testid=local-act-said]')}.textContent")
    out["deleted"] = list(ctx["mock"].deleted)
    shelf = q('[data-testid=local-shelf-row][data-model="nomic-embed-text"]')
    out["shelf"] = c.wait(f"!!{shelf} && [{shelf}.dataset.host, !!{shelf}.querySelector('[data-testid=local-shelf-repull]')]", 20)
    out["dialogs_after"] = c.js("document.querySelectorAll('[role=dialog]').length")
    return out


class CardsDriver(LocalDriver):
    @contextmanager
    def session(self, c):
        with super().session(c) as steps:
            yield ((cards, steps[0][1]),)


if __name__ == "__main__":
    sys.exit(CardsDriver(sys.argv[1:]).main())
