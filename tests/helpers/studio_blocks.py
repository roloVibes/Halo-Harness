"""tests.helpers.studio_blocks -- blocks on one canvas (Halo 3.3.16.3, the owner: "different blocks that you can almost
like drag and drop in the agents tab ... here is the media workflow ... here's my thinking block") in headless Chrome on
the driver base over a scratch home: the auto lineup (its tiers name their purpose), `workflows.enabled` = the shipped
`media` square and `my-media`, a copy of it in yours whose lineup has three agents. tests/test_studio_blocks.py runs it:

    python -m tests.helpers.studio_blocks blocks [--shots DIR]
        Cast draws the tiers (each with its purpose line) and the two squares as blocks with main's line into each,
        nothing open on load; my-media open shows its three agents (role, model, takes) and its footer; no block
        overlaps a tier box or another block, no text spills; the chevron folds it to its lines and a reload keeps it
        folded; a click on the block opens its summary in the inspector (Purpose, Agents, ... each its own page); the
        Purpose page saves into yours and the block's line says it; a click on the canvas clears it

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_agents import open_page  # noqa: E402
from tests.helpers.studio_hover_read import none_for  # noqa: E402

Q = "document.querySelector"
BLOCKS = "[...document.querySelectorAll('[data-testid=\"block\"]')]"
NEW_DOES = "Reads the scans and hands back the numbers."


def block(ref: str) -> str:
    return f"{Q}('[data-testid=\"block\"][data-ref=\"{ref}\"]')"


READ = """(() => {
  const r = (e) => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
  const hit = (a, b) => a[0] < b[2] - 0.5 && b[0] < a[2] - 0.5 && a[1] < b[3] - 0.5 && b[1] < a[3] - 0.5;
  const blocks = [...document.querySelectorAll('[data-testid="block"]')], tiers = [...document.querySelectorAll('[data-testid="roles-tier"]')];
  let overlap = 0;
  blocks.forEach((b, i) => { tiers.forEach((t) => hit(r(b), r(t)) && overlap++); blocks.slice(i + 1).forEach((o) => hit(r(b), r(o)) && overlap++); });
  const spill = [...document.querySelectorAll('.blk-name, .blk-purpose, .blk-agent-role, .blk-model-name, .blk-foot > span, .blk-lines dd')]
    .filter((e) => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).textOverflow !== 'ellipsis').length;
  const inside = blocks.every((b) => [...b.querySelectorAll('.blk-agent')].every((a) => { const x = r(a), y = r(b); return x[3] <= y[3] + 0.5; }));
  return {blocks: blocks.map((b) => [b.dataset.ref, b.dataset.open === 'true', b.querySelectorAll('[data-testid="block-agent"]').length]),
          edges: [...document.querySelectorAll('[data-testid="block-edge"]')].map((e) => e.dataset.to),
          tiers: tiers.map((t) => [t.dataset.tier, t.querySelector('[data-testid="roles-tier-purpose"]')?.textContent || '']),
          overlap, spill, inside};
})()"""


def go(c, page) -> None:
    """Cast on the auto lineup: a fresh home opens on the Start view, its "Open auto" opens the lineup (the browser keeps it)."""
    open_page(c, page, "mode=agents&view=cast")
    btn = f"{Q}('[data-testid=\"roles-start-open-default\"]')"
    c.wait(f"!!{btn} || document.querySelectorAll('[data-testid=\"roles-card\"]').length > 0", 40)
    if c.js(f"!!{btn}"):
        c.click_on(btn)


def cast(c, page) -> dict:
    go(c, page)
    c.wait(f"document.querySelectorAll('[data-testid=\"roles-card\"]').length > 0 && {BLOCKS}.length === 2", 40)
    out = {"quiet": none_for(c, 1.0), "insp_block": c.js(f"{Q}('[data-testid=\"roles-inspector-body\"]')?.dataset.block || ''")}
    out.update(c.js(READ))
    mine = block("my-media")
    out["agents"] = c.js(f"[...{mine}.querySelectorAll('[data-testid=\"block-agent\"]')].map((a) => [a.dataset.bio, a.querySelector('.blk-model-name')?.textContent])")
    out["purpose"] = c.js(f"{mine}.querySelector('[data-testid=\"block-purpose\"]').textContent")
    out["foot"] = c.js(f"{mine}.querySelector('[data-testid=\"block-foot\"]').textContent")
    return out


def fold(c, page) -> dict:
    mine = block("my-media")
    h0 = c.js(f"{mine}.offsetHeight")
    c.js(f"{mine}.scrollIntoView({{block: 'center', inline: 'center'}}); 1")
    c.click_on(f"{mine}.querySelector('[data-testid=\"block-toggle\"]')")
    out = {"folded": c.wait(f"{mine} && !{mine}.dataset.open && {mine}.offsetHeight < {h0} && [{mine}.offsetHeight, {mine}.querySelectorAll('.blk-lines > div').length]", 10)}
    go(c, page)
    out["kept"] = c.wait(f"{BLOCKS}.length === 2 && {mine} && !{mine}.dataset.open && 'folded'", 40)
    c.js(f"{mine}.scrollIntoView({{block: 'center', inline: 'center'}}); 1")
    c.click_on(f"{mine}.querySelector('[data-testid=\"block-toggle\"]')")
    out["reopened"] = c.wait(f"{mine}?.dataset.open === 'true' && {mine}.querySelectorAll('[data-testid=\"block-agent\"]').length", 10)
    return out


def inspect(c, page) -> dict:
    mine = block("my-media")
    insp = f"{Q}('[data-testid=\"roles-inspector-body\"][data-block=\"my-media\"] [data-testid=\"wf-inspector\"]')"
    c.click_on(mine, 0.5, 0.06)
    out = {"summary": c.wait(f"{insp} && [...{insp}.querySelectorAll('.ri-row')].map((r) => r.dataset.block)", 15)}
    c.js(f"{insp}.querySelector('[data-testid=\"wf-edit-agents\"]').scrollIntoView({{block: 'center'}}); 1")  # part 2: the When row
    c.click_on(f"{insp}.querySelector('[data-testid=\"wf-edit-agents\"]')")
    out["agents_page"] = c.wait(f"{Q}('[data-testid=\"wf-page-agents\"]') && [...document.querySelectorAll('[data-testid=\"wf-agent\"]')].map((a) => a.dataset.bio)", 10)
    c.click_on(f"{Q}('[data-testid=\"wf-page-back\"]')")
    c.wait(f"!!{Q}('[data-testid=\"wf-edit-purpose\"]')", 10)
    c.js(f"{Q}('[data-testid=\"wf-edit-purpose\"]').scrollIntoView({{block: 'center'}}); 1")
    c.click_on(f"{Q}('[data-testid=\"wf-edit-purpose\"]')")
    box = f"{Q}('[data-testid=\"wf-field-does\"]')"
    c.wait(f"!!{box} && !{box}.disabled", 10)
    c.click_on(box)
    c.js(f"{box}.select(); 1")
    c.type_text(NEW_DOES)
    c.wait(f"{box}.value === {NEW_DOES!r} && !{Q}('[data-testid=\"wf-page-save\"]').disabled", 10)
    c.click_on(f"{Q}('[data-testid=\"wf-page-save\"]')")
    out["saved_line"] = c.wait(f"{mine}?.querySelector('[data-testid=\"block-purpose\"]')?.textContent === {NEW_DOES!r} && 'saved'", 15)
    c.click_on(f"{Q}('.rc-scroll')", 0.02, 0.98)
    out["cleared"] = c.wait(f"!{Q}('[data-testid=\"roles-inspector-body\"]')?.dataset.block && 'clear'", 10)
    return out


def shots(c, page, folder: str) -> dict:
    if not folder:
        return {}
    Path(folder).mkdir(parents=True, exist_ok=True)
    c.call("Emulation.setDeviceMetricsOverride", width=1800, height=1100, deviceScaleFactor=1, mobile=False)
    go(c, page)
    c.wait(f"{BLOCKS}.length === 2", 40)
    time.sleep(0.8)
    c.shot(str(Path(folder) / "cast-blocks.png"), 1800, 1100, 1)
    return {"shots": folder}


class BlocksDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        from halo_harness.studio.server import url_for
        from halo_harness.theme import set_config_value
        from halo_harness.workflows.registry import folders
        from halo_harness.workflows.squares_cli import _new
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        _new("my-media", "media", Path.cwd())
        mine = folders(cwd=Path.cwd())[0][1] / "my-media.yaml"
        text = mine.read_text(encoding="utf-8").replace("  lead: {bio: auto-media, model: auto}",
                                                        "  lead: {bio: auto-media, model: auto}\n  members:\n"
                                                        "    - {bio: auto-researcher, model: auto}\n    - {bio: auto-reviewer, model: auto}")
        mine.write_text(text, encoding="utf-8", newline="\n")
        set_config_value("workflows.enabled", ["media", "my-media"])
        srv, _url = serve(state)
        base = url_for(srv)
        folder = self.argv[self.argv.index("--shots") + 1] if "--shots" in self.argv else ""

        def page(query: str) -> str:
            return base.replace("/#t=", f"/?{query}&feed=off&tour=off#t=")
        try:
            yield ((cast, (c, page)), (fold, (c, page)), (inspect, (c, page)), (shots, (c, page, folder)))
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    sys.exit(BlocksDriver(sys.argv[1:]).main())
