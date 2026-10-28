"""tests.helpers.studio_library -- Studio's Local -> Library (Halo 3.3.5.0 R2) in headless Chrome: real clicks, keys
and typing through tests/helpers/studio_local.LocalDriver's session (R1's seeded home: hosts pc and samus on 192.0.2.x
placeholders, `box` a fake Ollama on 127.0.0.1:0, their hardware cards through the panel's READERS seam) with the
library's fixture sources (BRIDGE_TEST_NO_BACKGROUND_NET=1: the shipped snapshot and the hub's fixtures). No provider
request, no model call, nothing pulled:

`library`: the page and its source line (the snapshot's date, Refresh); the source switch; a typed search; the host
picker and the window control moving gemma3:27b's fit badge (fits / tight / no, the numbers as its title); fits this
host; the embed intent; the unfold (the card's how lines, the other tags each with its fit); Pull disabled; Copy.
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.studio_local import PAGE, LocalDriver, page  # noqa: E402
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_settings import press, set_field  # noqa: E402

ROWS = "[data-testid=local-library-row]"
G27 = '[data-testid=local-library-row][data-name="gemma3:27b"]'


def _names(c) -> list:
    return c.js(f"{qa(ROWS)}.map((r) => r.dataset.name)")


def _window(c, w: int, level: str) -> list:
    set_field(c, q("[data-testid=local-library-window]"), str(w), "change")
    c.wait(f"{q(G27)}?.dataset.fit === '{level}'", 20)
    badge = q(f"{G27} [data-testid=local-library-fit]")
    return [c.js(f"{q(G27)}.dataset.fit"), c.js(f"{badge}.title")]


def library(c, url, ctx) -> dict:
    from halo_harness.ollama_steward import resources as R
    R.stop_all()  # R1's sampler reads the fake nvidia-smi (18 GB "not Ollama" on box): the badge would count it
    R.SAMPLER_SEAMS.clear()
    R.STORE.clear()
    c.go(f"{ctx['base']}?mode=local&page=library&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'library'", 40)
    page(c, "library")
    # WindowedRows draws 200 rows first and 100 more per frame: wait for the whole catalog, not the first paint
    # (the Linux runner read 200 at the 50-row gate)
    out = {"rows": c.wait(f"{qa(ROWS)}.length >= 300 && {qa(ROWS)}.length", 30)}
    src = q("[data-testid=local-library-sources]")
    out["sources"] = c.js(f"[{src}.dataset.ollama, {src}.dataset.hf, !!{q('[data-testid=local-library-snapshot]')}, "
                          f"{src}.textContent]")
    out["size_title"] = c.js(f"{q(ROWS + ' [data-testid=local-library-size]')}.title")
    press(c, q("[data-testid=local-library-source-btn][data-source=hf]"),
          f"{qa(ROWS)}.length > 0 && {qa(ROWS)}.every((r) => r.dataset.source === 'hf')")
    out["hf_rows"] = _names(c)
    press(c, q("[data-testid=local-library-source-btn][data-source=all]"), f"{qa(ROWS)}.some((r) => r.dataset.source === 'ollama')")
    c.click_on(q("[data-testid=local-library-search]"))
    c.type_text("gemma3")
    c.wait(f"{qa(ROWS)}.length > 0 && {qa(ROWS)}.every((r) => r.dataset.name.includes('gemma3'))", 20)
    out["searched"] = _names(c)
    set_field(c, q("[data-testid=local-library-host]"), "box", "change")
    c.wait(f"{q('[data-testid=local-library-host]')}.value === 'box' && !!{q(G27)}", 20)
    out["windows"] = {w: _window(c, w, lv) for w, lv in ((8192, "fits"), (16384, "tight"), (131072, "no"))}
    _window(c, 8192, "fits")
    press(c, q("[data-testid=local-library-fits]"), f"{qa(ROWS)}.every((r) => ['fits', 'tight'].includes(r.dataset.fit))")
    out["fits_only"] = c.js(f"{qa(ROWS)}.map((r) => [r.dataset.name, r.dataset.fit])")
    press(c, q("[data-testid=local-library-fits]"), f"{qa(ROWS)}.some((r) => r.dataset.fit === 'unknown' || r.dataset.fit === 'no' || r.dataset.fit === 'spill') || {qa(ROWS)}.length >= {len(out['searched'])}")
    press(c, q(f"{G27} [data-testid=local-library-unfold]"), f"{qa(G27 + ' [data-testid=local-library-other]')}.length >= 3")
    out["how"] = c.js(f"{qa(G27 + ' [data-testid=model-card-how] li')}.map((li) => li.textContent)")
    out["others"] = c.js(f"{qa(G27 + ' [data-testid=local-library-other]')}.map((o) => [o.dataset.name, o.dataset.fit, "
                         f"!!o.querySelector('[data-testid=fit-meter]')])")
    pull = q(f"{G27} [data-testid=local-library-pull]")
    out["pull"] = c.js(f"[{pull}.disabled, {pull}.title]")
    try:
        c.call("Browser.grantPermissions", permissions=["clipboardReadWrite", "clipboardSanitizedWrite"])
    except Exception:
        pass
    copy = q(f"{G27} .lc-model-acts [data-testid=local-library-copy]")
    press(c, copy, f"!!{copy}.dataset.copied")
    out["copied"] = c.js(f"[{copy}.dataset.copied, {q(G27 + ' .lc-model-acts [data-testid=local-library-line]')}.textContent]")
    out["clipboard"] = c.js("navigator.clipboard.readText().then((t) => t, () => 'unreadable')") if out["copied"][0] == "copied" else ""
    set_field(c, q("[data-testid=local-library-search]"), "")
    c.wait(f"{qa(ROWS)}.length >= 50", 20)
    press(c, q("[data-testid=local-library-intent][data-intent=embed]"), f"!!{q('[data-testid=local-library-intent-why]')}")
    c.wait(f"{qa(ROWS)}.length > 0 && {qa(ROWS)}.every((r) => r.dataset.purpose === 'embedding')", 20)
    out["embed"] = _names(c)[:6]
    out["ideas"] = c.js(f"{q('[data-testid=local-ideas]')}.textContent")
    time.sleep(0.2)
    return out


class LibraryDriver(LocalDriver):
    @contextmanager
    def session(self, c):
        with super().session(c) as steps:
            ctx = steps[0][1]
            yield ((library, ctx),)


if __name__ == "__main__":
    sys.exit(LibraryDriver(sys.argv[1:]).main())
