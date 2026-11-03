"""tests.test_receipts -- Halo 3.3.11.0 R1: the receipts ladder of what Studio sends a live session
(remote/receipts.py, remote/receipt_seams.py, the seams in agent/loop.py, studio/sessions_prompt_api.py).

1. a prompt typed in Studio climbs sent -> delivered -> read -> replied, in that order, on a REAL session (the
   real loop over the mock upstream, tests/helpers/fleet_rig.py): the user node the request is derived from
   carries the receipt id and the `read` row names that node's seq; the model's input holds the text; the
   turn's `user_message` frame says via studio and carries the receipt;
2. a retry with the same `client_id` returns the stored row and the session gets ONE turn;
3. a steer sent while a turn runs is read at the safe point that applies it (its log node carries the id);
4. `expired`: a sent row is failed(expired) by a fake clock two hours past the TTL, applied when a read or a send
   touches the file; a read row never expires;
5. at the session's end (the handle's detach) a delivered, unread row goes back to sent with the reason;
6. the file is append-only (every earlier line unchanged) and the last row per id wins; no move goes back down.
No model is called.
Run: python -m tests.test_receipts
"""
from __future__ import annotations

import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fleet_rig import FleetRig, gated, recorded, text_step, tool_step, wait_for  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _req(rig, method: str, path: str, body=None):
    from halo_harness.studio.api import Request
    from halo_harness.studio.sessions_api import dispatch_sessions
    return dispatch_sessions(Request(method=method, path=path, query={}, body=body or {}, cwd=rig.cwd, state_dir=rig.cwd))


def _live(rig, steps: list, name: str):
    from halo_harness.remote import runtime
    session = rig.session(rig.script(name, steps))
    controller = rig.controller(session)
    return session, controller, runtime.start_for_controller(controller)


def _history(sid: str, rid: str) -> list:
    from halo_harness.remote.receipts import Receipts, session_folder
    return [r["state"] for r in Receipts(session_folder(sid)).rows() if r["id"] == rid]


def _state(rig, sid: str, rid: str) -> str:
    rows = _req(rig, "GET", f"sessions/{sid}/receipts")[1].get("receipts") or []
    return next((r["state"] for r in rows if r["id"] == rid), "")


@test
def test_the_ladder_in_order_on_a_real_session(ctx: Ctx):
    with FleetRig() as rig:
        seen: list = []
        session, controller, act = _live(rig, [recorded(text_step("Read you."), seen)], "pp-ladder")
        reader = rig.reader(act)
        sid = act.session_id
        status, body = _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "submit", "text": "PP-LADDER please read me", "client_id": "pp-c1"})
        rid = (body.get("receipt") or {}).get("id", "")
        ctx.check(f"taken with a receipt, got {status} {body}", status == 200 and rid.startswith("r_"))
        ctx.check("it reaches replied", wait_for(lambda: _state(rig, sid, rid) == "replied", 30))
        ctx.check(f"in order, got {_history(sid, rid)}", _history(sid, rid) == ["sent", "delivered", "read", "replied"])
        node = next((n for n in session.log._nodes if n.get("type") == "user" and n.get("receipt") == rid), None)
        ctx.check("the transcript's user node carries the receipt id", node is not None)
        rows = _req(rig, "GET", f"sessions/{sid}/receipts")[1]["receipts"]
        from halo_harness.remote.receipts import Receipts, session_folder
        read = next(r for r in Receipts(session_folder(sid)).rows() if r["id"] == rid and r["state"] == "read")
        ctx.check(f"the read row names that node and the turn, got {read}", node is not None and read.get("seq") == node["seq"] and read.get("turn") == 1)
        ctx.check("the model's input held the text", any("PP-LADDER please read me" in str(b.get("messages")) for b in seen))
        row = next(r for r in rows if r["id"] == rid)
        ctx.check(f"the row: kind prompt, the text's sha256, the client id, got {row}", row["kind"] == "prompt"
                  and row["client_id"] == "pp-c1" and len(row["sha256"]) == 64 and "PP-LADDER" not in str(row))
        um = wait_for(lambda: [f for f in reader.of("user_message") if (f.get("data") or {}).get("receipt") == rid], 10) or [{}]
        ctx.check(f"the user_message frame says via studio, got {um[0].get('data')}", (um[0].get("data") or {}).get("via") == "studio")


@test
def test_a_retry_with_the_same_client_id_sends_nothing(ctx: Ctx):
    with FleetRig() as rig:
        session, controller, act = _live(rig, [text_step("Once.")], "pp-retry")
        sid = act.session_id
        body = {"cmd": "submit", "text": "PP-RETRY only once", "client_id": "pp-c2"}
        s1, b1 = _req(rig, "POST", f"sessions/{sid}/command", body)
        rid = b1["receipt"]["id"]
        ctx.check("the first one is replied", wait_for(lambda: _state(rig, sid, rid) == "replied", 30))
        s2, b2 = _req(rig, "POST", f"sessions/{sid}/command", body)
        ctx.check(f"the retry answers the stored row, got {s2} {b2}", s2 == 200 and b2.get("duplicate") is True and b2["receipt"]["id"] == rid)
        time.sleep(0.5)
        users = [n for n in session.log._nodes if n.get("type") == "user" and "PP-RETRY" in str(n.get("content"))]
        ctx.check(f"ONE turn, got {len(users)} user node(s), turn_count {session.turn_count}", len(users) == 1 and session.turn_count == 1)


