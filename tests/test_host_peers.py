"""tests.test_host_peers -- Halo 3.3.7.0 R2 deliverable 5, the Python half: peers act through the host
(fleet/hub_host_cmd.py, studio/local_host_acts.py, studio/local_host_api.py, ollama_steward/host_land.py,
host_fold.py, host/findings.py, host/ledger_push.py + ledger_take.py) over tests/helpers/host_act_rig.PeerRig:

1. controls: `via: "host"` and ok when this peer holds control, the grant line and "Request control" otherwise;
   the request writes a pending row the owner allows (the grant lands);
2. Load / Unload from Studio go through the host (no member session); Probe and Bench run on the host and their
   frames come back as this Studio's jobs (the bench's speed card kept here under this machine's name);
3. the steward lands through the host: `control/set_num_ctx` citing the finding, a host-apply journal line, the
   local mirror; the host's verdict comes back (`host_land.sync`) and a revert takes the mirror with it;
4. `GET findings` carries where / suggest; the peer's job folds them under its own names;
5. a peer's calls reach the host's ledger (`from` the peer) and the answer carries the host's profiles.
Run: python -m tests.test_host_peers
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_act_rig import BIG, CODER, SMALL, PeerRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _pc(rig) -> dict:
    code, got = rig.studio("GET", "local/hosts")
    return next((h for h in got.get("hosts") or [] if h["name"] == "pc"), {})


def _wait(fn, timeout: float = 10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.1)
    return fn()


@test
def test_controls_and_request_control(ctx: Ctx):
    from halo_harness.host import grants
    with PeerRig(cap="ask", grants=()) as rig:
        c = _pc(rig)["controls"]
        ctx.check(f"view only: the grant line and Request control, got {c}", c["via"] == "host" and c["ok"] is False
                  and c["request"] is True and "need `control`" in c["why"] and "Request control here" in c["why"])
        code, got = rig.studio("POST", "local/host/pc/request-control")
        rows = grants.pending(rig.home)
        ctx.check(f"request control: a pending grant row on the host, got {code} {got}", code == 200 and rows
                  and rows[0]["kind"] == "grant" and rows[0]["peer"] == "bob@peer" and "halo host allow" in got["say"])
        ok, line = grants.answer(rig.home, rows[0]["id"], True)
        from halo_harness.ollama_steward import host_client
        host_client.reset()
        c = _pc(rig)["controls"]
        ctx.check(f"allowed: control through the host, its owner asked first, got {c}", ok and c["ok"] is True
                  and c["via"] == "host" and c["asks"] is True and "its owner is asked first" in c["via_line"])


@test
def test_studio_acts_through_the_host(ctx: Ctx):
    with PeerRig(cap="all", grants=("manage",)) as rig:
        code, got = rig.studio("POST", "local/host/pc/load", {"model": SMALL, "num_ctx": 8192})
        ctx.check(f"Load from Studio: the host's warm, no member session, got {code} {got}", code == 200 and got.get("ok")
                  and rig.mock.generated and rig.mock.generated[-1]["model"] == SMALL and "halo host" in str(got.get("via")))
        code, got = rig.studio("POST", "local/host/pc/unload", {"model": SMALL})
        ctx.check(f"Unload, got {code}", code == 200 and rig.mock.generated[-1]["keep_alive"] in (0, "0"))
        frames: list = []
        import halo_harness.studio.local_control_api as LC
        saved = LC._pub
        LC._pub = lambda req: frames.append
        try:
            code, got = rig.studio("POST", "local/host/pc/probe", {"model": SMALL})
            ctx.check(f"Probe: the host's job started, a job here, got {code} {got}", code == 200 and got.get("host_job"))
            from halo_harness.studio import local_probe_job as PJ
            done = _wait(lambda: next((j for j in PJ.current()["jobs"] if j["job"] == got.get("job") and j["done"]), None))
            ctx.check(f"its frames came here and it ended, got {done}", done is not None
                      and any(f.get("event") == "probe" for f in frames))
            code, got = rig.studio("POST", "local/host/pc/bench", {"model": SMALL, "quick": True})
            ctx.check(f"Bench: the host runs it, got {code} {got}", code == 200 and got.get("host_job"))
            from halo_harness.studio import local_bench_job as BJ
            done = _wait(lambda: next((j for j in BJ.current()["jobs"] if j["job"] == got.get("job") and j["done"]), None))
            ctx.check(f"the bench job here ended with the host's answer, got {(done or {}).get('line')}", done is not None)
        finally:
            LC._pub = saved
        from tests.helpers.mock_ollama_pull import HF_SHOW
        rig.mock.pullable["new-model:7b"] = HF_SHOW
        code, got = rig.studio("POST", "local/host/pc/pull", {"name": "new-model:7b"})
        from halo_harness.studio import local_pull_job as LJ
        done = _wait(lambda: next((j for j in LJ.current()["jobs"] if j["job"] == got.get("job") and j["done"]), None))
        ctx.check(f"Pull through the host (manage): the job here follows the host's, got {code} {done}", code == 200
                  and done is not None and done.get("ok") and "new-model:7b" in str(rig.mock.pulled))
        code, got = rig.studio("POST", "local/host/pc/delete", {"name": SMALL})
        ctx.check(f"Delete through the host, got {code} {got}", code == 200 and SMALL in str(rig.mock.deleted))
        code, got = rig.studio("POST", "local/host/pc/copy", {"src": SMALL, "dst": "x:1"})
        ctx.check(f"copy is not in the vocabulary: one line, got {code} {got}", code == 409 and "not in its vocabulary" in got["error"])


def _finding(key="pc|qwen3-coder:30b") -> dict:
    return {"id": "cpu-spill-77aa01", "rule": "cpu-spill", "host": "pc", "model": CODER, "key": key, "severity": "warn",
            "finding": "3 CPU spills of qwen3-coder:30b", "evidence": {}, "proposal": None, "server_hint": None}


@test
def test_the_steward_lands_through_the_host(ctx: Ctx):
    from halo_harness.host import verify
    from halo_harness.ollama_steward import host_land, steward
    from halo_harness.ollama_steward.profiles import all_profiles
    with PeerRig(cap="all", grants=("control",)) as rig:
        f = _finding()
        change = {"field": "num_ctx", "from": None, "to": 16384, "why": "the card spills at 32,768"}
        row = steward.apply_change(rig.peer, f, change, mode_name="auto")
        host_rows = verify._rows(rig.home)
        ctx.check(f"a host-apply line, landed, the host's change id, got {row}", row["kind"] == "host-apply"
                  and row["landed"] is True and row["host_change"] and row["finding"] == f["id"])
        ctx.check(f"the host's fix row cites the finding, got {host_rows}", host_rows and host_rows[-1]["evidence"]["finding"]
                  == f["id"] and host_rows[-1]["peer"] == "bob@peer" and host_rows[-1]["op"] == "set_num_ctx")
        ctx.check("the local mirror", all_profiles().get(f["key"], {}).get("num_ctx") == 16384)
        ctx.check("no verdict yet", host_land.sync(rig.peer) == [])
        rig.lines(CODER, 10, tok_s=40.0, ago=600)
        rig.lines(CODER, 5, tok_s=40.0, trimmed=True, ago=-1)
        verify.tick(rig.svc)
        out = host_land.sync(rig.peer)
        ctx.check(f"the verdict comes back into the journal, got {[r.get('say') for r in out]}", out
                  and out[0]["verdict"] == "reverted" and "reverted it" in out[0]["say"])
        ctx.check("the revert took the mirror with it", "num_ctx" not in (all_profiles().get(f["key"]) or {}))
        ctx.check("once only", host_land.sync(rig.peer) == [])
    with PeerRig(cap="all", grants=()) as rig:
        row = steward.apply_change(rig.peer, _finding(), {"field": "num_ctx", "from": None, "to": 16384, "why": "x"},
                                   mode_name="auto")
        ctx.check(f"without the grant: a host-refused line naming it, got {row.get('say')}", row["kind"] == "host-refused"
                  and row["landed"] is False and "`control` grant" in row["say"])


@test
def test_findings_where_and_the_fold(ctx: Ctx):
    from halo_harness.host.findings import suggest_of, where_of
    from halo_harness.ollama_steward.host_fold import fold, reset
    ctx.check("a cut with no room is the client's", where_of({"rule": "reply-cut", "proposal": None}) == "client")
    ctx.check("a window proposal is the host's: set_num_ctx", suggest_of({"rule": "window-small", "proposal":
              {"field": "num_ctx", "to": 32768}}) == ["set_num_ctx 32768"])
    ctx.check("a KV line is a stated op", suggest_of({"rule": "thrash", "proposal": None, "server_hint":
              {"env": "OLLAMA_KV_CACHE_TYPE", "line": "OLLAMA_KV_CACHE_TYPE=q8_0"}}) == ["set_kv_cache_type q8_0"])
    with PeerRig(cap="all", grants=("control",)) as rig:
        rig.lines(BIG, 6, tok_s=40.0, trimmed=True, ago=300)
        got = rig.client().get("findings")["findings"]
        ctx.check(f"GET findings: each with where and suggest, got {[(f['rule'], f['where']) for f in got]}", got
                  and all(f.get("where") in ("host", "client") and isinstance(f.get("suggest"), list) for f in got))
        reset()
        folded = fold(rig.peer, [])
        ctx.check(f"folded under this machine's names, the host as the source, got {[f['key'] for f in folded]}",
                  folded and all(f["host"] == "pc" and "seen by the host at" in f["finding"] for f in folded))


@test
def test_a_peers_calls_reach_the_host(ctx: Ctx):
    from halo_harness.host.ledger_push import push_all, reset
    from halo_harness.ollama_steward.ledger import read_calls
    with PeerRig(cap="all", grants=()) as rig:
        reset()
        rig.peer_lines(CODER, 3, tok_s=55.0, ago=30)
        n = push_all(rig.peer, force=True)
        mine = [x for x in read_calls(rig.home) if x.get("from") == "bob@peer"]
        ctx.check(f"pushed to the host, kept there with from = the peer, got {n} {len(mine)}", n == 3 and len(mine) == 3)
        ctx.check("a second push sends nothing new", push_all(rig.peer, force=True) == 0)


@test
def test_the_hub_forwards_to_a_host_a_member_announced(ctx: Ctx):
    from types import SimpleNamespace
    from halo_harness.fleet import hub_hosts
    from halo_harness.fleet.hub_host_cmd import member_controls
    with PeerRig(cap="all", grants=("control",)) as rig:
        hub = SimpleNamespace(home=rig.peer)
        who = {"member": "pc-host", "member_host": "pc"}
        ctx.check("no announce: nothing to say", member_controls(hub, "pc-host", who) is None)
        hub_hosts.record(rig.peer, "h1", "pc-host", "192.0.2.10", {"host": True, "port": rig.svc.port,
                         "url": "https://192.0.2.99:7431", "fingerprint": "f" * 64, "serves": []})
        got = member_controls(hub, "pc-host", who)
        ctx.check(f"announced, not paired: the join line, got {got}", got and got["ok"] is False
                  and "halo host join https://192.0.2.99:7431" in got["why"])
        hub_hosts.record(rig.peer, "h1", "pc-host", "192.0.2.10", {"host": True, "port": rig.svc.port, "url": rig.entry["url"],
                         "fingerprint": rig.entry.get("fingerprint"), "serves": []})
        got = member_controls(hub, "pc-host", who)
        ctx.check(f"announced and paired: through the host, no session, got {got}", got and got["ok"] is True
                  and got["via"] == "host" and got["member"] == "pc-host")
        hub_hosts.HOSTS.pop(str(rig.peer), None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
