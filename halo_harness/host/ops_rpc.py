"""halo_harness.host.ops_rpc -- `rpc_server on | off`, the pool worker's op (Halo 3.3.8.0 R3; host/ops.py has the
registry; docs/HOST.md "rpc_server"; docs/POOL.md "The workers").

    rpc_server {to: on | off, port?, mem_mib?}   control grant (a pending row under host.allow_control: ask; under
        `none` one line naming the grant, and once per host that RPC is for a trusted LAN only)
        on:  `rpc-server -H <the LAN address this host serves on> -p <port: pool.rpc_port, 50052> --mem <this machine's
             free VRAM in MiB>` through host/rpc_runner (the runner seam), its pid, port, bound address, binary and
             version kept in `<state>/host/rpc_server.json`, its output in `<state>/host/rpc-server.log`
        off: the rpc-server this host started is stopped; the file keeps what it was
    GET rpc (view grant) -> status(home): {running, pid, port, bind, mem_mib, version, version_word, binary, started, by,
        log, line}

    free_mib(home, card_rows) -> (MiB | None, line)    usable with the helper - resident - claims (the pool's own claim
                                                       left out: it is the room rpc-server serves)
    turn_on(home, *, addr, card_rows, port=None, mem_mib=None, by) / turn_off(home, *, by) / status(home)
    refused(home, status, out) -> out   the refusal of an rpc_server request as one line (routes_act calls it)
Starting and stopping the rpc-server this host launched is the op's stated action; nothing else on the machine changes.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from halo_harness.host.ops import Op
from halo_harness.host.ops_control import LOCAL_TIME

FILE, LOG = "rpc_server.json", "rpc-server.log"
MIB = 2 ** 20


def _path(home) -> Path:
    from halo_harness.host.state import host_dir
    return host_dir(home) / FILE


def read(home) -> dict:
    try:
        got = json.loads(_path(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def _write(home, data: dict) -> None:
    from halo_harness.privateio import write_private_atomic
    p = _path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_private_atomic(p, json.dumps(data, indent=1) + "\n")


def lan_line(addr: Optional[str] = None) -> str:
    where = f"{addr}, the address this host serves on" if addr else "the LAN address this host serves on"
    return (f"rpc-server has no authentication and no encryption (llama.cpp calls it a proof of concept): a trusted LAN "
            f"only -- it binds {where}, never 0.0.0.0")


def _once(home, addr: Optional[str] = None) -> list:
    st = read(home)
    if st.get("lan_said"):
        return []
    _write(home, {**st, "lan_said": round(time.time(), 3)})
    return [lan_line(addr)]


def free_mib(home, card_rows: list) -> "tuple[Optional[int], str]":
    from halo_harness.local_pool.budget import GIB, _from_card
    from halo_harness.local_sched.claims_file import host_file, read as claims
    rows = [r for r in card_rows or [] if isinstance(r, dict) and (r.get("card") or {}).get("gpus")]
    if not rows:
        return None, "no GPU on this machine's card: rpc-server reports its own free memory (no --mem)"
    r = rows[0]
    held = [c for c in claims(host_file(home)) if not str(c.get("bundle") or "").startswith("pool:")
            and str(c.get("host") or "").lower() == str(r.get("name") or "").lower()]
    usable = r.get("usable_with_helper_gb")
    out: dict = {}
    _from_card(out, r.get("card") or {}, int(float(usable) * GIB) if isinstance(usable, (int, float)) else 0,
               r.get("helper"), held)
    if not isinstance(out.get("free_gb"), (int, float)) or out["free_gb"] <= 0:
        return None, f"{r.get('name')}'s card leaves no free VRAM: rpc-server reports its own (no --mem)"
    return int(out["free_gb"] * 1024), (f"{out['free_gb']:.1f} GB free on {r.get('name')}'s {out.get('gpu')} (usable "
                                        f"{out.get('usable_gb'):.1f} GB, {out.get('resident_gb'):.1f} GB resident)")


def status(home) -> dict:
    from halo_harness.host import rpc_runner as R
    from halo_harness.local_pool.versions import word
    st = read(home)
    up = bool(st.get("pid")) and R.alive(st.get("pid"))
    v = dict(st.get("version") or {})
    if up and not v.get("rpc_proto") and st.get("log"):
        v["rpc_proto"] = R.proto_from_log(st["log"])
    door = f"{st.get('bind')}:{st.get('port')}"
    line = (f"rpc-server runs on {door} (pid {st.get('pid')}, {word(v)}, --mem {st.get('mem_mib') or 'its own'} MiB)" if up
            else f"rpc-server is not running (last on {door}, stopped)" if st.get("port") else "rpc-server is not running")
    return {"running": up, **{k: st.get(k) for k in ("pid", "port", "bind", "mem_mib", "binary", "started", "by", "log")},
            "pid": st.get("pid") if up else None, "version": v, "version_word": word(v), "line": line}


def plan(home, *, addr: str, card_rows: list, port=None, mem_mib=None) -> dict:
    from halo_harness.host import rpc_runner as R
    from halo_harness.local_pool.members import rpc_port
    prefix, why = R.binary(home)
    mem, mem_why = (int(mem_mib), "asked") if isinstance(mem_mib, int) and mem_mib > 0 else free_mib(home, card_rows)
    p = int(port or rpc_port())
    return {"prefix": prefix, "binary": why, "argv": R.argv(prefix or ["rpc-server"], bind=addr, port=p, mem_mib=mem),
            "port": p, "bind": addr, "mem_mib": mem, "mem_why": mem_why}


def turn_on(home, *, addr: str, card_rows: list, port=None, mem_mib=None, by: str = "owner") -> dict:
    from halo_harness.host import rpc_runner as R
    from halo_harness.local_pool.versions import read as version, word
    now = status(home)
    if now["running"]:
        return {"ok": True, "already": True, "say": f"{now['line']}: already on", "rpc": now}
    pl = plan(home, addr=addr, card_rows=card_rows, port=port, mem_mib=mem_mib)
    if pl["prefix"] is None:
        return {"ok": False, "status": 422, "say": pl["binary"]}
    v = version(pl["prefix"])
    log = _path(home).with_name(LOG)
    try:
        pid = R.start(pl["argv"], log)
    except OSError as e:
        return {"ok": False, "say": f"rpc-server did not start: {e}"}
    st = {**read(home), "pid": pid, "port": pl["port"], "bind": addr, "mem_mib": pl["mem_mib"], "binary": pl["binary"],
          "argv": pl["argv"], "version": {k: v.get(k) for k in ("build", "commit", "rpc_proto", "line")},
          "started": round(time.time(), 3), "by": by, "log": str(log), "mem_why": pl["mem_why"]}
    _write(home, st)
    return {"ok": True, "say": f"rpc-server runs on {addr}:{pl['port']} (pid {pid}, {word(v)}; --mem from {pl['mem_why']})",
            "rpc": status(home), "argv": pl["argv"]}


def turn_off(home, *, by: str = "owner") -> dict:
    from halo_harness.host import rpc_runner as R
    st = read(home)
    if not st.get("pid") or not R.alive(st.get("pid")):
        return {"ok": True, "say": "rpc-server was not running: nothing to stop", "rpc": status(home)}
    how = R.stop(st["pid"])
    _write(home, {**st, "pid": None, "stopped": round(time.time(), 3), "stopped_by": by})
    return {"ok": True, "say": f"stopped rpc-server on {st.get('bind')}:{st.get('port')} (pid {st['pid']}): {how}",
            "rpc": status(home)}


def _rows(ctx) -> list:
    return ctx.view.card().get("hosts") or []


def p_rpc(ctx, p):
    if p["to"] not in ("on", "off"):
        raise ValueError("to: on or off")
    if p["to"] == "off":
        st = status(ctx.home)
        return {"would": [f"stop rpc-server on {st.get('bind')}:{st.get('port')} (pid {st.get('pid')})" if st["running"]
                          else "nothing: rpc-server is not running"], "writes": [f"<state>/host/{FILE}"], "takes": "~1 s",
                "cost": LOCAL_TIME}
    pl = plan(ctx.home, addr=ctx.svc.addr(), card_rows=_rows(ctx), port=p.get("port"), mem_mib=p.get("mem_mib"))
    out = {"would": [f"start {' '.join(pl['argv'])}", f"--mem: {pl['mem_why']}", lan_line(pl["bind"])],
           "writes": [f"<state>/host/{FILE}", f"<state>/host/{LOG}"], "takes": "~1 s", "cost": LOCAL_TIME,
           "argv": pl["argv"]}
    if pl["prefix"] is None:
        out["breach"] = pl["binary"]
    return out


def a_rpc(ctx, p):
    if p["to"] == "off":
        got = turn_off(ctx.home, by=ctx.peer)
    else:
        got = turn_on(ctx.home, addr=ctx.svc.addr(), card_rows=_rows(ctx), port=p.get("port"), mem_mib=p.get("mem_mib"),
                      by=ctx.peer)
        if got.get("ok"):
            got["notes"] = _once(ctx.home, ctx.svc.addr())
    ctx.publish("event", {"kind": f"rpc-server-{p['to']}", "say": got.get("say")})
    return got


def refused(home, status_code: int, out: dict) -> dict:
    """One line: the grant the op needs (and, the first time on this host, the trusted-LAN line)."""
    from halo_harness.peers import identity
    if status_code != 403:
        return out
    name = identity.harness_name(home)
    line = (f"rpc_server is a control operation: host.allow_control is none on {name}, so it runs only after "
            f"`halo config set host.allow_control ask` (or all) there and `halo host grant <peer> control`"
            if out.get("cap") == "none" else str(out.get("error") or ""))
    lan = _once(home)
    return {**out, "error": line + (f"; {lan[0]}" if lan else "")}


TABLE = [Op("rpc_server", "control", {"to": ("str", True, "on or off"), "port": ("int", False, "the RPC port (pool.rpc_port)"),
                                      "mem_mib": ("int", False, "--mem in MiB (default: this machine's free VRAM)")},
            p_rpc, a_rpc, help="start or stop llama.cpp's rpc-server for a pool (on the LAN address this host serves on)")]
