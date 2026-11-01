"""tests.test_bundle_claims -- Halo 3.3.8.0 R4 deliverable 3: bundles that claim more (packs/manifest_bundle_claims.py,
local_sched/bundle_parts.py, preempt.py, reserve_parts.py, claims_file's hours and notices; the shipped big-reasoner)
on the fixture 24 GB card (tests/helpers/bundle_rig.BundleHome: 22.0 GB usable, the coder qwen3-coder:30b 18.9 GB):

1. the contract: several reservations (host, min_free_gb), schedule, priority, min_free_gb validate and normalize;
   each bad value one line;
2. priority: a high bundle pre-empts a low claim that leaves it no room -- told in one line naming the winner and the
   number, the loser's verdict carries the notice; an equal priority holds (one line, nothing taken);
3. the schedule: outside its hours the claim is dormant (written, never counted), the verdict says when it holds;
   min_free_gb: a claim that would leave less free for tasks won't work, said with the floor;
4. big-reasoner: the pool for the reasoning lane (a row on host `pool`, Warm launches it, nothing here does), the
   coder resident on this card; a Warm of another model waits on it in one line; a lower pool claim is pre-empted;
   held by a halo process every reservation carries the lease.
Run: python -m tests.test_bundle_claims
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.bundle_rig import BundleHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
CODER, SMALL, QWEN = "qwen3-coder:30b", "qwen3.5:9b", "qwen3-next-80b-a3b-q4km"


def _pack(h, bid: str, bundle: dict) -> None:
    d = h.repo / ".halo" / "packs" / bid
    d.mkdir(parents=True, exist_ok=True)
    (d / "pack.yaml").write_text(json.dumps({"id": bid, "name": bid, "version": "1.0.0", "description": bid,
                                             "halo_api": {"min": "1.0", "max": "1.9"}, "bundle": bundle}),
                                 encoding="utf-8")


def _row(h, bundle: str, model: str, gb: float, *, priority: str, host: str = "pc") -> None:
    from halo_harness.local_sched import claims_file as CF
    from halo_harness.local_sched.reserve import forget
    CF.put(CF.local_file(h.state), {"bundle": bundle, "host": host, "model": model, "gb": gb, "holder": "keep",
                                    "priority": priority, "scope": "keep", "via": "local", "escalation": "on"})
    forget()


FOCUS = {"needs": {"coder": {"any_of": [CODER], "window": 32768, "tools": True}},
         "reservation": {"model": CODER}, "routing": {"task_work": "local"}}


@test
def test_the_contract(ctx: Ctx):
    from halo_harness.packs.manifest_bundle import block, bundle_lines
    good = {"needs": {"reasoner": {"any_of": [QWEN]}, "coder": {"any_of": [CODER]}},
            "reservations": [{"model": "reasoner", "host": "pool"}, {"model": "coder", "min_free_gb": 2}],
            "schedule": {"hours": "22:00-07:00"}, "priority": "high", "min_free_gb": 4}
    ctx.check(f"clean, got {bundle_lines({'bundle': good})}", bundle_lines({"bundle": good}) == [])
    b = block({"id": "x", "bundle": good})
    ctx.check(f"normalized, got {b['reservations']}", [(r["role"], r["host"], r["priority"], r["min_free_gb"]) for r in
                                                       b["reservations"]] == [("reasoner", "pool", "high", 4),
                                                                              ("coder", None, "high", 2)]
              and b["reservation"]["role"] == "coder" and b["schedule"] == {"hours": "22:00-07:00"}
              and b["priority"] == "high" and b["min_free_gb"] == 4)
    bad = {**good, "schedule": {"hours": "late"}, "priority": "urgent", "min_free_gb": -1,
           "reservations": [{"model": "reasoner", "host": "pool"}, {"model": "coder", "host": "pool"}]}
    got = bundle_lines({"bundle": bad})
    ctx.check(f"each bad value one line, got {got}", len(got) == 4
              and any(x.startswith("bundle.schedule: {hours:") for x in got)
              and any(x.startswith("bundle.priority: 'urgent'") for x in got)
              and any(x.startswith("bundle.min_free_gb: -1") for x in got)
              and any("two reservations on pool (reasoner and coder): one per host -- merge them" in x for x in got))


@test
def test_a_high_bundle_pre_empts_a_low_claim(ctx: Ctx):
    from halo_harness.local_sched import claims_file as CF
    from halo_harness.local_sched.bundle_parts import verdict
    from halo_harness.packs.bundles import find
    with BundleHome() as h:
        _pack(h, "focus", {**FOCUS, "priority": "high"})
        _pack(h, "night-batch", {"needs": {"worker": {"any_of": [SMALL], "window": 8192}},
                                 "reservation": {"model": SMALL, "priority": "low"}})
        _row(h, "night-batch", SMALL, 6.0, priority="low")
        v = verdict(find("focus", cwd=h.repo)["block"], h.host, state_dir=h.state)
        ctx.check(f"ready, the pre-emption said, got {v['state']}: {v['says']!r}", v["state"] == "ready"
                  and "pre-empts night-batch (low, 6.0 GB) on pc" in v["says"])
        code, out, err = h.pack("on", "focus")
        ctx.check(f"on: one line naming the winner and the number, got {code} {out!r} {err!r}", code == 0
                  and "pre-empted night-batch (low) on pc: focus (high) needs its 6.0 GB -- halo pack on night-batch "
                      "claims it again once there is room" in out)
        rows = {r["bundle"] for r in CF.read(CF.local_file(h.state))}
        ctx.check(f"the low claim is gone, the high one holds, got {rows}", rows == {"focus"})
        code, out, err = h.pack("verdict", "night-batch")
        ctx.check(f"the loser's verdict carries the notice, got {out!r}", "! pre-empted night-batch (low) on pc: focus "
                  "(high) needs its 6.0 GB" in out)
    with BundleHome() as h:
        _pack(h, "focus", FOCUS)
        _row(h, "night-batch", SMALL, 6.0, priority="normal")
        v = verdict(find("focus", cwd=h.repo)["block"], h.host, state_dir=h.state)
        ctx.check(f"an equal priority holds: won't work, one line, nothing taken, got {v['says']!r}", v["state"] == "wont"
                  and "night-batch holds 6.0 GB there at priority normal: focus's normal does not pre-empt it" in v["says"]
                  and not v["preempts"])


@test
def test_the_schedule_and_the_floor(ctx: Ctx):
    from halo_harness.local_sched.bundle_parts import verdict
    from halo_harness.local_sched.reserve import claims
    from halo_harness.packs.bundles import find
    t = time.localtime()
    a, b = (t.tm_hour + 2) % 24, (t.tm_hour + 3) % 24
    hours = f"{a:02d}:00-{b:02d}:00"
    with BundleHome() as h:
        _pack(h, "office", {**FOCUS, "schedule": {"hours": hours}})
        v = verdict(find("office", cwd=h.repo)["block"], h.host, state_dir=h.state)
        ctx.check(f"the verdict says when it holds, got {v['schedule']}", v["schedule"] == {
            "hours": hours, "now": False, "line": f"holds its claims {hours} (the host's local clock): not held now "
                                                  f"(from {a:02d}:00)"})
        code, out, _err = h.pack("on", "office")
        from halo_harness.local_sched import claims_file as CF
        raw = CF.read(CF.local_file(h.state), expired=True)
        ctx.check(f"on: written with its hours, dormant now (never counted), got {raw} {claims(h.host, state_dir=h.state)}",
                  code == 0 and [r["hours"] for r in raw] == [hours] and claims(h.host, state_dir=h.state) == [])
    with BundleHome() as h:
        _pack(h, "roomy", {**FOCUS, "min_free_gb": 6})
        v = verdict(find("roomy", cwd=h.repo)["block"], h.host, state_dir=h.state)
        ctx.check(f"min_free_gb: it would leave less for tasks, won't work, said, got {v['says']!r}", v["state"] == "wont"
                  and "it keeps 6 GB free for tasks (min_free_gb)" in v["says"])


def _pool(h) -> None:
    from halo_harness.local_pool import members as M
    models = Path(h.root) / "models"
    snap = models / "models--Qwen--Qwen3-Next-80B-A3B-Instruct-GGUF" / "snapshots" / "c0de"
    snap.mkdir(parents=True)
    (snap / "Qwen3-Next-80B-A3B-Instruct-Q4_K_M.gguf").write_bytes(b"GGUF" + b"\0" * 60)
    h.config(**{"huggingface.model_dirs": [str(models)]})
    for i in (1, 2, 3):
        M.add(f"w{i}", f"worker{i}.local", vram_gb=24.0, state_dir=h.state)


@test
def test_big_reasoner_claims_the_pool_and_the_coder(ctx: Ctx):
    from halo_harness.local_sched import claims_file as CF
    from halo_harness.local_sched.bundle_parts import verdict
    from halo_harness.ollama_steward.changes_pool import warm
    from halo_harness.packs.bundles import find
    with BundleHome() as h:
        _pool(h)
        _row(h, "night-pool", "gpt-oss-120b", 50.0, priority="low", host="pool")
        v = verdict(find("big-reasoner", cwd=h.repo)["block"], h.host, state_dir=h.state)
        part = (v.get("parts") or [{}])[0]
        ctx.check(f"two parts: the coder here, the pool for the reasoner, got {v['state']}: {v['says']!r}",
                  v["state"] == "ready" and v["reserved"]["model"] == CODER and part.get("host") == "pool"
                  and part.get("model") == QWEN and part.get("state") == "ready"
                  and "the pool for reasoner: Qwen3-Next-80B-A3B Q4_K_M fits the pool" in part["says"]
                  and "pre-empts night-pool (low) on the pool" in part["says"])
        code, out, err = h.pack("on", "big-reasoner")
        rows = {(r["bundle"], r["host"]): r for r in CF.read(CF.local_file(h.state))}
        ctx.check(f"on: the coder held here, the pool reserved, nothing launched, got {code} {out!r} {err!r}", code == 0
                  and ("big-reasoner", "pc") in rows and ("big-reasoner", "pool") in rows
                  and ("night-pool", "pool") not in rows and "pre-empted night-pool (low) on pool" in out
                  and f"reserved the pool for big-reasoner's reasoner (Qwen3-Next-80B-A3B Q4_K_M" in out
                  and f"Warm starts it (halo local serve --pool {QWEN}); nothing launches until then" in out)
        got = warm("gpt-oss-120b", state_dir=h.state)
        ctx.check(f"a Warm of another model waits on it, one line, got {got['lines']}", not got["ok"] and got["lines"] == [
            f"big-reasoner holds the pool for {QWEN} (priority high): a Warm of gpt-oss-120b waits until halo pack off "
            "big-reasoner"])
        h.pack("off", "big-reasoner")
        ctx.check("off: both released", not [r for r in CF.read(CF.local_file(h.state)) if r["bundle"] == "big-reasoner"])
        from halo_harness.local_sched.reserve_act import claim, release
        ok, lines, _v = claim("big-reasoner", holder="process", cwd=h.repo, state_dir=h.state)
        leased = [r for r in CF.read(CF.local_file(h.state)) if r["bundle"] == "big-reasoner"]
        ctx.check(f"held by a halo process: every reservation carries the lease, got {[(r['host'], r['until']) for r in leased]}",
                  ok and len(leased) == 2 and all(isinstance(r.get("until"), float) for r in leased))
        release("big-reasoner", state_dir=h.state, disable=False)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
