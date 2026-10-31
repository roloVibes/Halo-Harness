"""halo_harness.ollama_steward.host_fold -- a peer's steward job reads its paired hosts (Halo 3.3.7.0 R2;
plans/local-model-fit-brief.md H10.4 / H10.5).

    fold(state_dir, found) -> found + the hosts' own findings (`GET findings`, the rules over each host's ledger and
        events), under this machine's names for the host and model; a finding the local rules already made (same rule
        and key) is not repeated. A `where: host` finding keeps the host's id, so a fix sent through the host
        (`control/set_*`, host_land.py) cites a finding the host knows. A `where: client` one (a prompt that outgrew
        its window, a reply cut with no room, a compaction that did not run) becomes this harness's own finding: its
        proposal kept only when it is a client-side field (compact_at, host_for), its line naming the host as the
        source and what to do here ("compact", "a bigger-window model").
    tick(state_dir) -> {pushed, verdicts}   this machine's calls to host-served Ollamas pushed to their hosts
        (host/ledger_push.py) and the hosts' verdicts on this steward's changes written back (host_land.sync)

Each read is cached FINDINGS_TTL_S; a host that does not answer is skipped. No model is called here.
"""

from __future__ import annotations

import time
from typing import Optional

FINDINGS_TTL_S = 60.0
_CACHE: dict = {}  # host url -> (monotonic, findings)


def _clients() -> list:
    """[(HostClient, {port: this machine's host name})] for every paired host that serves a configured host."""
    from halo_harness.ollama_steward.host_client import _addr_port, _usable, for_host
    from halo_harness.providers.ollama import resolve_ollama_hosts
    out: dict = {}
    for h in resolve_ollama_hosts():
        c = for_host(h)
        if c is None or not _usable(c):
            continue
        out.setdefault(c.url, (c, {}))[1][_addr_port(h.url)[1]] = h.name
    return list(out.values())


def _findings(c) -> list:
    from halo_harness.ollama_steward.host_client import HostError
    hit = _CACHE.get(c.url)
    if hit and time.monotonic() - hit[0] < FINDINGS_TTL_S:
        return hit[1]
    try:
        rows = [f for f in c.get("findings").get("findings") or [] if isinstance(f, dict)]
    except HostError:
        rows = []
    _CACHE[c.url] = (time.monotonic(), rows)
    return rows


def fold(state_dir, found: list, *, now: Optional[float] = None) -> list:
    from halo_harness.host.findings import CLIENT_SUGGEST
    from halo_harness.ollama_steward.profiles import key_for
    have = {(f.get("rule"), f.get("key")) for f in found}
    out = list(found)
    for c, names in _clients():
        for f in _findings(c):
            name = names.get(int(f.get("port") or 0)) or (next(iter(names.values())) if len(names) == 1 else None)
            if not name:
                continue
            key = key_for(name, f.get("model"))
            if (f.get("rule"), key) in have:
                continue
            g = {**f, "host": name, "key": key, "source": f"the host at {c.addr}", "via": "host"}
            if f.get("where") == "client":
                p = f.get("proposal") or {}
                g["proposal"] = p if p.get("field") in ("compact_at", "host_for") else None
                todo = ", ".join(f.get("suggest") or CLIENT_SUGGEST)
                g["finding"] = f"{f.get('finding')} (seen by the host at {c.addr}; the fix is here: {todo})"
            else:
                g["finding"] = f"{f.get('finding')} (seen by the host at {c.addr})"
            out.append(g)
            have.add((f.get("rule"), key))
    return out


def tick(state_dir) -> dict:
    from halo_harness.host.ledger_push import push_all
    from halo_harness.ollama_steward.host_client import any_paired
    if not any_paired():
        return {"pushed": 0, "verdicts": []}
    pushed = push_all()
    from halo_harness.ollama_steward.host_land import sync
    return {"pushed": pushed, "verdicts": sync(state_dir)}


def reset() -> None:
    _CACHE.clear()
