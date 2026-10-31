"""tests.test_host_grants -- Halo 3.3.7.0 R2 deliverable 1: per-peer grants on a halo host (host/grants.py,
host/pending.py, the `halo host grant | revoke | peers | pending | allow | deny` commands, `GET me`):

1. each cap level (fleet.allow_control none / ask / all) with each grant (view / control / manage / admin): a view
   peer gets 403 naming `control`; `none` answers 403 "strictly a monitor"; `ask` queues a pending row (202) that
   the owner allows, after which the same request runs once; `all` applies it; manage holds control's ops; admin
   is its own grant and answers 501 "not part of this version";
2. the pending row's TTL (host.ask_ttl_s): expired rows leave `pending`, an answer to one says it expired;
3. `GET me`: the grants, the cap, what applies, the vocabulary; a peer's "request control" is a pending row the
   owner's allow turns into the grant;
4. the commands print their lines (grant / revoke / peers / pending / allow / deny).
Run: python -m tests.test_host_grants
"""
from __future__ import annotations

import contextlib
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_act_rig import SMALL, ActRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _unload(rig):
    return rig.act("control", "unload", {"model": SMALL})


@test
def test_each_cap_with_each_grant(ctx: Ctx):
    with ActRig(cap="all", grants=()) as rig:
        status, got = _unload(rig)
        ctx.check(f"view only: 403 naming the control grant and the command, got {status} {got}", status == 403
                  and "holds no `control` grant" in got["error"] and "halo host grant carol@peer control" in got["error"])
    with ActRig(cap="none", grants=("control",)) as rig:
        status, got = _unload(rig)
        ctx.check(f"none: 403, strictly a monitor, got {status} {got}", status == 403
                  and "fleet.allow_control is none" in got["error"] and "strictly a monitor" in got["error"])
        status, got = rig.act("control", "unload", {"model": SMALL}, dry=True)
        ctx.check("none: a dry preview is view-only too", status == 403)
    with ActRig(cap="ask", grants=("control",)) as rig:
        from halo_harness.host import grants
        status, got = _unload(rig)
        ctx.check(f"ask: 202 and a pending row named in the line, got {status} {got}", status == 202
                  and got["pending"].startswith("p-") and f"halo host allow {got['pending']}" in got["line"])
        status2, got2 = _unload(rig)
        ctx.check("ask: the same request again is the same row", status2 == 202 and got2["pending"] == got["pending"])
        status, dry = rig.act("control", "unload", {"model": SMALL}, dry=True)
        ctx.check(f"ask: a dry preview is not queued, got {status} {dry}", status == 200 and dry["dry"] is True)
        ok, line = grants.answer(rig.home, got["pending"], True)
        ctx.check(f"the owner allows it, got {line!r}", ok and "runs once" in line)
        status, ran = _unload(rig)
        ctx.check(f"after allow the request runs, got {status} {ran}", status == 200 and ran["ok"] is True)
        status, again = _unload(rig)
        ctx.check("spent: the next one is queued again", status == 202 and again["pending"] != got["pending"])
        grants.answer(rig.home, again["pending"], False)
        ctx.check("a denied row leaves pending", not [r for r in grants.pending(rig.home) if r["id"] == again["pending"]])
    with ActRig(cap="all", grants=("control",)) as rig:
        status, got = _unload(rig)
        ctx.check(f"all: applied, got {status} {got}", status == 200 and got["ok"] is True and got["op"] == "unload")
        status, got = rig.act("manage", "delete", {"model": SMALL})
        ctx.check(f"control does not hold manage, got {status}", status == 403 and "`manage` grant" in got["error"])
    with ActRig(cap="all", grants=("manage",)) as rig:
        status, got = _unload(rig)
        ctx.check(f"manage holds control's ops, got {status}", status == 200)
        status, got = rig.act("admin", "raw", {})
        ctx.check(f"manage never implies admin, got {status} {got}", status == 403 and "`admin` grant" in got["error"])
        from halo_harness.host import grants
        grants.grant(rig.home, rig.rig.peer_id, "admin")
        status, got = rig.act("admin", "raw", {"cmd": "x"})
        ctx.check(f"admin: 501, not part of this version, got {status} {got}", status == 501
                  and "not part of this version" in got["error"] and "nothing runs a shell" in got["error"])


