"""halo_harness.local_pool.members -- the pool's members (Halo 3.3.8.0 R1; docs/POOL.md "Members").

`<state>/pool/pool.json` = {"version": 1, "members": [Member]}, Member = {name, host, rpc_port, weight?, vram_gb?}.
`host` is a paired host's name (3.3.7.0 `halo host join`: its card gives the member's GPU and free VRAM), `local`
(this machine: the local reads), or a hostname / IP address of a worker that runs `rpc-server` by hand. An IP literal
is accepted here: the privacy scan governs committed files, not a user's own config. `vram_gb` is the VRAM you state
for a worker whose GPU no card enumerates (a worker-grade box with no `nvidia-smi`); the verdict then says so.

    path(state_dir=None) -> Path
    load(state_dir=None) -> [Member]           save(members, state_dir=None)
    parse_target("worker1.local:50052") -> (host, port | None)   "[fd00::1]:50052", "192.0.2.11", "pc-host"
    check(members) -> [line]                   duplicate names, a host:port twice, a port out of range, a bad weight
    add(name, target, *, weight=None, vram_gb=None, port=None, state_dir=None) -> (ok, lines, members)
    remove(name, state_dir=None) -> (ok, lines, members)
    resolve(member, home=None) -> {kind: paired | local | address, addr, entry}   who answers for its card
    rpc_port() -> pool.rpc_port (50052)        scan_subnets() -> pool.scan_subnets ([])
"""

from __future__ import annotations

import json
import re
import socket
from pathlib import Path
from typing import Optional

from halo_harness.local_pool import DEFAULT_RPC_PORT

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
LOCAL_NAMES = ("local", "localhost", "127.0.0.1", "::1")


def _state(state_dir=None) -> Path:
    if state_dir is not None:
        return Path(state_dir)
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def path(state_dir=None) -> Path:
    return _state(state_dir) / "pool" / "pool.json"


def rpc_port() -> int:
    from halo_harness.theme import get_config_value
    v = get_config_value("pool.rpc_port", default=DEFAULT_RPC_PORT)
    return int(v) if isinstance(v, int) and 0 < v < 65536 else DEFAULT_RPC_PORT


def scan_subnets() -> list:
    from halo_harness.theme import get_config_value
    v = get_config_value("pool.scan_subnets", default=[])
    return [str(x) for x in v] if isinstance(v, list) else []


