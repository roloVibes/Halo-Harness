"""tests.helpers.studio_local_hf -- Studio's Local -> Hugging Face (Halo 3.3.5.0 R5) in headless Chrome: real clicks and
typing through tests/helpers/studio_local.LocalDriver's session (R1's seeded home: hosts pc and samus on 192.0.2.x
placeholders, `box` a fake Ollama on 127.0.0.1:0 whose card is this machine's), plus the fake hub
(tests/helpers/mock_hub.py on 127.0.0.1:0, named by HF_ENDPOINT) serving `unsloth/Qwen3.8-27B-GGUF` (the Library's
fixture repo) and the fake llama-server (tests/helpers/fake_llama_server.py as huggingface.llama_server_bin). No real
hub, no real server, no model call:

1. `folder`: the page is built (not framed); Add folder puts a scratch folder on huggingface.model_dirs;
2. `download`: Library -> the hub row's Download: the licence card (its line, the files, the folder) first, then the
   progress bar in the row, then "on disk in <folder>"; the Hugging Face page lists the model with its fit;
3. `serve`: Serve shows each flag with its source, Start, the row says which server serves it; Hosts has the server's
   card (Stop, Log); Models has `hf:local/<model>`; Log shows the tail; Stop ends it;
4. `delete`: a role naming `hf:local/<model>`: the uses card, Delete anyway, the row gone.
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import os
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

REPO_ID = "unsloth/Qwen3.8-27B-GGUF"
FILE = "Qwen3.8-27B-Q4_K_M.gguf"
MODEL = "Qwen3.8-27B-Q4_K_M"
LIB_ROW = f'[data-testid=local-library-row][data-source=hf][data-name="{REPO_ID}"]'
HF_ROW = f'[data-testid=local-hf-row][data-model="{MODEL}"]'
FAKE = Path(__file__).resolve().parent / "fake_llama_server.py"


def _esc(c) -> None:
    c.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true})); "
         "window.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true})); 1")
    c.wait(f"!{q('[data-testid=local-hf-card]')}", 10)


def folder(c, url, ctx) -> dict:
    from halo_harness.ollama_steward import resources as R
    R.stop_all()
    R.SAMPLER_SEAMS.clear()
    R.STORE.clear()
    c.go(f"{ctx['base']}?mode=local&page=huggingface&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'huggingface'", 40)
    out = {"built": c.wait(f"!!{q('[data-testid=local-hf]')} && !{q('[data-testid=local-framed]')}", 20)}
    out["none"] = c.wait(f"!!{q('[data-testid=local-hf-none]')}", 15)
    set_field(c, q("[data-testid=local-hf-add-path]"), str(ctx["models"]))
    out["add_title"] = c.js(f"{q('[data-testid=local-hf-add]')}.title")
    press(c, q("[data-testid=local-hf-add]"), f"!!{q('[data-testid=local-hf-dir]')}")
    out["dir"] = c.js(f"{q('[data-testid=local-hf-dir]')}.dataset.path")
    out["config_dirs"] = json.loads((ctx["state"] / "config.json").read_text(encoding="utf-8"))["huggingface"]["model_dirs"]
    return out


def download(c, url, ctx) -> dict:
    page(c, "library")
    press(c, q("[data-testid=local-library-source-btn][data-source=hf]"), f"!!{q(LIB_ROW)}")
    btn = q(f"{LIB_ROW} .lc-model-acts [data-testid=local-library-pull]")
    c.wait(f"!!{btn} && !{btn}.disabled", 20)
    out = {"dl_title": c.js(f"{btn}.title"), "dl_text": c.js(f"{btn}.textContent")}
    press(c, btn, f"!!{q('[data-testid=local-dl-licence]')}")
    out["licence"] = c.js(f"{q('[data-testid=local-dl-licence]')}.textContent")
    out["files"] = c.js(f"{q('[data-testid=local-dl-files]')}.textContent")
    out["dl_dir"] = c.js(f"{q('[data-testid=local-dl-dir]')}.value")
    out["before_bytes"] = len(ctx["hub"].resolves())
    ctx["hub"].delay_s = 0.03
    bar = q(f"{LIB_ROW} [data-testid=local-pull-progress]")
    press(c, q("[data-testid=local-dl-go]"), f"!!{bar}")
    out["moving"] = c.wait(f"{bar} && {bar}.dataset.state === 'running' && +{bar}.dataset.percent > 0 && +{bar}.dataset.percent < 100 && +{bar}.dataset.percent", 30)
    out["ondisk"] = c.wait(f"{q(LIB_ROW + ' [data-testid=local-library-ondisk]')}?.textContent", 40)
    ctx["hub"].delay_s = 0.0
    page(c, "huggingface")
    out["hf_row"] = c.wait(f"!!{q(HF_ROW)} && [{q(HF_ROW)}.dataset.kind, {q(HF_ROW)}.dataset.fit, "
                           f"{q(HF_ROW + ' [data-testid=local-hf-fit]')}.querySelector('[data-testid=fit-meter]').title]", 20)
    return out


def serve(c, url, ctx) -> dict:
    press(c, q(f"{HF_ROW} [data-testid=local-hf-serve]"), f"{qa('[data-testid=local-hf-flag]')}.length >= 3")
    out = {"flags": c.js(f"{qa('[data-testid=local-hf-flag]')}.map((f) => [f.dataset.flag, f.dataset.value, f.title])"),
           "argv": c.js(f"{q('[data-testid=local-hf-argv]')}.textContent"), "go_title": c.js(f"{q('[data-testid=local-hf-serve-go]')}.title")}
    press(c, q("[data-testid=local-hf-serve-go]"), f"{q('[data-testid=local-hf-said]')}?.dataset.ok === 'true'")
    out["said"] = c.js(f"{q('[data-testid=local-hf-said]')}.textContent")
    _esc(c)
    out["served"] = c.wait(f"{q(HF_ROW + ' [data-testid=local-hf-served]')}?.textContent", 20)
    out["default_title"] = c.js(f"{q(HF_ROW + ' [data-testid=local-hf-default]')}?.title || ''")
    page(c, "hosts")
    mcard = q("[data-testid=local-host-card][data-source='managed server']")
    out["host_card"] = c.wait(f"!!{mcard} && [{mcard}.dataset.name, {mcard}.dataset.kind, "
                              f"{mcard}.querySelector('[data-testid=local-host-managed-model]').textContent, "
                              f"{mcard}.querySelector('[data-testid=local-host-stop]').title]", 20)
    other = q("[data-testid=local-host-card][data-source='local server'] [data-testid=local-host-stop]")
    out["not_ours"] = c.js(f"{other} ? [{other}.disabled, {other}.title] : null")
    page(c, "models")
    out["models_row"] = c.wait(f"{qa('[data-testid=local-model-row]')}.filter((r) => r.dataset.model === '{MODEL}').map((r) => r.dataset.host)", 20)
    page(c, "huggingface")
    press(c, q(f"{HF_ROW} [data-testid=local-hf-log]"), f"{q('[data-testid=local-hf-log-lines]')}?.textContent.includes('offloaded')")
    out["log"] = c.js(f"{q('[data-testid=local-hf-log-lines]')}.textContent.split('\\n').filter((l) => l.includes('offloaded') || l.includes('listening'))")
    _esc(c)
    press(c, q(f"{HF_ROW} [data-testid=local-hf-stop]"), f"!{q(HF_ROW + ' [data-testid=local-hf-served]')}")
    from halo_harness.providers.local_server import servers
    out["after_stop"] = [e["id"] for e in servers(ctx["state"])]
    return out


def delete(c, url, ctx) -> dict:
    cfg_path = ctx["state"] / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["roles"] = {"reviewer": f"hf:local/{MODEL}"}
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    press(c, q(f"{HF_ROW} [data-testid=local-hf-delete]"), f"!!{q('[data-testid=local-hf-delete-uses]')}")
    out = {"uses": c.js(f"{q('[data-testid=local-hf-delete-uses]')}.textContent"),
           "go": [c.js(f"{q('[data-testid=local-hf-delete-go]')}.textContent"), c.js(f"{q('[data-testid=local-hf-delete-go]')}.title")]}
    press(c, q("[data-testid=local-hf-delete-go]"), f"{q('[data-testid=local-hf-said]')}?.dataset.ok === 'true'")
    _esc(c)
    out["gone"] = c.wait(f"!{q(HF_ROW)}", 20)
    out["on_disk"] = [p.name for p in Path(ctx["models"]).rglob("*.gguf")]
    return out


class HfDriver(LocalDriver):
    @contextmanager
    def session(self, c):
        from tests.helpers.mock_hub import MockHub, gguf_bytes
        with super().session(c) as steps:
            args = steps[0][1]
            ctx = args[2]
            hub = MockHub().start()
            hub.add(REPO_ID, {"README.md": b"# fixture\n", FILE: gguf_bytes(2 * 1024 * 1024, "drv", ctx=40960, layers=36),
                              "Qwen3.8-27B-Q8_0.gguf": gguf_bytes(90_000, "q8")})
            saved = os.environ.get("HF_ENDPOINT")
            os.environ["HF_ENDPOINT"] = hub.base_url
            models = ctx["state"].parent / "l4_models"
            models.mkdir(exist_ok=True)
            from halo_harness.theme import set_config_value
            set_config_value("huggingface.llama_server_bin", [sys.executable, str(FAKE)])
            ctx.update(hub=hub, models=models)
            try:
                yield ((folder, args), (download, args), (serve, args), (delete, args))
            finally:
                from halo_harness.providers.local_server import servers, stop
                for e in servers(ctx["state"]):
                    stop(e["id"], state_dir=ctx["state"])
                hub.stop()
                if saved is None:
                    os.environ.pop("HF_ENDPOINT", None)
                else:
                    os.environ["HF_ENDPOINT"] = saved
                time.sleep(0.1)



if __name__ == "__main__":
    sys.exit(HfDriver(sys.argv[1:]).main())
