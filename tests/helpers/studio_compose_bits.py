"""tests.helpers.studio_compose_bits -- the small moves the composing drivers share (Halo 3.3.16.3 part 2): where a box
is, a real pointer drag from one box to another point (tests/helpers/cdp.py `drag`: press, eight moves, release), a key
through the DevTools protocol, the confirm card's lines, and the canvas's empty spot to drop on."""
from __future__ import annotations

Q = "document.querySelector"


def sel(testid: str, **attrs) -> str:
    extra = "".join(f'[data-{k}=\\"{v}\\"]' for k, v in attrs.items())
    return f"{Q}('[data-testid=\\\"{testid}\\\"]{extra}')"


def block(ref: str) -> str:
    return sel("block", ref=ref)


def see(c, expr: str) -> None:
    c.wait(f"!!({expr})", 15)
    c.js(f"({expr}).scrollIntoView({{block: 'center', inline: 'center'}}); 1")


def center(c, expr: str, fx: float = 0.5, fy: float = 0.5) -> "tuple[float, float]":
    x, y, w, h = c.rect(expr)
    return x + w * fx, y + h * fy


def drag(c, expr: str, to: "tuple[float, float]", fx: float = 0.5, fy: float = 0.5) -> None:
    """The real pointer: press on `expr`, move in eight steps, release at `to`."""
    x0, y0 = center(c, expr, fx, fy)
    c.drag(x0, y0, to[0], to[1], steps=10)


def empty_spot(c) -> "tuple[float, float]":
    """A point of the Cast canvas no tier, card, block or panel covers (searched on a grid, right to left)."""
    return tuple(c.js("""(() => { const s = document.querySelector('.rc-scroll').getBoundingClientRect();
      for (let fy = 0.92; fy > 0.2; fy -= 0.08) for (let fx = 0.95; fx > 0.3; fx -= 0.05) {
        const x = s.left + s.width * fx, y = s.top + s.height * fy, e = document.elementFromPoint(x, y);
        if (e && (e.classList.contains('rc-world') || e.classList.contains('rc-inner') || e.classList.contains('rc-scroll'))) return [x, y]; }
      return [s.left + s.width * 0.9, s.top + s.height * 0.9]; })()"""))


def press(c, key: str, code: str, vk: int, text: str = "") -> None:
    for kind in ("keyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key=key, code=code, windowsVirtualKeyCode=vk, modifiers=0,
               **({"text": text} if kind == "keyDown" and text else {}))


def confirm_lines(c) -> dict:
    return c.js(f"Object.fromEntries([...{Q}('[data-testid=\"blk-confirm\"]').querySelectorAll('dd')].map((d) => [d.dataset.line, d.textContent]))")


def asked(c, kind: str) -> dict:
    """Wait for the confirm card of `kind`, then its title and lines."""
    c.wait(f"{sel('blk-confirm', kind=kind)} && 'ok'", 15)
    return {"title": c.js(f"{Q}('[data-testid=\"blk-confirm\"] .wf-confirm-title').textContent"), **confirm_lines(c)}


def do_it(c) -> None:
    c.click_on(sel("blk-confirm-do"))
    c.wait(f"!{sel('blk-confirm')}", 20)


def note(c) -> str:
    return c.js(f"{Q}('[data-testid=\"blk-note\"] .blk-note-text')?.textContent || ''")


def undo(c) -> None:
    c.wait(f"!{sel('roles-undo')}.disabled", 10)
    c.click_on(sel("roles-undo"))


def agents_in(ref: str) -> str:
    return f"[...({block(ref)})?.querySelectorAll('[data-testid=\"block-agent\"]') || []].map((a) => a.dataset.bio)"


SPILL = ("[...document.querySelectorAll('.blk-when-label, .blk-note-text, .wf-row-name, .wf-row-does, .lib-kind-title, .blk-foot-off, "
         ".blk-menu-item, .blk-agent-role, .blk-model-name, .blk-name, .blk-purpose')].filter((e) => e.offsetParent && "
         "e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).textOverflow !== 'ellipsis' && getComputedStyle(e).whiteSpace === 'nowrap')"
         ".map((e) => e.className)")


def named(fn):
    """A step whose answer's keys carry its name (`drag_b_card`), so steps never overwrite each other's."""
    import functools

    @functools.wraps(fn)
    def run(*args):
        return {f"{fn.__name__}_{k}": v for k, v in fn(*args).items()}
    return run
