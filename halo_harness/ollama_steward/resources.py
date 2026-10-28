"""halo_harness.ollama_steward.resources -- Halo 3.3.5.0 R1: the Local tab's
live resources, one sample a second per host this machine serves, while the
tab watches (`want("tab", on)`, a lease the page renews) or the steward job
runs (`want("job", on)`, ollama_steward/job.py). Readers:
resources_readers.py (GPU) and resources_system.py (RAM, CPU).

A sample (the `resources` frame's data):

    {host, url, t, gpu (%), vram_used, vram_total, holder, holders [{name,
     bytes, kind: model | process}], ram_used, ram_total, cpu (%), temp (C),
     others (bytes not Ollama's), from (the member, on a hub), sources {field:
     where the figure came from, or why there is none}}

`holder` is the biggest holder: nvidia-smi's compute processes where they
carry bytes, else the models `/api/ps` has loaded (read every PS_EVERY_S).
STORE keeps the last KEEP_S per host in memory (`recent`, `latest`, a page
that opens later); `<state>/ollama/resources-recent.json` holds the last
minute for the member's ledger push (fleet/ollama_share.py, another process);
`take_remote` is the hub's side. `others_for` is the fit planner's "others"
share (fit.card_budget) when the sample is newer than the card.
"""

from __future__ import annotations

import collections
import threading
import time
from typing import Callable, Optional

SAMPLE_S = 1.0
KEEP_S = 300.0
PS_EVERY_S = 5.0
FILE_EVERY_S = 5.0
FILE_KEEP_S = 60.0
LEASE_S = 45.0
RECENT_FILE = "resources-recent.json"
_LOCK = threading.RLock()
_WANT: dict = {}  # owner -> expiry (monotonic), None = until released
_SAMPLER: dict = {}  # "one" -> the running Sampler of this process
SAMPLER_SEAMS: dict = {}  # the tests' and the captures' Sampler keywords (seams, hosts, ps, clock) for `want`


class Store:
    def __init__(self) -> None:
        self.by_host: "dict[str, collections.deque]" = {}

    def add(self, s: dict) -> None:
        with _LOCK:
            q = self.by_host.setdefault(str(s.get("host")), collections.deque())
            q.append(s)
            cut = float(s.get("t") or 0) - KEEP_S
            while q and float(q[0].get("t") or 0) < cut:
                q.popleft()

    def recent(self, host: str = "", since_s: float = KEEP_S, now: Optional[float] = None) -> list:
        now = time.time() if now is None else now
        with _LOCK:
            rows = [s for h, q in self.by_host.items() if not host or h.lower() == host.lower() for s in q]
        return sorted((s for s in rows if float(s.get("t") or 0) >= now - since_s), key=lambda s: s.get("t") or 0)

    def latest(self, host: str) -> Optional[dict]:
        with _LOCK:
            q = self.by_host.get(host)
            return dict(q[-1]) if q else None

    def hosts(self) -> list:
        with _LOCK:
            return [h for h, q in self.by_host.items() if q]

    def clear(self) -> None:
        with _LOCK:
            self.by_host.clear()


STORE = Store()


def local_hosts() -> list:
    """The Ollama hosts this machine serves; none configured here: one pseudo host, "this machine"."""
    from halo_harness.fleet.ollama_share import served_here
    from halo_harness.providers.ollama import resolve_ollama_hosts
    try:
        mine = [h for h in resolve_ollama_hosts() if served_here(h.url)]
    except Exception:
        mine = []
    return mine or [None]


def holders_of(apps: Optional[list], loaded: Optional[list]) -> "tuple[list, str]":
    """[{name, bytes, kind}] biggest first, and where they came from."""
    from halo_harness.ollama_steward.hardware_sources import _OWN_PROCESSES
    procs = [a for a in apps or [] if isinstance(a.get("bytes"), int)]
    models = [{"name": m.get("model"), "bytes": m.get("size_vram"), "kind": "model"} for m in loaded or [] if m.get("model")]
    if procs:
        rest = [{"name": a.get("name") or "a process this user cannot see", "bytes": a["bytes"], "kind": "process"}
                for a in procs if not any(o in str(a.get("name") or "").lower() for o in _OWN_PROCESSES)]
        out, src = rest + models, "nvidia-smi --query-compute-apps" + (" and /api/ps" if models else "")
    else:
        out, src = models, "/api/ps (the driver gives no per-process numbers)" if apps else "/api/ps"
    return sorted(out, key=lambda h: -(h.get("bytes") or 0)), src


