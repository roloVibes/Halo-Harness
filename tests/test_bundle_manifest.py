"""tests.test_bundle_manifest -- Halo 3.3.7.0 R5: the bundle contract (halo_harness/packs/manifest_bundle.py, the
`bundle:` block of pack.yaml; plans/local-model-fit-brief.md L5):

1. the brief's glasses block validates clean as a pack's `bundle:` and normalizes with its defaults (device gpu,
   priority normal, escalation on; a speech model's runtime is voice; the reservation's role is found);
2. each bad value is one line naming the key: no any_of, a bad window, an unknown device, a reservation naming
   neither a need nor a listed model, a reserved speech model, a bad vram_gb / keep_alive / priority, a bad routing
   value, a bad latency budget, and an unknown key (the shape check names the closest known one);
3. a needs role as the reservation's model resolves to the model the verdict chose (else the need's first any_of);
   `vram_gb` left out stays None (the verdict computes it);
4. the JSON schema twin: pack.schema.json's `bundle` property and `$defs.bundle` is bundle.schema.json's object, and
   its keys are the Python shape's (schemas/pack_yaml.py BUNDLE_KEYS, NEED_KEYS, RESERVATION_KEYS, ROUTING_KEYS);
5. a pack without `bundle:` is no bundle and gets no bundle line.
Run: python -m tests.test_bundle_manifest
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
GLASSES = {"needs": {"chat": {"any_of": ["lfm3:1.7b", "qwen3-coder:30b-gpu"], "window": 8192},
                     "stt": {"any_of": ["faster-whisper:large-v3-turbo", "faster-whisper:small.en"], "device": "cpu-or-gpu"},
                     "tts": {"any_of": ["kokoro-82m"], "device": "cpu"}},
           "reservation": {"model": "lfm3:1.7b", "vram_gb": 1.2, "keep_alive": -1, "priority": "high"},
           "routing": {"task_work": "coder-or-cloud", "never_evict": "reserved"}, "latency_budget_ms": 1500}


def _pack(bundle) -> dict:
    return {"id": "meta-glasses", "name": "Meta glasses", "version": "1.0.0", "halo_api": {"min": "1.0"},
            "bundle": copy.deepcopy(bundle)}


def _lines(bundle) -> list:
    from halo_harness.packs.manifest import validate_manifest
    return validate_manifest(_pack(bundle))


@test
def test_the_glasses_block_validates_and_normalizes(ctx: Ctx):
    from halo_harness.packs.manifest_bundle import block, is_bundle
    ctx.check(f"the brief's block is clean, got {_lines(GLASSES)}", _lines(GLASSES) == [])
    b = block(_pack(GLASSES))
    ctx.check("it is a bundle", is_bundle(_pack(GLASSES)) and b["id"] == "meta-glasses")
    ctx.check(f"needs normalized, got {b['needs']['chat']}", b["needs"]["chat"] == {
        "any_of": ["lfm3:1.7b", "qwen3-coder:30b-gpu"], "window": 8192, "device": "gpu", "vision": False, "tools": False,
        "runtime": "ollama"})
    ctx.check("a speech model's runtime is voice", b["needs"]["stt"]["runtime"] == "voice"
              and b["needs"]["tts"]["device"] == "cpu")
    ctx.check(f"the reservation: its role found, keep_alive -1, its window the need's, got {b['reservation']}",
              b["reservation"] == {"model": "lfm3:1.7b", "role": "chat", "vram_gb": 1.2, "keep_alive": -1,
                                   "priority": "high", "window": 8192})
    ctx.check(f"routing defaults, got {b['routing']}", b["routing"] == {"task_work": "coder-or-cloud",
                                                                         "never_evict": "reserved", "escalation": "on"})
    ctx.check("the latency budget", b["latency_budget_ms"] == 1500)


@test
def test_each_bad_value_is_one_line(ctx: Ctx):
    cases = [
        (("needs", "tts", "any_of"), None, "bundle.needs.tts.any_of: required"),
        (("needs", "chat", "window"), 100, "bundle.needs.chat.window: 100 is not a window"),
        (("needs", "stt", "device"), "npu", "bundle.needs.stt.device: 'npu' is not one of gpu, cpu, cpu-or-gpu"),
        (("reservation", "model"), "nosuch:1b", "bundle.reservation.model: 'nosuch:1b' is neither a needs role"),
        (("reservation", "model"), "kokoro-82m", "is a speech model; a reservation holds an Ollama model"),
        (("reservation", "vram_gb"), -2, "bundle.reservation.vram_gb: -2 is not a size in GB"),
        (("reservation", "keep_alive"), "forever", "bundle.reservation.keep_alive: 'forever' is not -1 or a duration"),
        (("reservation", "priority"), "urgent", "bundle.reservation.priority: 'urgent' is not one of high, normal, low"),
        (("routing", "task_work"), "anywhere", "bundle.routing.task_work: 'anywhere' is not one of coder"),
        (("latency_budget_ms",), 0, "bundle.latency_budget_ms: 0 is not a time in milliseconds"),
    ]
    for path, value, want in cases:
        b = copy.deepcopy(GLASSES)
        node = b
        for k in path[:-1]:
            node = node[k]
        if value is None:
            node.pop(path[-1], None)
        else:
            node[path[-1]] = value
        got = _lines(b)
        ctx.check(f"{'.'.join(path)} = {value!r}: one line with {want!r}, got {got}",
                  len(got) == 1 and want in got[0])
    b = copy.deepcopy(GLASSES)
    b["reservation"]["vram"] = 1.0
    got = _lines(b)
    ctx.check(f"an unknown key is named with the closest known one, got {got}",
              any("vram" in ln and "vram_gb" in ln for ln in got))
    got = _lines("on")
    ctx.check(f"a bundle that is not a mapping, got {got}", any("bundle" in ln for ln in got))


@test
def test_a_needs_role_as_the_reserved_model(ctx: Ctx):
    from halo_harness.packs.manifest_bundle import block, reserved_model
    b = {"needs": {"worker": {"any_of": ["qwen3.5:9b", "qwen3:8b"], "window": 32768}}, "reservation": {"model": "worker"}}
    ctx.check(f"clean, got {_lines(b)}", _lines(b) == [])
    nb = block(_pack(b))
    ctx.check(f"the role is the role, vram_gb left to the verdict, got {nb['reservation']}",
              nb["reservation"]["role"] == "worker" and nb["reservation"]["vram_gb"] is None
              and nb["reservation"]["window"] == 32768 and nb["reservation"]["keep_alive"] == -1)
    ctx.check("the need's first any_of when nothing was chosen", reserved_model(nb) == "qwen3.5:9b")
    ctx.check("the chosen model when the verdict chose one", reserved_model(nb, {"worker": "qwen3:8b"}) == "qwen3:8b")


@test
def test_the_json_schema_twin(ctx: Ctx):
    from halo_harness.schemas import pack_yaml as P
    d = REPO / "halo_harness" / "packs" / "schema"
    pack = json.loads((d / "pack.schema.json").read_text(encoding="utf-8"))
    alone = json.loads((d / "bundle.schema.json").read_text(encoding="utf-8"))
    body = {k: v for k, v in alone.items() if k not in ("$schema", "$id", "title")}
    ctx.check("pack.schema.json has the bundle property", pack["properties"]["bundle"]["$ref"] == "#/$defs/bundle")
    ctx.check("$defs.bundle is bundle.schema.json's object", pack["$defs"]["bundle"] == body)
    ctx.check("the top-level keys", tuple(body["properties"]) == P.BUNDLE_KEYS)
    ctx.check("the need keys", tuple(body["properties"]["needs"]["additionalProperties"]["properties"]) == P.NEED_KEYS)
    ctx.check("the reservation keys", tuple(body["properties"]["reservation"]["properties"]) == P.RESERVATION_KEYS)
    ctx.check("the routing keys", tuple(body["properties"]["routing"]["properties"]) == P.ROUTING_KEYS)
    from halo_harness.packs import manifest_bundle as M
    ctx.check("the device and routing enums match the Python's",
              tuple(body["properties"]["needs"]["additionalProperties"]["properties"]["device"]["enum"]) == M.DEVICES
              and tuple(body["properties"]["routing"]["properties"]["task_work"]["enum"]) == M.TASK_WORK)


@test
def test_a_pack_without_a_bundle(ctx: Ctx):
    from halo_harness.packs.manifest_bundle import block, bundle_lines, is_bundle
    plain = {"id": "plain", "name": "Plain", "version": "1.0.0", "halo_api": {"min": "1.0"}}
    ctx.check("no bundle, no line", not is_bundle(plain) and block(plain) is None and bundle_lines(plain) == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
