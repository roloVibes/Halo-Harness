"""tests.helpers.studio_advise -- Studio's Adviser panel and the guards' lines (Halo 3.3.7.0 R4) in headless Chrome:
real clicks through tests/helpers/studio_local.LocalDriver's session (R1's seeded home; `box` a fake Ollama on
127.0.0.1:0). Seeded here: a lineup `adv` in force whose coder and verify lanes are both qwen models on box, and box's
catalog with a gemma3:12b and a second 9B qwen beside its own three; box's /api/ps holds llama3:8b that no halo call
explains. No provider request, no model call, nothing sent but to the fake:

`advise`: Local -> Models' Adviser lists its suggestions by kind, each with its one button and its CLI line; the
mismatch's "Point verify at gemma3:12b@box" writes roles.verify and nothing else; Local -> Hosts' box card shows the
foreign line and the refresh line; the traffic view shows the foreign line; Steward shows the refresh block. The last
stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.studio_local import PAGE, LocalDriver, card, config, page  # noqa: E402
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_settings import press  # noqa: E402

ROWS = "[data-testid=local-adviser-row]"


def seed(ctx) -> None:
    import yaml
    from halo_harness.studio import ollama_hosts_view as V
    from tests.helpers import local_seed as L
    state, mock = ctx["state"], ctx["mock"]
    (state / "teams").mkdir(parents=True, exist_ok=True)
    (state / "teams" / "adv.yaml").write_text(yaml.safe_dump({"name": "adv", "description": "adviser fixture", "version": 1,
                                                             "roles": {"main": "general",
                                                                       "coder": {"agent": "general", "models": {"preference": "ol:qwen3-coder:30b@box"}},
                                                                       "verify": {"agent": "general", "models": {"preference": "ol:qwen3.5:9b@box"}}}}),
                                              encoding="utf-8")
    cfg = config(ctx)
    cfg.update(team="adv", roles={**(cfg.get("roles") or {}), "enabled": True})
    (state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    extra = [{"model": "gemma3:12b", "size": 8164039587, "digest": "sha256:9e33", "capabilities": ["vision"],
              "details": {"family": "gemma3", "parameter_size": "12.2B", "quantization_level": "Q4_K_M"}},
             {"model": "qwen3.5:9b-q8", "size": 9600000000, "digest": "sha256:9e34", "capabilities": ["tools"],
              "details": {"family": "qwen35", "parameter_size": "9.0B", "quantization_level": "Q8_0"}}]
    base = V.READERS["catalog"]
    V.READERS["catalog"] = lambda h: {"models": base(h)["models"] + extra} if h.name == "box" else base(h)
    V.reset_cache()
    mock.ps_response = {"models": [{"name": "llama3:8b", "model": "llama3:8b", "size": 4_700_000_000,
                                    "size_vram": 4_700_000_000, "expires_at": "2099-01-01T00:00:00Z"}]}
    assert L  # the seed module is the driver's


def advise(c, url, ctx) -> dict:
    seed(ctx)
    c.go(f"{ctx['base']}?mode=local&page=models&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'models'", 40)
    out = {"rows": c.wait(f"{qa(ROWS)}.length >= 2 && {qa(ROWS)}.map((r) => [r.dataset.kind, r.dataset.verb])", 40)}
    out["head"] = c.js(f"{q('[data-testid=local-adviser-head]')}?.textContent || ''")
    out["clis"] = c.js(f"{qa('[data-testid=local-adviser-cli]')}.map((x) => x.textContent)")
    point = q(f"{ROWS}[data-kind=mismatch][data-verb=point]")
    out["point_label"] = c.js(f"{point}?.querySelector('[data-testid=local-adviser-act]')?.textContent || ''")
    before = dict(config(ctx).get("roles") or {})
    press(c, f"{point}.querySelector('[data-testid=local-adviser-act]')", f"!!{point}.querySelector('[data-testid=local-adviser-said]')")
    out["said"] = c.js(f"{point}.querySelector('[data-testid=local-adviser-said]').textContent")
    after = dict(config(ctx).get("roles") or {})
    out["written"] = {k: v for k, v in after.items() if before.get(k) != v}
    page(c, "hosts")
    out["foreign"] = c.wait(f"{card('box', '[data-testid=local-host-foreign]')}?.textContent", 30)
    out["refresh"] = c.js(f"{card('box', '[data-testid=local-host-refresh]')}?.textContent || ''")
    page(c, "resources")
    out["traffic_foreign"] = c.wait(f"{q('[data-testid=local-traffic-foreign-row][data-host=box]')}?.textContent", 30)
    page(c, "steward")
    out["steward"] = c.wait(f"{q('[data-testid=local-steward-refresh-next]')}?.textContent", 30)
    return out


class AdviseDriver(LocalDriver):
    @contextmanager
    def session(self, c):
        with super().session(c) as steps:
            yield ((advise, steps[0][1]),)


if __name__ == "__main__":
    sys.exit(AdviseDriver(sys.argv[1:]).main())
