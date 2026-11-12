"""tests.helpers.studio_replay_time -- Agents -> Live's scrubber and the replay file (Halo 3.4.1.0 R1 "Time") in headless
Chrome on the driver base, over a scratch home with one ended session (tests/helpers/replay_seed.py) and nothing live.
tests/test_studio_replay_time.py reads it:

    python -m tests.helpers.studio_replay_time

History's row opens the session on the scrubber (marks, bands); the canvas is redrawn at three seeded moments (+5 s: main
alone; +22 s: main waits on a permission card, the scout reads, the fixer works; +95 s: the scout done, the fixer
failed) with the banner's moment and the session's own title, the sentence and the cost; Play at 16x moves and pauses; Save says what it holds and
writes; Export a clip saves first and says its frames, width and path; Now returns; a saved file is a History row; Open
a file takes one from elsewhere; `?replay=<id>&at=22` opens it at that moment. The last stdout line is a JSON object of
what it saw (exit 2: no Chrome). No model is called.
"""
from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

Q = "document.querySelector"
QA = "document.querySelectorAll"
BAR = f"{Q}('[data-testid=\"replay-bar\"]')"
BANNER = f"{Q}('[data-testid=\"live-replay-banner\"]')"
ROWS = f"[...{QA}('[data-testid=\"live-history-row\"]')]"
NODES = f"[...{QA}('[data-testid=\"roles-live-node\"]')].map((n) => [n.dataset.agent, n.dataset.state])"
DIALOG = f"{Q}('[data-testid=\"replay-{{}}-dialog\"]')"


def open_page(c, page, query: str) -> None:
    c.go("about:blank")  # a navigation to the same address with a #t= fragment is a fragment hop
    c.go(page(query))
    c.wait(f"{QA}('[data-testid=\"section-tab\"]').length > 0 && !!{Q}('.section-view')", 40)


def history(c) -> None:
    c.wait(f"!!{Q}('[data-testid=\"live-history\"]')", 30)
    if not c.js(f"!!{Q}('[data-testid=\"live-history-drawer\"]')"):
        c.click_on(f"{Q}('[data-testid=\"live-history\"]')")
    c.wait(f"{ROWS}.length >= 1", 20)


def scrub_to(c, secs: float) -> dict:
    v = int(round(secs * 10))
    c.js(f"""(() => {{ const r = {BAR}.querySelector('[data-testid="replay-scrub"]');
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(r, '{v}');
      r.dispatchEvent(new Event('input', {{bubbles: true}})); return 1; }})()""")
    c.wait(f"{BAR}.dataset.t10 === '{v}' && {BANNER}?.dataset.at === '{int(round(secs))}'", 15)
    return {"nodes": c.wait(f"{NODES}.length && {NODES}", 10), "lit": c.js(f"{BAR}.dataset.lit"),
            "banner": c.js(f"{BANNER}.textContent"), "said": c.js(f"{Q}('[data-testid=\"live-narration\"]')?.dataset.text || ''"),
            "cost": c.js(f"{Q}('[data-testid=\"replay-cost\"]')?.textContent || ''")}


def opened(c, page, sid: str) -> dict:
    open_page(c, page, "mode=agents")
    history(c)
    c.click_on(f"{ROWS}.find((r) => r.dataset.kind === 'session' && r.dataset.id === '{sid}')")
    out = {"opened": c.wait(f"{BAR}?.dataset.mode === 'replay' && {BANNER}?.dataset.kind === 'session' && +{BAR}.dataset.marks > 0 && {BAR}.dataset.marks", 20)}
    out["kinds"] = c.js(f"[...new Set([...{QA}('[data-testid=\"replay-mark\"]')].map((m) => m.dataset.kind))]")
    out["bands"] = c.js(f"[...new Set([...{QA}('[data-testid=\"replay-band\"]')].map((m) => m.dataset.phase))]")
    out["at_end"] = c.js(f"{BAR}.dataset.t")
    for t in (5, 22, 95):
        out[f"at{t}"] = scrub_to(c, t)
    return out


def playing(c) -> dict:
    scrub_to(c, 0)
    c.click_on(f"{BAR}.querySelector('[data-speed=\"16\"]')")
    c.wait(f"{BAR}.dataset.speed === '16'", 10)
    c.click_on(f"{Q}('[data-testid=\"replay-play\"]')")
    out = {"moving": c.wait(f"{BAR}.dataset.playing === 'true' && +{BAR}.dataset.t >= 16 && +{BAR}.dataset.t", 20)}
    c.click_on(f"{Q}('[data-testid=\"replay-play\"]')")
    out["paused"] = c.wait(f"!{BAR}.dataset.playing && 'paused'", 10)
    return out


