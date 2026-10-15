"""tests.test_review3_d1 -- pins for the 3.0.2.0 review fix pass, round D1
(remote control core), part one:

  * review item 26  a correctly signed command refused as stale burns its
                    counter, so the same bytes cannot be replayed later
  * review item 27  a sub-agent's feed events never close the parent's open
                    cards; a sub-agent's own card is relayed, tagged
  * review item 28  a sub-agent's status event never re-keys the registry
  * review item 29  a pulse whose pid now belongs to another process reads
                    as stopped
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

from halo_harness.remote import signing
from halo_harness.remote.bridge import Bridge
from tests.helpers.fake_signal_cli import data_message
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.signal_rig import ACI_A, SAFETY_A, Home, NoRegistry, StubTransport, now_ms, pair_peer

test, TESTS = new_registry()


def _deliver(bridge, text: str, ts: int) -> None:
    params = data_message(ACI_A, text, ts)
    bridge.handle({"kind": "envelope", "envelope": params["envelope"], "exception": None, "account": None})


# ---- item 26 -------------------------------------------------------------------

@test
def test_item26_stale_signed_command_burns_its_counter(ctx: Ctx):
    with Home():
        tr = StubTransport()
        b = Bridge({"rate_per_minute": 100}, tr, NoRegistry())
        secret = pair_peer(b.pairing, ACI_A, "+15555550101", SAFETY_A, signed=True)
        late = signing.sign(secret, 7, "/remote status")
        _deliver(b, late, now_ms() - 10 * 60 * 1000)
        ctx.check("the late copy is refused as outside the window", "time window" in "\n".join(tr.texts(ACI_A)))
        ctx.check("its counter is used up", b.pairing.peer(ACI_A)["signing"]["counter"] == 7)
        _deliver(b, late, now_ms())
        joined = "\n".join(tr.texts(ACI_A))
        ctx.check("the identical bytes with a fresh timestamp are a replay", "already used" in joined)
        ctx.check("and were never acted on", "Paired as" not in joined and tr.receipts == [])
        tampered = late.replace("/remote status", "/remote unpair")
        _deliver(b, tampered, now_ms() - 10 * 60 * 1000)
        ctx.check("a stale message with a bad MAC burns nothing", b.pairing.peer(ACI_A)["signing"]["counter"] == 7)
        _deliver(b, signing.sign(secret, 8, "/remote status"), now_ms())
        ctx.check("re-signed with a higher counter it is answered",
                  "Paired as" in "\n".join(tr.texts(ACI_A)) and len(tr.receipts) == 1)


# ---- item 27 -------------------------------------------------------------------

class _FeedBridge:
    def __init__(self) -> None:
        self.said: list = []
        self.typing: list = []
        self.registry = NoRegistry()
        self.transport = SimpleNamespace(typing=SimpleNamespace(start=lambda a: self.typing.append("start"),
                                                                stop=lambda a: self.typing.append("stop")))

    def say(self, aci, text, **kw) -> None:
        self.said.append(text)


@test
def test_item27_child_feed_never_closes_parent_cards(ctx: Ctx):
    from halo_harness.remote import bridge_session as sess
    b, rt = _FeedBridge(), sess.PeerRT(ACI_A, "loud")
    perm = {"id": "p1", "name": "Bash", "input": {"command": "make"}, "suggested_rule": "Bash(make:*)"}
    sess.on_feed(b, rt, {"event": "permission_request", "data": perm, "agent_id": None})
    ctx.check("the parent's card is open", [c["id"] for c in rt.permission] == ["p1"])
    n = len(b.said)
    for ev in ("message_start", "text_chunk", "error", "turn_done"):
        sess.on_feed(b, rt, {"event": ev, "data": {"text": "child words", "message": "child broke"},
                             "agent_id": "ab12cd34ef"})
    ctx.check("a sub-agent's text, typing, error and turn_done send nothing", len(b.said) == n and b.typing == [])
    ctx.check("a sub-agent's turn_done leaves the parent's card open", [c["id"] for c in rt.permission] == ["p1"])
    sess.on_feed(b, rt, {"event": "permission_request", "data": {**perm, "id": "c1"}, "agent_id": "ab12cd34ef"})
    ctx.check("a sub-agent's own card is answerable", [c["id"] for c in rt.permission] == ["p1", "c1"])
    ctx.check("and tagged with the sub-agent", b.said[n].startswith("[sub-agent ab12cd34] Permission needed"))
    sess.on_feed(b, rt, {"event": "text_chunk", "data": {"text": "parent words"}, "agent_id": None})
    ctx.check("the parent's own text is still relayed", any("parent words" in s for s in b.said))
    sess.on_feed(b, rt, {"event": "turn_done", "data": {}, "agent_id": None})
    ctx.check("the parent's turn_done closes the cards", rt.permission == [] and "stop" in b.typing)


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
    from halo_harness.remote import bridge_state as BS, proc_ident
    path = Path(tempfile.mkdtemp(prefix="d1-pulse-")) / "bridge.json"

    def pulse(**row) -> dict:
        path.write_text(json.dumps({"state": "connected", "until": 0.0, **row}), encoding="utf-8")
        return BS.read(path)
    BS.BridgeState(path=path).write("connected")
    ctx.check("this process's own pulse reads as running", BS.read(path)["running"] is True)
    ctx.check("the pulse carries the process's start record",
              json.loads(path.read_text(encoding="utf-8")).get("pstart") == proc_ident.start_token(os.getpid()))
    mine = proc_ident.start_token(os.getpid())
    if mine is not None:
        other = proc_ident.start_token(os.getppid())
        ctx.check("a live pid whose start record differs reads as stopped (the pid was reused)",
                  pulse(pid=os.getpid(), pstart=(other if other and other != mine else mine + "x"),
                        started=time.time())["state"] == "stopped")
    boot = proc_ident.boot_time()
    if boot is not None:
        ctx.check("an old pulse with no start record written before this boot reads as stopped",
                  pulse(pid=os.getpid(), started=boot - 3600)["running"] is False)
    ctx.check("an old pulse with no start record from this boot still reads as running",
              pulse(pid=os.getpid(), started=time.time())["running"] is True)


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
