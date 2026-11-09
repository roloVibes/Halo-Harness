"""tests.test_review3_d1 -- pins for the 3.0.2.0 review fix pass, round D1
(remote control core), part one:

  * review items 26-27 (the Signal bridge): the signal pack's tests/test_bridge_pins.py since 3.3.13.0 R3
  * review item 28  a sub-agent's status event never re-keys the registry
  * review item 29  a pulse whose pid now belongs to another process reads
                    as stopped (3.3.13.0 R3: remote/proc_ident.pulse_alive)
  * review item 96  a deny with scope session/always learns no allow rule

Part two is tests/test_review3_d1b.py.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

# items 26 and 27 (the Signal bridge's signed counter and a sub-agent's feed): moved to the signal pack
# (3.3.13.0 R3), its tests/test_bridge_pins.py.


# ---- item 28 -------------------------------------------------------------------

@test
def test_item28_child_status_never_rekeys_the_registry(ctx: Ctx):
    from halo_harness.remote import fleet_frames, registry, runtime
    calls: list = []
    saved = (list(runtime._actives), registry.register, registry.unregister, registry.update,
             fleet_frames.fleet_frame)
    registry.register = lambda e: calls.append(("register", e["session_id"]))
    registry.unregister = lambda sid: calls.append(("unregister", sid))
    registry.update = lambda sid, **f: calls.append(("update", sid, f)) or True
    fleet_frames.fleet_frame = lambda *a, **k: None
    handle = SimpleNamespace(cwd="/w", kind="tui", title=lambda: "t", hub=SimpleNamespace(meta={}))
    # 3.0.5.0 Fleet R1: one process may hold several sessions, so `_active` became the `_actives`
    # list and the tap is bound per Active
    act = runtime.Active(handle, SimpleNamespace(endpoint="unix:/x", token=None), "parent-sid",
                         mode="default", entry={"session_id": "parent-sid", "mode": "default"})
    runtime._actives[:] = [act]
    try:
        child = SimpleNamespace(kind="status", agent_id="ab12cd34",
                                data={"session_id": "agent-ab12cd34", "permission_mode": "plan"})
        runtime._watch_status(act, child)
        ctx.check("a sub-agent's status touches nothing", calls == [] and act.session_id == "parent-sid"
                  and act.mode == "default")
        untagged = SimpleNamespace(kind="status", agent_id=None, data={"session_id": "agent-ab12cd34"})
        runtime._watch_status(act, untagged)
        ctx.check("an agent-<id> session id is never adopted either", calls == [])
        runtime._watch_status(act, SimpleNamespace(kind="status", agent_id=None,
                                                   data={"session_id": "parent-sid", "permission_mode": "plan"}))
        ctx.check("the parent's own mode change still lands", calls == [("update", "parent-sid", {"mode": "plan"})])
        runtime._watch_status(act, SimpleNamespace(kind="status", agent_id=None, data={"session_id": "forked-sid"}))
        ctx.check("the parent's own /clear still re-keys",
                  calls[1:] == [("unregister", "parent-sid"), ("register", "forked-sid")])
    finally:
        runtime._actives[:] = saved[0]
        registry.register, registry.unregister, registry.update, fleet_frames.fleet_frame = saved[1:]


# ---- item 29 -------------------------------------------------------------------

@test
def test_item29_reused_pid_reads_as_stopped(ctx: Ctx):
    """3.3.13.0 R3: the rule moved from the Signal bridge's pulse to remote/proc_ident.pulse_alive (the supervisor's
    pulse and its services read it)."""
    from halo_harness.remote import proc_ident
    mine = proc_ident.start_token(os.getpid())
    ctx.check("this process's own row reads as alive",
              proc_ident.pulse_alive({"pid": os.getpid(), "pstart": mine, "started": time.time()}))
    if mine is not None:
        other = proc_ident.start_token(os.getppid())
        ctx.check("a live pid whose start record differs reads as stopped (the pid was reused)",
                  not proc_ident.pulse_alive({"pid": os.getpid(), "pstart": (other if other and other != mine else mine + "x"),
                                              "started": time.time()}))
    boot = proc_ident.boot_time()
    if boot is not None:
        ctx.check("an old row with no start record written before this boot reads as stopped",
                  not proc_ident.pulse_alive({"pid": os.getpid(), "started": boot - 3600}))
    ctx.check("a row with no start record from this boot still reads as alive",
              proc_ident.pulse_alive({"pid": os.getpid(), "started": time.time()}))
    ctx.check("no pid is not alive", not proc_ident.pulse_alive({}) and not proc_ident.pulse_alive({"pid": -1}))


# ---- item 96 -------------------------------------------------------------------

@test
def test_item96_deny_learns_no_rules(ctx: Ctx):
    from halo_harness.remote.base import _BaseHandle
    resolved: list = []
    rules: list = []

    class _H(_BaseHandle):
        def _add_rule(self, rule, scope):
            rules.append((rule, scope))
    session = SimpleNamespace(resolve_permission=lambda rid, d: resolved.append((rid, d.action, d.rule)) or True)
    h = _H(session, tempfile.gettempdir())
    for rid, scope in (("r1", "always"), ("r2", "session")):
        h._suggested[rid] = "Bash(rm:*), Bash(make:*)"
        ctx.check(f"deny with scope {scope} resolves", h.answer_permission(rid, "deny", scope=scope))
    ctx.check("a deny carries no rule and learns nothing", rules == [] and [r[2] for r in resolved] == [None, None])
    h._suggested["r3"] = "Bash(rm:*), Bash(make:*)"
    h.answer_permission("r3", "allow", scope="always")
    ctx.check("an allow with always still learns the suggested rules",
              resolved[-1][2] == "Bash(rm:*)" and ("Bash(make:*)", "session") in rules
              and ("Bash(rm:*)", "local") in rules and ("Bash(make:*)", "local") in rules)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
