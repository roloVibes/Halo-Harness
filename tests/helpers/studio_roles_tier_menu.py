"""tests.helpers.studio_roles_tier_menu -- the tier box menu steps of
tests/helpers/studio_roles_tiers.py (Halo 3.1.6.0 R1), kept here so that
file stays small: the box's `...` menu, Model (the ModelSelect bound to
`tiers[i].model`; the card under it shows the tier's model and says so),
Trigger (kind, its one field, the prompt), Max parallel, a second added tier
and the edge labels on that three-tier lineup, Delete (tier 0's is off) and
Ctrl+Z bringing the deleted tier back. Each change is read back from the
lineup file on disk."""
from __future__ import annotations

import json
import time
from pathlib import Path

from tests.helpers.studio_roles import ctrl
from tests.helpers.studio_roles_model import pick
from tests.helpers.studio_roles_tiers import LABELS, card, dblclick, empty_spot, members, on_disk, settle, tier, until  # noqa: F401

MENU = "document.querySelector('[data-testid=\"roles-tier-menu\"]')"
NAME = "studio-media"


def fill(c, expr: str, text: str) -> None:
    """Type `text` into the input `expr` the way React sees a user's typing (an input event)."""
    c.js(f"""(() => {{ const el = {expr}; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      set.call(el, {json.dumps(text)}); el.dispatchEvent(new Event('input', {{bubbles: true}})); return 1; }})()""")


def open_menu(c, name: str, item: str = "") -> None:
    more = f"{tier(name)}.querySelector('[data-testid=\"roles-tier-more\"]')"
    for _ in range(3):  # a box whose head just grew a chip row is still moving: click once it stands still
        settle(c, more)
        c.click_on(more)
        if until(lambda: c.js(f"{MENU}?.dataset.tier === {json.dumps(name)}"), 3):
            break
    c.wait(f"{MENU}?.dataset.tier === {json.dumps(name)}", 5)
    if item:
        c.click_on(f"{MENU}.querySelector('[data-item=\"{item}\"]')")


def tier_on_disk(state: Path, name: str = NAME) -> dict:
    return next((t for t in on_disk(state) if t.get("name") == name), {})


def palette_and_rename(c, url: str, state: Path) -> dict:
    """The palette's "Roles: add tier" opens the bar's name field (Escape closes it); the menu's Rename opens the head's."""
    out: dict = {}
    c.click_on("document.querySelector('.palette-btn')")
    c.wait("document.activeElement?.classList.contains('palette-input')", 10)
    c.type_text("Roles: add tier")
    c.key("Enter")
    out["palette_field"] = c.wait("document.activeElement?.dataset.testid === 'roles-tier-new-name' && 'open'", 10)
    c.key("Escape")
    out["palette_field_closed"] = c.wait("!document.querySelector('[data-testid=\"roles-tier-new-name\"]') && 'closed'", 5)
    open_menu(c, NAME, "rename")
    out["menu_rename"] = c.wait(f"document.activeElement?.dataset.testid === 'roles-tier-rename' && document.activeElement.value", 10)
    c.key("Escape")
    out["menu_rename_kept"] = c.wait(f"!document.querySelector('[data-testid=\"roles-tier-rename\"]') && {tier(NAME)} && 'kept'", 5)
    return out


def menu_model(c, url: str, state: Path) -> dict:
    out: dict = {}
    open_menu(c, NAME)
    out["menu_items"] = c.js(f"[...{MENU}.querySelectorAll('[role=menuitem]')].map((b) => b.dataset.item)")
    c.click_on(f"{MENU}.querySelector('[data-item=\"model\"]')")
    sel = "document.querySelector('[data-testid=\"roles-tier-model-select\"] [data-testid=\"model-select\"]')"
    out["model_first_option"] = c.wait(f"{sel}?.querySelector('option')?.textContent", 10)
    c.wait(f"[...{sel}.querySelectorAll('option')].some((o) => o.value === 'or:qwen/qwen3-coder')", 15)
    pick(c, sel, "or:qwen/qwen3-coder")
    out["model_on_disk"] = until(lambda: tier_on_disk(state).get("model"))
    out["model_pill"] = c.wait(f"{tier(NAME)}.querySelector('[data-testid=\"roles-tier-model\"]')?.textContent", 10)
    pill = f"{card('implementer')}.querySelector('[data-testid=\"roles-model-pill\"]')"
    out["card_pill"] = c.wait(f"{pill}.textContent.includes('qwen3-coder') && [{pill}.textContent, {pill}.title, {pill}.dataset.source]", 10)
    out["menu_closed"] = c.wait(f"!{MENU} && 'closed'", 5)
    return out


