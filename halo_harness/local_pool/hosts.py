"""halo_harness.local_pool.hosts -- the pool's members, reached through their halo hosts (Halo 3.3.8.0 R3; docs/POOL.md
"The controller").

    client(member, home=None) -> (HostClient | None, kind, line)   kind: paired | local | address (members.resolve)
    rpc(member, to, *, home=None) -> {ok, kind, say, status, queued?}
        to: status | on | off. A paired member: `GET rpc` / `control/rpc_server {to, port}` on its halo host (the
        host's grants: a pending row under fleet.allow_control: ask, one line under none). `local`: this machine's GPU
        serves its share in llama-server itself, no rpc-server. A bare address: nobody here starts it ("start
        rpc-server there by hand: rpc-server -H <its LAN address> -p 50052"); its port is probed instead.
    act(member, op, params, *, home=None, why="") -> (ok, say, answer)   one control op on that member's host
    rpc_addr(member, home=None) -> "192.0.2.11:50052" the --rpc entry (a paired host's url address)
Nothing here loads a model; every request is one signed call to a paired host.
"""

from __future__ import annotations

from typing import Optional


def client(member: dict, home=None):
    from halo_harness.local_pool.members import resolve
    how = resolve(member, home)
    if how["kind"] != "paired":
        return None, how["kind"], ""
    from halo_harness.peers import identity, store
    from halo_harness.ollama_steward.host_client import HostClient
    key = store.key_for(how["entry"], home)
    if key is None:
        return None, "paired", f"the paired host {member['host']} has no pair key here (halo host join again)"
    return HostClient(how["entry"], key, identity.harness()["id"]), "paired", ""


def rpc_addr(member: dict, home=None) -> str:
    from halo_harness.local_pool.members import resolve
    addr = resolve(member, home)["addr"] or member["host"]
    return f"[{addr}]:{member['rpc_port']}" if ":" in addr else f"{addr}:{member['rpc_port']}"


def served(c, home=None) -> Optional[str]:
    rows = [r for r in c.entry.get("serves") or [] if isinstance(r, dict) and r.get("name")]
    return str(rows[0]["name"]) if rows else None


def act(member: dict, op: str, params: dict, *, home=None, why: str = "") -> "tuple[bool, str, dict]":
    from halo_harness.ollama_steward.host_client import HostError
    c, kind, line = client(member, home)
    if c is None:
        return False, line or f"{member['name']} has no halo host here ({kind})", {}
    if "host" not in params and op not in ("rpc_server",):
        name = served(c, home)
        if name:
            params = {**params, "host": name}
    try:
        got = c.act("control", op, params, why=why)
    except HostError as e:
        return False, f"{member['name']}: {e}", {"status": e.status}
    if got.get("queued"):
        return False, f"{member['name']}: {got.get('line') or 'queued for the host owner (fleet.allow_control: ask)'}", got
    return bool(got.get("ok", True)), str(got.get("say") or ""), got


def _by_hand(member: dict) -> str:
    return (f"no halo host serves {member['host']}: start rpc-server there by hand (rpc-server -H <its LAN address> "
            f"-p {member['rpc_port']}); a trusted LAN only")


def rpc(member: dict, to: str, *, home=None) -> dict:
    from halo_harness.ollama_steward.host_client import HostError
    c, kind, line = client(member, home)
    if kind == "local":
        return {"ok": True, "kind": kind, "status": {"running": None, "local": True},
                "say": f"{member['name']} is this machine: llama-server serves its share on its own GPU (no rpc-server)"}
    if kind == "address":
        from halo_harness.providers.rpc_probe import probe
        got = probe(member["host"], int(member["rpc_port"]))
        return {"ok": to == "status", "kind": kind, "say": f"{_by_hand(member)}; now {got['line']}",
                "status": {"running": got["alive"] or None, "probe": got}}
    if c is None:
        return {"ok": False, "kind": kind, "say": line, "status": {}}
    try:
        if to == "status":
            got = c.get("rpc")
            st = got.get("rpc") or {}
            return {"ok": True, "kind": kind, "status": st, "say": f"{member['name']}: {st.get('line') or 'not read'}"}
        got = c.act("control", "rpc_server", {"to": to, "port": int(member["rpc_port"])}, why="the pool's worker")
    except HostError as e:
        return {"ok": False, "kind": kind, "say": f"{member['name']}: {e}", "status": {}, "http": e.status}
    if got.get("queued"):
        return {"ok": False, "kind": kind, "queued": True, "status": {},
                "say": f"{member['name']}: {got.get('line') or 'queued for the host owner'}"}
    notes = [n for n in got.get("notes") or [] if isinstance(n, str)]
    return {"ok": bool(got.get("ok", True)), "kind": kind, "status": got.get("rpc") or {},
            "say": f"{member['name']}: {got.get('say') or ''}" + (f" ({notes[0]})" if notes else "")}
