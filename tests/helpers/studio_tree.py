"""tests.helpers.studio_tree -- the Fleet tree for the Studio drivers (Halo 3.3.2.0 R2). The tree (every
harness, session and agent, the inline answer for a waiting session, the "While you were away" card) left
the expanded rail for the Fleet section's optional Tree panel (`fleet-tree`); a driver brings it up the way
a user does: the Fleet icon in the rail, then the header's "+" menu, then the Tree row. The layout it saves
keeps the panel for the next load of Fleet in that browser."""
from __future__ import annotations

import json

TREE = "document.querySelector('[data-testid=\"fleet-tree-list\"]')"
CUR = "(document.querySelector('[data-testid=section-tab][aria-selected=true]')?.textContent || '')"


def _q(sel: str) -> str:
    return f"document.querySelector({json.dumps(sel)})"


def open_tree(c, timeout: float = 30):
    """The Fleet section with its Tree panel up (added through the "+" menu when it is not); True when it shows."""
    if c.js(f"!!{TREE}"):
        return True
    if not c.js(f"{CUR}.startsWith('Fleet')"):
        c.click_on(_q(".rail [data-testid=section-tab][data-tab-id=fleet]"))
        c.wait(f"{CUR}.startsWith('Fleet')", 15)
    c.wait(f"!!{_q('[data-testid=panels-add]')}", 15)
    c.click_on(_q("[data-testid=panels-add]"))
    row = _q("[data-testid=panels-menu-item][data-panel=fleet-tree]")
    c.wait(f"!!{row}", 10)
    c.click_on(row)
    return c.wait(f"!!{TREE}", timeout)


def node(kind: str, nid: str, harness: str = "") -> str:
    """A tree node by kind (harness, session, agent) and id; `harness` limits it to that harness's block."""
    scope = f"[...document.querySelectorAll('.fr-harness')].find((h) => h.querySelector('[data-kind=harness]')?.dataset.id === '{harness}')" if harness else "document"
    return (f"[...(({scope}) || document).querySelectorAll('[data-testid=\"fleet-tree-node\"]')]"
            f".find((n) => n.dataset.kind === '{kind}' && n.dataset.id === '{nid}')")


def click_node(c, expr: str) -> None:
    """Scroll a tree node into view inside its panel, then click it."""
    c.wait(f"!!({expr})", 20)
    c.js(f"({expr}).scrollIntoView({{block: 'center'}}); 1")
    c.click_on(expr)