def menu_trigger(c, url: str, state: Path) -> dict:
    out: dict = {}
    open_menu(c, NAME, "trigger")
    form = "document.querySelector('[data-testid=\"roles-tier-trigger-form\"]')"
    c.wait(f"!!{form}", 10)
    pick(c, f"{form}.querySelector('[data-testid=\"roles-tier-trigger-kind\"]')", "schedule")
    c.wait(f"!!{form}.querySelector('[data-testid=\"roles-tier-trigger-field\"]')", 5)
    fill(c, f"{form}.querySelector('[data-testid=\"roles-tier-trigger-field\"]')", "30m")
    fill(c, f"{form}.querySelector('[data-testid=\"roles-tier-trigger-prompt\"]')", "Cut the new clips")
    c.click_on(f"{form}.querySelector('[data-testid=\"roles-tier-trigger-form-save\"]')")
    out["trigger_on_disk"] = until(lambda: tier_on_disk(state).get("trigger"))
    out["trigger_chip"] = c.wait(f"{tier(NAME)}.querySelector('[data-testid=\"roles-tier-trigger\"]')?.textContent", 10)
    return out


def menu_max(c, url: str, state: Path) -> dict:
    out: dict = {}
    c.wait(f"!{MENU}", 5)
    open_menu(c, NAME, "max")
    box = "document.querySelector('[data-testid=\"roles-tier-max-input\"]')"
    c.wait(f"!!{box}", 10)
    fill(c, box, "2")
    c.click_on("document.querySelector('[data-testid=\"roles-tier-max-form-save\"]')")
    out["max_on_disk"] = until(lambda: tier_on_disk(state).get("max_parallel"))
    out["max_count"] = c.wait(f"{tier(NAME)}.querySelector('.rc-tier-count').textContent.includes('max 2') && "
                              f"{tier(NAME)}.querySelector('.rc-tier-count').textContent", 10)
    return out


def three_tiers(c, url: str, state: Path) -> dict:
    out: dict = {}
    c.wait(f"!{MENU}", 5)
    c.click_on("document.querySelector('[data-testid=\"roles-tier-add\"]')")
    c.wait("document.activeElement?.dataset.testid === 'roles-tier-new-name'", 10)
    c.type_text("review-tier")
    c.key("Enter")
    until(lambda: "review-tier" in members(state))
    drop = f"{tier('review-tier')}?.querySelector('[data-testid=\"roles-tier-drop\"]')"
    c.wait(f"!!{drop}", 10)
    settle(c, drop)
    x, y, w, h = settle(c, card("reviewer"))
    bx, by, bw, bh = c.rect(drop)
    c.drag(x + w / 2, y + h / 2, bx + bw / 2, by + bh / 2)
    out["three_tiers"] = until(lambda: members(state).get("review-tier") == ["review"] and members(state))
    time.sleep(0.6)
    c.click_on(card("orchestrator"), 0.5, 0.25)
    out["three_selected"] = c.wait(f"{card('orchestrator')}.dataset.selected && {LABELS}", 10)
    empty_spot(c)
    time.sleep(0.4)
    out["three_plain"] = c.js(LABELS)
    out["three_boxes"] = c.js("[...document.querySelectorAll('[data-testid=\"roles-tier\"]')].map((t) => t.dataset.tier)")
    return out


def menu_delete(c, url: str, state: Path) -> dict:
    out: dict = {}
    open_menu(c, "top")
    out["top_delete_disabled"] = c.js(f"{MENU}.querySelector('[data-item=\"delete\"]').disabled")
    c.key("Escape")
    c.wait(f"!{MENU}", 5)
    open_menu(c, "review-tier", "delete")
    out["deleted"] = until(lambda: "review-tier" not in members(state) and members(state))
    out["review_in_rest"] = c.wait(f"!{tier('review-tier')} && !!{tier('rest')} && (() => {{ const r = {card('reviewer')}.getBoundingClientRect(), "
                                   f"b = {tier('rest')}.getBoundingClientRect(); return r.left >= b.left - 1 && r.right <= b.right + 1 && 'rest'; }})()", 10)
    # the save must have settled before the undo: on a slow runner the PUT's answer used to land after Ctrl+Z and
    # put the deleted mapping back (actions.ts save() now keeps a mapping that changed while it was in flight)
    out["saved_settled"] = c.wait("!document.querySelector('[data-testid=\"roles-dirty\"]') && 'settled'", 20)
    empty_spot(c)
    ctrl(c, "z")
    out["undo_back"] = c.wait(f"!!{tier('review-tier')} && !!document.querySelector('[data-testid=\"roles-dirty\"]') && 'back'", 20)
    return out


STEPS = (palette_and_rename, menu_model, menu_trigger, menu_max, three_tiers, menu_delete)
