"""tests.helpers.studio_replay_compare -- History's Compare (Halo 3.4.1.0 R2 "Time") in headless Chrome on the driver
base, over a scratch home with two ended sessions (tests/helpers/replay_seed.py, compare_seed.py) and a finished goal run
in Studio's folder, nothing live. tests/test_studio_replay_compare.py reads it:

    python -m tests.helpers.studio_replay_compare

Nothing opens by itself (no tick, no Compare bar); tick session A and the goal run -> Compare: the drawer goes wide,
one page, two columns of lanes over one axis, the rows with the better figure's word in its cell, three "what differed"
lines; Back keeps the ticks; one ticked -> Compare before / after (split at its steer, then where asked); the goal run's
report -> Replay -> Save this run's replay says what it holds and writes one file, Export a clip is on. The last stdout
line is a JSON object of what it saw (exit 2: no Chrome). No model is called.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_replay_time import BAR, DIALOG, Q, QA, ROWS, history, open_page  # noqa: E402

PAGE = f"{Q}('[data-testid=\"history-compare\"]')"
TICK = f"{Q}('[data-testid=\"live-history-tick\"][data-kind=\"{{}}\"][data-id=\"{{}}\"]')"
GO = f"{Q}('[data-testid=\"live-history-compare\"]')"
ROW_OF = f"[...{QA}('[data-testid=\"compare-row\"]')].map((r) => ({{key: r.dataset.key, better: r.dataset.better || '', " \
         "word: r.querySelector('[data-testid=\"compare-word\"]')?.textContent || '', side: r.querySelector('[data-better]')?.dataset.side || '', " \
         "a: r.querySelector('[data-side=\"a\"] .cmp-val').textContent, b: r.querySelector('[data-side=\"b\"] .cmp-val').textContent}))"


def compared(c, page, sid: str, run: str) -> dict:
    open_page(c, page, "mode=agents")
    history(c)
    c.wait(f"{ROWS}.length >= 3", 20)
    out = {"quiet": c.js(f"!{GO} && !{PAGE} && {QA}('[data-testid=\"live-history-tick\"]:checked').length === 0")}
    c.click_on(TICK.format("session", sid))
    out["one"] = c.wait(f"{GO}?.dataset.n === '1' && {GO}.textContent", 10)
    c.click_on(TICK.format("run", run))
    c.wait(f"{GO}?.dataset.n === '2'", 10)
    c.click_on(GO)
    c.wait(f"{PAGE}?.dataset.state === 'ready'", 30)
    out["wide"] = c.js(f"{Q}('[data-testid=\"live-history-drawer\"]').dataset.wide === 'true'")
    out["refs"] = c.js(f"[{PAGE}.dataset.a, {PAGE}.dataset.b]")
    out["rows"] = c.js(ROW_OF)
    out["differed"] = c.js(f"[...{QA}('[data-testid=\"compare-line\"]')].map((l) => l.textContent)")
    out["lanes"] = c.js(f"[...{QA}('[data-testid=\"compare-lane\"]')].map((l) => l.dataset.side + ':' + l.dataset.agent)")
    out["segs"] = c.js(f"{QA}('[data-testid=\"compare-seg\"]').length")
    c.click_on(f"{Q}('[data-testid=\"compare-back\"]')")
    out["back"] = c.wait(f"!{PAGE} && {QA}('[data-testid=\"live-history-tick\"]:checked').length", 15)
    return out


def split(c, sid: str, run: str, sid_b: str) -> dict:
    c.click_on(TICK.format("session", sid_b))  # a third tick lets the oldest (session A) go
    out = {"third": c.wait(f"{GO}?.dataset.n === '2' && !{TICK.format('session', sid)}.checked && {TICK.format('run', run)}.checked", 10)}
    c.click_on(TICK.format("run", run))
    out["label"] = c.wait(f"{GO}?.dataset.n === '1' && {GO}.textContent", 10)
    c.click_on(GO)
    out["split"] = c.wait(f"{PAGE}?.dataset.state === 'ready' && {PAGE}.dataset.split", 30)
    out["titles"] = c.js(f"[...{QA}('[data-testid=\"compare-column\"] .cmp-col-title')].map((t) => t.textContent)")
    out["self_rows"] = c.js(ROW_OF)
    c.js(f"""(() => {{ const i = {Q}('[data-testid="compare-split"]');
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, '0:20');
      i.dispatchEvent(new Event('input', {{bubbles: true}})); return 1; }})()""")
    c.wait(f"!{Q}('[data-testid=\"compare-split-go\"]').disabled", 10)
    c.click_on(f"{Q}('[data-testid=\"compare-split-go\"]')")
    out["moved"] = c.wait(f"{PAGE}?.dataset.state === 'ready' && {PAGE}.dataset.split === '20' && {PAGE}.dataset.split", 30)
    c.click_on(f"{Q}('[data-testid=\"compare-back\"]')")
    c.wait(f"!{PAGE}", 15)
    return out


def saved_run(c, run: str) -> dict:
    c.click_on(f"{ROWS}.find((r) => r.dataset.kind === 'run' && r.dataset.id === '{run}')")
    c.wait(f"{Q}('[data-testid=\"history-report\"]')?.dataset.run === '{run}'", 20)
    c.click_on(f"{Q}('[data-testid=\"history-report-replay\"]')")
    out = {"kind": c.wait(f"{BAR}?.dataset.mode === 'replay' && {BAR}.dataset.kind", 20)}
    out["clip_on"] = c.js(f"!{Q}('[data-testid=\"replay-clip\"]').disabled")
    c.wait(f"!{Q}('[data-testid=\"replay-save\"]').disabled", 10)
    c.click_on(f"{Q}('[data-testid=\"replay-save\"]')")
    d = DIALOG.format("save")
    out["holds"] = c.wait(f"{d}?.querySelectorAll('[data-testid=\"replay-save-holds\"] li').length >= 4 && [...{d}.querySelectorAll('li')].map((l) => l.textContent)", 20)
    out["says"] = c.js(f"[...{d}.querySelectorAll('[data-testid=\"dialog-cost\"] dd')].map((x) => x.textContent)")
    c.click_on(f"{Q}('[data-testid=\"replay-save-go\"]')")
    out["wrote"] = c.wait(f"{Q}('[data-testid=\"replay-save-done\"]')?.dataset.path", 20)
    return out


class ReplayCompareDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        from halo_harness.studio.server import url_for
        from tests.helpers.compare_seed import RUN, SID_B, seed_b, seed_run
        from tests.helpers.replay_seed import SID, seed
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        seed(state)
        seed_b(state)
        proj = state.parent / "project"
        seed_run(proj)
        srv, _url = serve(state, proj=proj)
        base = url_for(srv)

        def page(query: str) -> str:
            return base.replace("/#t=", f"/?{query}&tour=off&level=mid#t=")
        try:
            yield ((compared, (c, page, SID, RUN)), (split, (c, SID, RUN, SID_B)), (saved_run, (c, RUN)))
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    sys.exit(ReplayCompareDriver(sys.argv[1:]).main())
