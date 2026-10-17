"""tests.test_media_models -- the media-model inventory (Halo 3.0.4.0 round
R2): `providers.media_models` classifies ComfyUI's model files by what they
produce (the live file list is the fixture), `scan` writes
`~/.halo/media-models.json` from tests/helpers/fake_comfy.py, `best_for_media`
ranks (bf16 over int8, the 4-step LoRA chip), `halo models --media` and
`--best-for video-gen` print it, Studio's `get_models?media=1` returns it, and
no LLM row, picker row or Design ranking ever carries a `comfy:` ref.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.fake_comfy import FakeComfy, fixture  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
TTS_NODE = {"IndexTTSEngineNode": {"category": "TTS Audio Suite/Engines", "input": {}, "output": ["TTS_ENGINE"]}}


def _state():
    from halo_harness.config.paths import bridge_home
    d = Path(bridge_home())
    d.mkdir(parents=True, exist_ok=True)
    (d / "media-models.json").unlink(missing_ok=True)
    return d


@contextlib.contextmanager
def _comfy_env(url):
    saved = os.environ.get("COMFY_URL")
    os.environ["COMFY_URL"] = url
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("COMFY_URL", None)
        else:
            os.environ["COMFY_URL"] = saved


def _models_cli(*argv):
    from halo_harness.catalog_cli import cmd_models
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cmd_models(list(argv))
    return rc, out.getvalue(), err.getvalue()


def _row(file, kind, family, quant, size, folder="diffusion_models"):
    return {"ref": "comfy:" + file, "provider": "comfyui", "folder": folder, "file": file, "kind": kind, "family": family,
            "quant": quant, "size_bytes": size, "modalities_in": [], "modalities_out": []}


@test
def test_classification_table(ctx: Ctx):
    from halo_harness.providers.media_models import classify
    oi = {"IndexTTSEngineNode": TTS_NODE["IndexTTSEngineNode"]}

    def one(folder, name):
        return classify(folder, name, oi)

    k, (mi, mo), fam, q = one("diffusion_models", "qwen_image_2.1_bf16.safetensors")
    ctx.check(f"qwen image bf16 is image-gen, text in, image out: {k, mi, mo, fam, q}", (k, mi, mo, fam, q) == ("image-gen", ["text"], ["image"], "qwen-image", "bf16"))
    k, _m, fam, q = one("diffusion_models", "qwen_image_2.1_int8_convrot.safetensors")
    ctx.check("qwen image int8 is image-gen int8", (k, fam, q) == ("image-gen", "qwen-image", "int8"))
    k, (mi, mo), fam, q = one("diffusion_models", "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors")
    ctx.check(f"wan2.2 i2v fp8 is video-gen with image in: {k, mi, mo, q}", k == "video-gen" and "image" in mi and mo == ["video"] and q == "fp8" and fam == "wan")
    k, (mi, mo), fam, q = one("diffusion_models", "wan2.2_s2v_14B_fp8_scaled.safetensors")
    ctx.check("wan2.2 s2v is video-gen with audio in", k == "video-gen" and "audio" in mi and "image" not in mi)
    k, _m, fam, q = one("diffusion_models", "Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors")
    ctx.check("Wan2_1 I2V fp8 e4m3fn is video-gen fp8", (k, q) == ("video-gen", "fp8"))
    k, _m, fam, q = one("diffusion_models", "wan2.1_14B_SCAIL_2_int8_convrot.safetensors")
    ctx.check("SCAIL is video-gen int8", (k, q) == ("video-gen", "int8"))
    k, _m, fam, q = one("diffusion_models", "seedvr2_7b_int8_convrot.safetensors")
    ctx.check("seedvr2 7b int8 is upscale", (k, fam, q) == ("upscale", "seedvr", "int8"))
    ctx.check("an upscale_models file is upscale", one("upscale_models", "4x_foo.pth")[0] == "upscale")
    ctx.check("lightx2v loras are lora", one("loras", "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors")[0] == "lora")
    ctx.check("umt5_xxl and qwen3vl are encoders", one("text_encoders", "umt5_xxl_fp8_e4m3fn_scaled.safetensors")[0] == "encoder"
              and one("text_encoders", "qwen3vl_8b_int8_convrot.safetensors")[0] == "encoder")
    ctx.check("clip_vision and audio_encoders are encoders", one("clip_vision", "clip_vision_h.safetensors")[0] == "encoder"
              and one("audio_encoders", "wav2vec2_large_english_fp16.safetensors")[0] == "encoder")
    ctx.check("vaes are vae", one("vae", "Wan2_1_VAE_bf16.safetensors")[0] == "vae" and one("vae", "wan_2.1_vae.safetensors")[3] == "unknown")
    ctx.check("sam3.1 in checkpoints is other", one("checkpoints", "sam3.1_multiplex_fp16.safetensors")[0] == "other")
    ctx.check("a TTS file is tts with a TTS engine node on the server", classify("TTS", "IndexTTS\\a\\gpt.pth", oi)[0] == "tts")
    ctx.check("a TTS file is other without a TTS node class", classify("TTS", "IndexTTS\\a\\gpt.pth", {})[0] == "other")


@test
def test_scan_writes_the_cache(ctx: Ctx):
    from halo_harness.media.comfy_client import ComfyClient
    from halo_harness.providers import media_models as MM
    state = _state()
    with FakeComfy() as fake:
        fake.object_info.update(TTS_NODE)
        fake.model_files["custom_nodes"] = ["node.py"]
        fake.model_files["configs"] = ["a.yaml"]
        fake.model_sizes["qwen_image_2.1_bf16.safetensors"] = 14_230_280_616
        rows = MM.scan(ComfyClient(fake.url, timeout=10), state)
        ctx.check("custom_nodes and configs are left out", not any(r["folder"] in ("custom_nodes", "configs") for r in rows))
        by = {r["file"]: r for r in rows}
        q = by["qwen_image_2.1_bf16.safetensors"]
        ctx.check(f"a row has the spec'd fields: {q}", q["ref"] == "comfy:qwen_image_2.1_bf16.safetensors" and q["provider"] == "comfyui"
                  and q["local"] is True and q["price_in_per_m"] == 0 and q["price_out_per_m"] == 0 and q["size_bytes"] == 14_230_280_616
                  and q["kind"] == "image-gen" and q["quant"] == "bf16" and q["family"] == "qwen-image" and q["folder"] == "diffusion_models")
        kinds = {k: sorted(r["file"] for r in rows if r["kind"] == k) for k in MM.GENERATORS + MM.SUPPORTING}
        ctx.check(f"2 image-gen, 5 video-gen, 1 upscale, got {[(k, len(v)) for k, v in kinds.items()]}",
                  len(kinds["image-gen"]) == 2 and len(kinds["video-gen"]) == 5 and len(kinds["upscale"]) == 1)
        ctx.check("the TTS files collapse to one row per engine folder", kinds["tts"] == ["IndexTTS"] and by["IndexTTS"]["ref"] == "comfy:IndexTTS"
                  and "engine node IndexTTSEngineNode" in by["IndexTTS"]["notes"])
        ctx.check("the supporting kinds are listed", len(kinds["lora"]) == 6 and len(kinds["vae"]) == 4 and len(kinds["encoder"]) == 5)
        doc = MM.load_cached(state)
        ctx.check("the cache has scanned, url, rows and the saved workflow names", doc["url"] == fake.url and doc["scanned"] > 0
                  and len(doc["rows"]) == len(rows) and "Fixture UI workflow.json" in doc["workflows"])
        ctx.check("rows_for filters by kind and takes the audio-gen alias", [r["file"] for r in MM.rows_for("upscale", state)] == kinds["upscale"]
                  and [r["file"] for r in MM.rows_for("audio-gen", state)] == ["IndexTTS"] and len(MM.rows_for("all", state)) == len(rows))
    ctx.check("load_cached of a missing cache is {} and rows_for is []", MM.load_cached(state / "nope") == {} and MM.rows_for("image-gen", state / "nope") == [])


@test
def test_best_for_media_order(ctx: Ctx):
    from halo_harness.capabilities import OUTPUT_KINDS, best_for_media
    rows = [_row("qwen_image_2.1_int8.safetensors", "image-gen", "qwen-image", "int8", 7_000_000_000),
            _row("qwen_image_2.1_bf16.safetensors", "image-gen", "qwen-image", "bf16", 14_000_000_000),
            _row("wan2.2_i2v_low_noise_14B_fp8.safetensors", "video-gen", "wan", "fp8", 14_000_000_000),
            _row("wan2.2_s2v_14B_fp8.safetensors", "video-gen", "wan", "fp8", 14_000_000_000),
            _row("wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors", "lora", "wan", "bf16", 1_000_000_000, "loras")]
    ctx.check("OUTPUT_KINDS names the four output kinds", OUTPUT_KINDS == ("image-gen", "video-gen", "audio-gen", "upscale"))
    img = best_for_media(rows, "image-gen")
    ctx.check(f"bf16 ranks over int8 of the same family: {[r['ref'] for r in img]}", [r["ref"] for r in img][0].endswith("bf16.safetensors") and len(img) == 2)
    ctx.check("each ranked row has a one-line reason with size and quant", "14.0 GB" in img[0]["reason"] and "bf16" in img[0]["reason"] and "\n" not in img[0]["reason"])
    vid = best_for_media(rows, "video-gen")
    ctx.check("a 4-step LoRA for the family adds the speed chip (and only to the i2v row)",
              "4-step" in vid[0]["chips"] and vid[0]["ref"].endswith("i2v_low_noise_14B_fp8.safetensors") and "4-step" not in vid[1]["chips"])
    ctx.check("supporting rows are never ranked", not any(r["kind"] == "lora" for r in vid + img) and best_for_media(rows, "upscale") == [])
    try:
        best_for_media(rows, "design")
        ctx.check("an input kind is rejected", False)
    except ValueError:
        ctx.check("an input kind is rejected", True)


@test
def test_models_cli_media_and_best_for(ctx: Ctx):
    _state()
    with FakeComfy() as fake, _comfy_env(fake.url):
        fake.object_info.update(TTS_NODE)
        rc, out, err = _models_cli("--media", "--refresh")
        ctx.check(f"--media --refresh prints the inventory, rc {rc}: {out[:300]}{err}", rc == 0 and "9 generator(s)" in out and "image-gen (2)" in out
                  and "video-gen (5)" in out and "upscale (1)" in out and "tts (1)" in out and "supporting (listed, never ranked)" in out)
        ctx.check("a line has file, size, quant and family", any("qwen_image_2.1_bf16.safetensors" in ln and "bf16" in ln and "qwen-image" in ln
                                                                 and ("GB" in ln or "MB" in ln) for ln in out.splitlines()))
        ctx.check("lora, vae and encoder groups are printed", "lora (6)" in out and "vae (4)" in out and "encoder (5)" in out)
        n = len(fake.requests)
        rc, out, _e = _models_cli("--media", "video")
        ctx.check("--media video is served from the cache and keeps only video + wan supporting rows",
                  rc == 0 and len(fake.requests) == n and "video-gen (5)" in out and "image-gen" not in out and "tts" not in out and "lightx2v" in out)
        rc, out, _e = _models_cli("--media", "audio")
        ctx.check("--media audio lists tts and the audio encoders", "tts (1)" in out and "wav2vec2_large_english" in out and "video-gen" not in out)
        rc, out, _e = _models_cli("--best-for", "video-gen")
        lines = [ln for ln in out.splitlines() if ln[:3].strip().rstrip(".").isdigit()]
        ctx.check(f"--best-for video-gen ranks the Wan rows: {lines[:2]}", rc == 0 and len(lines) == 5 and all("wan" in ln.lower() for ln in lines) and "Best for video-gen" in out)
        rc, out, _e = _models_cli("--best-for", "audio-gen")
        ctx.check("--best-for audio-gen ranks the TTS row", rc == 0 and "comfy:IndexTTS" in out)
        rc, out, _e = _models_cli("--media", "--json")
        ctx.check("--media --json is the cached document", rc == 0 and '"rows"' in out and '"workflows"' in out)
    from halo_harness.media import cli as media_cli
    with FakeComfy() as fake:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = media_cli.cmd_media(["models", "image", "--url", fake.url])
        ctx.check("halo media models prints through the inventory", rc == 0 and "image-gen (2)" in buf.getvalue() and "upscale (1)" in buf.getvalue()
                  and "video-gen" not in buf.getvalue())
    with _comfy_env("http://127.0.0.1:1"):
        rc, out, err = _models_cli("--media", "--refresh")
        ctx.check("an unreachable server is an error line, rc 1", rc == 1 and "not reachable" in err)


@test
def test_studio_get_models_media(ctx: Ctx):
    from halo_harness.media.comfy_client import ComfyClient
    from halo_harness.providers import media_models as MM
    from halo_harness.studio import design_api
    state = _state()
    with FakeComfy() as fake:
        MM.scan(ComfyClient(fake.url, timeout=10), state)
    req = SimpleNamespace(method="GET", path="design/models", query={"media": "1"}, state_dir=state, body={})
    status, body = design_api.dispatch_design(req)
    ctx.check("get_models?media=1 is {media: rows}", status == 200 and set(body) == {"media"} and len(body["media"]) > 20
              and all(r["ref"].startswith("comfy:") for r in body["media"]))
    status, body = design_api.dispatch_design(SimpleNamespace(method="GET", path="design/models", query={}, state_dir=state, body={}))
    ctx.check("get_models without media is still the design ranking (a list)", status == 200 and isinstance(body, list))
    ctx.check("the design ranking carries no comfy: ref", not any(str(r.get("ref", "")).startswith("comfy:") for r in body))
    # 3.0.7.0 R2: the classic page's model chooser (its "Media models (ComfyUI)" group) went with static/legacy;
    # the routes above are what the React section reads.


@test
def test_no_comfy_ref_in_llm_rows_or_pickers(ctx: Ctx):
    from halo_harness.media.comfy_client import ComfyClient
    from halo_harness.providers import media_models as MM
    from halo_harness.providers.model_enumeration import build_model_rows
    from halo_harness.studio import model as studio_model
    state = _state()
    with FakeComfy() as fake:
        MM.scan(ComfyClient(fake.url, timeout=10), state)
    ctx.check("the cache is on disk", (state / "media-models.json").is_file())
    rows = build_model_rows(state, env=dict(os.environ))
    ctx.check(f"build_model_rows ({len(rows)} rows) has no comfy: ref and no comfyui provider",
              not any(str(r.get("ref", "")).startswith("comfy:") or r.get("provider") == "comfyui" for r in rows))
    srows = studio_model.model_rows(state)
    ctx.check("studio's model rows have no comfy: ref", not any(str(r.get("ref", "")).startswith("comfy:") for r in srows))
    from halo_harness.tui.dialogs.model_picker import ModelPicker, _grouped
    picker = ModelPicker(rows, current="")
    shown = [m.get("ref", "") for m in picker._effective_models()]
    ctx.check("the TUI picker rows (also the roles and org pickers' source) have no comfy: ref",
              not any(r.startswith("comfy:") for r in shown) and not any(str(m.get("ref", "")).startswith("comfy:") for _g, ms in _grouped(picker.models) for m in ms))
    import halo_harness.providers.model_enumeration as me
    import halo_harness.providers.local_models as lm
    src = Path(me.__file__).read_text(encoding="utf-8") + Path(lm.__file__).read_text(encoding="utf-8")
    ctx.check("neither model_enumeration nor local_models imports media_models", "media_models" not in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="media models tests"))
