"""tests.test_bundles_shipped -- Halo 3.3.7.0 R5: the bundles Halo ships (halo_harness/templates/bundles/<id>/pack.yaml;
plans/local-model-fit-brief.md L6), on the fixture 24 GB card and roster (tests/helpers/bundle_rig.BundleHome):

1. the eleven: meta-glasses (the brief's any_of lists and reservation), bulk-worker, verifier, compactor, embeddings,
   translation, vision, offline-only, coder-first, (3.3.8.0 R4) big-reasoner and (3.3.9.0 R2) voice-local -- each
   validates clean and is named by its folder;
2. each gets a verdict on the fixture roster (ready, needs downloads or won't work; none "not judged") and none
   downloads (the fake's pulls stay empty);
3. the verifier is of another family than the coder (the adviser's mismatch rule: no qwen for a qwen coder); vision
   takes only a model that sees; offline-only reserves nothing and turns the cloud rung off while it is on;
   coder-first reserves nothing and judges the coder alone;
4. the shipped bundles ship as package data (pyproject's templates/bundles/*/pack.yaml).
Run: python -m tests.test_bundles_shipped
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.bundle_rig import BundleHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
SHIPPED = ("big-reasoner", "bulk-worker", "coder-first", "compactor", "embeddings", "meta-glasses", "offline-only",
        "translation", "verifier", "vision", "voice-local")  # 3.3.8.0 R4: big-reasoner; 3.3.9.0 R2: voice-local


@test
def test_the_eleven_validate(ctx: Ctx):
    from halo_harness.packs.bundles import shipped_dir
    from halo_harness.packs.discover import read_pack
    from halo_harness.packs.manifest_bundle import block
    folders = sorted(d.name for d in shipped_dir().iterdir() if (d / "pack.yaml").is_file())
    ctx.check(f"eleven bundles ship, got {folders}", tuple(folders) == SHIPPED)
    for name in folders:
        pack = read_pack(shipped_dir() / name, "source", folder_is_id=True)
        ctx.check(f"{name} validates clean, got {pack.problems}", pack.problems == [] and pack.id == name
                  and block(pack) is not None)
    g = block(read_pack(shipped_dir() / "meta-glasses", "source"))
    ctx.check(f"the glasses bundle is the brief's, got {g['needs']} {g['reservation']}",
              g["needs"]["chat"]["any_of"] == ["lfm3:1.7b", "qwen3-coder:30b-gpu"] and g["needs"]["chat"]["window"] == 8192
              and g["needs"]["stt"]["any_of"] == ["faster-whisper:large-v3-turbo", "faster-whisper:small.en"]
              and g["needs"]["stt"]["device"] == "cpu-or-gpu" and g["needs"]["tts"] == {
                  "any_of": ["kokoro-82m"], "window": None, "device": "cpu", "vision": False, "tools": False, "runtime": "voice"}
              and g["reservation"]["model"] == "lfm3:1.7b" and g["reservation"]["vram_gb"] == 1.2
              and g["reservation"]["priority"] == "high" and g["latency_budget_ms"] == 1500
              and g["routing"]["task_work"] == "coder-or-cloud")


@test
def test_each_gets_a_verdict_and_none_downloads(ctx: Ctx):
    from halo_harness.local_sched.bundle_fit import verdict
    from halo_harness.packs.bundles import listing
    with BundleHome() as h:
        got = {e["id"]: verdict(e["block"], h.host, state_dir=h.state) for e in listing(cwd=h.repo)}
        ctx.check(f"all eleven, got {sorted(got)}", tuple(sorted(got)) == SHIPPED)
        for bid, v in sorted(got.items()):
            ctx.check(f"{bid}: a verdict on the fixture roster, got {v['state']}: {v['says']}",
                      v["state"] in ("ready", "downloads", "wont") and v["says"])
        ready = ("meta-glasses", "voice-local", "compactor", "coder-first", "offline-only")
        ctx.check(f"the glasses, voice-local, the compactor, coder-first, offline-only are ready here, got "
                  f"{[(b, got[b]['state']) for b in ready]}", all(got[b]["state"] == "ready" for b in ready))
        ctx.check(f"the embeddings need a download (the button names it), got {got['embeddings']['button']}",
                  got["embeddings"]["state"] == "downloads" and got["embeddings"]["button"]["tags"] == ["nomic-embed-text"])
        ctx.check(f"nothing was pulled, got {h.mock.pulled}", h.mock.pulled == [] and not any(
            "/api/pull" in str(r.get("path")) for r in h.mock.requests if isinstance(r, dict)))


@test
def test_the_rules_each_bundle_carries(ctx: Ctx):
    from halo_harness.agent.escalation import load_escalation_policy
    from halo_harness.local_sched.bundle_fit import verdict
    from halo_harness.packs.bundles import find
    with BundleHome() as h:
        v = verdict(find("verifier", cwd=h.repo)["block"], h.host, state_dir=h.state)
        pick = next(n for n in v["needs"] if n["role"] == "verify")
        ctx.check(f"the verifier is not of the coder's (qwen) family, got {pick['tag']}: {pick['why']}",
                  pick["tag"] and not pick["tag"].startswith("qwen") and "the coder's family (qwen)" in pick["why"])
        v = verdict(find("vision", cwd=h.repo)["block"], h.host, state_dir=h.state)
        see = next(n for n in v["needs"] if n["role"] == "see")
        ctx.check(f"vision skips qwen3.5:9b (its row has no vision) for one that sees, got {see['tag']}: {see['why']}",
                  see["tag"] == "gemma3:12b" and "qwen3.5:9b: its profile says vision: no" in see["why"])
        v = verdict(find("coder-first", cwd=h.repo)["block"], h.host, state_dir=h.state)
        ctx.check(f"coder-first reserves nothing, judges the coder alone, got {v['says']!r}", v["reserved"] is None
                  and v["says"].startswith("fits today -- nothing reserved") and v["coder"] is None)
        h.config(**{"routing.escalation": {"to": "or:vendor/cloud-model", "when": ["tool_failures"], "ask": False}})
        ctx.check("a cloud policy before", load_escalation_policy() is not None)
        code, out, err = h.pack("on", "offline-only")
        ctx.check(f"offline-only on: nothing reserved, the cloud rung off, got {code} {out!r} {err!r}", code == 0
                  and "offline-only is on: nothing reserved" in out and "no cloud rung" in out
                  and load_escalation_policy() is None)
        h.pack("off", "offline-only")
        ctx.check("off: the policy is back", load_escalation_policy() is not None)


@test
def test_they_ship_as_package_data(ctx: Ctx):
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    ctx.check("templates/bundles/*/pack.yaml is package data", '"templates/bundles/*/pack.yaml"' in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
