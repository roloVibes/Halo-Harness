"""tests.test_sched_pivot -- Halo 3.3.7.0 R3: one pivot as a visible step (local_sched/pivot.py), over a fake
Ollama on 127.0.0.1:0 (tests/helpers/sched_rig.SchedHome) and, for the host path, R2's PeerRig (a real halo host
serving a fake, this process the peer holding `control`):

1. local: "pivot: main (qwen3-coder:30b) -> coder (qwen3.8:27b) on pc, ~25 s (the ledger), fits history to 32 k",
   the unload then the load at the window on the fake, "pivoted in N s", the load on the session's loading tax;
2. one pivot at a time per card: a second waits, said in one line, then runs;
3. the minimum residency: a model the scheduler loaded 0 s ago is held local.min_resident_s, said with the seconds;
4. a host-served model pivots through the host's `pivot` operation (its invariants first), said so in the line.
Nothing leaves 127.0.0.1; no model is called.
Run: python -m tests.test_sched_pivot
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.sched_rig import BIG, CODER, SchedHome, ps_row  # noqa: E402

test, TESTS = new_registry()


class _S:
    def __init__(self, state, sid="s-pivot"):
        from types import SimpleNamespace
        self.state_dir, self.log = state, SimpleNamespace(session_id=sid)


def _drain(gen) -> "tuple[list, dict]":
    out = []
    while True:
        try:
            out.append(next(gen))
        except StopIteration as stop:
            return out, stop.value


@test
def test_a_local_pivot_is_one_visible_step(ctx: Ctx):
    from halo_harness.local_sched.loads import tally
    from halo_harness.local_sched.pivot import held_for, plan, run
    with SchedHome(loaded=[ps_row(CODER, 18.0)]) as h:
        h.loads(BIG, 26.0, 25.0, 24.0, session="older")
        p = plan(h.host, CODER, BIG, window=32768, labels=("main", "coder"))
        ctx.check(f"the plan's line, got {p['line']!r}", p["line"] == "pivot: main (qwen3-coder:30b) -> coder "
                  "(qwen3.8:27b) on pc, ~25 s (the ledger), fits history to 32 k" and p["via"] == "local")
        evs, got = _drain(run(p, host=h.host, session=_S(h.state)))
        texts = [e.data["text"] for e in evs]
        ctx.check(f"one line before, one after, got {texts}", len(texts) == 2 and texts[0] == p["line"]
                  and texts[1].startswith("pivoted in ") and got["ok"])
        gen = [(g["model"], g["keep_alive"], (g.get("options") or {}).get("num_ctx")) for g in h.mock.generated]
        ctx.check(f"the fake saw the unload, then the load at the window, got {gen}",
                  gen[0] == (CODER, 0, None) and gen[1][0] == BIG and gen[1][2] == 32768)
        t = tally(h.state, "s-pivot")
        ctx.check(f"the load is on the session's loading tax, got {t}", t["count"] == 1 and t["line"].startswith("loading: 1 load,"))
        ctx.check("the residency clock started for the new model", held_for(h.host, BIG) > 0)


@test
def test_one_pivot_at_a_time_per_card(ctx: Ctx):
    from halo_harness.local_sched.pivot import _lock, plan, run
    with SchedHome(loaded=[ps_row(CODER, 18.0)]) as h:
        lock = _lock(h.host)
        lock.acquire()
        out: dict = {}

        def second():
            out["evs"], out["got"] = _drain(run(plan(h.host, CODER, BIG, window=32768), host=h.host))
        t = threading.Thread(target=second)
        t.start()
        time.sleep(0.4)
        seen = len(h.mock.generated)
        lock.release()
        t.join(10)
        texts = [e.data["text"] for e in out.get("evs") or []]
        ctx.check(f"nothing sent while the other pivot ran, got {seen}", seen == 0)
        ctx.check(f"the wait said in one line, then it ran, got {texts}", any(
            "waits -- a pivot is already running on pc (one at a time per card)" in x for x in texts)
                  and out["got"]["ok"])


@test
def test_the_minimum_residency_holds_a_fresh_model(ctx: Ctx):
    from halo_harness.local_sched.pivot import mark_loaded, plan, run
    with SchedHome(loaded=[ps_row(CODER, 18.0)]) as h:
        h.config(**{"local.min_resident_s": 60})
        mark_loaded(h.host, CODER)
        slept: list = []
        evs, got = _drain(run(plan(h.host, CODER, BIG, window=32768), host=h.host, sleep=slept.append))
        held = [e.data["text"] for e in evs if e.data["text"].startswith("pivot held")]
        ctx.check(f"held the rest of the 60 s, said, got {held} {slept}", held and slept and 59 <= slept[0] <= 60
                  and "(local.min_resident_s 60; this halo's own clock" in held[0] and "qwen3-coder:30b was loaded 0 s ago" in held[0])
        ctx.check("then it pivoted", got["ok"])


@test
def test_a_host_served_model_pivots_through_the_host(ctx: Ctx):
    from halo_harness.local_sched.pivot import plan, run
    from halo_harness.providers.ollama import OllamaHost
    from tests.helpers.host_act_rig import PeerRig
    with PeerRig() as rig:
        rig.mock.ps_response = {"models": [ps_row(CODER, 18.0)]}
        host = OllamaHost(name="pc", url=rig.peer_url)
        p = plan(host, CODER, BIG, window=32768, labels=("main", "coder"))
        ctx.check(f"via the host, said, got {p['via']} {p['line']!r}", p["via"] == "host"
                  and p["line"].endswith("(through the halo host)"))
        evs, got = _drain(run(p, host=host))
        gen = [(g["model"], g["keep_alive"]) for g in rig.mock.generated]
        ctx.check(f"the host unloaded then loaded on its server, got {got} {gen}", got["ok"] and got["via"] == "host"
                  and gen[0] == (CODER, 0) and gen[1][0] == BIG)
        from halo_harness.host.state import read_audit
        paths = [str(a.get("path") or "") for a in read_audit(rig.home)]
        ctx.check(f"the host's audit has the pivot request, got {paths[-3:]}", any(x.endswith("control/pivot") for x in paths))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
