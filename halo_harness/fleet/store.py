"""halo_harness.fleet.store -- the joiner's side of the fleet (Halo 3.0.5.0
"Fleet" round R2): `~/.halo/fleet.json` and the pair keys.

    fleet.json                  {version: 1, hubs: [{url, name, hub_id, key_ref, fingerprint, tls, share,
                                                     allow_control, member_name, joined_at, state}],
                                 hosts: [...]  (3.3.7.0 R1: the paired halo hosts, add_host below)}
    fleet/keys/<key_ref>.key    that hub's 32-byte pair key as hex (0600)

A hub's `share` / `allow_control` of null follows the config keys
(`fleet.share`, `fleet.allow_control`). `state` is `joined`, or `kicked`
once that hub removed this harness (the relay then stops trying it until
the next join). Nothing is written here before `halo fleet join`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from halo_harness.privateio import write_private_atomic
from halo_harness.remote.pairing_files import _edit, _read

FILENAME = "fleet.json"


def _home(home) -> Path:
    if home is not None:
        return Path(home)
    from halo_harness.fleet.identity import home as _h
    return _h()


def path(home=None) -> Path:
    return _home(home) / FILENAME


def keys_dir(home=None) -> Path:
    return _home(home) / "fleet" / "keys"


def load(home=None) -> dict:
    data = _read(path(home), {})
    hubs = data.get("hubs") if isinstance(data.get("hubs"), list) else []
    return {"version": 1, "hubs": [h for h in hubs if isinstance(h, dict) and h.get("url")]}


def hubs(home=None) -> list:
    return load(home)["hubs"]


def has_hubs(home=None) -> bool:
    """Cheap: True when fleet.json exists and lists a joined hub."""
    p = path(home)
    return p.exists() and any(h.get("state", "joined") == "joined" for h in hubs(home))


def mtime(home=None) -> float:
    try:
        return path(home).stat().st_mtime
    except OSError:
        return 0.0


def key_for(entry: dict, home=None) -> Optional[bytes]:
    ref = str((entry or {}).get("key_ref") or "")
    if not ref or not ref.replace("-", "").isalnum():
        return None
    try:
        key = bytes.fromhex((keys_dir(home) / f"{ref}.key").read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return None
    return key if len(key) == 32 else None


def add_hub(entry: dict, key: bytes, home=None) -> dict:
    """Store (or replace: same hub id or url) one joined hub and its key."""
    ref = str(entry.get("hub_id") or "hub")[:16] + "-" + format(int(time.time()), "x")
    write_private_atomic(keys_dir(home) / f"{ref}.key", key.hex() + "\n")
    row = {**entry, "key_ref": ref, "joined_at": time.time(), "state": "joined"}
    old_refs = []
    with _edit(path(home), {"version": 1, "hubs": []}) as d:
        kept = []
        for h in d.get("hubs", []):
            if h.get("hub_id") == row.get("hub_id") or h.get("url") == row.get("url"):
                old_refs.append(h.get("key_ref"))
            else:
                kept.append(h)
        d["hubs"] = kept + [row]
    for old in old_refs:
        _drop_key(old, home)
    return row


def _drop_key(ref, home=None) -> None:
    if ref:
        try:
            (keys_dir(home) / f"{ref}.key").unlink()
        except OSError:
            pass


def find(selector: Optional[str], home=None) -> list:
    """Hubs whose name, url or hub id (a prefix) is `selector`; every hub for None."""
    rows = hubs(home)
    if not selector:
        return rows
    s = selector.strip()
    exact = [h for h in rows if s.lower() in (str(h.get("name") or "").lower(), str(h.get("url") or "").lower())]
    return exact or [h for h in rows if str(h.get("hub_id") or "").startswith(s) or s in str(h.get("url") or "")]


def remove(entries: list, home=None) -> list:
    """Drop these hubs (and their keys); returns the ones removed."""
    ids = {(h.get("hub_id"), h.get("url")) for h in entries}
    gone = []
    if not path(home).exists():
        return gone
    with _edit(path(home), {"version": 1, "hubs": []}) as d:
        kept = []
        for h in d.get("hubs", []):
            (gone if (h.get("hub_id"), h.get("url")) in ids else kept).append(h)
        d["hubs"] = kept
    for h in gone:
        _drop_key(h.get("key_ref"), home)
    return gone


def mark(hub_id: str, home=None, **fields) -> None:
    if not path(home).exists():
        return
    with _edit(path(home), {"version": 1, "hubs": []}) as d:
        for h in d.get("hubs", []):
            if h.get("hub_id") == hub_id:
                h.update(fields)


# ---- 3.3.7.0 R1: the paired halo hosts (`halo host join`, host/join.py) -------------------------------------
# fleet.json's `hosts`: [{url, name, host_id, key_ref, fingerprint, tls, serves: [{name, port, addr}], grants,
# joined_at, state}]; the pair key beside the hubs' in fleet/keys/<key_ref>.key.

def hosts(home=None) -> list:
    data = _read(path(home), {})
    rows = data.get("hosts") if isinstance(data.get("hosts"), list) else []
    return [h for h in rows if isinstance(h, dict) and h.get("url")]


def add_host(entry: dict, key: bytes, home=None) -> dict:
    """Store (or replace: same host id or url) one paired host and its key."""
    ref = "host-" + str(entry.get("host_id") or "x")[:12] + "-" + format(int(time.time()), "x")
    write_private_atomic(keys_dir(home) / f"{ref}.key", key.hex() + "\n")
    row = {**entry, "key_ref": ref, "joined_at": time.time(), "state": "joined"}
    old_refs = []
    with _edit(path(home), {"version": 1, "hubs": []}) as d:
        kept = []
        for h in d.get("hosts") or []:
            same = h.get("host_id") == row.get("host_id") or h.get("url") == row.get("url")
            (old_refs.append(h.get("key_ref")) if same else kept.append(h))
        d["hosts"] = kept + [row]
    for old in old_refs:
        _drop_key(old, home)
    return row


def find_host(selector: Optional[str], home=None) -> list:
    rows = hosts(home)
    if not selector:
        return rows
    s = selector.strip().lower()
    exact = [h for h in rows if s in (str(h.get("name") or "").lower(), str(h.get("url") or "").lower())]
    return exact or [h for h in rows if str(h.get("host_id") or "").startswith(s) or s in str(h.get("url") or "")]


def remove_host(entries: list, home=None) -> list:
    ids = {(h.get("host_id"), h.get("url")) for h in entries}
    gone: list = []
    if not path(home).exists():
        return gone
    with _edit(path(home), {"version": 1, "hubs": []}) as d:
        kept = []
        for h in d.get("hosts") or []:
            (gone if (h.get("host_id"), h.get("url")) in ids else kept).append(h)
        d["hosts"] = kept
    for h in gone:
        _drop_key(h.get("key_ref"), home)
    return gone
