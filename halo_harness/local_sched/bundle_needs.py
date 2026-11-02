"""halo_harness.local_sched.bundle_needs -- which model fills each of a bundle's needs on one host, and what it costs
there (Halo 3.3.7.0 R5; plans/local-model-fit-brief.md L3; local_sched/bundle_fit.py turns the picks into the verdict).

    reads(host, state_dir=None) -> Reads    the card's numbers: from a paired halo host's `route` when one serves the
        card (3.3.7.0 R1), else this machine's reads (local_sched/facts: the card, the catalog row, the library snapshot)
    Reads.need(model, window) -> {bytes, installed, row, source}      Reads.usable (bytes, the helper subtracted)
    pick(b, reads, *, coder=None, state_dir=None) -> {role: Pick}
    Pick = {role, model, runtime, device, placed (gpu | cpu), installed, gb, download_gb, minutes, window, why,
            gpu_model, gpu_gb, smaller [{model, gb, words}]}
    coder_of(host, state_dir=None) -> {model, lane, window, need_gb} | None   where task work goes on this host: the
        active lineup's coder / worker lane, else main, else the configured `model`, when it is an `ol:` model there

The rules, need by need: a speech model (runtime voice) runs beside Ollama, resolved through the speech catalog and what
is on disk (local_sched/bundle_voice.py, 3.3.9.0 R1: present -> its footprint, absent -> a download); an Ollama model is the
first of its any_of that passes the need's filters and is installed there, else the first that passes and has a
size (a download), else the first that passes. The filters: `vision` / `tools` (the battery profile, else the catalog
row's capabilities); a verify role never takes the coder's family (the adviser's mismatch rule). Arithmetic only.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.local_sched import facts as F
from halo_harness.packs.manifest_bundle import runtime

DEFAULT_WINDOW = 8192
VERIFY = ("verify", "verifier", "reviewer", "review", "judge", "checker")


class Reads:
    def __init__(self, host, state_dir=None) -> None:
        from halo_harness.local_sched.pivot import _client
        self.host, self.state_dir = host, state_dir
        self.name = str(getattr(host, "name", "") or "")
        self.client = _client(host) if host is not None else None
        self.via = "host" if self.client is not None else "local"
        self.card = F.card(host) if self.via == "local" else {}
        self.rows = F.loaded(host) if host is not None else []
        self.b = F.budget(self.card, self.name)
        self.helper = F.helper(host, self.rows) if host is not None else None
        self.usable = F.usable(self.b, self.helper)
        self.reserve = (512 if self.b.get("metal") else 457) * 2 ** 20 * int(self.b.get("cards") or 1)  # fit._together's
        self._memo: dict = {}

    def need(self, model: str, window: int) -> dict:
        key = (model, int(window))
        if key in self._memo:
            return self._memo[key]
        got = self._via_host(model, window) if self.client is not None else None
        if got is None:
            row, src = F.row(self.host, model) if self.host is not None else (None, "no host")
            n = F.need(self.b, row, window) if row else None
            got = {"bytes": int(n) if n else None, "installed": src.startswith("installed"), "row": row, "source": src,
                   "download_gb": round(row["size"] / 1e9, 1) if row and isinstance(row.get("size"), int) else None}
        self._memo[key] = got
        return got

    def _via_host(self, model: str, window: int) -> Optional[dict]:
        from halo_harness.ollama_steward.host_client import HostError
        try:
            r = self.client.route({"model": model, "window": int(window)})
        except (HostError, OSError, AttributeError):
            return None
        usable = r.get("usable_with_helper_gb")
        if isinstance(usable, (int, float)) and usable > 0:
            self.usable = int(float(usable) * F.GIB)
        n = r.get("need_bytes")  # fit._need's: the per-card reserve is not in it
        row, _src = F.row(self.host, model)
        return {"bytes": int(n) if isinstance(n, (int, float)) else None, "installed": bool(r.get("installed")),
                "row": row, "source": "the halo host's route", "download_gb": round(row["size"] / 1e9, 1)
                if row and isinstance(row.get("size"), int) else None}


def reads(host, state_dir=None) -> Reads:
    return Reads(host, state_dir)


def _root(model: str) -> str:
    from halo_harness.models_library.advise_lines import lineage
    lin = lineage(model)
    return lin[0] if lin else str(model or "").split(":", 1)[0]


def _sees(rd: Reads, model: str, row: Optional[dict], want: str) -> Optional[bool]:
    from halo_harness.providers.placement import profile_for_ref
    p = profile_for_ref(f"ol:{model}@{rd.name}", rd.state_dir) or {}
    if p.get(want) in ("yes", "no"):
        return p[want] == "yes"
    caps = [str(c).lower() for c in (row or {}).get("capabilities") or []]
    if caps:
        return want in caps
    from halo_harness.models_library import snapshot
    e = snapshot.entry_of(model.split(":", 1)[0]) or {}
    caps = [str(c).lower() for c in e.get("capabilities") or []]
    return (want in caps) if caps else None


def words(model: str, row: Optional[dict]) -> str:
    d = (row or {}).get("details") or {}
    if d.get("parameter_size"):
        return str(d["parameter_size"])
    from halo_harness.models_library.nearest import facts
    p = facts(model, row)["params_b"]
    return f"{p:g}B" if p else model


def _voice(role: str, need: dict) -> dict:
    from halo_harness.local_sched.bundle_voice import pick as speech  # 3.3.9.0 R1: the catalog and what is on disk
    return speech(role, need)


def _ollama(role: str, need: dict, rd: Reads, coder: Optional[dict]) -> dict:
    from halo_harness.models_library.advise_lines import cost
    window = need["window"] or DEFAULT_WINDOW
    skip_root = _root(coder["model"]) if coder and any(v in role for v in VERIFY) else None
    passed, said = [], []
    for name in need["any_of"]:
        if skip_root and _root(name) == skip_root:
            said.append(f"{name}: the coder's family ({skip_root}); a verifier of another family checks it")
            continue
        got = rd.need(name, window)
        for want in ("vision", "tools"):
            if need[want] and _sees(rd, name, got["row"], want) is False:
                said.append(f"{name}: its profile says {want}: no")
                break
        else:
            passed.append((name, got))
    best = next((x for x in passed if x[1]["installed"]), None) or next((x for x in passed if x[1]["bytes"]), None) \
        or (passed[0] if passed else None)
    if best is None:
        return {"role": role, "model": None, "runtime": "ollama", "device": need["device"], "placed": "gpu",
                "installed": False, "gb": None, "download_gb": None, "minutes": 0, "window": window,
                "why": "; ".join(said) or "no model listed", "gpu_model": None, "gpu_gb": None, "smaller": []}
    name, got = best
    gb = got["bytes"] / F.GIB if got["bytes"] else None
    dl = 0.0 if got["installed"] else (got["download_gb"] or 0.0)
    smaller = [{"model": n, "gb": g["bytes"] / F.GIB, "words": words(n, g["row"])} for n, g in passed
               if n != name and g["bytes"] and got["bytes"] and g["bytes"] < got["bytes"]]
    on_cpu = need["device"] == "cpu"
    return {"role": role, "model": name, "runtime": "ollama", "device": need["device"], "placed": "cpu" if on_cpu else "gpu",
            "installed": got["installed"], "gb": 0.0 if on_cpu else gb, "download_gb": dl, "minutes":
            cost(dl, None, None, None)["minutes"], "window": window, "why": got["source"] + ("; " + "; ".join(said) if said
                                                                                         else ""),
            "gpu_model": name, "gpu_gb": gb, "smaller": sorted(smaller, key=lambda s: s["gb"]), "words": words(name, got["row"])}


def pick(b: dict, rd: Reads, *, coder: Optional[dict] = None, state_dir=None) -> dict:
    out = {}
    for role, need in (b.get("needs") or {}).items():
        out[role] = _voice(role, need) if runtime(need["any_of"][0] if need["any_of"] else "", need.get("runtime")) \
            == "voice" else _ollama(role, need, rd, coder)
    return out


def coder_of(host, state_dir=None) -> Optional[dict]:
    """The model task work runs on, on this host (see the module docstring), with its need at its window."""
    name = str(getattr(host, "name", "") or "")
    lanes: list = []
    try:
        from halo_harness.local_sched.preview import lanes_for
        from halo_harness.teams_runtime import active_team_name
        lineup = active_team_name(None)
        lanes = lanes_for(lineup, state_dir=state_dir)[0] if lineup else []
    except Exception:
        lanes = []
    here = [ln for ln in lanes if str(ln.get("host") or "").lower() == name.lower()]
    lane = next((ln for ln in here if any(w in ln["lane"] for w in ("coder", "worker", "implement", "builder"))), None) \
        or next((ln for ln in here if ln["lane"] == "main"), None)
    if lane is None:
        from halo_harness.start.provider import default_model
        model, h = F.split_ref(default_model()) if default_model().startswith("ol:") else (None, None)
        default = getattr(F.host_named(None), "name", None)
        if not model or str(h or default or "").lower() != name.lower():
            return None
        lane = {"lane": "main", "model": model}
    row, _src = F.row(host, lane["model"])
    w, _wf = F.window(host, lane["model"], role=lane["lane"])
    return {"model": lane["model"], "lane": lane["lane"], "window": w, "row": row}
