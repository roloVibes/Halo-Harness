"""halo_harness.providers.local_bench_link -- Halo 3.3.8.1 "Bench from any halo": a bench (or the battery) run from a
peer against an Ollama host this machine does not serve goes over the LAN, and its card says so -- the link's round
trip is in every number it measured, so the card is never read as the machine's own (docs/MODELS-cards.md "A card
measured over the LAN").

    from_where(state_dir=None) -> str     this halo's name: `harness.name` when it has one, else the host name ("mac")
    link_of(host, state_dir=None) -> {rtt_ms, kind, line}   measured once, before the battery: the TCP connect RTT to
                                          the host's port (providers/rpc_probe.probe, the pool's prober) and this
                                          machine's adapter (local_pool/link.read: wired | Wi-Fi | None)
    over_lan(host, state_dir=None) -> {over_lan: True, measured_from, link, label} | None    None: served here
    label(host, state_dir=None) -> "" | "measured over the LAN from mac: includes the link (RTT 1.8 ms, wired)"
    stamp(row, lan) -> row                the three fields on a card or a battery speed row (`over_lan` False: own)
    tail(row) -> "" | "over the LAN from mac"     what a reader of a card or a speed row says after the number
    offer_line(url, name="", *, bench=False) -> the way to a card without the link (or to a load from here): `halo host
                                          serve` on that machine, `halo host join <addr>` here, the grant there
    same_class(a, b) -> bool              the readers' pick: a machine-own card wins over a LAN-measured one of the same
                                          age class (same digest, same Ollama, the same age bucket); else the newer wins

Nothing here changes a setting on the other machine or starts anything there.
"""

from __future__ import annotations

import time
import urllib.parse
from typing import Optional

AGE_BUCKETS = (7 * 86400.0, 30 * 86400.0)  # a week, a month, older
FIELDS = ("over_lan", "measured_from", "link")


def _served_here(url: str) -> bool:
    from halo_harness.peers.ollama_share import served_here
    return served_here(url)


def from_where(state_dir=None) -> str:
    """`harness.name` (the fleet and host peer name) when this halo has one, else the machine's host name."""
    try:
        from halo_harness.peers import identity
        name = str(identity.config_value("harness.name", "", state_dir) or "").strip()
        if name:
            return name[:64]
        from halo_harness.remote.session_identity import _host
        return _host()
    except Exception:
        return "this halo"


def _addr(url: str) -> "tuple[str, int]":
    try:
        u = urllib.parse.urlparse(str(url or ""))
        return (u.hostname or ""), (u.port or 11434)
    except ValueError:
        return "", 11434


def link_of(host, state_dir=None) -> dict:
    """{rtt_ms, kind: wired | Wi-Fi | None, line: "RTT 1.8 ms, wired"}: one probe of the host's port, the adapter here."""
    addr, port = _addr(getattr(host, "url", ""))
    rtt, why = None, ""
    try:
        from halo_harness.providers.rpc_probe import probe
        got = probe(addr, port)
        rtt, why = (got.get("rtt_ms") if got.get("alive") else None), str(got.get("error") or "")
    except Exception as e:
        why = type(e).__name__
    kind = None
    try:
        from halo_harness.local_pool.link import read
        t = read().get("type")
        kind = "wired" if t == "wired" else "Wi-Fi" if t == "wireless" else None
    except Exception:
        pass
    return {"rtt_ms": rtt, "kind": kind, "line": link_line(rtt, kind, why)}


def link_line(rtt, kind: Optional[str], why: str = "") -> str:
    from halo_harness.providers.rpc_probe import ms_word
    head = f"RTT {ms_word(rtt)}" if isinstance(rtt, (int, float)) else "RTT not measured" + (f": {why}" if why else "")
    return head + (f", {kind}" if kind else "")


def over_lan(host, state_dir=None) -> Optional[dict]:
    """The LAN fields of a bench of `host` from here; None when this machine serves it (the card is its own)."""
    url = getattr(host, "url", "") or ""
    if not url or _served_here(url):
        return None
    frm, link = from_where(state_dir), link_of(host, state_dir)
    return {"over_lan": True, "measured_from": frm, "link": link,
            "label": f"measured over the LAN from {frm}: includes the link ({link['line']})"}


def label(host, state_dir=None) -> str:
    got = over_lan(host, state_dir)
    return got["label"] if got else ""


def stamp(row: dict, lan: Optional[dict]) -> dict:
    """The fields on a card or a speed row: a LAN bench's three, or `over_lan: False` (the machine's own)."""
    if not isinstance(row, dict):
        return row
    if lan:
        row.update(over_lan=True, measured_from=lan.get("measured_from"), link=lan.get("link"))
    else:
        row.update(over_lan=False, measured_from=None, link=None)
    return row


def card_label(row: Optional[dict]) -> str:
    """The card's first line when it was measured over the LAN ("" for a machine-own card)."""
    if not isinstance(row, dict) or not row.get("over_lan"):
        return ""
    line = (row.get("link") or {}).get("line") or "RTT not measured"
    return f"measured over the LAN from {row.get('measured_from') or 'a peer'}: includes the link ({line})"


def tail(row: Optional[dict]) -> str:
    if not isinstance(row, dict) or not row.get("over_lan"):
        return ""
    return f"over the LAN from {row.get('measured_from') or 'a peer'}"


def _bucket(at, now: float) -> int:
    age = max(0.0, now - float(at or 0))
    return next((i for i, b in enumerate(AGE_BUCKETS) if age < b), len(AGE_BUCKETS))


def same_class(a: dict, b: dict, now: Optional[float] = None) -> bool:
    now = time.time() if now is None else now
    return (a.get("digest") == b.get("digest") and a.get("ollama_version") == b.get("ollama_version")
            and _bucket(a.get("at"), now) == _bucket(b.get("at"), now))


def pick(own: Optional[dict], lan: Optional[dict], now: Optional[float] = None) -> Optional[dict]:
    """The card the readers read: the machine's own when both are of the same age class, else the newer."""
    if not own or not lan:
        return own or lan
    if same_class(own, lan, now):
        return own
    return own if float(own.get("at") or 0) >= float(lan.get("at") or 0) else lan


def _you() -> str:
    try:
        from halo_harness.peers import identity
        return identity.harness_name()
    except Exception:
        return "<you>"


def offer_line(url: str, name: str = "", *, bench: bool = False) -> str:
    """One wording for the way through the machine's own halo: the bench's offer ("a card without the link: ...") and
    the refused load's line ("served by another machine: a load is the owner's: ...")."""
    addr = _addr(url)[0] or name or "that machine"
    way = (f"`halo host serve` on {addr} (`halo host install` for a service), then `halo host join {addr}` here"
           f" and `halo host grant {_you()} control` there")
    if bench:
        return f"a card without the link: {way}"
    return f"served by another machine: a load is the owner's: {way}"