@test
def test_the_pending_rows_ttl(ctx: Ctx):
    with ActRig(cap="ask", grants=("control",)) as rig:
        from halo_harness.host import grants
        rig.rig.set_peer(**{"host.ask_ttl_s": 30})
        status, got = _unload(rig)
        row = next(r for r in grants.pending(rig.home) if r["id"] == got["pending"])
        ctx.check(f"the row lives host.ask_ttl_s, got {row['expires'] - row['at']:.0f}", 29 <= row["expires"] - row["at"] <= 31)
        later = time.time() + 60
        ctx.check("an expired row leaves pending", not grants.pending(rig.home, now=later))
        ok, line = grants.answer(rig.home, got["pending"], True, now=later)
        ctx.check(f"answering it says it expired, got {line!r}", not ok and "expired" in line)


@test
def test_me_and_a_grant_request(ctx: Ctx):
    with ActRig(cap="ask", grants=()) as rig:
        from halo_harness.host import grants
        status, me = rig.get("me")
        ctx.check(f"me: the grants, the cap, the vocabulary, got {status} {list(me)}", status == 200
                  and me["grants"] == ["view"] and me["cap"] == "ask" and me["effective"] == ["view"]
                  and {"warm", "set_num_ctx", "pull", "revert"} <= {o["name"] for o in me["vocabulary"]})
        got = rig.client().request_grant("control", "to load models from the laptop")
        ctx.check(f"request control: queued, got {got}", got.get("queued") and got["pending"].startswith("p-"))
        ok, line = grants.answer(rig.home, got["pending"], True)
        ctx.check(f"the owner's allow gives the grant, got {line!r}", ok and "control" in line)
        status, me = rig.get("me")
        ctx.check(f"me now holds control and asks first, got {me}", "control" in me["grants"] and me["asks"] is True)


def _run(fn, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = fn(argv)
    return rc, out.getvalue() + err.getvalue()


@test
def test_the_commands(ctx: Ctx):
    from halo_harness import host_pair_cli as P
    with ActRig(cap="ask", grants=()) as rig:
        rc, out = _run(P.cmd_grant, ["carol@peer", "control"])
        ctx.check(f"grant: the peer's grants and the cap's word, got {out!r}", rc == 0 and "view, control" in out
                  and "queued for you first" in out)
        rc, out = _run(P.cmd_peers, [])
        ctx.check(f"peers: name, grants, last seen, requests, got {out!r}", rc == 0 and "carol@peer" in out
                  and "view, control" in out and "requests" in out and "ask" in out)
        _unload(rig)
        rc, out = _run(P.cmd_pending, [])
        ctx.check(f"pending: the row and how to answer it, got {out!r}", rc == 0 and "carol@peer asks: unload" in out)
        pid = out.split("[", 1)[1].split("]", 1)[0]
        rc, out = _run(P.cmd_allow, [pid])
        ctx.check(f"allow, got {out!r}", rc == 0 and "allowed unload" in out)
        rc, out = _run(P.cmd_deny, [pid])
        ctx.check(f"deny of an answered row says so, got {out!r}", rc == 1 and "nothing to answer" in out)
        rc, out = _run(P.cmd_revoke, ["carol@peer", "control"])
        ctx.check(f"revoke, got {out!r}", rc == 0 and "holds view on" in out)
        rc, out = _run(P.cmd_revoke, ["carol@peer", "view"])
        ctx.check(f"view stays, got {out!r}", rc == 1 and "every paired peer's" in out)
        rc, out = _run(P.cmd_grant, ["nobody", "control"])
        ctx.check(f"an unknown peer, got {out!r}", rc == 1 and "no peer of this host matches" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