def _clean(row: dict) -> Optional[dict]:
    if not isinstance(row, dict) or not row.get("name") or not row.get("host"):
        return None
    try:
        port = int(row.get("rpc_port") or DEFAULT_RPC_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_RPC_PORT
    out = {"name": str(row["name"]), "host": str(row["host"]), "rpc_port": port}
    for k in ("weight", "vram_gb"):
        if isinstance(row.get(k), (int, float)) and not isinstance(row.get(k), bool):
            out[k] = float(row[k])
    return out


def load(state_dir=None) -> list:
    try:
        got = json.loads(path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = got.get("members") if isinstance(got, dict) else None
    return [m for m in (_clean(r) for r in rows or []) if m]


def save(members: list, state_dir=None) -> None:
    from halo_harness.privateio import write_private_atomic
    p = path(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_private_atomic(p, json.dumps({"version": 1, "members": members}, indent=1) + "\n")


def parse_target(target: str) -> "tuple[str, Optional[int]]":
    """`host[:port]`; a bracketed IPv6 address keeps its brackets off; a bare IPv6 address has no port."""
    t = str(target or "").strip()
    if t.startswith("["):
        host, _, rest = t[1:].partition("]")
        port = rest[1:] if rest.startswith(":") else ""
        return host, int(port) if port.isdigit() else (None if not port else -1)
    if t.count(":") == 1:
        host, port = t.split(":")
        return host, int(port) if port.isdigit() else -1
    return t, None


def check(members: list) -> "list[str]":
    lines, names, doors = [], {}, {}
    for m in members:
        n, door = m["name"], f"{m['host']}:{m['rpc_port']}"
        if not NAME.match(n):
            lines.append(f"{n!r}: a member's name is letters, digits, '.', '-' or '_' (64 at most)")
        if n.lower() in names:
            lines.append(f"{n} is a member twice (hosts {names[n.lower()]} and {door}): one name per member")
        names.setdefault(n.lower(), door)
        if door.lower() in doors:
            lines.append(f"{door} is the member {doors[door.lower()]} already: one rpc-server answers one member")
        doors.setdefault(door.lower(), n)
        if not 0 < int(m["rpc_port"]) < 65536:
            lines.append(f"{n}: port {m['rpc_port']} is out of range (1-65535)")
        for k, word in (("weight", "a weight"), ("vram_gb", "the VRAM you state")):
            if k in m and not m[k] > 0:
                lines.append(f"{n}: {word} is a number above 0, got {m[k]:g}")
    return lines


def add(name: str, target: str, *, weight: Optional[float] = None, vram_gb: Optional[float] = None,
        port: Optional[int] = None, state_dir=None) -> "tuple[bool, list, list]":
    host, tport = parse_target(target)
    if not host:
        return False, ["add takes <name> <host[:port]>: the paired host's name, `local`, or the worker's address"], load(state_dir)
    if tport == -1:
        return False, [f"{target!r}: the port after ':' is a number (the rpc-server port, {rpc_port()} by default)"], \
            load(state_dir)
    member = {"name": str(name or "").strip(), "host": host, "rpc_port": int(port or tport or rpc_port())}
    if weight is not None:
        member["weight"] = float(weight)
    if vram_gb is not None:
        member["vram_gb"] = float(vram_gb)
    rows = load(state_dir)
    problems = check(rows + [member])
    if problems:
        return False, problems, rows
    how = resolve(member)
    same = next((m for m in rows if how["kind"] != "address" and (r := resolve(m))["kind"] == how["kind"]
                 and r["addr"] == how["addr"]), None)
    if same:  # a card read twice would count its free VRAM twice
        return False, [f"{host} is the machine of the member {same['name']} already: its card's free VRAM would count twice "
                       "(one rpc-server per machine serves every GPU there)"], rows
    rows.append(member)
    save(rows, state_dir)
    said = {"paired": f"the paired host {host}: its card gives the GPU and the free VRAM",
            "local": "this machine: the local card gives the GPU and the free VRAM",
            "address": "no paired host by that name: the VRAM comes from the --vram you state" if vram_gb is None else
            f"VRAM as you stated it ({vram_gb:g} GB)"}[how["kind"]]
    return True, [f"added {member['name']} ({host}:{member['rpc_port']}): {said}"], rows


def remove(name: str, state_dir=None) -> "tuple[bool, list, list]":
    rows = load(state_dir)
    kept = [m for m in rows if m["name"].lower() != str(name or "").strip().lower()]
    if len(kept) == len(rows):
        names = ", ".join(m["name"] for m in rows) or "none yet"
        return False, [f"no member named {name!r} (members: {names})"], rows
    save(kept, state_dir)
    return True, [f"removed {name} from the pool ({len(kept)} member{'' if len(kept) == 1 else 's'} left)"], kept


def _is_local(host: str) -> bool:
    h = host.strip().lower().strip("[]")
    if h in LOCAL_NAMES:
        return True
    try:
        return h == socket.gethostname().lower() or h == socket.gethostname().lower().split(".")[0]
    except OSError:
        return False


def resolve(member: dict, home=None) -> dict:
    """Who answers for the member's card: a paired halo host by its name, this machine, or nobody (an address)."""
    host = str(member.get("host") or "")
    if _is_local(host):
        return {"kind": "local", "addr": "127.0.0.1", "entry": None}
    try:
        from halo_harness.fleet import store
        hit = [e for e in store.hosts(home) if str(e.get("name") or "").lower() == host.lower()
               and e.get("state", "joined") == "joined"]
    except Exception:
        hit = []
    if hit:
        from halo_harness.ollama_steward.host_client import _addr_port
        return {"kind": "paired", "addr": _addr_port(hit[0].get("url") or "", 7431)[0], "entry": hit[0]}
    return {"kind": "address", "addr": host, "entry": None}
