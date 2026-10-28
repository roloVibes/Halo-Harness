"""halo_harness.ollama_steward.resources_share -- Halo 3.3.5.0 R1: the live
samples between processes and machines (the sampler is resources.py).

    write_recent(state_dir, now)   <state>/ollama/resources-recent.json: this
                                   machine's own samples of the last minute
    read_recent(state_dir, after)  those newer than `after` (the member's
                                   ledger push sends them: fleet/ollama_share.py),
                                   each with `lan_url` (this machine's LAN
                                   address and the host's port) so a hub can
                                   tell which of its hosts the member serves
    take_remote(home, member, samples)   the hub's side: kept in STORE (the
                                   last 5 minutes per host) under the hub's own
                                   name for the host when one of its entries
                                   points at `lan_url`, else `<host>@<member>`;
                                   `from` is the member; a `resources` frame
                                   each through the ledger tap
    serving(host_url)              the member whose samples say it serves the
                                   url (the Hosts page routes a control there)
    others_for(host_name, card)    the newest sample's `others` (bytes held by
                                   programs that are not Ollama) when it is
                                   newer than the card (fit.card_budget)
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
from typing import Optional

MAX_SAMPLES = 120


def _path(state_dir):
    from halo_harness.ollama_steward.ledger import ledger_dir
    from halo_harness.ollama_steward.resources import RECENT_FILE
    return ledger_dir(state_dir) / RECENT_FILE


def write_recent(state_dir, now: float) -> None:
    from halo_harness.ollama_steward.resources import FILE_KEEP_S, STORE
    if state_dir is None:
        return
    rows = [s for s in STORE.recent("", FILE_KEEP_S, now) if not s.get("from")]
    path = _path(state_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps({"at": now, "samples": rows}, default=str), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def _port_of(url) -> Optional[int]:
    try:
        p = urllib.parse.urlparse(str(url or ""))
        return p.port or (443 if p.scheme == "https" else 80) if p.hostname else None
    except ValueError:
        return None


def read_recent(state_dir, after: float = 0.0, *, lan: Optional[str] = None) -> list:
    """This machine's samples newer than `after` (at most MAX_SAMPLES, the newest), each with `lan_url`."""
    try:
        data = json.loads(_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = [s for s in (data.get("samples") if isinstance(data, dict) else None) or []
            if isinstance(s, dict) and float(s.get("t") or 0) > after]
    if lan is None:
        try:
            from halo_harness.fleet.hub import lan_address
            lan = lan_address()
        except Exception:
            lan = "127.0.0.1"
    out = []
    for s in rows[-MAX_SAMPLES:]:
        port = _port_of(s.get("url"))
        out.append({**s, "lan_url": f"http://{lan}:{port}" if port and s.get("url") else None})
    return out


def _key(url) -> Optional[tuple]:
    try:
        p = urllib.parse.urlparse(str(url or ""))
        return ((p.hostname or "").lower(), _port_of(url)) if p.hostname else None
    except ValueError:
        return None


def _clean(s: dict) -> dict:
    keep = ("host", "url", "lan_url", "t", "gpu", "vram_used", "vram_total", "holder", "holders", "ram_used",
            "ram_total", "cpu", "temp", "others", "unified", "sources")
    return {k: s.get(k) for k in keep}


def take_remote(home, member: str, samples, *, hosts=None) -> int:
    """A member's samples into this hub's STORE; returns how many were kept."""
    from halo_harness.ollama_steward.resources import STORE
    if not isinstance(samples, list) or not member:
        return 0
    if hosts is None:
        try:
            from halo_harness.ollama_steward.profiles import _hosts_of
            hosts = _hosts_of(home)  # the hub's own ollama.hosts (its home's config.json)
        except Exception:
            hosts = []
    by_key = {_key(h.url): h for h in hosts}
    frames, n = [], 0
    for s in samples[-MAX_SAMPLES:]:
        if not isinstance(s, dict) or not isinstance(s.get("t"), (int, float)):
            continue
        row = _clean(s)
        own = by_key.get(_key(row.get("lan_url"))) if row.get("lan_url") else None
        row.update(member_host=row.get("host"), host=own.name if own else f"{row.get('host')}@{member}",
                   url=own.url if own else row.get("lan_url") or row.get("url"), **{"from": member})
        STORE.add(row)
        frames.append({"session_id": "local", "event": "resources", "ts": row["t"], "data": row})
        n += 1
    if frames:
        from halo_harness.ollama_steward import ledger_tap
        ledger_tap.frames(home, frames)
    return n


def serving(host_url: str = "", host_name: str = "") -> Optional[dict]:
    """{member, member_host} for the member whose samples serve this host (the newest), else None."""
    from halo_harness.ollama_steward.resources import STORE
    want = _key(host_url) if host_url else None
    best = None
    for s in STORE.recent("", 3600.0):
        if not s.get("from"):
            continue
        if (want and _key(s.get("url")) == want) or (host_name and s.get("host") == host_name):
            best = s
    return {"member": best["from"], "member_host": best.get("member_host") or best.get("host")} if best else None


def others_for(host_name: str, card: Optional[dict], *, now: Optional[float] = None) -> Optional[int]:
    """The newest sample's `others` for `host_name` when it is newer than the card's `read_at`, else None."""
    from halo_harness.ollama_steward.ledger import parse_at
    from halo_harness.ollama_steward.resources import STORE
    if not host_name:
        return None
    s = STORE.latest(host_name)
    if not s or not isinstance(s.get("others"), int):
        return None
    now = time.time() if now is None else now
    if now - float(s.get("t") or 0) > 120.0:
        return None  # an old sample says nothing about now
    read = parse_at((card or {}).get("read_at")) if card else None
    return s["others"] if read is None or float(s["t"]) > read else None
