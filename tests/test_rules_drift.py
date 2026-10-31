"""tests.test_rules_drift -- Halo 3.3.7.0 R4: the drift and deletion guards as steward rules (ollama_steward/
rules_drift.py, tag_digests.py) over a scratch home (tests/helpers/steward_seed.Home: host `pc` at a 192.0.2.x
placeholder no request reaches; the catalog is the rules' `catalogs` seam):

1. the first catalog read stores each tag's digest (and the window truth's, where it had none); a changed digest is a
   `tag-drift` finding naming what it invalidated (the battery profile, the speed card, the window truth) "measured on
   an older build of this tag"; the swap cost stops reading that speed card; the refresh plan queues the tag first;
2. a role on a tag the catalog no longer has is a `tag-deleted` error with the one dead-tag line and its point line;
   a tag that left the catalog and that nothing names is an info line.
No model is called; nothing is sent.
Run: python -m tests.test_rules_drift
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import PC, Home, rows  # noqa: E402

test, TESTS = new_registry()
BIG, CODER = "qwen3.8:27b", "qwen3-coder:30b"


def cat(big_digest: str, *, big: bool = True, gpu: bool = False) -> dict:
    r = rows()
    out = {CODER: {**r[CODER], "digest": "sha256:c0de"}}
    if big:
        out[BIG] = {**r[BIG], "digest": big_digest}
    if gpu:
        out["qwen3.8:27b-gpu"] = {**r[BIG], "model": "qwen3.8:27b-gpu", "digest": "sha256:9a9a"}
    return out


def run(h, catalog) -> list:
    from halo_harness.ollama_steward.rules import findings
    from halo_harness.providers.ollama import OllamaHost
    return findings(h.state, catalogs={"pc": catalog}, hosts=[OllamaHost(name="pc", url=PC["url"])])


@test
def test_a_changed_digest_is_drift(ctx: Ctx):
    from halo_harness.ollama_steward import tag_digests as D
    from halo_harness.providers.local_bench_runs import save
    from halo_harness.providers.ollama_capability import save_profile
    with Home() as h:
        from tests.helpers.host_rig import profile
        save_profile(h.state, {**profile(BIG), "digest": "sha256:0b27"})
        save(h.state, {"model": BIG, "host": "pc", "digest": "sha256:0b27", "at": time.time() - 60, "cold_load_s": 21.0,
                       "windows": []})
        h.cap(BIG, 49152)
        first = [f for f in run(h, cat("sha256:0b27")) if f["rule"] in ("tag-drift", "tag-deleted")]
        ctx.check(f"the first read stores the digests, no finding, got {first}", first == []
                  and D.current(h.state, "pc", BIG) == "sha256:0b27")
        from halo_harness.providers.ollama_calibrate import _find_entry, load_fit_store
        e = _find_entry(load_fit_store(h.state)["entries"], host_url=PC["url"], model=BIG)
        ctx.check(f"the window truth with no digest got the tag's, got {e}", e and e.get("digest") == "sha256:0b27")
        from halo_harness.local_sched.swap_cost import load_s_for
        before = load_s_for("pc", BIG, state_dir=h.state, fetch=False)
        got = [f for f in run(h, cat("sha256:9f1c")) if f["rule"] == "tag-drift"]
        ctx.check(f"a tag-drift finding, got {[f['finding'] for f in got]}", len(got) == 1 and got[0]["severity"] == "warn"
                  and got[0]["model"] == BIG and "its battery profile (" in got[0]["finding"]
                  and "its speed card (" in got[0]["finding"] and "its window truth (the learned cap 49,152)" in got[0]["finding"]
                  and "were measured on an older build of this tag" in got[0]["finding"]
                  and "sha256:0b27 -> sha256:9f1c" in got[0]["finding"])
        after = load_s_for("pc", BIG, state_dir=h.state, fetch=False)
        ctx.check(f"the swap cost drops the stale speed card, got {before['source']} -> {after['source']}",
                  before["source"] == "the speed card (the bench)" and after["source"] != before["source"])
        from halo_harness.host.refresh_plan import plan
        from halo_harness.providers.ollama import OllamaHost
        p = plan(h.state, [OllamaHost(name="pc", url=PC["url"])], catalogs={"pc": {"models": list(cat("sha256:9f1c").values())}})
        ctx.check(f"the refresh queues it first, got {p['rows'][:1]}", p["rows"][0]["model"] == BIG
                  and p["rows"][0]["why"] == "drifted")
        again = [f for f in run(h, cat("sha256:9f1c")) if f["rule"] == "tag-drift"]
        ctx.check("it stays until the records are measured again", len(again) == 1)


@test
def test_a_role_on_a_deleted_tag(ctx: Ctx):
    with Home(extra={"roles": {"coder": f"ol:{BIG}@pc"}}) as h:
        h.calls(__import__("tests.helpers.steward_seed", fromlist=["line"]).line(model=BIG))  # Halo called it there
        run(h, cat("sha256:0b27", gpu=True))
        got = [f for f in run(h, cat("sha256:0b27", big=False, gpu=True)) if f["rule"] == "tag-deleted"]
        err = [f for f in got if f["severity"] == "error"]
        ctx.check(f"an error naming the role and the nearest equivalent, got {[f['finding'] for f in got]}", len(err) == 1
                  and err[0]["finding"].startswith(f"role coder: `{BIG}` was deleted from pc -- nearest equivalent "
                                                   "`qwen3.8:27b-gpu`")
                  and err[0]["point"] == "halo roles point coder ol:qwen3.8:27b-gpu@pc")
    with Home() as h:
        run(h, cat("sha256:0b27"))
        got = [f for f in run(h, cat("sha256:0b27", big=False)) if f["rule"] == "tag-deleted"]
        ctx.check(f"a tag nothing names: info, got {[(f['severity'], f['finding']) for f in got]}", len(got) == 1
                  and got[0]["severity"] == "info" and "left pc's catalog" in got[0]["finding"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
