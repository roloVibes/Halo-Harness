"""tests.test_host_rpc -- Halo 3.3.8.0 R3 deliverable 1: the `rpc_server on | off` host op (host/ops_rpc.py,
host/rpc_runner.py), over tests/helpers/host_act_rig.ActRig and a fake runner (tests/helpers/pool_run_rig.FakeRpc: it
records the argv and listens on 127.0.0.1:<-p>; no rpc-server starts); never a request beyond 127.0.0.1:

1. on: the argv (`-H` the address the host serves on, `-p` the port, `--mem` the card's free VRAM in MiB), the state
   file with pid, port, bound address, binary and version, the trusted-LAN note once; `GET rpc` and status answer it;
   on again is "already on"; off stops it; the audit lines carry the op (read after `audited(n)`);
2. the grants: under fleet.allow_control `none` one line naming the grant and, once per host, the trusted-LAN line;
   `ask` queues a pending row (202); a peer without `control` is refused with the grant named; a dry preview lands
   nothing; no binary is one line (422);
3. `halo host rpc on | status | off` on the worker itself, and `halo pool rpc <member> status | on` from the
   controller through the paired host (tests/helpers/pool_run_rig.RunRig).
Run: python -m tests.test_host_rpc
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_act_rig import ActRig  # noqa: E402
from tests.helpers.pool_rig import free_port  # noqa: E402
from tests.helpers.pool_run_rig import RunRig, rpc_seams  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_on_status_off_and_the_audit(ctx: Ctx):
    from halo_harness.host import ops_rpc
    with ActRig(cap="all", grants=("control",)) as rig, rpc_seams() as fake:
        port = free_port()
        status, got = rig.act("control", "rpc_server", {"to": "on", "port": port})
        argv = fake.argvs[0] if fake.argvs else []
        ctx.check(f"on: 200, the argv binds the host's address, the port, --mem from the card, got {status} {argv}",
                  status == 200 and argv[:5] == ["rpc-server", "-H", "192.0.2.10", "-p", str(port)]
                  and argv[5] == "--mem" and int(argv[6]) == 4096)
        st = json.loads(ops_rpc._path(rig.home).read_text(encoding="utf-8"))
        ctx.check(f"the state file: pid, port, bind, binary, version, got {st}", st["pid"] > 0 and st["port"] == port
                  and st["bind"] == "192.0.2.10" and st["binary"] == "pool.rpc_server_bin"
                  and st["version"]["build"] == 7300 and st["by"] == "carol@peer")
        ctx.check(f"the trusted-LAN note, once, got {got.get('notes')}", "a trusted LAN only" in " ".join(got.get("notes") or []))
        status, view = rig.get("rpc")
        r = view.get("rpc") or {}
        ctx.check(f"GET rpc: running, its pid, port and version, got {status} {r}", status == 200 and r["running"] is True
                  and r["port"] == port and r["version_word"].startswith("b7300") and "rpc v3.0.0" in r["version_word"])
        status, again = rig.act("control", "rpc_server", {"to": "on", "port": port})
        ctx.check(f"on again: already on, no second process, got {again.get('say')!r} {len(fake.argvs)}",
                  status == 200 and again.get("already") is True and len(fake.argvs) == 1 and not again.get("notes"))
        status, off = rig.act("control", "rpc_server", {"to": "off"})
        ctx.check(f"off: stopped, got {status} {off.get('say')!r}", status == 200 and "stopped rpc-server on 192.0.2.10"
                  in off["say"] and not fake.socks)
        ctx.check("status after off: not running", ops_rpc.status(rig.home)["running"] is False)
        n = rig.rig.audited(4)
        from halo_harness.host.state import read_audit
        acts = [a for a in read_audit(rig.home, limit=100) if a.get("op") == "rpc_server"]
        ctx.check(f"the audit: three rpc_server lines, landed, got {n} {acts}", len(acts) == 3
                  and all(a.get("landed") for a in acts) and acts[0]["params"]["to"] == "on")


@test
def test_the_grants_and_the_refusals(ctx: Ctx):
    with ActRig(cap="none", grants=("control",)) as rig, rpc_seams() as fake:
        status, got = rig.act("control", "rpc_server", {"to": "on"})
        err = got.get("error") or ""
        ctx.check(f"none: one line naming the grant and the trusted-LAN line, got {status} {err!r}", status == 403
                  and "rpc_server is a control operation: fleet.allow_control is none on" in err
                  and "halo host grant <peer> control" in err and "a trusted LAN only" in err and not fake.argvs)
        status, got = rig.act("control", "rpc_server", {"to": "on"})
        ctx.check(f"the trusted-LAN line once per host, got {got.get('error')!r}", status == 403
                  and "trusted LAN" not in got["error"])
    with ActRig(cap="ask", grants=("control",)) as rig, rpc_seams() as fake:
        status, got = rig.act("control", "rpc_server", {"to": "on"})
        ctx.check(f"ask: a pending row (202), nothing started, got {status} {got}", status == 202
                  and str(got.get("pending") or "").startswith("p-") and not fake.argvs)
        status, dry = rig.act("control", "rpc_server", {"to": "on"}, dry=True)
        ctx.check(f"dry: the preview, nothing started, got {status} {dry.get('would')}", status == 200 and dry.get("dry")
                  and dry["would"][0].startswith("start rpc-server -H 192.0.2.10") and not fake.argvs)
    with ActRig(cap="all", grants=()) as rig, rpc_seams():
        status, got = rig.act("control", "rpc_server", {"to": "on"})
        ctx.check(f"no control grant: 403 naming it, got {status} {got.get('error')!r}", status == 403
                  and "holds no `control` grant" in got["error"])
    with ActRig(cap="all", grants=("control",)) as rig:
        from halo_harness.theme import set_config_value
        set_config_value("pool.rpc_server_bin", None)
        status, got = rig.act("control", "rpc_server", {"to": "on"})
        ctx.check(f"no binary under the test flag: one line, got {status} {got.get('error')!r}", status == 422
                  and "only a configured pool.rpc_server_bin runs" in got["error"])


def _run(fn, argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn(argv)
    return rc, buf.getvalue()


@test
def test_halo_host_rpc_and_halo_pool_rpc(ctx: Ctx):
    from halo_harness.host_rpc_cli import cmd_rpc
    with ActRig(cap="all", grants=("control",)) as rig, rpc_seams() as fake:
        port = free_port()
        rc, out = _run(cmd_rpc, ["on", "--port", str(port), "--mem", "8192"])
        ctx.check(f"halo host rpc on: the owner needs no grant, its own --mem, got {rc} {out!r} {fake.argvs}", rc == 0
                  and "rpc-server runs on 192.0.2.10:" in out and fake.argvs[-1][-2:] == ["--mem", "8192"]
                  and "a trusted LAN only" in out)
        rc, out = _run(cmd_rpc, ["status"])
        ctx.check(f"status, got {out!r}", rc == 0 and out.startswith(f"rpc-server runs on 192.0.2.10:{port}"))
        rc, out = _run(cmd_rpc, ["off"])
        ctx.check(f"off, got {out!r}", rc == 0 and out.startswith("stopped rpc-server"))
    from halo_harness.pool_run_cli import cmd_rpc as pool_rpc
    with RunRig() as rig:
        rc, out = _run(pool_rpc, ["pc", "status"])
        ctx.check(f"halo pool rpc pc status: through the host, got {rc} {out!r}", rc == 0
                  and out.startswith("pc: rpc-server is not running"))
        rc, out = _run(pool_rpc, ["pc", "on"])
        ctx.check(f"halo pool rpc pc on: the host started it, got {rc} {out!r} {rig.fake.argvs}", rc == 0
                  and "rpc-server runs on 192.0.2.10:" in out and len(rig.fake.argvs) == 1)
        rc, out = _run(pool_rpc, ["me", "status"])
        ctx.check(f"the local member needs none, got {out!r}", rc == 0 and "no rpc-server" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
