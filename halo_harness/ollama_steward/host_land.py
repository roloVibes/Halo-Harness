"""halo_harness.ollama_steward.host_land -- the steward lands through the host (Halo 3.3.7.0 R2;
plans/local-model-fit-brief.md H10.5: the steward's three homes, one vocabulary).

When the host and model of a change are served by a paired `halo host` (ollama_steward/host_client.for_host), the
change does not land in this harness's profile alone: `steward.apply_change` sends it as the host's typed operation
(`control/set_num_ctx`, `set_num_predict`, `set_keep_alive`, `set_tools_max`) with `evidence.finding` = the finding's
id and the steward's `why`. The host applies it, measures before and after, and keeps or reverts it (host/verify.py).
This harness mirrors a landed change in its own profile (`by: "hub"`, so the host's later answer can replace it) and
writes one journal line:

    {kind: "host-apply", key, field, from, to, why, finding, via: "host", host: <addr>, host_change, verdict: "verifying"}
    {kind: "host-pending", ...}   queued for the host's owner (fleet.allow_control: ask there)
    {kind: "host-refused", ...}   the host's one line (a missing grant, a guard, an invariant)

`sync(state_dir)` (the steward job's pass) reads each host's `GET changes` and writes the verdict back:
{kind: "host-verdict", reverts?, verdict, line}; a reverted change takes the local mirror back with it.
A field the host vocabulary has no op for (host_for, compact_at: client-side decisions) lands here as before.

    via_host(state_dir, f, change, *, mode_name, now, scope) -> journal row | None (not served by a paired host)
    sync(state_dir, now=None) -> the verdict rows written
"""

from __future__ import annotations

import time
from typing import Optional

FIELD_OPS = {"num_ctx": "set_num_ctx", "num_predict": "set_num_predict", "keep_alive": "set_keep_alive",
             "tools_max": "set_tools_max"}


def client_for(host_name: str):
    from halo_harness.ollama_steward.host_client import _usable, for_host
    from halo_harness.providers.ollama import resolve_ollama_host
    h = resolve_ollama_host(host_name) if host_name else None
    c = for_host(h) if h is not None else None
    return (c, h) if _usable(c) else (None, h)


def via_host(state_dir, f: dict, change: dict, *, mode_name: str, now: Optional[float] = None,
             scope: Optional[str] = None) -> Optional[dict]:
    from halo_harness.ollama_steward.host_client import HostError, _addr_port
    from halo_harness.ollama_steward.steward import _append
    op = FIELD_OPS.get(change.get("field"))
    if op is None:
        return None
    c, h = client_for(str(f.get("host") or ""))
    if c is None:
        return None
    params = {"model": f["model"], "value": change["to"]}
    name = c.served_name(_addr_port(h.url)[1])
    if name:
        params["host"] = name
    ev = {"finding": f["id"], "lines": [str(f.get("finding") or "")[:300]]}
    base = {"_now": now, "key": f["key"], "field": change["field"], "from": change.get("from"), "to": change["to"],
            "why": change["why"], "finding": f["id"], "rule": f.get("rule"), "via": "host", "host": c.addr,
            "mode": mode_name}
    try:
        got = c.act("control", op, params, evidence=ev, why=change["why"], scope=scope)
    except HostError as e:
        return {**_append(state_dir, {**base, "id": f"hr-{f['id']}-{int(now or time.time())}", "kind": "host-refused",
                                      "say": f"steward: {op} {change['to']} for {f['key']} -- the host at {c.addr}: {e}"}),
                "landed": False}
    if got.get("queued"):
        return {**_append(state_dir, {**base, "id": f"hp-{f['id']}-{int(now or time.time())}", "kind": "host-pending",
                                      "pending": got.get("pending"), "say": f"steward: {op} {change['to']} for "
                                      f"{f['key']} -- {got.get('line')}"}), "landed": False}
    from halo_harness.ollama_steward.profiles import set_field
    note = f"steward through the host at {c.addr}: {change['field']} {change['to']} ({change['why']})"
    set_field(f["key"], change["field"], change["to"], by="hub", note=note[:300])
    row = _append(state_dir, {**base, "id": f"ch-{f['id']}-{int(now or time.time())}", "kind": "host-apply",
                              "host_change": got.get("change_id"), "verdict": "verifying",
                              "say": f"{note}; the host verifies it ({got.get('say')})"})
    return {**row, "landed": True}


def sync(state_dir, now: Optional[float] = None) -> list:
    """The hosts' verdicts on this steward's changes, written back into the journal (once each)."""
    from halo_harness.ollama_steward.host_client import HostError
    from halo_harness.ollama_steward.steward import _append, read_journal
    journal = read_journal(state_dir)
    done = {r.get("reverts") or r.get("host_change") for r in journal if r.get("kind") == "host-verdict"}
    open_ = [r for r in journal if r.get("kind") == "host-apply" and r.get("host_change") and r["host_change"] not in done]
    out: list = []
    seen: dict = {}
    for r in open_:
        from halo_harness.ollama_steward.profiles import split_key
        c, _h = client_for(split_key(r["key"])[0])
        if c is None:
            continue
        if c.url not in seen:
            try:
                seen[c.url] = {x.get("id"): x for x in c.get("changes").get("changes") or []}
            except HostError:
                seen[c.url] = {}
        x = seen[c.url].get(r["host_change"])
        if not x or x.get("verdict") in (None, "verifying"):
            continue
        line = x.get("verify_line") or x.get("line") or ""
        if x.get("verdict") == "reverted" or x.get("reverted_at"):
            from halo_harness.ollama_steward.profiles import set_field
            set_field(r["key"], r["field"], r.get("from"), by="hub", note=f"the host put it back: {line}"[:300])
        out.append(_append(state_dir, {"_now": now, "id": f"hv-{r['id']}", "kind": "host-verdict",
                                       "host_change": r["host_change"], "key": r["key"], "field": r["field"],
                                       "verdict": x.get("verdict"), "line": line,
                                       "say": f"steward: the host at {c.addr} {x.get('verdict')} it -- {line}"}))
    return out