def build_sample(host, t: float, g: Optional[dict], why_g: str, apps: Optional[list], loaded: Optional[list],
                 r: Optional[dict], why_r: str, cpu, why_c: str) -> dict:
    from halo_harness.ollama_steward.profiles import short_model
    g = g or {}
    hs, hsrc = holders_of(apps, loaded)
    ollama = sum(int(m.get("size_vram") or 0) for m in loaded or [])
    procs_known = any(h["kind"] == "process" for h in hs)
    used = g.get("vram_used")
    if procs_known:
        others = sum(int(h.get("bytes") or 0) for h in hs if h["kind"] == "process")
    else:
        others = max(0, int(used) - ollama) if isinstance(used, int) and loaded is not None else None
    top = hs[0] if hs else None
    name = short_model(top["name"]) if top and top["kind"] == "model" else (top or {}).get("name")
    return {"host": getattr(host, "name", None) or "this machine", "url": getattr(host, "url", None), "t": round(t, 3),
            "gpu": g.get("gpu"), "vram_used": used, "vram_total": g.get("vram_total"), "holder": name, "holders": hs[:6],
            "ram_used": (r or {}).get("used"), "ram_total": (r or {}).get("total"), "cpu": cpu, "temp": g.get("temp"),
            "others": others, "unified": bool(g.get("unified")), "from": None,
            "sources": {"gpu": g.get("source") or why_g, "vram": g.get("source") or why_g,
                        "holder": hsrc if hs else "nothing holds the card, or no reader answered",
                        "ram": (r or {}).get("source") or why_r, "cpu": why_c, "temp": g.get("source") if g.get("temp") is not None
                        else "the tool reports no temperature here", "others": "vram used minus Ollama's models"
                        if not procs_known else "the compute processes that are not Ollama's"}}


class Sampler:
    def __init__(self, state_dir, *, publish: Optional[Callable] = None, seams=None, clock: Callable = time.time,
                 hosts: Optional[Callable] = None, ps: Optional[Callable] = None) -> None:
        from halo_harness.ollama_steward.resources_readers import default_seams
        from halo_harness.ollama_steward.resources_system import Cpu
        self.state_dir, self.publish, self.clock = state_dir, publish, clock
        self.seams = seams or default_seams()
        self.cpu = Cpu(self.seams)
        self.cpu.read()  # primed: the CPU share is between two reads, so the first sample has one too
        self.hosts_fn, self.ps_fn = hosts or local_hosts, ps
        self.ps_cache: dict = {}
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.last_file = 0.0

    def _loaded(self, host, now: float) -> Optional[list]:
        if host is None:
            return None
        hit = self.ps_cache.get(host.url)
        if hit is not None and now - hit[0] < PS_EVERY_S:
            return hit[1]
        from halo_harness.ollama_steward.hardware_sources import parse_ps
        from halo_harness.ollama_steward.resources_readers import off
        body = None
        if self.ps_fn is not None:
            body = self.ps_fn(host)
        elif not off(self.seams):
            from halo_harness.providers.ollama import fetch_ps
            body = fetch_ps(host, timeout=2.0)
        rows = parse_ps(body) if isinstance(body, dict) else None
        self.ps_cache[host.url] = (now, rows)
        return rows

    def sample_once(self, now: Optional[float] = None) -> list:
        from halo_harness.ollama_steward import resources_readers as rr
        from halo_harness.ollama_steward.resources_system import ram
        now = self.clock() if now is None else now
        g, why_g = rr.gpu(self.seams)
        apps, _why_a = rr.apps(self.seams)
        r, why_r = ram(self.seams)
        cpu, why_c = self.cpu.read()
        out = []
        for host in self.hosts_fn():
            s = build_sample(host, now, g, why_g or "", apps, self._loaded(host, now), r, why_r or "", cpu, why_c or "")
            STORE.add(s)
            out.append(s)
            if self.publish is not None:
                try:
                    self.publish({"session_id": "local", "event": "resources", "ts": now, "data": s})
                except Exception:
                    pass
        if now - self.last_file >= FILE_EVERY_S:
            self.last_file = now
            write_recent(self.state_dir, now)
        return out

    def _loop(self) -> None:
        while not self.stop_event.is_set() and wanted():
            try:
                self.sample_once()
            except Exception:
                pass
            self.stop_event.wait(SAMPLE_S)
        with _LOCK:
            if _SAMPLER.get("one") is self:
                _SAMPLER.pop("one", None)

    def start(self) -> None:
        self.thread = threading.Thread(target=self._loop, name="halo-local-resources", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()


def wanted(now: Optional[float] = None) -> bool:
    now = time.monotonic() if now is None else now
    with _LOCK:
        for owner, exp in list(_WANT.items()):
            if exp is not None and exp < now:
                _WANT.pop(owner, None)
        return bool(_WANT)


def want(state_dir, owner: str, on: bool, *, publish: Optional[Callable] = None, lease: Optional[float] = LEASE_S,
         start: bool = True) -> dict:
    """An owner ("tab", "job") wants the sampler on (a lease of `lease` s, None = until released) or off."""
    with _LOCK:
        if on:
            _WANT[owner] = time.monotonic() + lease if lease else None
        else:
            _WANT.pop(owner, None)
        running = _SAMPLER.get("one")
        if running is not None and publish is not None and running.publish is None:
            running.publish = publish
        if on and running is None and start:
            s = _SAMPLER["one"] = Sampler(state_dir, publish=publish, **SAMPLER_SEAMS)
            s.start()
    return status()


def status() -> dict:
    on = wanted()
    with _LOCK:
        return {"on": on, "owners": sorted(_WANT), "running": "one" in _SAMPLER, "every_s": SAMPLE_S, "keep_s": KEEP_S}


def stop_all() -> None:
    with _LOCK:
        _WANT.clear()
        s = _SAMPLER.pop("one", None)
    if s is not None:
        s.stop()


from halo_harness.ollama_steward.resources_share import others_for, read_recent, take_remote, write_recent  # noqa: E402,F401