def saving(c) -> dict:
    c.click_on(f"{Q}('[data-testid=\"replay-save\"]')")
    d = DIALOG.format("save")
    out = {"holds": c.wait(f"{d}?.querySelectorAll('[data-testid=\"replay-save-holds\"] li').length >= 4 && [...{d}.querySelectorAll('li')].map((l) => l.textContent)", 20)}
    out["says"] = c.js(f"[...{d}.querySelectorAll('[data-testid=\"dialog-cost\"] dd')].map((x) => x.textContent)")
    c.click_on(f"{Q}('[data-testid=\"replay-save-go\"]')")
    out["wrote"] = c.wait(f"{Q}('[data-testid=\"replay-save-done\"]')?.dataset.path", 20)
    c.click_on(f"[...{d}.querySelectorAll('button')].find((b) => b.textContent === 'Done')")
    c.wait(f"!{d}", 10)
    c.click_on(f"{Q}('[data-testid=\"replay-clip\"]')")
    d = DIALOG.format("clip")
    c.wait(f"!!{Q}('[data-testid=\"replay-clip-save\"]') && !{Q}('[data-testid=\"replay-clip-save\"]').disabled", 20)
    out["clip_first"] = c.js(f"[...{d}.querySelectorAll('[data-testid=\"dialog-cost\"] dd')].map((x) => x.textContent)")
    c.click_on(f"{Q}('[data-testid=\"replay-clip-save\"]')")
    out["clip_says"] = c.wait(f"!!{Q}('[data-testid=\"replay-clip-from\"]') && {d}.querySelector('[data-line=\"does\"]')?.textContent.includes('frames') && [...{d}.querySelectorAll('[data-testid=\"dialog-cost\"] dd')].map((x) => x.textContent)", 20)
    out["now_file"] = c.wait(f"{BANNER}?.dataset.kind === 'file' && {BANNER}.dataset.id", 15)
    c.click_on(f"[...{d}.querySelectorAll('button')].find((b) => b.textContent === 'Cancel')")
    c.wait(f"!{d}", 10)
    c.click_on(f"{Q}('[data-testid=\"replay-close\"]')")
    out["now"] = c.wait(f"!{BANNER} && !{BAR} && 'now'", 15)
    return out


def files(c, page, state: Path) -> dict:
    history(c)
    out = {"rows": c.wait(f"{ROWS}.filter((r) => r.dataset.kind === 'file').length >= 1 && {ROWS}.map((r) => r.dataset.kind)", 20)}
    src = sorted((state / "replays").glob("*.halo-replay"))[0]
    data = json.loads(src.read_text(encoding="utf-8"))
    data["id"] = "elsewhere-1"
    other = state.parent / "elsewhere" / "theirs.halo-replay"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text(json.dumps(data), encoding="utf-8")
    doc = c.call("DOM.getDocument")["root"]["nodeId"]
    node = c.call("DOM.querySelector", nodeId=doc, selector='[data-testid="live-history-file"]')["nodeId"]
    c.call("DOM.setFileInputFiles", files=[str(other)], nodeId=node)
    out["picked"] = c.wait(f"{BANNER}?.dataset.kind === 'file' && {BANNER}.dataset.id === 'elsewhere-1' && {BANNER}.dataset.id", 20)
    out["kept"] = (state / "replays" / "elsewhere-1.halo-replay").is_file()
    open_page(c, page, "mode=agents&view=live&replay=elsewhere-1&at=22")
    out["door"] = c.wait(f"{BAR}?.dataset.replay === 'elsewhere-1' && {BAR}.dataset.t === '22' && {NODES}.length === 3 && {NODES}", 25)
    return out


class ReplayTimeDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        from halo_harness.studio.server import url_for
        from tests.helpers.replay_seed import SID, seed
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        seed(state)
        srv, _url = serve(state)
        base = url_for(srv)

        def page(query: str) -> str:
            return base.replace("/#t=", f"/?{query}&tour=off&level=mid#t=")
        try:
            yield ((opened, (c, page, SID)), (playing, (c,)), (saving, (c,)), (files, (c, page, state)))
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    sys.exit(ReplayTimeDriver(sys.argv[1:]).main())
