"""halo_harness.local_pool.degrade -- the running pool's health and its failure modes as lines (Halo 3.3.8.0 R3;
docs/POOL.md "When something fails").

    status(state_dir=None, home=None) -> {state, line, run, members, degraded, down, health, claims_line, judge, log}
        state: stopped | loading | running | degraded | down
        running   llama-server answers /health and every worker's rpc-server port answers
        degraded  a worker is down: its RPC port does not answer, or the controller's log (R2's server-log reader)
                  shows an RPC backend failing -- "degraded (worker2 down)" on the page, in `route` and in a failed
                  request's line; nothing retries it
        down      the pool's llama-server exited (its last log line said)
        each member row: {name, kind, addr, share_gb, alive, claim {gb, until, live}}, the claims' lease said
    rpc_failures(lines) -> [line]   the RPC lines of the controller's log ("Remote RPC server crashed or returned
                                    malformed response", "failed to connect to <addr>", "RPC ... connection closed")
    is_pool_ref(ref) -> bool        an `hf:local/<model>@pool` ref
    failed_line(message, state_dir=None, http=None) -> the request's error line: "the pool is degraded (worker2
                                    down): the request failed once and is not retried -- the pool's llama-server answered 500"
Reads only: the probe is one TCP connect per worker, the log a tail of the file Halo's own llama-server writes.
"""

from __future__ import annotations

import re
import time
from typing import Optional

RPC_BAD = re.compile(r"RPC server crashed|returned malformed response|failed to connect to|RPC\S*\s.*(?:closed|lost|"
                     r"refused|failed|error)|ggml_backend_rpc\S*.*(?:failed|error)", re.IGNORECASE)


def rpc_failures(lines: list) -> list:
    return [x.strip() for x in lines if RPC_BAD.search(x)]


def is_pool_ref(ref) -> bool:
    from halo_harness.local_pool import POOL_SERVER_NAME
    return getattr(ref, "provider", "") == "huggingface" and bool(getattr(ref, "local", False)) \
        and str(getattr(ref, "host", "") or "").lower() == POOL_SERVER_NAME


def _log_tail(r: dict, n: int = 400) -> list:
    from halo_harness.providers.local_server_cmd import tail_lines
    lines = tail_lines(r.get("log") or "", n)
    start = max((i for i, x in enumerate(lines) if x.startswith("--- halo starts:")), default=-1)
    return lines[start + 1:]


def _claim(p: dict, bundle: str, state_dir, home) -> dict:
    from halo_harness.local_sched import claims_file as CF
    if p["kind"] == "local":
        from halo_harness.local_pool.claims import _state
        rows = CF.read(CF.local_file(_state(state_dir)), expired=True)
    elif p["kind"] == "paired":
        from halo_harness.local_pool.hosts import client
        c, _k, _l = client({"name": p["member"], "host": p["host"], "rpc_port": p["rpc_port"]}, home)
        try:
            rows = [x for x in (c.get("residency").get("claims") or []) if isinstance(x, dict)] if c else []
        except Exception:
            rows = []
    else:
        return {"gb": 0.0, "until": None, "live": None, "line": "no halo host there: nothing claimed"}
    hit = next((x for x in rows if x.get("bundle") == bundle), None)
    if hit is None:
        return {"gb": 0.0, "until": None, "live": False, "line": "no claim there now (released, or its lease ended)"}
    until = hit.get("until")
    live = CF.live(hit)
    left = (float(until) - time.time()) if isinstance(until, (int, float)) else None
    return {"gb": float(hit.get("gb") or 0), "until": until, "live": live,
            "line": (f"{float(hit.get('gb') or 0):.1f} GB claimed" + (f", lease {left:.0f} s left" if left and left > 0
                                                                       else ", lease ended" if left is not None else ""))}


def status(state_dir=None, home=None) -> dict:
    from halo_harness.local_pool import launch
    from halo_harness.local_pool.claims import scope
    from halo_harness.providers.local_server_cmd import get
    from halo_harness.providers.rpc_probe import probe
    r = launch.run(state_dir)
    if not r:
        return {"state": "stopped", "line": "the pool is not running", "run": {}, "members": [], "degraded": [],
                "lines": ["the pool is not running"]}
    log = _log_tail(r)
    fails = rpc_failures(log)
    members, down = [], []
    for p in r.get("placed") or []:
        row = {"name": p["member"], "kind": p["kind"], "share_gb": p.get("gb"), "alive": None,
               "addr": next((x["addr"] for x in r.get("rpc") or [] if x["member"] == p["member"]), None)}
        if row["addr"]:
            door, _s, port = row["addr"].rpartition(":")
            row["alive"] = probe(door.strip("[]"), int(port), tries=1)["alive"]
            if not row["alive"] or any(row["addr"] in f for f in fails):
                down.append(p["member"])
        row["claim"] = _claim(p, scope(r.get("model") or ""), state_dir, home)
        members.append(row)
    if fails and not down:
        down.append("a worker")
    up = launch.alive(r)
    code = get(f"{str(r.get('url') or '').removesuffix('/v1')}/health", timeout=1.0)[0] if up else 0
    state = "down" if not up else "degraded" if down else "running" if code == 200 else "loading"
    word = {"down": f"down: the pool's llama-server exited ({(log or ['no log line'])[-1][:160]})",
            "degraded": f"degraded ({', '.join(down)} down)", "running": "running", "loading": "loading"}[state]
    line = f"the pool serves {r.get('display') or r.get('model')}: {word}"
    from halo_harness.ollama_steward.changes_pool import judge
    j = judge(state_dir, home=home) if state == "running" else {"verdict": "none", "line": ""}
    lines = [line] + [f"  {m['name']}: {'up' if m['alive'] else 'down' if m['alive'] is False else 'this GPU'}; "
                      f"{m['claim']['line']}" for m in members] + [f"  log: {f}" for f in fails[-3:]] + (
        [f"  {j['line']}"] if j.get("line") else [])
    return {"state": state, "line": line, "run": r, "members": members, "degraded": down, "health": code,
            "log": fails[-5:], "judge": j, "lines": lines}


def failed_line(message: str, state_dir=None, http=None) -> str:
    try:
        st = status(state_dir)
    except Exception:
        st = {"state": "unknown", "degraded": []}
    head = (f"the pool is degraded ({', '.join(st['degraded'])} down)" if st.get("state") == "degraded" else
            "the pool is down (its llama-server exited)" if st.get("state") == "down" else "the pool's request failed")
    tail = f"the pool's llama-server answered {http}" if http else message  # not the cloud wording ("retries")
    return f"{head}: the request failed once and is not retried -- {tail}"
