"""tests.test_host_steward -- Halo 3.3.7.0 R2 deliverable 6: the duty steward (host_steward_cli.py, host/duty.py) with
a fake host and a fake Ollama (tests/helpers/host_act_rig.ActRig) and a fake model call (no model is ever called):

1. `on`: a separate process (the spawn seam sees `halo host steward run`), steward.json with its pid and model, the
   switch on, its own peer record (duty, the control grant), its model's profile at keep_alive 2m;
2. a pass: the host's finding -> the cited op (`control/set_num_ctx`, evidence.finding) -> verified and kept; the
   audit line names the finding; fleet.allow_control: ask does not queue the owner's own steward; a note per pass;
3. eviction: a peer's warm of a model that needs the room unloads the steward's model first;
4. `off`: no process, no peer record, the switch off; `status` says so; `run` with the switch off does no pass.
Run: python -m tests.test_host_steward
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_act_rig import BIG, CODER, GIB, SMALL, ActRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MODEL = f"ol:{SMALL}@pc"


class _Proc:
    pid = os.getpid()


def _on(spawned: list) -> "tuple[int, str]":
    from halo_harness import host_steward_cli as H
    H.SEAMS["spawn"] = lambda argv: spawned.append(argv) or _Proc()
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = H.cmd_steward(["on", "--model", MODEL])
    finally:
        H.SEAMS.pop("spawn", None)
    return rc, out.getvalue()


def _trims(rig, n: int = 6) -> None:
    from halo_harness.ollama_steward.ledger import append_lines
    from tests.helpers.steward_seed import line
    append_lines(rig.home, [line(host={"name": "pc", "url": rig.mock.base_url}, model=BIG, num_ctx_sent=16384,
                                 prompt_eval_count=16000, trimmed=True, eval_tok_s=16.0, ago=300 + i) for i in range(n)])


@test
def test_on_starts_a_separate_process(ctx: Ctx):
    from halo_harness.host import duty
    from halo_harness.host.state import HostPairing, _cfg
    from halo_harness.ollama_steward.profiles import all_profiles
    with ActRig(cap="ask") as rig:
        spawned: list = []
        rc, out = _on(spawned)
        ctx.check(f"on: one line, a separate `halo host steward run`, got {rc} {out!r} {spawned}", rc == 0 and spawned
                  and spawned[0][-3:] == ["host", "steward", "run"] and "a separate process" in out)
        st = duty.read_state(rig.home)
        rec = HostPairing(rig.home).member(st.get("peer") or "") or {}
        ctx.check(f"steward.json: pid, model; the switch on; its own peer (duty, control), got {st} {rec.get('grants')}",
                  st.get("pid") == os.getpid() and st.get("model") == MODEL and _cfg("host.steward.enabled", False, rig.home) is True
                  and rec.get("duty") is True and rec.get("grants") == ["view", "control"])
        ctx.check("its model is kept briefly (keep_alive 2m)", (all_profiles().get(f"pc|{SMALL}") or {}).get("keep_alive") == "2m")


@test
def test_a_pass_sends_a_cited_fix_that_is_kept(ctx: Ctx):
    from halo_harness.host import duty, verify
    from halo_harness.host.state import read_audit
    with ActRig(cap="ask") as rig:
        _on([])
        _trims(rig)
        calls: list = []

        def caller(model, system, user, state_dir=None):
            calls.append((model, user))
            return {"text": "The 27B's prompts outgrew 16,384 on pc and were trimmed.\nThe window goes up.", "local": True}
        got = duty.pass_once(rig.home, MODEL, caller=caller)
        sent = got["sent"][0] if got["sent"] else {}
        ctx.check(f"one model call reading the host's findings, got {len(calls)}", len(calls) == 1 and calls[0][0] == MODEL
                  and "where: host" in calls[0][1])
        ctx.check(f"the cited fix landed (ask does not queue the owner's own steward), got {got['sent']}",
                  sent.get("op") == "set_num_ctx" and sent.get("ok") is True and sent.get("finding", "").startswith("window-small"))
        time.sleep(0.3)
        rows = [a for a in read_audit(rig.home) if a.get("op") == "set_num_ctx"]
        ctx.check(f"the audit line names the finding, got {rows[-1] if rows else None}", rows
                  and rows[-1]["evidence"]["finding"] == sent.get("finding") and rows[-1]["peer"] == "duty steward")
        ctx.check(f"a note for the pass, got {got['note']['say'] if got['note'] else None!r}", got["note"]
                  and got["note"]["where"] == "duty steward" and "outgrew" in got["note"]["say"])
        from halo_harness.ollama_steward.ledger import append_lines
        from tests.helpers.steward_seed import line
        append_lines(rig.home, [line(host={"name": "pc", "url": rig.mock.base_url}, model=BIG, num_ctx_sent=sent["to"],
                                     prompt_eval_count=16000, eval_tok_s=40.0, ago=-1 - i) for i in range(5)])
        closed = verify.tick(rig.svc)
        ctx.check(f"verified and kept, got {closed[0]['line'] if closed else None!r}", closed and closed[0]["verdict"] == "kept"
                  and closed[0]["line"].startswith(f"set_num_ctx {sent['to']} on pc|qwen3.8:27b: 16 -> 40 tok/s, no trims"))


@test
def test_the_helper_is_evicted_when_the_card_is_needed(ctx: Ctx):
    with ActRig(cap="all") as rig:
        _on([])
        helper = {"name": SMALL, "model": SMALL, "size": 2 * GIB, "size_vram": 2 * GIB, "context_length": 4096,
                  "expires_at": "2099-01-01T00:00:00Z"}
        rig.mock.ps_response = {"models": [helper]}
        status, got = rig.act("control", "warm", {"model": CODER, "num_ctx": 32768})
        sent = [(g["model"], g["keep_alive"]) for g in rig.mock.generated]
        ctx.check(f"the steward's model unloaded first, then the peer's, got {status} {sent}", status == 200
                  and sent[0] == (SMALL, 0) and sent[-1][0] == CODER)


@test
def test_off_means_no_process(ctx: Ctx):
    from halo_harness import host_steward_cli as H
    from halo_harness.host import duty
    from halo_harness.host.state import HostPairing, _cfg
    with ActRig(cap="all") as rig:
        _on([])
        peer = duty.read_state(rig.home)["peer"]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = H.cmd_steward(["off"])
        ctx.check(f"off: the switch, the state and the peer record gone, got {out.getvalue()!r}", rc == 0
                  and _cfg("host.steward.enabled", True, rig.home) is False and duty.read_state(rig.home) == {}
                  and HostPairing(rig.home).member(peer) is None and "no process" in out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            H.cmd_steward(["status"])
        ctx.check(f"status says off, got {out.getvalue()!r}", "is off" in out.getvalue())
        from halo_harness.ollama_steward import notes
        n = len(notes.read(rig.home))
        ctx.check("run with the switch off does no pass", H.cmd_steward(["run", "--once"]) == 0 and len(notes.read(rig.home)) == n)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
