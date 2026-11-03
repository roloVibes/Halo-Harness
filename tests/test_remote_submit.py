"""tests.test_remote_submit -- Halo 3.3.11.0 R1: the control socket's `submit` for Studio's Prompt panel
(remote/protocol.py, remote/handle.py, remote/prompt_queue.py).

1. `origin` and `receipt` ride on the `user_input` Command's meta ({via, by, receipt}); the transcript line says
   "(from Studio) prompt: ..."; a submit without them is the Command it always was ("(remote) prompt: ...");
2. `when_busy`: steer is the default (the Signal remote unchanged: Session.steer); `refuse` answers
   {busy: true, line} and takes nothing; an unknown value is an error;
3. `queue` holds ONE turn: a second `queue` answers {busy, held, line}; the TUI's hint says "1 queued from
   Studio"; when the running turn ends (`turn_done`) the held turn runs exactly once, with its meta;
4. a session that quits with a turn held drops it with one line.
Over the remote rig (the real Controller + handle + socket over tests/helpers/fake_remote_session.py: a turn whose
text says "ask" parks on a permission card until it is answered). No model is called.
Run: python -m tests.test_remote_submit
"""
from __future__ import annotations

import queue
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.remote_rig import Rig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
STUDIO = {"via": "studio", "by": "you@studio"}


def _notes(rig) -> list:
    out = []
    while True:
        try:
            ev = rig.controller.events.get_nowait()
        except queue.Empty:
            return out
        if ev is not None and ev.kind == "system_note":
            out.append(ev.data["text"])


def _wait(fn, timeout: float = 8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.02)
    return None


def _busy_on_card(rig, c) -> bool:
    """A turn that parks on its permission card (the fake session's "ask")."""
    c.call("submit", text="please ask first")
    return bool(_wait(lambda: rig.session.busy and "perm_1" in rig.session._permission_waiters))


@test
def test_origin_and_receipt_ride_on_the_command_meta(ctx: Ctx):
    with Rig(start_controller=False) as rig:
        c = rig.client()
        r = c.call("submit", text="hello from the panel", origin=STUDIO, receipt="r_abc123")
        ctx.check(f"taken as a new turn, got {r}", r["ok"] and r["result"]["steered"] is False)
        cmd = rig.controller.commands.get(timeout=2)
        ctx.check(f"a user_input Command with meta {{via, by, receipt}}, got {cmd.kind} {cmd.data.get('meta')}",
                  cmd.kind == "user_input" and cmd.data["meta"] == {"via": "studio", "by": "you@studio", "receipt": "r_abc123"})
        c.call("submit", text="plain phone turn")
        cmd = rig.controller.commands.get(timeout=2)
        ctx.check("a submit without origin carries no meta (the Signal remote's call, unchanged)", not cmd.data.get("meta"))
        notes = _notes(rig)
        ctx.check(f"the transcript says (from Studio), got {notes}", any(t.startswith("(from Studio) prompt: hello from the panel") for t in notes))
        ctx.check("a remote turn still says (remote)", any(t.startswith("(remote) prompt: plain phone turn") for t in notes))
        ctx.check("an unknown when_busy is an error", not c.call("submit", text="x", when_busy="later")["ok"])


@test
def test_when_busy_steer_is_the_default_and_refuse_takes_nothing(ctx: Ctx):
    with Rig() as rig:
        c = rig.client()
        ctx.check("the turn parks on its card", _busy_on_card(rig, c))
        r = c.call("submit", text="not now please", origin=STUDIO, when_busy="refuse")
        ctx.check(f"refuse answers busy with one line, got {r}", r["ok"] and r["result"]["busy"] is True
                  and "queue" in r["result"]["line"].lower() and "steer" in r["result"]["line"].lower())
        ctx.check("refuse took nothing", rig.session.steered == [] and rig.controller.commands.qsize() == 0)
        r = c.call("submit", text="steer it now")
        ctx.check(f"no when_busy: a steer, as always, got {r}", r["ok"] and r["result"]["steered"] is True
                  and rig.session.steered == ["steer it now"])
        r = c.call("submit", text="and steer again", origin=STUDIO, when_busy="steer")
        ctx.check("when_busy steer: the same", r["result"]["steered"] is True and rig.session.steered[-1] == "and steer again")
        c.call("answer", kind="permission", request_id="perm_1", action="allow")
        ctx.check("the turn ends", rig.wait_idle())


@test
def test_queue_holds_one_turn_and_submits_it_on_turn_done(ctx: Ctx):
    from halo_harness.remote.prompt_queue import HINT, hint_for
    with Rig() as rig:
        c = rig.client()
        ctx.check("the turn parks on its card", _busy_on_card(rig, c))
        r = c.call("submit", text="queued from the panel", origin=STUDIO, when_busy="queue", receipt="r_q1")
        ctx.check(f"queued, got {r}", r["ok"] and r["result"]["queued"] is True and r["result"]["busy"] is True)
        ctx.check("the TUI's hint says it", hint_for(rig.controller) == HINT and "1 queued from Studio" in HINT)
        r = c.call("submit", text="a second one", origin=STUDIO, when_busy="queue")
        ctx.check(f"a second queue answers held with one line, got {r}", r["ok"] and r["result"]["held"] is True
                  and r["result"]["queued"] is False and "already queued" in r["result"]["line"])
        ctx.check("nothing steered, nothing queued on the worker yet", rig.session.steered == [] and rig.session.turn_count == 1)
        c.call("answer", kind="permission", request_id="perm_1", action="allow")
        ctx.check("the held turn runs as the next turn", _wait(lambda: rig.session.turn_count == 2 and not rig.session.busy))
        users = [n["content"][0]["text"] for n in rig.session.log.nodes() if n["type"] == "user"]
        ctx.check(f"it ran exactly once, after the first, got {users}", users == ["please ask first", "queued from the panel"])
        ctx.check("the hint is gone", hint_for(rig.controller) == "")
        notes = _notes(rig)
        ctx.check(f"the transcript says it queued and started, got {notes}",
                  any("(from Studio) queued: queued from the panel" in t for t in notes)
                  and any("(from Studio) the queued turn starts: queued from the panel" in t for t in notes))
        time.sleep(0.3)
        ctx.check("no second run", rig.session.turn_count == 2)


@test
def test_a_held_turn_is_dropped_with_one_line_on_quit(ctx: Ctx):
    with Rig() as rig:
        c = rig.client()
        ctx.check("the turn parks on its card", _busy_on_card(rig, c))
        c.call("submit", text="this one waits", origin=STUDIO, when_busy="queue")
        _notes(rig)
        rig.handle.detach()
        notes = _notes(rig)
        ctx.check(f"one line says it was dropped, got {notes}",
                  [t for t in notes if "dropped" in t] == ["(from Studio) the queued turn was dropped (the session is ending): this one waits"])
        ctx.check("nothing is held", rig.controller.prompt_queue.held is None)
        rig.session.resolve_permission("perm_1", {"behavior": "allow"})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
