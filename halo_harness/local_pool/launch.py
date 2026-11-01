"""halo_harness.local_pool.launch -- the pool runs: the controller's llama-server over every worker's rpc-server (Halo
3.3.8.0 R3; docs/POOL.md "The launch"; `halo local serve --pool <model>`, the Pool page's Warm through
ollama_steward/changes_pool.py, which keeps the steward contract around this).

    argv(prefix, pf, *, gguf, port, key, addr) -> [prefix..., -m <gguf> --alias <model> --rpc <addr:port,...>
        --tensor-split <the fit's model_split, the --rpc devices first, this GPU last> -ngl 999 --host <LAN address>
        --port <p> --api-key <generated> -c <F16 window>]   past the F16 window: --cache-type-k q8_0 --cache-type-v q8_0
        --flash-attn on -c <Q8_0 window>. Every layer on the GPUs: never a CPU fallback.
    start(pf, *, port=0, state_dir=None, home=None, by="user", wait_s=None) -> {ok, lines, run}
        the preflight's answer `pf` must be green; then the claims on every member (local_pool/claims.place: the
        resident Ollama models pivoted out first), each paired worker's rpc-server turned on through its host and its
        version checked again, the api key generated (local_pool/entry.new_key), llama-server started through the
        serve runner (huggingface.llama_server_bin, PATH or a fetched runtime: providers/local_server_cmd.binary) with
        its output in <state>/local/servers/pool-<port>.log, /health waited for, the `pool` entry written and
        <state>/pool/run.json kept. A load that fails (an OOM on a node) is refused with the node and its share, the
        claims released.
    stop(*, state_dir=None, home=None, why="") -> {ok, lines}   the process stopped, the entry removed, the claims
        released (the models the pool pivoted out come back as stated pivot lines), the rpc-servers it started off
    run(state_dir=None) -> run.json | {}        alive(run) -> bool
    redact(argv) -> the argv with the key shown as *** (every logged or recorded copy)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

SEAMS: dict = {}


def _state(state_dir=None):
    from halo_harness.local_pool.claims import _state as s
    return s(state_dir)


def addr() -> str:
    """The LAN address the pool's llama-server binds: pool.bind, else the address this machine's halo host serves on,
    else the interface the default route uses."""
    if "addr" in SEAMS:
        return SEAMS["addr"]()
    from halo_harness.theme import get_config_value
    v = get_config_value("pool.bind", default=None)
    if isinstance(v, str) and v.strip():
        return v.strip()
    from halo_harness.host_rpc_cli import _addr
    from halo_harness.fleet import identity
    return _addr(identity.home())


def _file(state_dir=None) -> Path:
    return Path(_state(state_dir)) / "pool" / "run.json"


def run(state_dir=None) -> dict:
    try:
        got = json.loads(_file(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def _save(data: Optional[dict], state_dir=None) -> None:
    from halo_harness.privateio import write_private_atomic
    p = _file(state_dir)
    if data is None:
        p.unlink(missing_ok=True)
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    write_private_atomic(p, json.dumps(data, indent=1, default=str) + "\n")


def alive(r: dict) -> bool:
    from halo_harness.bg_run import pid_alive
    return bool(r.get("pid")) and bool(pid_alive(r["pid"]))


def redact(cmd: list) -> list:
    return [("***" if i and cmd[i - 1] == "--api-key" else x) for i, x in enumerate(cmd)]


def argv(prefix: list, pf: dict, *, gguf: str, port: int, key: str, addr_: str) -> list:
    split = ",".join(f"{w:g}" for w in pf["split"])
    out = list(prefix) + ["-m", str(gguf), "--alias", pf["model"]]
    if pf["rpc"]:
        out += ["--rpc", ",".join(r["addr"] for r in pf["rpc"])]
    out += ["--tensor-split", split, "-ngl", "999", "--host", addr_, "--port", str(int(port)), "--api-key", key]
    if pf["q8"]:
        out += ["--cache-type-k", "q8_0", "--cache-type-v", "q8_0", "--flash-attn", "on"]
    return out + ["-c", str(int(pf["ctx"]))]


def _rpc_on(pf: dict, home) -> "tuple[bool, list, list]":
    from halo_harness.local_pool import versions as V
    from halo_harness.local_pool.hosts import rpc
    lines, started, workers = [], [], []
    for w in pf["versions"]["workers"]:
        r = next((x for x in pf["rows"] if x["name"] == w["name"]), None)
        if r is None or r["kind"] != "paired":
            workers.append(w)
            continue
        m = {"name": r["name"], "host": r["host"], "rpc_port": r["rpc_port"]}
        if not w.get("running"):
            got = rpc(m, "on", home=home)
            lines.append(got["say"])
            if not got["ok"]:
                return False, lines, started
            started.append(r["name"])
        st = rpc(m, "status", home=home).get("status") or {}
        workers.append({"name": r["name"], "version": st.get("version") or {}})
    blocks, notes = V.compare(pf["versions"]["controller"], workers)
    from halo_harness.local_pool.catalog import get
    more, more_notes = V.min_build(get(pf["model"]) or {}, pf["versions"]["controller"], workers)
    return not (blocks or more), lines + blocks + more + notes + more_notes, started


def _oom(log: Path, pf: dict, shares: dict) -> str:
    import re
    from halo_harness.providers.local_server_cmd import tail_lines
    text = tail_lines(log, 60)
    bad = next((x for x in reversed(text) if re.search(r"out of memory|cudaMalloc failed|failed to allocate|"
                                                       r"unable to allocate", x, re.IGNORECASE)), "")
    if not bad:
        return " | ".join(text[-4:])
    who = next((r["member"] for r in pf["rpc"] if r["addr"] in bad), (pf["local"] or ["this machine"])[0])
    return (f"refused: the load ran out of memory on {who} ({bad.strip()[:160]}) -- its share is {shares.get(who, 0):.1f} "
            "GB; no CPU fallback (-ngl 999)")


def start(pf: dict, *, port: int = 0, state_dir=None, home=None, by: str = "user", wait_s: Optional[float] = None) -> dict:
    from halo_harness.local_pool import catalog as C, claims, entry
    from halo_harness.providers import local_runtime as R
    from halo_harness.providers.local_server_cmd import binary, get
    if not pf or not pf.get("ok"):
        return {"ok": False, "lines": [(pf or {}).get("line") or "the preflight did not pass"]}
    if alive(run(state_dir)):
        return {"ok": False, "lines": [f"the pool already runs {run(state_dir).get('model')}: stop it first"]}
    if entry.clash():
        return {"ok": False, "lines": [entry.clash()]}
    prefix, why = binary("llama-server", state_dir=_state(state_dir))
    if prefix is None:
        return {"ok": False, "lines": [why]}
    model = C.get(pf["model"])
    ok, lines, placed = claims.place(model, pf["fit"], pf["rows"], ctx=pf["ctx"], q8=pf["q8"], state_dir=state_dir, home=home)
    if not ok:
        return {"ok": False, "lines": lines}
    ok, more, started = _rpc_on(pf, home)
    lines += more
    if not ok:
        return {"ok": False, "lines": lines + claims.release(placed, state_dir=state_dir, home=home, model=model["name"])
                + _rpc_off(started, placed, home)}
    a, port = addr(), int(port) if port else R.find_free_port()
    cmd = argv(prefix, pf, gguf=pf["gguf"]["path"], port=port, key=entry.new_key(), addr_=a)
    log = Path(_state(state_dir)) / "local" / "servers" / f"pool-{port}.log"
    from halo_harness.local_pool.spawn import spawn, wait_ready
    pid = spawn(cmd, log, redact(cmd))
    url = f"http://{a}:{port}"
    r = {"model": pf["model"], "display": pf["display"], "pid": pid, "port": port, "addr": a, "url": f"{url}/v1",
         "log": str(log), "argv": redact(cmd), "ctx": pf["ctx"], "cache": pf["cache"], "placed": placed,
         "rpc_started": started, "members": pf["used"], "rpc": pf["rpc"], "split": pf["split"], "order": pf["order"],
         "started": round(time.time(), 3), "by": by, "binary": why}
    _save(r, state_dir)
    ready, said = wait_ready(pid, url, get, wait_s if wait_s is not None else 120.0)
    if not ready and said == "exited":
        why = _oom(log, pf, claims.shares(model, pf["fit"], pf["ctx"], pf["q8"]))
        return {"ok": False, "lines": lines + [why] + stop(state_dir=state_dir, home=home, why="the load failed")["lines"]}
    entry.write(url=f"{url}/v1", model=pf["model"], ctx=pf["ctx"], log=str(log), members=pf["used"], cache=pf["cache"])
    lines.append(f"the pool serves {pf['display']} on {url}/v1 as hf:local/{pf['model']}@pool -- " +
                 ("ready" if ready else f"still loading ({said}): halo local log pool shows its progress"))
    return {"ok": True, "lines": lines, "run": r, "ready": ready}


def _rpc_off(names: list, placed: list, home) -> list:
    """The rpc-servers this launch turned on are turned off again (one it found running stays)."""
    from halo_harness.local_pool.hosts import rpc
    out = []
    for name in names:
        row = next((p for p in placed if p["member"] == name), None)
        if row:
            out.append(rpc({"name": name, "host": row["host"], "rpc_port": row["rpc_port"]}, "off", home=home)["say"])
    return out


def stop(*, state_dir=None, home=None, why: str = "") -> dict:
    from halo_harness.local_pool import claims, entry
    r = run(state_dir)
    if not r:
        gone = entry.remove()
        return {"ok": True, "lines": ["the pool is not running" + ("; its stale pool entry was removed" if gone else "")]}
    lines = []
    if alive(r):
        from halo_harness.local_pool.spawn import halt
        lines.append(f"stopped the pool's llama-server (pid {r['pid']}): {halt(r['pid'])}")
    else:
        lines.append(f"the pool's llama-server (pid {r.get('pid')}) had already exited")
    if entry.remove():
        lines.append("removed the pool entry (hf:local/...@pool)")
    lines += claims.release(r.get("placed") or [], state_dir=state_dir, home=home, model=r.get("model") or "")
    lines += _rpc_off(r.get("rpc_started") or [], r.get("placed") or [], home)
    _save(None, state_dir)
    return {"ok": True, "lines": lines + ([f"why: {why}"] if why else [])}
