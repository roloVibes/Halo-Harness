"""halo_harness.local_sched.reserve -- a bundle's reservations: what is held on each card and what is left for tasks
(Halo 3.3.7.0 R5; plans/local-model-fit-brief.md L2, L4; local_sched/reserve_act.py claims and releases).

A reservation is a deterministic claim: the reserved model is never evicted by work that is not the bundle's, its
GB count in every budget line, and a request that would breach what is left is refused or queued with one line that
names the claim and the numbers. When a paired `halo host` serves the card the claims live on the host (`GET
residency` answers them: every peer reads one list); with no host, this machine's scheduler keeps them
(`<state>/ollama/claims.json`).

    claims(host=None, *, state_dir=None) -> [Claim]   (local_sched/claims_file.py's shape) on that host, or every host
    held(host, model, *, state_dir=None) -> Claim | None       the claim that holds `model` on that card
    claimed_bytes(host, *, exclude=None, state_dir=None) -> int
    free_after_claims(host, usable, *, exclude=None, state_dir=None) -> {usable, claimed, free, claims, line}
        line: "1.2 GB reserved for meta-glasses; 20.8 GB free for tasks"
    breach_line(host, model, need, free) -> "would need 19.2 GB with meta-glasses' 1.2 GB held; 18.0 GB free -- queued
        behind meta-glasses"           route_line(host, to, need?) -> "meta-glasses holds 1.2 GB; sending this task to
        <cloud model> rather than evicting it"
    cloud_target() -> routing.escalation's `to`, or None     escalation_off(state_dir=None) -> the bundle id | None
    forget() -> the cache of the hosts' answers cleared (a claim or a release just landed)
Reads only; nothing loads or unloads.
"""

from __future__ import annotations

import os
import time
from typing import Optional

from halo_harness.local_sched import claims_file as CF

GIB = 2 ** 30
TTL_S = 2.0
_CACHE: dict = {}


def _state(state_dir=None):
    if state_dir is not None:
        return state_dir
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def forget() -> None:
    _CACHE.clear()


def _name(host) -> str:
    return str(getattr(host, "name", host) or "")


def _alive(row: dict) -> bool:
    """A claim a halo process holds (Studio's tick) ends with that process; one from the CLI is kept until `off`."""
    pid = row.get("holder_pid")
    if row.get("holder") != "process" or not isinstance(pid, int) or pid == os.getpid():
        return True
    from halo_harness.bg_run import pid_alive
    return bool(pid_alive(pid))


def _from_host(host) -> Optional[list]:
    from halo_harness.local_sched.pivot import _client
    if host is None or isinstance(host, str):
        return None
    c = _client(host)
    if c is None:
        return None
    from halo_harness.ollama_steward.host_client import HostError, _addr_port
    key = c.url
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < TTL_S:
        rows = hit[1]
    else:
        try:
            rows = list(c.get("residency").get("claims") or [])
        except (HostError, OSError, AttributeError):
            return None
        _CACHE[key] = (time.monotonic(), rows)
    served = c.served_name(_addr_port(str(getattr(host, "url", "")))[1]) or _name(host)
    return [{**r, "host": _name(host), "via": "host"} for r in rows
            if isinstance(r, dict) and str(r.get("host") or "").lower() == served.lower()]


def claims(host=None, *, state_dir=None) -> list:
    remote = _from_host(host) if host is not None else None
    if remote is not None:
        return remote
    rows = [r for r in CF.read(CF.local_file(_state(state_dir))) if _alive(r)]
    if host is not None:
        rows = [r for r in rows if str(r.get("host") or "").lower() == _name(host).lower()]
    return [{**r, "via": r.get("via") or "local"} for r in rows]


def held(host, model: Optional[str], *, state_dir=None) -> Optional[dict]:
    from halo_harness.providers.ollama import ollama_names_match
    if not model:
        return None
    return next((c for c in claims(host, state_dir=state_dir) if c.get("model") and ollama_names_match(c["model"], model)),
                None)


def claimed_bytes(host, *, exclude=None, state_dir=None) -> int:
    return int(sum(float(c.get("gb") or 0) * GIB for c in claims(host, state_dir=state_dir) if c.get("bundle") != exclude))


def gb(n) -> str:
    return f"{(n or 0) / GIB:.1f}"


def _who(cs: list) -> str:
    return ", ".join(sorted({str(c["bundle"]) for c in cs})) or "nothing"


