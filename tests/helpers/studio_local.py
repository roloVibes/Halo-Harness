"""tests.helpers.studio_local -- Studio's Local section (Halo 3.3.5.0 R1), real clicks and keys in headless Chrome
through the driver base, over a scratch home (capture_studio's seeded_home) with tests/helpers/local_seed.py's fixture
(the Ollama panel's hosts, ledger, cards and catalogs, and `box`, a fake Ollama on 127.0.0.1:0); the sampler runs on
the fixture's nvidia-smi and /proc answers (resources.SAMPLER_SEAMS); the live feed is on. No provider request, no
model call:

1. `alt0`: from Roles, Alt+0 opens Local with nothing over it (no help, no dialog), on Resources;
2. `pages`: the rail's seven pages, each with its title; the three framed ones say what they will hold and the CLI;
   Steward shows the job's status line and the last note;
3. `resources`: a strip per sampled host; it moves on `resources` frames; every number carries its source;
4. `traffic`: the rows match the fixture ledger; a line written now arrives as a `traffic` frame at the foot;
5. `hosts`: the cards' numbers; Load and Unload on box against the fake; Make it fit on pc, then Undo;
6. `models`: the rows' chips and meters; the intent filter's order; the coder-lane button.
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_packs_steps import CUR, alt, q, qa  # noqa: E402
from tests.helpers.studio_settings import press  # noqa: E402

OPEN = "[document.querySelectorAll('[data-testid=section-help]').length, document.querySelectorAll('[role=dialog]').length]"
PAGE = "(document.querySelector('[data-testid=local-page]')?.dataset.page || '')"
STRIP = "[data-testid=local-resources-host]"
TROWS = "[data-testid=local-traffic-row]"
MROWS = "[data-testid=local-model-row]"


def page(c, pid: str) -> None:
    press(c, q(f"[data-testid=local-rail-page][data-page={pid}]"), f"{PAGE} === '{pid}'")


def card(name: str, inner: str = "") -> str:
    return q(f'[data-testid=local-host-card][data-name="{name}"] {inner}'.strip())


def config(ctx) -> dict:
    return json.loads((ctx["state"] / "config.json").read_text(encoding="utf-8"))


def alt0(c, url, ctx) -> dict:
    c.go(f"{ctx['base']}?mode=roles&tour=off#{ctx['frag']}")
    c.wait(f"{CUR}.startsWith('Roles')", 40)
    c.js("document.activeElement?.blur?.(); 1")
    alt(c, 10)
    out = {"alt0": c.wait(f"{CUR}.startsWith('Local') && {CUR}", 15)}
    time.sleep(1.5)
    out["alt0_open"] = c.js(OPEN)
    out["alt0_page"] = c.wait(f"!!{q('[data-testid=local-room]')} && {PAGE}", 15)
    return out


def pages(c, url, ctx) -> dict:
    out = {"rail": c.js(f"{qa('[data-testid=local-rail-page]')}.map((b) => b.dataset.page)"), "titles": {}, "framed": {}}
    for pid in out["rail"]:
        page(c, pid)
        out["titles"][pid] = c.js(f"{q('[data-testid=local-page-title]')}.textContent")
        if c.js(f"!!{q('[data-testid=local-framed]')}"):
            out["framed"][pid] = [len(c.js(f"{q('[data-testid=local-framed-holds]')}.textContent")),
                                  c.js(f"{qa('[data-testid=local-framed-cli]')}.length")]
    page(c, "steward")
    out["steward_status"] = c.wait(f"{q('[data-testid=local-steward-status]')}.textContent.includes('steward job') && "
                                   f"{q('[data-testid=local-steward-status]')}.textContent", 15)
    out["steward_note"] = c.wait(f"{q('[data-testid=local-steward-note]')}?.textContent", 15)
    out["ideas"] = c.js(f"{q('[data-testid=local-ideas]')}.textContent")
    return out


def resources(c, url, ctx) -> dict:
    page(c, "resources")
    out = {"strips": c.wait(f"{qa(STRIP)}.length >= 2 && {qa(STRIP)}.map((s) => s.dataset.host).sort()", 30)}
    pc = q(f'{STRIP}[data-host="pc"]')
    t0 = c.wait(f"+{pc}.dataset.t", 10)
    out["moved"] = [t0, c.wait(f"+{pc}.dataset.t > {t0} && +{pc}.dataset.t", 10)]
    out["vram"] = c.js(f"{pc}.querySelector('[data-testid=local-res-vram]').textContent")
    out["holder"] = c.js(f"{pc}.querySelector('[data-testid=local-res-holder]').textContent")
    out["res_titles"] = c.js(f"[...{pc}.querySelectorAll('[data-testid^=local-res-]')].filter((e) => e.title).map((e) => [e.dataset.testid, e.title])")
    out["spark"] = c.wait(f"+{pc}.querySelector('[data-testid=local-res-spark]').dataset.points >= 2 && "
                          f"+{pc}.querySelector('[data-testid=local-res-spark]').dataset.points", 10)
    return out


def traffic(c, url, ctx) -> dict:
    from halo_harness.ollama_steward.ledger import append_lines
    from tests.helpers.steward_seed import line
    page(c, "resources")
    out = {"trows": c.wait(f"{qa(TROWS)}.length >= 13 && {qa(TROWS)}.map((r) => [r.dataset.host, r.dataset.model, r.dataset.state])", 20)}
    out["sparks"] = c.js(f"{qa('[data-testid=local-traffic-spark]')}.map((s) => [s.dataset.host, +s.dataset.calls])")
    append_lines(ctx["state"], [line(host={"name": "box", "url": ctx["box"]}, model="followup:1b", ago=1, bytes_in=900, bytes_out=40)])
    out["live_row"] = c.wait(f"{qa(TROWS)}.at(-1)?.dataset.model === 'followup:1b' && {qa(TROWS)}.at(-1).dataset.host", 15)
    lst = q("[data-testid=local-traffic-list]")
    out["follow_at_foot"] = c.js(f"Math.abs({lst}.scrollHeight - {lst}.scrollTop - {lst}.clientHeight) < 30")
    return out


def hosts(c, url, ctx) -> dict:
    page(c, "hosts")
    out = {"cards": c.wait(f"{qa('[data-testid=local-host-card]')}.length >= 4 && {qa('[data-testid=local-host-card]')}.map((h) => [h.dataset.name, h.dataset.source, h.dataset.control])", 20)}
    out["pc_vram"] = c.js(f"{card('pc', '[data-testid=local-host-vram]')}.textContent")
    out["pc_users"] = c.js(f"{card('pc', '[data-testid=local-host-users]')}.textContent")
    out["pc_why"] = c.js(f"{card('pc', '[data-testid=local-control-why]')}?.textContent || ''")
    load = q('[data-testid=local-host-card][data-name="box"] [data-testid=local-host-model][data-model="qwen3.5:9b"] [data-testid=local-load]')
    loaded = card("box", '[data-testid=local-host-loaded][data-model="qwen3.5:9b"]')
    press(c, load, f"!!{loaded}")
    out["loaded"] = [g["model"] for g in ctx["mock"].generated]
    press(c, card("box", '[data-testid=local-host-loaded][data-model="qwen3.5:9b"] [data-testid=local-unload]'),
          f"!{card('box', '[data-testid=local-host-loaded]')}")
    out["unloaded"] = ctx["mock"].generated[-1].get("keep_alive")
    before = dict((config(ctx).get("ollama") or {}).get("profiles") or {})
    press(c, card("pc", "[data-testid=local-make-fit]"), f"!!{card('pc', '[data-testid=local-fit-undo]')}")
    out["fit_profiles"] = {k: v for k, v in ((config(ctx).get("ollama") or {}).get("profiles") or {}).items() if k not in before}
    press(c, card("pc", "[data-testid=local-fit-undo]"), f"!{card('pc', '[data-testid=local-fit-undo]')}")
    time.sleep(0.5)
    out["after_undo"] = {k: v for k, v in ((config(ctx).get("ollama") or {}).get("profiles") or {}).items() if k not in before}
    return out


def models(c, url, ctx) -> dict:
    page(c, "models")
    out = {"mrows": c.wait(f"{qa(MROWS)}.length >= 6 && {qa(MROWS)}.map((r) => [r.dataset.host, r.dataset.model, r.dataset.fit, "
                          f"!!r.querySelector('[data-testid=model-card-chips]'), !!r.querySelector('[data-testid=fit-meter]')])", 20)}
    press(c, q("[data-testid=local-intent][data-intent=embed]"), f"!!{q('[data-testid=local-intent-why]')}")
    out["embed"] = c.js(f"{qa(MROWS)}.map((r) => r.dataset.model)")
    press(c, q("[data-testid=local-intent][data-intent=code]"), f"{q('[data-testid=local-intent-why]')}.textContent.includes('coding')")
    out["code_box"] = c.js(f"{qa('[data-testid=local-models-host][data-host=box] [data-testid=local-model-row]')}.map((r) => r.dataset.model)")
    out["why"] = c.js(f"{q('[data-testid=local-intent-why]')}.textContent")
    press(c, q("[data-testid=local-intent][data-intent='']"), f"{qa(MROWS)}.length >= 6")
    lane = q('[data-testid=local-model-row][data-host=box][data-model="qwen3-coder:30b"] [data-testid=local-coder-lane]')
    out["lane_buttons"] = c.js(f"{qa('[data-testid=local-coder-lane]')}.map((b) => b.closest('[data-testid=local-model-row]').dataset.model)")
    said = q('[data-testid=local-model-row][data-host=box][data-model="qwen3-coder:30b"] [data-testid=local-said]')
    press(c, lane, f"!!{said}")
    out["lane_said"] = c.js(f"{said}.textContent")
    out["lane_config"] = [config(ctx).get("team"), config(ctx).get("model")]
    return out


class LocalDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.ollama_steward import resources as R
        from halo_harness.providers import ollama as O
        from halo_harness.studio import model as M
        from halo_harness.studio import ollama_hosts_view as V
        from tests.helpers import local_seed as L
        state = seeded_home()
        mock = L.start_box()
        L.seed(state, mock)
        V.reset_cache()
        V.READERS.update(L.readers(mock))
        R.SAMPLER_SEAMS.update(L.sampler_seams(mock))
        box = O.resolve_ollama_host("box")
        with O._CATALOG_LOCK:  # the card and the lane offer read the catalog this process has
            O._CATALOG_CACHE[box.url] = (time.monotonic() + 3600, {"models": L.box_rows()})
        saved = (M.model_rows, M.catalog_rows)
        refs = [f"ol:{n}@box" for n in L.BOX_MODELS]
        M.catalog_rows = lambda *_a, **_k: [{"ref": r, "local": True} for r in refs]
        M.model_rows = lambda *_a, **_k: [{"ref": r, "provider": "ollama", "detail": r, "local": True} for r in refs]
        srv, url = serve(state, True)
        base, frag = url.split("?", 1)[0], url.split("#", 1)[1]
        ctx = {"state": state, "srv": srv, "base": base, "frag": frag, "mock": mock, "box": mock.base_url}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (alt0, pages, resources, traffic, hosts, models))
        finally:
            M.model_rows, M.catalog_rows = saved
            R.stop_all()
            R.SAMPLER_SEAMS.clear()
            R.STORE.clear()
            V.READERS.clear()
            O.reset_catalog_cache()
            srv.shutdown()
            srv.server_close()
            mock.stop()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(LocalDriver(sys.argv[1:]).main())
