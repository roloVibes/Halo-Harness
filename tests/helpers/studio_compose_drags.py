"""tests.helpers.studio_compose_drags -- the four drags, the keys and the density of composing blocks (Halo 3.3.16.3
part 2; tests/helpers/studio_compose.py runs them after its own steps, the library open):

    drag_a   the "thinking" template dragged onto the canvas: its card (WHAT / COSTS / WRITES), Add: a thinking block with
             three agents, wired to main; Undo takes it off (its file goes); Redo puts it back; the research workflow
             dragged onto the canvas: its card, Add: its block
    drag_b   the auto-writer bio dragged into the shipped media block: the card says media is copied to yours first; Add:
             my-media in its place with auto-writer inside
    drag_c   auto-writer dragged out of my-media onto the empty canvas: its card, Take it out: one agent left; Undo puts it
             back; Undo again puts the shipped media back
    drag_d   the media block dragged by its title bar: it moves and the lineup's layout keeps `block:media`; Undo puts it back
    keys     a thinking agent focused, M: the move's hint; an arrow picks another block; Enter raises its card; Cancel
    dense    the block menu (its items by keyboard), no text spilling but by ellipsis on any new box, the When page's rows
    shots    the composed board (--shots DIR): composed.png
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from tests.helpers.studio_compose_bits import Q, SPILL, named, agents_in, asked, block, do_it, drag, empty_spot, note, press, see, sel, undo


def drag_a(c, page) -> dict:
    see(c, sel("lib-template", name="thinking"))
    drag(c, sel("lib-template", name="thinking"), empty_spot(c))
    out = {"card": asked(c, "template")}
    do_it(c)
    out["block"] = c.wait(f"{agents_in('thinking')}.length === 3 && !!{sel('block-edge', to='thinking')} && {agents_in('thinking')}", 20)
    out["note"] = note(c)
    c.click_on(sel("roles-undo"))
    out["undone"] = c.wait(f"!{block('thinking')} && 'gone'", 20)
    c.click_on(sel("roles-redo"))
    out["redone"] = c.wait(f"{agents_in('thinking')}.length === 3 && 'back'", 20)
    see(c, sel("wf-row", ref="research"))
    drag(c, sel("wf-row", ref="research"), empty_spot(c))
    out["wf_card"] = asked(c, "workflow")
    do_it(c)
    out["research"] = c.wait(f"!!{block('research')} && !!{sel('block-edge', to='research')} && 'on'", 20)
    return out


def drag_b(c, page) -> dict:
    see(c, block("media"))
    x, y, w, h = c.rect(block("media"))
    see(c, sel("lib-bio", bio="auto-writer"))
    x, y, w, h = c.rect(block("media"))
    drag(c, sel("lib-bio", bio="auto-writer"), (x + w * 0.5, y + h * 0.7))
    out = {"card": asked(c, "join")}
    do_it(c)
    out["copy"] = c.wait(f"!{block('media')} && {agents_in('my-media')}.includes('auto-writer') && {agents_in('my-media')}", 20)
    out["note"] = note(c)
    return out


def drag_c(c, page) -> dict:
    agent = f"{block('my-media')}.querySelector('[data-testid=\"block-agent\"][data-bio=\"auto-writer\"]')"
    see(c, agent)
    drag(c, agent, empty_spot(c))
    out = {"card": asked(c, "leave")}
    do_it(c)
    out["left"] = c.wait(f"{agents_in('my-media')}.length === 1 && {agents_in('my-media')}", 20)
    out["note"] = note(c)
    c.click_on(sel("roles-undo"))
    out["back"] = c.wait(f"{agents_in('my-media')}.length === 2 && {agents_in('my-media')}", 20)
    c.click_on(sel("roles-undo"))
    out["shipped_back"] = c.wait(f"!!{block('media')} && !{block('my-media')} && 'media'", 20)
    return out


def drag_d(c, page, state: Path) -> dict:
    see(c, block("media"))
    top0 = c.js(f"{block('media')}.offsetTop")
    head = f"{block('media')}.querySelector('[data-testid=\"block-name\"]')"
    x, y = c.rect(head)[0] + 10, c.rect(head)[1] + 6
    c.drag(x, y, x + 40, y + 260, steps=10)
    out = {"moved": c.wait(f"{block('media')}.offsetTop > {top0} + 100 && {block('media')}.offsetTop - {top0}", 10)}
    layout = state / "studio" / "layouts" / "auto.json"
    for _ in range(40):
        if layout.is_file() and "block:media" in layout.read_text(encoding="utf-8"):
            break
        time.sleep(0.2)
    out["saved"] = json.loads(layout.read_text(encoding="utf-8"))["nodes"].get("block:media") if layout.is_file() else None
    out["note"] = note(c)
    c.click_on(sel("roles-undo"))
    out["undone"] = c.wait(f"Math.abs({block('media')}.offsetTop - {top0}) < 2 && 'home'", 10)
    return out


def keys(c, page) -> dict:
    agent = f"{block('thinking')}.querySelector('[data-testid=\"block-agent\"]')"
    see(c, agent)
    c.js(f"{agent}.focus(); 1")
    press(c, "m", "KeyM", 77, "m")
    out = {"hint": c.wait(f"{Q}('[data-testid=\"blk-move-target\"]')?.textContent", 10)}
    press(c, "ArrowRight", "ArrowRight", 39)
    out["next"] = c.wait(f"{Q}('[data-testid=\"blk-move-target\"]').textContent !== {json.dumps(out['hint'])} && {Q}('[data-testid=\"blk-move-target\"]').textContent", 10)
    for _ in range(8):  # to a square block: its card (a tier's move needs no card)
        if "(square)" in c.js(f"{Q}('[data-testid=\"blk-move-target\"]').textContent"):
            break
        press(c, "ArrowRight", "ArrowRight", 39)
    press(c, "Enter", "Enter", 13)
    out["card"] = asked(c, "join")
    c.click_on(sel("blk-confirm-cancel"))
    c.wait(f"!{sel('blk-confirm')}", 10)
    c.js(f"{agent}.focus(); 1")
    press(c, "m", "KeyM", 77, "m")
    c.wait(f"!!{sel('blk-move')}", 10)
    press(c, "Escape", "Escape", 27)
    out["stopped"] = c.wait(f"!{sel('blk-move')} && 'stopped'", 10)
    return out


def dense(c, page) -> dict:
    out = {"spill": c.js(SPILL)}
    see(c, block("plan"))
    c.click_on(f"{block('plan')}.querySelector('[data-testid=\"block-more\"]')")
    out["menu"] = c.wait(f"{sel('block-menu')} && [...{sel('block-menu')}.querySelectorAll('button')].map((b) => b.dataset.testid)", 10)
    out["menu_focus"] = c.js("document.activeElement?.dataset.testid || ''")
    out["menu_spill"] = c.js(SPILL)
    press(c, "Escape", "Escape", 27)
    c.wait(f"!{sel('block-menu')}", 10)
    see(c, sel("block-when", to="plan"))
    c.click_on(sel("block-when", to="plan"))
    c.wait(f"!!{sel('wf-page-when')}", 10)
    out["rows"] = c.js("[...document.querySelectorAll('.blk-when-pick, .blk-when-need')].map((r) => Math.round(r.getBoundingClientRect().height))")
    out["page_spill"] = c.js("[...document.querySelectorAll('[data-testid=\"wf-page-when\"] *')].filter((e) => e.children.length === 0 && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible' && getComputedStyle(e).textOverflow !== 'ellipsis').length")
    c.click_on(sel("wf-page-back"))
    return out


def shots(c, page, folder: str) -> dict:
    if not folder:
        return {}
    Path(folder).mkdir(parents=True, exist_ok=True)
    c.js("document.activeElement?.blur(); 1")
    c.shot(str(Path(folder) / "composed.png"), 1800, 1100, 1)
    return {"shots": folder}


def steps(c, page, state: Path, folder: str) -> tuple:
    return ((named(drag_a), (c, page)), (named(drag_b), (c, page)), (named(drag_c), (c, page)), (named(drag_d), (c, page, state)),
            (named(keys), (c, page)), (named(dense), (c, page)), (shots, (c, page, folder)))
