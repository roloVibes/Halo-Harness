"""halo_harness.host.routes_view -- the host's `view` answers (Halo 3.3.7.0 R1; host/http.py routes them).

    View(home, readers=None).card()            {hosts: [{name, port, card, log, other_clients, footprint}], link}
    View.catalog(window)                       {window, hosts: [{name, port, models: [{model, size, digest, fit, speed,
                                                measured, profile}]}], pool (3.3.8.0 R3: local_pool/peer.offer)}
    View.profiles()                            {profiles: [battery profile without its evidence]}
    View.events(since, kind)                   {events: [...]} (the newest EVENTS_MAX)
    View.tail(n, host)                         {host, lines, source, why, n} (prompt sizes, never a request body)
    3.3.8.0 R2: the card's `servers` (this machine's llama-server / LM Studio / mlx_lm.server: runtime, model, window
    per slot, log status; ollama_steward/hardware_servers.py), `events` carries theirs (`server: true`, `runtime`), and
    `tail(n, host)` answers a server's log when `host` names one of them.

Everything is computed here from this machine's own files and its own Ollama (`/api/tags`, `/api/show`, `/api/ps`,
the server log, nvidia-smi): no model is called, nothing is written to the server. `readers` is the tests' seam:
{"hosts": fn() -> [OllamaHost], "card": fn(host) -> card, "catalog": fn(host) -> {"models": [...]},
"tail": fn(host, n) -> (lines, source, why), "log": fn(host) -> log status, "servers": fn() -> [servers_hf.Server]}.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

EVENTS_MAX = 500
CARD_TTL_S = 10.0
GIB = 2 ** 30
_BODY = re.compile(r'(\bprompt="|"prompt"\s*:|"messages"\s*:|"content"\s*:|\bmessages=\[|\bsystem="|'
                   r'msg="(chat|completion|generate|embed) request")')


def scrub_line(line: str) -> str:
    """A log line as a peer may read it: a request-body line is replaced by its size."""
    text = str(line or "")
    if _BODY.search(text):
        return f"[a request body line ({len(text):,} characters) stays on this machine]"
    return text[:2000]


def scrub_event(ev: dict) -> dict:
    out = dict(ev)
    for k in ("line", "evidence"):
        v = out.get(k)
        if isinstance(v, str):
            out[k] = scrub_line(v)
        elif isinstance(v, list):
            out[k] = [scrub_line(x) for x in v]
    return out


class View:
    def __init__(self, home, readers: Optional[dict] = None) -> None:
        self.home = Path(home)
        self.readers = dict(readers or {})
        self._cards: dict = {}

    # ---- the readers ---------------------------------------------------------------------------
    def hosts(self) -> list:
        if "hosts" in self.readers:
            return list(self.readers["hosts"]())
        from halo_harness.host.state import served_hosts
        return served_hosts()

    def host_card(self, h) -> dict:
        hit = self._cards.get(h.name)
        if hit and time.monotonic() - hit[0] < CARD_TTL_S:
            return hit[1]
        try:
            if "card" in self.readers:
                card = self.readers["card"](h) or {}
            else:
                from halo_harness.ollama_steward.hardware import hardware_card
                card = hardware_card(h)
        except Exception as e:
            card = {"gpus": None, "sources": [{"reader": "hardware card", "ok": False, "detail": str(e)[:200]}]}
        self._cards[h.name] = (time.monotonic(), card)
        return card

    def host_catalog(self, h) -> list:
        try:
            if "catalog" in self.readers:
                got = self.readers["catalog"](h) or {}
            else:
                from halo_harness.providers.ollama import get_catalog
                got = get_catalog(h)
        except Exception:
            got = {}
        return [r for r in got.get("models") or [] if isinstance(r, dict)]

    def servers(self) -> list:
        """3.3.8.0 R2: this machine's local servers (servers_hf.roster, the ones served here)."""
        if "servers" in self.readers:
            return list(self.readers["servers"]())
        from halo_harness.ollama_steward.servers_hf import is_local, roster
        try:
            return [s for s in roster(self.home) if is_local(s)]
        except Exception:
            return []

    def _pick(self, name: str = "") -> list:
        hs = self.hosts()
        return [h for h in hs if h.name.lower() == name.lower()] if name else hs

    # ---- card ----------------------------------------------------------------------------------
    def other_clients(self, h) -> list:
        """The ledger's foreign `from`s for this host over 24 h: [{from, calls}] (a peer's pushed lines, a hub's)."""
        from halo_harness.ollama_steward.ledger import read_calls
        who: dict = {}
        for x in read_calls(self.home, since=86400.0, host=h.name):
            if x.get("from"):
                who[x["from"]] = who.get(x["from"], 0) + 1
        return sorted(({"from": k, "calls": v} for k, v in who.items()), key=lambda r: -r["calls"])

    def card(self) -> dict:
        from halo_harness.host.invariants import footprint
        from halo_harness.host.state import port_of
        rows = []
        for h in self.hosts():
            c = self.host_card(h)
            fp = footprint(self, h, rows=[m for m in c.get("loaded") or [] if isinstance(m, dict)])  # R2: the helper
            rows.append({"name": h.name, "port": port_of(h.url), "card": c, "log": self.log_status(h),
                         "other_clients": self.other_clients(h), "footprint": fp["line"], "usable_gb": fp["usable_gb"],
                         "usable_with_helper_gb": fp["usable_with_helper_gb"], "helper": fp["helper"]})
        from halo_harness.ollama_steward.hardware_servers import rows as server_rows
        return {"hosts": rows, "link": self.link(), "servers": server_rows(self.home, self.servers())}

    def link(self) -> dict:
        """3.3.8.0 R1: the adapter that carries this machine's address (local_pool/link.py), read once a minute."""
        hit = self._cards.get("~link")
        if hit and time.monotonic() - hit[0] < 60.0:
            return hit[1]
        from halo_harness.local_pool.link import read
        got = self.readers["link"]() if "link" in self.readers else read()
        self._cards["~link"] = (time.monotonic(), got)
        return got

    def log_status(self, h) -> Optional[dict]:
        if "log" in self.readers:
            return self.readers["log"](h)
        try:
            from halo_harness.ollama_steward.log_status import status
            st = status(self.home, h)
            return {k: st.get(k) for k in ("state", "path", "readable", "last_line_at", "line", "debug", "why", "rung",
                                           "tail_cli")}
        except Exception:
            return None

    # ---- catalog -------------------------------------------------------------------------------
    def fit_row(self, card: dict, row: dict, h, window: int) -> dict:
        from halo_harness.ollama_steward.fit import model_window_on_card, plan
        m = str(row.get("model") or row.get("name") or "")
        p = plan(card, [{"model": m, "window": window, "max_prompt": 0, "calls": 1}], {m: row}, host_name=h.name)
        need = (p.get("models") or [{}])[0].get("need") if p.get("models") else None
        return {"fits": p.get("fits_now"), "says": p.get("says"), "need_bytes": int(need) if need else None,
                "window": window, "max_window": model_window_on_card(card, row, forced=False, step=4096),
                "max_window_forced": model_window_on_card(card, row, forced=True, step=4096)}

    def model_facts(self, h, m: str) -> dict:
        from halo_harness.providers.local_bench_runs import speed_index
        from halo_harness.providers.measured import measured_for
        from halo_harness.providers.ollama_capability import profile_for
        meas = measured_for(h, m, state_dir=self.home)
        keep = {k: (meas.get(k) or {}).get("value") for k in ("tok_s", "ttft_ms", "load_s", "cache_reused_pct")
                if isinstance(meas.get(k), dict)}
        prof = profile_for(self.home, m, h.name)
        truth = ({"truth": "verified", "probed_at": prof.get("probed_at"), "digest": prof.get("digest"),
                  "ollama_version": prof.get("ollama_version"), "sits": prof.get("sits"),
                  "tools": prof.get("tools"), "vision": prof.get("vision")} if prof else {"truth": "expected"})
        return {"speed": speed_index(self.home, h.name).get(m), "measured": {**keep, "n_calls": meas.get("n_calls")},
                "profile": truth}

    def catalog(self, window: int) -> dict:
        from halo_harness.host.state import port_of
        out = []
        for h in self.hosts():
            card = self.host_card(h)
            models = []
            for r in self.host_catalog(h):
                m = str(r.get("model") or r.get("name") or "")
                models.append({"model": m, "size": r.get("size"), "digest": r.get("digest"),
                               "capabilities": r.get("capabilities") or [], "details": r.get("details") or {},
                               "fit": self.fit_row(card, r, h, window), **self.model_facts(h, m)})
            out.append({"name": h.name, "port": port_of(h.url), "models": models})
        from halo_harness.local_pool.peer import offer  # 3.3.8.0 R3: the pool this machine runs, its entry and key
        return {"window": window, "hosts": out, "pool": offer(self.home)}

    # ---- profiles, events, tail ----------------------------------------------------------------
    def profiles(self) -> dict:
        from halo_harness.host.state import port_of
        from halo_harness.providers.ollama_capability import all_profiles
        ports = {h.name: port_of(h.url) for h in self.hosts()}
        rows = [{**{k: v for k, v in p.items() if k != "evidence"}, "port": ports[p.get("host")]}
                for p in all_profiles(self.home) if p.get("host") in ports]
        return {"profiles": rows}

    def events(self, since=None, kind: Optional[str] = None) -> dict:
        from halo_harness.host.state import port_of
        from halo_harness.ollama_steward.server_events import read_events
        ports = {h.name.lower(): port_of(h.url) for h in self.hosts()}
        from halo_harness.ollama_steward.servers_hf import port_of as server_port
        servers = {s.name.lower(): s for s in self.servers()}
        rows = []
        for e in read_events(self.home, since=since if since is not None else 86400.0, kind=kind or None):
            name = str(e.get("host") or "").lower()
            if e.get("from") or (name not in ports and name not in servers):
                continue
            extra = {"server": True, "runtime": servers[name].runtime} if name not in ports else {}
            rows.append({**scrub_event(e), "port": ports[name] if name in ports else server_port(servers[name].url), **extra})
        return {"events": rows[-EVENTS_MAX:]}

    def tail(self, n: int, host: str = "") -> dict:
        from halo_harness.host.state import tail_max
        n = max(1, min(int(n), tail_max(self.home)))
        hs = self._pick(host)
        srv = next((x for x in self.servers() if host and x.name.lower() == host.lower()), None) if not hs else None
        if srv is not None:  # 3.3.8.0 R2: a local server's log (ollama_steward/server_log_hf.py)
            from halo_harness.ollama_steward.server_log_hf import tail_lines as server_tail
            lines, source, why = server_tail(srv, n)
            return {"host": srv.name, "lines": [scrub_line(x) for x in lines][-n:], "source": source, "why": why, "n": n,
                    "server": True, "runtime": srv.runtime}
        if not hs:
            return {"host": host, "lines": [], "source": "", "why": "this machine serves no Ollama host", "n": n}
        h = hs[0]
        if "tail" in self.readers:
            lines, source, why = self.readers["tail"](h, n)
        else:
            from halo_harness.ollama_steward.log_tail import tail_lines
            lines, source, why = tail_lines(h, n)
        return {"host": h.name, "lines": [scrub_line(x) for x in lines][-n:], "source": source, "why": why, "n": n}
