"""tests.test_host_invariants -- Halo 3.3.7.0 R2 deliverable 4: the host's deterministic invariants
(host/invariants.py; plans/local-model-fit-brief.md H10.6) on fixture cards and a fake Ollama:

1. never load what does not fit: warm / pin / pivot run fit.plan first and refuse with the verdict line, the same
   words the dry preview shows;
2. one resident per card: a second resident is refused unless `beside: true` and the plan says both fit;
3. keep_alive asked is honoured on the load and reported back;
4. the helper's footprint: the card and `route` answers carry usable_gb and usable_with_helper_gb and the line
   "22.0 GB usable; 20.0 GB with the helper (...)"; a warm that needs the helper's room unloads it first.
Run: python -m tests.test_host_invariants
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_act_rig import BIG, CODER, GIB, SMALL, ActRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _card(total_gib: float = 24.0, loaded=None) -> dict:
    from tests.helpers.steward_seed import card
    c = card(total_mib=int(total_gib * 1024), others=[{"name": "ComfyUI", "bytes": 2 * GIB}], kv="f16")
    c["loaded"] = list(loaded or [])
    return c


def _resident(model: str, gb: float, ctx_len: int = 8192) -> dict:
    return {"name": model, "model": model, "size": int(gb * GIB), "size_vram": int(gb * GIB), "context_length": ctx_len,
            "expires_at": "2099-01-01T00:00:00Z"}


@test
def test_never_load_what_does_not_fit(ctx: Ctx):
    with ActRig(card=_card()) as rig:
        status, dry = rig.act("control", "warm", {"model": BIG, "num_ctx": 262144}, dry=True)
        ctx.check(f"the preview says the card would be breached, got {dry.get('breach')!r}", status == 200
                  and str(dry.get("breach") or "").startswith("qwen3.8:27b does not fit pc at 262,144:"))
        status, got = rig.act("control", "warm", {"model": BIG, "num_ctx": 262144})
        ctx.check(f"refused in the same words, nothing sent, got {status} {got}", status == 422
                  and got["error"] == dry["breach"] and rig.mock.generated == [])
        status, got = rig.act("control", "pin", {"model": BIG, "num_ctx": 262144})
        ctx.check("pin: the same invariant", status == 422 and "does not fit" in got["error"])
        status, got = rig.act("control", "set_num_ctx", {"model": BIG, "value": 262144},
                              evidence={"finding": "window-small-1"})
        ctx.check(f"a fix that would breach the card is refused, got {status} {got}", status == 422
                  and "would breach pc's card" in got["error"])
        status, got = rig.act("control", "warm", {"model": "not-here:1b"})
        ctx.check(f"a model the host does not have, got {got}", status == 422 and "is not on pc" in got["error"])


@test
def test_one_resident_per_card(ctx: Ctx):
    with ActRig(card=_card(48.0)) as rig:
        rig.mock.ps_response = {"models": [_resident(CODER, 18.0)]}
        status, got = rig.act("control", "warm", {"model": SMALL, "num_ctx": 8192})
        ctx.check(f"a second resident is refused, got {status} {got}", status == 422 and got["error"].startswith(
            "one resident per card: qwen3-coder:30b is loaded on pc; pivot to qwen3.5:9b") and "beside: true" in got["error"])
        status, got = rig.act("control", "warm", {"model": SMALL, "num_ctx": 8192, "beside": True, "keep_alive": "5m"})
        ctx.check(f"beside, and both fit: loaded, keep_alive reported, got {status} {got}", status == 200 and got["ok"]
                  and got["keep_alive"] == "5m" and rig.mock.generated[-1]["keep_alive"] == "5m")
        status, got = rig.act("control", "pivot", {"from": CODER, "to": SMALL, "num_ctx": 8192})
        ctx.check(f"pivot is the way past it, got {status}", status == 200)
    with ActRig(card=_card(24.0)) as rig:
        rig.mock.ps_response = {"models": [_resident(CODER, 18.0)]}
        status, got = rig.act("control", "warm", {"model": BIG, "num_ctx": 8192, "beside": True})
        ctx.check(f"beside, but they do not fit together: the plan's words, got {status} {got}", status == 422
                  and got["error"].startswith("qwen3.8:27b beside qwen3-coder:30b on pc:"))


@test
def test_the_helpers_footprint_and_eviction(ctx: Ctx):
    helper = _resident(SMALL, 2.0, 4096)
    with ActRig(card=_card(24.0, loaded=[helper])) as rig:
        rig.rig.set_peer(**{"host.steward.enabled": True, "host.steward.model": f"ol:{SMALL}@pc"})
        rig.mock.ps_response = {"models": [dict(helper)]}
        card = rig.client().card(fresh=True)["hosts"][0]
        ctx.check(f"the card: usable and usable with the helper, the line, got {card['footprint']!r}",
                  card["usable_gb"] == 22.0 and card["usable_with_helper_gb"] == 20.0
                  and card["footprint"] == "22.0 GB usable; 20.0 GB with the helper (qwen3.5:9b, 2.0 GB)")
        r = rig.client().route({"model": CODER, "window": 8192})
        ctx.check(f"route carries them too, got {r.get('footprint')!r}", r["usable_with_helper_gb"] == 20.0
                  and "with the helper" in r["footprint"])
        status, got = rig.act("control", "warm", {"model": CODER, "num_ctx": 32768})
        sent = [(g["model"], g["keep_alive"]) for g in rig.mock.generated]
        ctx.check(f"the helper is not a second resident and is evicted when the card is needed, got {status} {sent}",
                  status == 200 and sent[0] == (SMALL, 0) and sent[-1][0] == CODER and got["evicted"] == SMALL)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
