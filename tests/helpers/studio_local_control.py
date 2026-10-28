"""tests.helpers.studio_local_control -- Studio's Local tab, controlled (Halo 3.3.5.0 R3), in headless Chrome: real
clicks and typing through tests/helpers/studio_local.LocalDriver's session (R1's seeded home: hosts pc and samus on
192.0.2.x placeholders, `box` a fake Ollama on 127.0.0.1:0 that can pull, copy and delete; the live feed on). No
provider request, no model call, nothing sent but to the fake:

1. `pull`: Library -> Pull on gemma3:4b to box: the progress bar moves on `pull` frames, then "installed on box";
   the typed pull of an HF GGUF; a slow pull cancelled from the Jobs list;
2. `acts`: Models -> a row's actions menu: Show (the /api/show facts beside the card), Load now and the Loaded-now
   strip's Unload, the tuned twin (its name and cost, then made), Copy and Rename, Delete with the uses card (a role
   names it: Delete anyway), and a live session on a model keeping Delete disabled.
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
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

G4 = '[data-testid=local-library-row][data-name="gemma3:4b"]'
HF = "hf.co/example-org/Some-8B-GGUF:Q4_K_M"
MENU = "[data-testid=local-model-menu]"
JOB_G4 = '[data-testid=local-job][data-name="gemma3:4b"]'
LOADED_9B = '[data-testid=local-loaded-row][data-host=box][data-model="qwen3.5:9b"]'


def _row(model: str, inner: str = "") -> str:
    return q(f'[data-testid=local-model-row][data-host=box][data-model="{model}"] {inner}'.strip())


def pull(c, url, ctx) -> dict:
    from halo_harness.ollama_steward import resources as R
    from tests.helpers.control_env import QWEN_SHOW
    R.stop_all()
    R.SAMPLER_SEAMS.clear()
    R.STORE.clear()
    mock = ctx["mock"]
    for name in ("gemma3:4b", "llama3.2:3b"):
        mock.pullable[name] = json.loads(json.dumps(QWEN_SHOW))
    mock.pull_delay_s = 0.35
    c.go(f"{ctx['base']}?mode=local&page=library&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'library'", 40)
    page(c, "library")
    c.wait(f"{qa('[data-testid=local-library-row]')}.length >= 50", 30)
    set_field(c, q("[data-testid=local-library-host]"), "box", "change")
    c.wait(f"{q('[data-testid=local-library-host]')}.value === 'box'", 20)
    set_field(c, q("[data-testid=local-library-search]"), "gemma3")
    c.wait(f"!!{q(G4)}", 20)
    btn = q(f"{G4} .lc-model-acts [data-testid=local-library-pull]")
    out = {"pull_title": c.js(f"{btn}.title")}
    bar = q(f"{G4} [data-testid=local-pull-progress]")
    press(c, btn, f"!!{bar}")
    out["moving"] = c.wait(f"{bar} && {bar}.dataset.state === 'running' && +{bar}.dataset.percent > 0 && +{bar}.dataset.percent < 100 "
                           f"&& !!{bar}.querySelector('[data-testid=local-pull-speed]') && [{bar}.dataset.percent, {bar}.querySelector('[data-testid=local-pull-speed]').textContent, {bar}.querySelector('[data-testid=local-pull-eta]')?.textContent || '']", 20)
    out["installed"] = c.wait(f"{q(G4 + ' .lc-model-acts [data-testid=local-library-installed]')}?.textContent", 30)
    out["job_done"] = c.wait(f"{q(JOB_G4)}?.dataset.state === 'done' && 'done'", 10)
    mock.pull_delay_s = 0.05
    set_field(c, q("[data-testid=local-pull-name]"), HF)
    out["go_title"] = c.js(f"{q('[data-testid=local-pull-go]')}.title")
    tb = q("[data-testid=local-pull-box] [data-testid=local-pull-progress]")
    press(c, q("[data-testid=local-pull-go]"), f"!!{tb}")
    out["typed"] = c.wait(f"{tb}.dataset.state === 'done' && {tb}.querySelector('[data-testid=local-pull-said]').textContent", 30)
    out["pulled"] = list(mock.pulled)
    mock.pull_delay_s = 0.6
    set_field(c, q("[data-testid=local-pull-name]"), "llama3.2:3b")
    job = q('[data-testid=local-jobs] [data-testid=local-job][data-name="llama3.2:3b"]')
    press(c, q("[data-testid=local-pull-go]"), f"{job}?.dataset.state === 'running'")
    press(c, q('[data-testid=local-jobs] [data-testid=local-job][data-name="llama3.2:3b"] [data-testid=local-pull-cancel]'),
          f"{job}?.dataset.state === 'cancelled'")
    out["cancelled"] = [c.js(f"{job}.dataset.state"), c.js(f"{job}.querySelector('[data-testid=local-pull-said]').textContent")]
    time.sleep(0.8)
    out["fake_cancelled"] = list(mock.pull_cancelled)
    return out


def _act(c, model: str, act: str, done: str) -> None:
    press(c, _row(model, "[data-testid=local-model-acts]"), f"!!{q(MENU)}")
    press(c, q(f"{MENU} [data-act={act}]"), done)


def _close(c) -> None:
    c.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true})); "
         "window.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true})); 1")
    c.wait(f"!{q('[data-testid=local-act-card]')}", 10)


def acts(c, url, ctx) -> dict:
    from halo_harness.studio import local_uses
    cfg_path = ctx["state"] / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["roles"] = {"reviewer": "ol:qwen3-coder:30b@box"}
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    page(c, "models")
    c.wait(f"!!{_row('qwen3.5:9b')}", 20)
    out = {"menu_titles": None}
    press(c, _row("qwen3.5:9b", "[data-testid=local-model-acts]"), f"!!{q(MENU)}")
    out["menu_titles"] = c.js(f"{qa(MENU + ' [data-act]')}.map((b) => [b.dataset.act, b.title])")
    press(c, q(f"{MENU} [data-act=show]"), f"{qa('[data-testid=local-show-facts] [data-fact]')}.length >= 3")
    out["show"] = c.js(f"{qa('[data-testid=local-show-facts] [data-fact]')}.map((d) => d.dataset.fact)")
    out["show_card"] = c.js(f"!!{q('[data-testid=local-act-card] [data-testid=model-card-how]')}")
    out["show_cli"] = c.js(f"{q('[data-testid=local-act-cli]')}.textContent")
    _close(c)
    strip = q(LOADED_9B)
    _act(c, "qwen3.5:9b", "load", f"!!{strip}")
    out["loaded"] = [c.js(f"{strip}.querySelector('[data-testid=local-loaded-vram]').textContent"),
                     c.js(f"{strip}.querySelector('[data-testid=local-loaded-unload]').title")]
    samus = q('[data-testid=local-loaded-row][data-host=samus] [data-testid=local-loaded-unload]')
    out["samus_unload"] = c.js(f"{samus} ? [{samus}.disabled, {samus}.title] : null")
    press(c, f"{strip}.querySelector('[data-testid=local-loaded-unload]')", f"!{strip}")
    out["unloaded"] = ctx["mock"].generated[-1].get("keep_alive")
    _act(c, "qwen3.5:9b", "twin", f"!!{q('[data-testid=local-twin-name]')}")
    out["twin"] = [c.js(f"{q('[data-testid=local-twin-name]')}.textContent"), c.js(f"{q('[data-testid=local-twin-cost]')}.textContent")]
    press(c, q("[data-testid=local-twin-make]"), f"{q('[data-testid=local-act-said]')}?.dataset.ok === 'true'")
    out["twin_said"] = c.js(f"{q('[data-testid=local-act-said]')}.textContent")
    _close(c)
    out["twin_row"] = c.wait(f"!!{_row('qwen3.5-halo:9b')}", 20)
    _act(c, "nomic-embed-text", "copy", f"!!{q('[data-testid=local-copy-name]')}")
    set_field(c, q("[data-testid=local-copy-name]"), "embed-two:latest")
    press(c, q("[data-testid=local-copy-go]"), f"{q('[data-testid=local-act-said]')}?.dataset.ok === 'true'")
    _close(c)
    out["copied"] = c.wait(f"!!{_row('embed-two')}", 20)
    _act(c, "embed-two", "rename", f"!!{q('[data-testid=local-copy-name]')}")
    set_field(c, q("[data-testid=local-copy-name]"), "embed-three:latest")
    press(c, q("[data-testid=local-copy-go]"), f"{q('[data-testid=local-act-said]')}?.dataset.ok === 'true'")
    _close(c)
    out["renamed"] = c.wait(f"!!{_row('embed-three')} && !{_row('embed-two')}", 20)
    _act(c, "qwen3-coder:30b", "delete", f"!!{q('[data-testid=local-delete-uses]')}")
    out["uses"] = [c.js(f"{q('[data-testid=local-delete-uses]')}.textContent"), c.js(f"{q('[data-testid=local-delete-go]')}.textContent"),
                   c.js(f"{q('[data-testid=local-delete-go]')}.title")]
    press(c, q("[data-testid=local-delete-go]"), f"{q('[data-testid=local-act-said]')}?.dataset.ok === 'true'")
    _close(c)
    out["deleted"] = c.wait(f"!{_row('qwen3-coder:30b')}", 20)
    out["fake_deleted"] = list(ctx["mock"].deleted)
    local_uses.READERS["live"] = lambda: [{"session_id": "s-live", "title": "on the 9B", "model": "ol:qwen3.5:9b@box"}]
    try:
        _act(c, "qwen3.5:9b", "delete", f"!!{q('[data-testid=local-delete-uses]')}")
        out["live"] = [c.js(f"{q('[data-testid=local-delete-uses]')}.textContent"), c.js(f"{q('[data-testid=local-delete-go]')}.disabled")]
        _close(c)
    finally:
        local_uses.READERS.clear()
    return out


class ControlDriver(LocalDriver):
    @contextmanager
    def session(self, c):
        with super().session(c) as steps:
            ctx = steps[0][1]
            yield ((pull, ctx), (acts, ctx))


if __name__ == "__main__":
    sys.exit(ControlDriver(sys.argv[1:]).main())