def free_after_claims(host, usable: int, *, exclude=None, state_dir=None) -> dict:
    cs = [c for c in claims(host, state_dir=state_dir) if c.get("bundle") != exclude and float(c.get("gb") or 0) > 0]
    claimed = int(sum(float(c["gb"]) * GIB for c in cs))
    free = max(0, int(usable or 0) - claimed)
    line = (f"{gb(claimed)} GB reserved for {_who(cs)}; {gb(free)} GB free for tasks" if cs
            else f"nothing reserved; {gb(free)} GB free for tasks")
    return {"usable": int(usable or 0), "claimed": claimed, "free": free, "claims": cs, "line": line}


def breach_line(host, model: str, need: float, free: int, *, state_dir=None, held_by: Optional[list] = None) -> str:
    cs = held_by if held_by is not None else [c for c in claims(host, state_dir=state_dir) if float(c.get("gb") or 0) > 0]
    if not cs:
        return ""
    who = _who(cs)
    held_gb = sum(float(c.get("gb") or 0) for c in cs)
    return (f"{model} would need {gb(need)} GB with {who}'s {held_gb:.1f} GB held; {gb(free)} GB free -- queued behind "
            f"{who} (halo pack off {cs[0]['bundle']} frees it)")


def cloud_target() -> Optional[str]:
    try:
        from halo_harness.agent.escalation import load_escalation_policy
        p = load_escalation_policy()
    except Exception:
        p = None
    return p.to if p is not None else None


def holds_words(host, *, state_dir=None) -> str:
    """"meta-glasses holds 1.2 GB" ('' when nothing is reserved on that card)."""
    cs = [c for c in claims(host, state_dir=state_dir) if float(c.get("gb") or 0) > 0]
    return f"{_who(cs)} holds {sum(float(c.get('gb') or 0) for c in cs):.1f} GB" if cs else ""


def route_line(host, to: Optional[str], *, state_dir=None) -> str:
    who = holds_words(host, state_dir=state_dir)
    if not who:
        return ""
    if to:
        return f"{who}; sending this task to {to} rather than evicting it"
    return f"{who}; queued behind it (no cloud model to send it to: routing.escalation.to names one)"


def escalation_off(state_dir=None) -> Optional[str]:
    """The bundle that turned the cloud rung off while it is on (offline-only), else None."""
    for c in claims(None, state_dir=state_dir):
        if c.get("escalation") == "off":
            return str(c["bundle"])
    return None


def budget_line(host, *, state_dir=None) -> str:
    """The Hosts card's, `halo local hosts`' and the Cost panel's line: "1.2 GB reserved for meta-glasses; 20.8 GB
    free for tasks" ('' when nothing is reserved on that host)."""
    from halo_harness.local_sched import facts as F
    h = F.host_named(host) if isinstance(host, str) or host is None else host
    if h is None or not [c for c in claims(h, state_dir=state_dir) if float(c.get("gb") or 0) > 0]:
        return ""
    b = F.budget(F.card(h), h.name)
    usable = F.usable(b, F.helper(h, F.loaded(h)))
    got = free_after_claims(h, usable, state_dir=state_dir)
    if not usable:
        return f"{gb(got['claimed'])} GB reserved for {_who(got['claims'])} (the card was not read: what is left is not known)"
    return got["line"]


def all_lines(state_dir=None) -> list:
    """[{host, line}] for every configured host with a reservation."""
    from halo_harness.providers.ollama import resolve_ollama_hosts
    try:
        hosts = list(resolve_ollama_hosts())
    except Exception:
        hosts = []
    out = []
    for h in hosts:
        line = budget_line(h, state_dir=state_dir)
        if line:
            out.append({"host": h.name, "line": line})
    return out


def load_breach(host, model: Optional[str], window: Optional[int] = None, *, state_dir=None) -> str:
    """'' when loading `model` at `window` keeps every claim on that card, else the line naming the claim and the numbers
    (the scheduler's own check on a card no halo host serves; a host's invariants say the same words there)."""
    from halo_harness.local_sched import facts as F
    if not model or host is None:
        return ""
    cs = [c for c in claims(host, state_dir=state_dir) if float(c.get("gb") or 0) > 0
          and not (c.get("model") and _match(c["model"], model))]
    if not cs:
        return ""
    row, _src = F.row(host, model)
    card = F.card(host)
    b = F.budget(card, getattr(host, "name", ""))
    if not row or not b.get("budget"):
        return ""
    w = int(window or F.window(host, model, row_=row, card_=card)[0])
    need = F.together(b, [{"row": row, "window": w}])
    free = max(0, F.usable(b, F.helper(host, F.loaded(host))) - int(sum(float(c["gb"]) * GIB for c in cs)))
    return "" if need <= free else breach_line(host, model, need, free, held_by=cs)


def _match(a, b) -> bool:
    from halo_harness.providers.ollama import ollama_names_match
    return ollama_names_match(a, b)