@test
def test_a_steer_is_read_where_it_applies(ctx: Ctx):
    with FleetRig() as rig:
        gate = threading.Event()
        notes = str(rig.cwd / "notes.md")
        steps = [gated(gate, tool_step(("Read", {"file_path": notes}, "call_r1"))), text_step("Steered and done.")]
        session, controller, act = _live(rig, steps, "pp-steer")
        sid = act.session_id
        controller.submit("PP-STEER start the work")
        ctx.check("the turn runs", wait_for(lambda: session.busy, 10))
        status, body = _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "steer", "text": "PP-STEER look at the notes too"})
        rid = (body.get("receipt") or {}).get("id", "")
        ctx.check(f"a steer receipt, got {status} {body}", status == 200 and body["result"].get("steered") is True and rid)
        gate.set()
        ctx.check("it reaches replied", wait_for(lambda: _state(rig, sid, rid) == "replied", 30))
        hist = _history(sid, rid)
        ctx.check(f"sent, delivered, read, replied, got {hist}", hist == ["sent", "delivered", "read", "replied"])
        node = next((n for n in session.log._nodes if n.get("kind") == "steer" and n.get("receipt") == rid), None)
        ctx.check("the steer's log node carries the receipt id", node is not None)


@test
def test_expired_by_the_ttl_when_touched(ctx: Ctx):
    from halo_harness.remote.receipts import TTL_S, Receipts
    base = time.time() + 7200  # flake rule 4: the fake clock stays ahead of the real one
    now = [base]
    rec = Receipts(Path(tempfile.mkdtemp(prefix="pp-rcpt-")), clock=lambda: now[0])
    a, _ = rec.record("prompt", "old one")
    b, _ = rec.record("steer", "read one")
    rec.advance(b["id"], "delivered")
    rec.advance(b["id"], "read", turn=1)
    now[0] = base + TTL_S - 60
    ctx.check("inside the TTL nothing expires", {r["state"] for r in rec.read_all()} == {"sent", "read"})
    now[0] = base + TTL_S + 7200
    rows = {r["id"]: r for r in rec.read_all()}
    ctx.check(f"a read touches it: failed(expired), got {rows[a['id']]}", rows[a["id"]]["state"] == "failed" and rows[a["id"]]["reason"] == "expired")
    ctx.check("a read row never expires", rows[b["id"]]["state"] == "read")
    c, _ = rec.record("prompt", "new one")
    now[0] = base + 2 * TTL_S + 3 * 7200
    rec.record("prompt", "a send touches it too")
    ctx.check("a send applies the TTL as well", {r["id"]: r for r in rec.read_all()}[c["id"]]["state"] == "failed")


@test
def test_requeue_at_the_end_of_the_session(ctx: Ctx):
    from halo_harness.remote.receipts import Receipts, session_folder
    from tests.helpers.remote_rig import Rig
    with Rig() as rig:
        c = rig.client()
        c.call("submit", text="please ask first")
        ctx.check("the turn parks on its card", wait_for(lambda: "perm_1" in rig.session._permission_waiters, 8))
        rec = Receipts(session_folder(rig.session.log.session_id, rig.cwd))
        row, _ = rec.record("prompt", "held for later")
        r = c.call("submit", text="held for later", origin={"via": "studio"}, when_busy="queue", receipt=row["id"])
        ctx.check("held and delivered", r["result"].get("queued") is True and rec.get(row["id"])["state"] == "delivered")
        rig.handle.detach()
        got = rec.get(row["id"])
        ctx.check(f"delivered -> sent at the end, with the reason, got {got}", got["state"] == "sent" and "ended" in got.get("reason", ""))
        ctx.check("the history", [x["state"] for x in rec.rows() if x["id"] == row["id"]] == ["sent", "delivered", "sent"])
        rig.session.resolve_permission("perm_1", {"behavior": "allow"})


@test
def test_append_only_and_the_last_row_wins(ctx: Ctx):
    from halo_harness.remote.receipts import Receipts
    rec = Receipts(Path(tempfile.mkdtemp(prefix="pp-rcpt-")))
    row, dup = rec.record("prompt", "one", client_id="cid-1")
    before = rec.path.read_text(encoding="utf-8")
    again, dup2 = rec.record("prompt", "one", client_id="cid-1")
    ctx.check("the same client_id: the stored row, nothing written", dup2 and again["id"] == row["id"] and rec.path.read_text(encoding="utf-8") == before)
    rec.advance(row["id"], "delivered")
    rec.advance(row["id"], "read", turn=3)
    ctx.check("no move back down", rec.advance(row["id"], "delivered") is None and rec.advance(row["id"], "sent") is None)
    after = rec.path.read_text(encoding="utf-8")
    ctx.check("every earlier line unchanged (append-only)", after.startswith(before) and len(after.splitlines()) == 3)
    ctx.check("the last row wins", rec.get(row["id"])["state"] == "read" and rec.get(row["id"])["turn"] == 3)
    rec.advance(row["id"], "replied", turn=3)
    ctx.check("replied is the end of it", rec.advance(row["id"], "failed", reason="x") is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
