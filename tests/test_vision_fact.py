"""tests.test_vision_fact -- Halo 3.3.6.0 R6: which models can see, as one fact with one of three truths
(providers/vision_fact.py), and the battery's vision probe (providers/battery_probes.vision_turn) on the scripted
fake Ollama (tests/helpers/mock_ollama_eyes.py):

1. the probe's three outcomes: verified yes on the colour, verified no on an answer that says it cannot see and on
   a server error naming image input, unverified on a wrong colour; a thinking model re-asked at 600; a model whose
   /api/show lists no vision is not asked (its declared no stands); no capabilities list at all is asked;
2. the probe is cached by digest + Ollama version + probe set (battery-3): a second run sends no image;
3. the order: the probe over /api/show, /api/show and a projector (declared), Hugging Face configs (fixtures:
   vision_config, an image processor, a VL architecture; a CausalLM is a declared no), the cloud catalog's
   modalities, the family rule (expected, a yes only), else unknown;
4. the four homes agree: the card (`vision`, `vision_truth`, `sources.vision`), truth_rules.vision, the eyes
   placement verdict, the measured modality; the card's blocks say "reads images" / "cannot see images".
Run: python -m tests.test_vision_fact
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.battery_rig import BatteryRig  # noqa: E402
from tests.helpers import mock_ollama_eyes as ME  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FIX = Path(__file__).resolve().parent / "fixtures" / "vision"


def _rig():
    rig = BatteryRig(["bt-coder:30b"]).__enter__()
    ME.add(rig.mock)
    return rig


@test
def test_the_probe_outcomes(ctx: Ctx):
    rig = _rig()
    try:
        want = {"ey-sees:7b": "yes", "ey-blind:7b": "no", "ey-refuse:7b": "no", "ey-odd:7b": "unverified",
                "ey-think:7b": "yes", "ey-text:7b": "not asked", "ey-old:7b": "yes"}
        got = {n: rig.probe(n) for n in want}
        for n, w in want.items():
            ctx.check(f"{n}: vision {w}, got {got[n].get('vision')} ({got[n].get('vision_why')})", got[n].get("vision") == w)
        ctx.check(f"the refusal names what the server said, got {got['ey-refuse:7b']['vision_why']}",
                  "missing data required for image input" in got["ey-refuse:7b"]["vision_why"])
        sent = ME.images_sent(rig.mock)
        ctx.check(f"the text model is never shown the image, got {sent}", not any(n == "ey-text:7b" for n, _c in sent))
        think = [c for n, c in sent if n == "ey-think:7b"]
        ctx.check(f"the thinker is re-asked at 600 tokens, got {think}", think == [24, 600])
        ctx.check(f"one tiny call for a model that answers, got {[c for n, c in sent if n == 'ey-sees:7b']}",
                  [c for n, c in sent if n == "ey-sees:7b"] == [24])
        body = next(r["body"] for r in rig.mock.requests if r.get("path") == "/api/chat"
                    and any(m.get("images") for m in r["body"].get("messages") or []))
        from halo_harness.providers.battery_probes import VISION_PNG
        import base64
        png = base64.b64decode(body["messages"][0]["images"][0])
        ctx.check(f"the image is the module's 1 px PNG, got {len(png)} bytes", png == VISION_PNG and png[:4] == b"\x89PNG")
        from halo_harness.tools.imageutil import sniff_dimensions
        ctx.check(f"1 x 1, got {sniff_dimensions(png)}", sniff_dimensions(png) == (1, 1))
        ev = got["ey-text:7b"]["evidence"]["vision"]
        ctx.check(f"the evidence says why it was not asked, got {ev}", "no vision" in ev.get("skipped", ""))
        from halo_harness.providers.battery_profile import summary_line
        ctx.check(f"the summary says it sees, got {summary_line(got['ey-sees:7b'])}", "sees" in summary_line(got["ey-sees:7b"]))
    finally:
        rig.__exit__(None, None, None)


@test
def test_the_probe_is_cached_by_digest_version_and_probe_set(ctx: Ctx):
    from halo_harness.providers import battery_probes as B
    rig = _rig()
    try:
        ctx.check(f"the probe set moved to battery-3, got {B.PROBE_SET}", B.PROBE_SET == "battery-3")
        rig.probe("ey-sees:7b")
        n = len(ME.images_sent(rig.mock))
        again = rig.probe("ey-sees:7b")
        ctx.check(f"a second run is the cache, no image sent, got cached={again.get('cached')}",
                  again.get("cached") is True and len(ME.images_sent(rig.mock)) == n and again.get("vision") == "yes")
        rig.probe("ey-sees:7b", force=True)
        ctx.check("force sends it again", len(ME.images_sent(rig.mock)) == n + 1)
        from halo_harness.providers.capability_battery import cost_line
        ctx.check(f"the cost line says one 1 px image, got {cost_line('m', 'h')}", "one 1 px image, one tiny call" in cost_line("m", "h"))
    finally:
        rig.__exit__(None, None, None)


@test
def test_the_order_and_the_hf_configs(ctx: Ctx):
    from halo_harness.providers.vision_fact import hf_config_vision, line, vision_of, word
    cfg = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in FIX.glob("*.json")}
    ctx.check(f"three fixtures, got {sorted(cfg)}", sorted(cfg) == ["llama_causal", "llava_processor", "qwen2_5_vl"])
    ctx.check("a vision_config is declared vision", hf_config_vision(cfg["qwen2_5_vl"])[0] is True)
    ctx.check("an image processor is declared vision", hf_config_vision(cfg["llava_processor"])[0] is True)
    no = hf_config_vision(cfg["llama_causal"])
    ctx.check(f"a CausalLM is a declared no, got {no}", no[0] is False and "text only" in no[1])
    hf = vision_of({"name": "org/some-model"}, {"config": cfg["qwen2_5_vl"]}, None)
    ctx.check(f"the HF config on a row, got {hf}", hf["value"] is True and hf["truth"] == "declared")
    probe = {"vision": "no", "vision_why": "it said it cannot see", "probed_at": 1.0}
    ctx.check("the probe wins over /api/show", vision_of(None, {"capabilities": ["completion", "vision"]}, probe)["truth"] == "verified"
              and vision_of(None, {"capabilities": ["completion", "vision"]}, probe)["value"] is False)
    ctx.check("an unverified probe leaves the declared fact",
              vision_of(None, {"capabilities": ["vision"]}, {"vision": "unverified"})["truth"] == "declared")
    show_no = vision_of(None, {"capabilities": ["completion", "tools"]}, None)
    ctx.check(f"/api/show without vision is a declared no, got {show_no}", show_no["value"] is False and show_no["truth"] == "declared")
    proj = vision_of(None, {"projector_bytes": 12345}, None)
    ctx.check(f"a projector is declared, got {proj}", proj["value"] is True and "projector" in proj["source"])
    cloud = vision_of(None, {"modalities_in": ["text", "image"]}, None)
    ctx.check(f"the cloud catalog's modalities, got {cloud}", cloud["value"] is True and cloud["source"] == "the catalog's modalities")
    fam = vision_of({"name": "llava:13b"}, None, None)
    ctx.check(f"the family rule is expected, got {fam}", fam["value"] is True and fam["truth"] == "expected")
    small = vision_of({"name": "gemma3:1b"}, None, None)
    ctx.check(f"gemma3:1b names no vision, got {small}", small["value"] is None)
    ctx.check("gemma3:12b is a vision family", vision_of({"name": "gemma3:12b"}, None, None)["value"] is True)
    unknown = vision_of({"name": "mystery:7b"}, None, None)
    ctx.check(f"nothing says: unknown, got {unknown}", unknown["value"] is None and unknown["truth"] is None)
    ctx.check("the chip words", (word(fam), word(show_no), word(unknown)) == ("sees", "no eyes", "eyes?"))
    ctx.check(f"the lines, got {line(show_no)}", line(show_no).startswith("cannot see images (declared")
              and line(unknown, "ol:x@h").endswith("(halo models probe ol:x@h settles it)"))


@test
def test_the_four_homes_agree(ctx: Ctx):
    from halo_harness.models_library.truth_rules import vision as truth_vision
    from halo_harness.providers.measured import _modality
    from halo_harness.providers.model_card import card_of
    from halo_harness.providers.placement import verdict
    from halo_harness.providers.ollama import get_catalog
    rig = _rig()
    try:
        cat = get_catalog(rig.host)
        for name, want in (("ey-sees:7b", True), ("ey-blind:7b", False)):
            p = rig.probe(name)
            card = card_of(rig.ref(name), state_dir=rig.state, host=rig.host, catalog=cat)
            ctx.check(f"{name}: the card says {want} (verified), got {card['vision']} {card.get('vision_truth')} {card['sources']['vision']}",
                      card["vision"] is want and card["vision_truth"] == "verified" and "image probe" in card["sources"]["vision"])
            t = truth_vision({}, card, p)
            ctx.check(f"{name}: truth_rules agrees, got {t}", t["value"] is want and t["truth"] == "verified")
            v = verdict(p, "visual")
            ctx.check(f"{name}: the eyes verdict, got {v}", (v["ok"] is not False) is want)
            m = _modality(p)
            ctx.check(f"{name}: the measured modality, got {m}", ("images" in str(m.get("value"))) is want and "verified" in str(m.get("source")))
            text = [x["text"] for x in (card["blocks"]["use_for"] + card["blocks"]["dont_use_for"])]
            ctx.check(f"{name}: the blocks, got {text}", ("reads images" in text) is want and ("cannot see images" in text) is (not want))
            ctx.check(f"{name}: eyes fit, got {card['fit_for']['eyes']}", card["fit_for"]["eyes"] is want)
        text_card = card_of(rig.ref("ey-text:7b"), state_dir=rig.state, host=rig.host, catalog=cat)
        ctx.check(f"a declared no on the card, got {text_card['vision']} {text_card['vision_truth']}",
                  text_card["vision"] is False and text_card["vision_truth"] == "declared")
    finally:
        rig.__exit__(None, None, None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
