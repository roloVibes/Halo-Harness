"""tests.test_bundle_fit -- Halo 3.3.7.0 R5: the honest verdict (halo_harness/local_sched/bundle_fit.py,
bundle_needs.py, bundle_options.py; plans/local-model-fit-brief.md L3, L7), on the fixture 24 GB card (ComfyUI holding
2 GiB: 22.0 GB usable; tests/helpers/bundle_rig.BundleHome) with the coder qwen3-coder:30b (18.9 GB at 32 k):

1. the glasses bundle is ready: "fits today -- 1.2 GB reserved leaves ~20.8 GB, the coder (18.9 GB) still fits beside
   it, barely", STT and TTS on the CPU (no VRAM), and the option line "GPU STT ... would break that";
2. with lfm3:1.7b not pulled it is "needs 1 download", the one button names the tag, nothing downloads;
3. a bundle that won't work says what it needs against what there is and three ways out or more, each a number;
4. the latency from a speed card, against the bundle's budget;
5. another bundle's claim counts: the coder no longer fits beside, task work goes to routing.escalation's cloud model,
   and "turn ... off" is a way out;
6. `halo pack verdict` and `halo pack list --bundles` print it (nothing pulled); GET pack/bundles answers it;
7. through a paired halo host the verdict reads the host's `route` (R2's PeerRig).
Run: python -m tests.test_bundle_fit
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.bundle_rig import LFM, BundleHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
WONT = {"id": "talker", "name": "Talker", "needs": {
    "chat": {"any_of": ["qwen3.5:9b", "qwen2.5:1.5b"], "window": 32768, "device": "gpu", "vision": False, "tools": False,
             "runtime": "ollama"},
    "stt": {"any_of": ["faster-whisper:large-v3-turbo"], "window": None, "device": "gpu", "vision": False, "tools": False,
            "runtime": "voice"}},
    "reservation": {"model": "qwen3.5:9b", "role": "chat", "vram_gb": None, "keep_alive": -1, "priority": "high",
                    "window": 32768},
    "routing": {"task_work": "coder", "never_evict": "reserved", "escalation": "on"}, "latency_budget_ms": None}


def _glasses(h):
    from halo_harness.local_sched.bundle_fit import verdict
    from halo_harness.packs.bundles import find
    return verdict(find("meta-glasses", cwd=h.repo)["block"], h.host, state_dir=h.state)


@test
def test_the_glasses_bundle_fits_today_barely(ctx: Ctx):
    with BundleHome() as h:
        v = _glasses(h)
        ctx.check(f"ready, got {v['state']}: {v['says']}", v["state"] == "ready")
        ctx.check(f"the brief's line, got {v['says']!r}", v["says"].startswith(
            "fits today -- 1.2 GB reserved leaves ~20.8 GB, the coder (18.9 GB) still fits beside it, barely"))
        ctx.check("speech on the CPU, no VRAM, said", "stt (faster-whisper:small.en) and tts (kokoro-82m) on the CPU: no VRAM"
                  in v["says"])
        warn = [o for o in v["options"] if o["kind"] == "warn"]
        ctx.check(f"GPU STT would break that, got {warn}", warn and warn[0]["says"] == (
            "GPU STT (faster-whisper:large-v3-turbo, 1.5 GB) would break that: the coder would no longer fit beside it")
            and warn[0]["frees_gb"] == -1.5)
        ctx.check(f"the numbers, got {v['usable_gb']} {v['free_gb']} {v['coder']}", v["usable_gb"] == 22.0
                  and v["coder"]["gb"] == 18.9 and v["coder"]["beside"] and 0 <= v["coder"]["spare_gb"] < 2.0)
        ctx.check("no latency yet: said with the bench line", "latency not measured yet" in v["says"]
                  and "halo local bench lfm3:1.7b" in v["says"])
        ctx.check(f"no download, no button, got {v['downloads']} {v['button']}", not v["downloads"] and v["button"] is None)


@test
def test_needs_a_download_and_one_button(ctx: Ctx):
    with BundleHome(lfm=False) as h:
        v = _glasses(h)
        ctx.check(f"needs 1 download, got {v['state']}: {v['says']}", v["state"] == "downloads"
                  and v["says"].startswith("needs 1 download (size not known yet): lfm3:1.7b"))
        ctx.check(f"the one button names the tag, got {v['button']}", v["button"]["tags"] == [LFM]
                  and v["button"]["host"] == "pc" and v["button"]["label"].startswith("download 1"))
        ctx.check("then the fit line", "then fits today -- 1.2 GB reserved" in v["says"])
        ctx.check("an installed model like it is named", any(o["kind"] == "instead" for o in v["options"]))
        ctx.check(f"nothing was pulled, got {h.mock.pulled}", h.mock.pulled == [])


@test
def test_a_bundle_that_wont_work_and_its_ways_out(ctx: Ctx):
    from halo_harness.local_sched.bundle_fit import verdict
    with BundleHome() as h:
        v = verdict(WONT, h.host, state_dir=h.state)
        ctx.check(f"won't work, got {v['state']}: {v['says']}", v["state"] == "wont")
        ctx.check(f"what it needs against what there is, got {v['says']!r}",
                  re.match(r"won't work -- this bundle needs 27\.\d GB; you have 22\.0 GB usable", v["says"]) is not None)
        ways = [o for o in v["options"] if o["kind"] != "warn"]
        ctx.check(f"three ways out or more, got {[o['says'] for o in ways]}", len(ways) >= 3)
        ctx.check("each a number", all(o["frees_gb"] > 0 and re.search(r"\d+(\.\d+)? GB", o["says"]) for o in ways))
        kinds = {o["kind"] for o in ways}
        ctx.check(f"STT on the CPU, the smaller model, a smaller window, got {kinds}", {"device", "smaller", "window"} <= kinds)
        dev = next(o for o in ways if o["kind"] == "device")
        ctx.check(f"the STT line, got {dev['says']!r}", dev["says"] == "run stt on the CPU instead of the GPU (-1.5 GB)")
        small = next(o for o in ways if o["kind"] == "smaller")
        ctx.check(f"the 1.5 B instead of the 9 B, got {small['says']!r}",
                  small["says"].startswith("the 1.5B qwen2.5:1.5b instead of the 9.0B qwen3.5:9b for chat (-5."))


@test
def test_the_latency_from_a_speed_card(ctx: Ctx):
    from halo_harness.providers.local_bench_runs import save
    with BundleHome() as h:
        save(h.state, {"model": LFM, "host": "pc", "digest": "sha256:1f3", "cold_load_s": 2.0, "at": 1,
                       "windows": [{"window": 8192, "tok_s": 120.0, "ttft_ms": 300, "on_gpu": True}]})
        v = _glasses(h)
        ctx.check(f"500 ms: first token 300 + 24 tokens at 120 tok/s, within 1500, got {v['latency_ms']} {v['says']!r}",
                  v["latency_ms"] == 500 and "expected latency ~500 ms" in v["says"]
                  and "(within the 1500 ms budget)" in v["says"])


@test
def test_another_bundles_claim_counts(ctx: Ctx):
    with BundleHome() as h:
        h.config(**{"routing.escalation": {"to": "or:vendor/cloud-model", "when": ["tool_failures"], "ask": False}})
        h.claim("embeddings", "qwen3.5:9b", 2.0)
        v = _glasses(h)
        ctx.check(f"still on (it fits), got {v['state']} {v['says']!r}", v["state"] == "ready")
        ctx.check("the coder no longer fits beside: task work goes to the cloud model", "the coder (18.9 GB) does not fit "
                  "beside it: task work goes to or:vendor/cloud-model while it is on" in v["says"])
        ctx.check(f"the claim is in the budget line, got {v['claims_line']!r}",
                  v["claims_line"] == "2.0 GB reserved for embeddings; 20.0 GB free for tasks")
        ctx.check("turning the other off is a way out", any(o["kind"] == "claims" and "halo pack off embeddings" in o["says"]
                                                             for o in v["options"]))


@test
def test_the_cli_and_the_studio_route(ctx: Ctx):
    with BundleHome() as h:
        code, out, err = h.pack("verdict", "meta-glasses")
        ctx.check(f"halo pack verdict, got {code} {out!r} {err!r}", code == 0
                  and out.startswith("meta-glasses on pc: ready\n  fits today -- 1.2 GB reserved"))
        code, out, _e = h.pack("verdict", "meta-glasses", "--json")
        ctx.check("--json", code == 0 and json.loads(out)["state"] == "ready")
        code, out, _e = h.pack("list", "--bundles")
        lines = out.strip().splitlines()
        ctx.check(f"list --bundles: eleven (3.3.8.0 R4: big-reasoner, 3.3.9.0 R2: voice-local), off, each with its state, "
                  f"got {lines}", len(lines) == 11
                  and all(ln.startswith("[ ] ") for ln in lines) and any("meta-glasses" in ln and "ready" in ln for ln in lines))
        code, _o, err = h.pack("verdict", "nosuch")
        ctx.check(f"an unknown bundle, got {code} {err!r}", code == 1 and "no bundle 'nosuch'" in err)
        status, body = h.studio("GET", "pack/bundles")
        ids = [b["id"] for b in body.get("bundles") or []]
        ctx.check(f"GET pack/bundles: the eleven with their verdicts, got {status} {ids}", status == 200 and len(ids) == 11
                  and next(b for b in body["bundles"] if b["id"] == "meta-glasses")["verdict"]["state"] == "ready")
        ctx.check(f"nothing pulled, got {h.mock.pulled}", h.mock.pulled == [])


@test
def test_through_a_paired_halo_host(ctx: Ctx):
    from halo_harness.local_sched.bundle_fit import verdict
    from halo_harness.packs.bundles import find
    from halo_harness.providers.ollama import OllamaHost
    from tests.helpers.host_act_rig import PeerRig
    with PeerRig() as rig:
        host = OllamaHost(name="pc", url=rig.peer_url)
        v = verdict(find("compactor", cwd=Path(rig.rig.root_p))["block"], host, state_dir=rig.peer)
        ctx.check(f"via the host's route, got {v['via']} {v['state']} {v['says']!r}", v["via"] == "host"
                  and v["state"] in ("ready", "downloads", "wont"))
        paths = [str(a.get("path") or "") for a in rig.rig.audit_rows(1, path="route")]  # the line lands after the reply
        ctx.check(f"the host answered route, got {paths[-3:]}", any(p.endswith("route") for p in paths))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
