"""tests.helpers.model_pick -- pick a model in Studio the way a person does (Halo 3.4.1.3 "Pick, don't type"): click the
field (routes/shared/ModelSelect.tsx, `data-testid=model-select`), wait for the picker's row of that ref (folded in
place or in the dialog), click it. No hidden text box, no value set from the outside.

`field` is a JS expression for the field's root (its `data-testid` the caller's) or the trigger itself.
"""
from __future__ import annotations

import json

DIALOG = "document.querySelector('[data-testid=\"model-select-dialog\"]')"


def trigger(field: str) -> str:
    return f"(({field}).matches('[data-testid=\"model-select\"]') ? ({field}) : ({field}).querySelector('[data-testid=\"model-select\"]'))"


def scope(field: str) -> str:
    """Where the open picker is: the dialog when one is open, else the field (an inline fold)."""
    return f"({DIALOG} || ({field}).closest('.msel') || ({field}))"


def open_picker(c, field: str, timeout: float = 15) -> None:
    t = trigger(field)
    c.js(f"{t}.scrollIntoView({{block: 'center'}}); 1")
    c.js(f"{t}.click(); 1")
    c.wait(f"!!{scope(field)}.querySelector('[data-testid$=\"-search\"]')", timeout)


def rows(c, field: str) -> list:
    return c.js(f"[...{scope(field)}.querySelectorAll('[role=option][data-ref]')].filter((r) => /-row$/.test(r.dataset.testid)).map((r) => r.dataset.ref)") or []


def pick_model(c, field: str, ref: str, timeout: float = 15) -> None:
    """Open the field's picker and click the row of `ref` ("" picks its first row, what the field inherits)."""
    open_picker(c, field, timeout)
    if ref:
        row = f"{scope(field)}.querySelector('[data-testid$=\"-row\"][data-ref={json.dumps(ref)}]')"
    else:
        row = f"{scope(field)}.querySelector('[data-testid$=\"-inherit\"]')"
    c.wait(f"!!{row}", timeout)
    c.js(f"{row}.scrollIntoView({{block: 'nearest'}}); {row}.click(); 1")


def close_picker(c, field: str) -> None:
    """Esc closes it (the picker's own key; the dialog's too)."""
    c.js(f"(() => {{ const s = {scope(field)}.querySelector('[data-testid$=\"-search\"]'); s && s.focus(); return 1; }})()")
    c.key("Escape")
    c.wait(f"!{DIALOG} && !({field}).closest('.msel')?.querySelector('[data-testid=\"model-select-fold\"]')", 10)
