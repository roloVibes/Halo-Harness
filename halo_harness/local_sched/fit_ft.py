"""halo_harness.local_sched.fit_ft -- the fit for a FreeToken server: RAM + link, not VRAM (Halo 3.3.9.1; docs/MODELS-
freetoken.md "The fit"). One deterministic line per model and host.

FreeToken's offload strategy (the default for an MoE on a discrete GPU) keeps the routed experts in host RAM with an
LRU cache of expert slots on the GPU, misses streamed over PCIe; the dense layers and the KV stay on the GPU; the
engine takes `--memory-ratio` 0.9 of the free VRAM; the expert cache must hold at least one whole layer of experts;
under WSL CUDA pinning is capped near half of RAM and FreeToken budgets 40 % of it (engine._pin_budget_bytes), the
layers over it OS-locked for CPU decode (docs/models.md, docs/cli.md, engine/engine.py: from the source, unverified
against a live run).

    fit(shape, host, *, window=32768) -> {level, line, numbers, link_gbs, link, strategy}
        shape: freetoken/shape.py's Shape; host: {name, gpu, vram_free_bytes, ram_bytes, linux, x86, wsl, link_gbs,
               speed} (link_gbs None: the extrapolated PCIe figure is said; speed: "12.1 tok/s measured" or None)
        level: fits | tight | no | unknown
    host_from_card(name, card, *, facts=None, link_gbs=None, speed=None) -> host   a hardware card (gpus, ram_bytes)
    for_row(row, card, *, host_name, window, state_dir=None) -> fit | None   a Library row FreeToken serves
    badge(row, card, window, *, host_name="") -> models_library/rows.fit_for_row's shape {level, why, numbers, ...}

Reads only: nothing loads, nothing is measured here (`halo local bench --host freetoken --bw` measures the link).
"""

from __future__ import annotations

from typing import Optional

MEMORY_RATIO = 0.9
PIN_SHARE_WSL = 0.4
RAM_SHARE = 0.9
TIGHT_RAM = 0.75
DEFAULT_WINDOW = 32768
GB = 2 ** 30  # memory is said in binary GB, as the hardware card and a "64 GB" RAM kit count it


def _gb(n) -> str:
    v = float(n or 0) / GB
    return f"{v:.0f} GB" if v >= 10 else f"{v:.1f} GB"


def host_from_card(name: str, card: Optional[dict], *, facts: Optional[dict] = None, link_gbs=None, speed=None) -> dict:
    gpus = [g for g in (card or {}).get("gpus") or [] if isinstance(g, dict)]
    from halo_harness.ollama_steward.fit import card_budget
    b = card_budget(card or {}) if card else {"budget": 0}
    f = facts or {}
    return {"name": name, "gpu": (gpus[0].get("name") if gpus else None) or "the GPU", "vram_free_bytes": b["budget"],
            "ram_bytes": (card or {}).get("ram_bytes"), "linux": f.get("linux", True), "x86": f.get("x86", True),
            "wsl": bool(f.get("wsl")), "os": f.get("os") or "linux", "link_gbs": link_gbs, "speed": speed}


def _gpu_word(gpu: str) -> str:
    g = str(gpu or "the GPU")
    for p in ("NVIDIA GeForce RTX ", "NVIDIA GeForce ", "GeForce RTX ", "NVIDIA "):
        if g.startswith(p):
            return "the " + g[len(p):]
    return g if g.startswith(("the ", "a ", "an ")) else f"the {g}"


def fit(shape: Optional[dict], host: dict, *, window: int = DEFAULT_WINDOW, state_dir=None) -> dict:
    from halo_harness.freetoken.link import link_words
    window = int(window or DEFAULT_WINDOW)
    name, where = (shape or {}).get("name") or "the model", host.get("name") or "this machine"
    gbs, link = link_words(state_dir, gbs=host.get("link_gbs"))
    base = {"level": "unknown", "numbers": None, "link_gbs": gbs, "link": link, "strategy": "offload", "runtime": "freetoken"}
    if not (host.get("linux") and host.get("x86", True)):
        return {**base, "level": "no", "line": f"does not fit: FreeToken runs on Linux x86_64 ({where} is {host.get('os')}; "
                                               "on Windows, WSL2 runs it with the pinned-memory cap)"}
    if not shape or not shape.get("expert_bytes") or not shape.get("dense_bytes"):
        tables = (f"; its {shape['nvme_bytes'] / 2 ** 30:g} GiB of tables stream from NVMe and "
                  f"{shape['ram_extra_bytes'] / 2 ** 30:g} GiB stay in RAM" if (shape or {}).get("nvme_bytes") else
                  f"; its {shape['ram_extra_bytes'] / 2 ** 30:g} GiB table stays pinned in RAM"
                  if (shape or {}).get("ram_extra_bytes") else "")
        return {**base, "line": f"{name} on {where}: its dense and expert sizes are not known yet (download it: its "
                                f"config.json and files split them){tables}"}
    vram, ram = int(host.get("vram_free_bytes") or 0), int(host.get("ram_bytes") or 0)
    if not vram or not ram:
        return {**base, "line": f"{name} on {where}: no hardware card read yet (the Hosts page or halo ollama hardware reads it)"}
    kv = int(shape["kv_per_token"] * window) if shape.get("kv_per_token") else 0
    layer = int(shape.get("layer_expert_bytes") or 0)
    dense, experts, extra = int(shape["dense_bytes"]), int(shape["expert_bytes"]), int(shape.get("ram_extra_bytes") or 0)
    usable_vram, usable_ram = int(vram * MEMORY_RATIO), int(ram * RAM_SHARE)
    gpu_need = dense + kv + layer
    pin = int(ram * PIN_SHARE_WSL) if host.get("wsl") else None
    nums = {"dense": dense, "kv": kv, "kv_window": window, "layer_experts": layer, "experts": experts, "ram_extra": extra,
            "vram_free": vram, "vram_usable": usable_vram, "ram": ram, "ram_usable": usable_ram, "pin_cap": pin,
            "nvme": int(shape.get("nvme_bytes") or 0), "shape_from": shape.get("from")}
    gpu = _gpu_word(host.get("gpu"))
    extra_words = f" + {extra / 2 ** 30:g} GiB of tables" if extra else ""
    nvme = (f"; its {nums['nvme'] / 2 ** 30:g} GiB of tables stream from NVMe (a fast one)" if nums["nvme"] else "")
    if gpu_need > usable_vram:
        parts = f"{_gb(dense)} dense" + (f" + KV {_gb(kv)} at {window // 1024}k" if kv else "") + (
            f" + one layer of experts {_gb(layer)}" if layer else "")
        return {**base, "level": "no", "numbers": nums,
                "line": f"does not fit: {name} needs {parts} on {gpu}, {_gb(usable_vram)} usable on {where}{nvme}"}
    if experts + extra > usable_ram:
        return {**base, "level": "no", "numbers": nums,
                "line": f"does not fit: {name} needs {_gb(experts)} of experts{extra_words} in RAM, {_gb(ram)} on "
                        f"{where} ({_gb(usable_ram)} usable){nvme}"}
    speed = host.get("speed") or "speed not measured yet"
    head = f"{name} on {where}, {_gb(dense)} active on {gpu}, {_gb(experts)} of experts{extra_words} in RAM over {link}"
    if pin is not None and experts + extra > pin:
        return {**base, "level": "tight", "numbers": nums,
                "line": f"fits, slower: {head}; under WSL about {_gb(pin)} pins (FreeToken budgets 40 % of RAM), the "
                        f"rest decodes on the CPU (--moe-cpu-layers auto){nvme}; {speed}"}
    level = "tight" if experts + extra > ram * TIGHT_RAM else "fits"
    tail = "; little RAM is left for the rest of the machine" if level == "tight" else ""
    return {**base, "level": level, "numbers": nums, "line": f"{'fits' if level == 'fits' else 'fits, tight'}: {head}"
                                                             f"{tail}{nvme}; {speed}"}


def _facts_for(host_name: str) -> Optional[dict]:
    """This machine's platform when the host is served here; a far host's card says no OS (taken as Linux, the only one
    FreeToken runs on: its own `halo doctor --local` says otherwise there)."""
    try:
        from halo_harness.fleet.ollama_share import served_here
        from halo_harness.providers.ollama import resolve_ollama_hosts
        h = next((x for x in resolve_ollama_hosts() if x.name.lower() == str(host_name or "").lower()), None)
        if h is not None and served_here(h.url):
            from halo_harness.freetoken.requirements import platform_facts
            return platform_facts()
    except Exception:
        pass
    return None


def for_row(row: dict, card: Optional[dict], *, host_name: str, window: int, state_dir=None) -> Optional[dict]:
    """The FreeToken fit for a Library row it serves (catalog.match on the repo); None for any other row."""
    from halo_harness.freetoken.catalog import match
    hit = match(row.get("id") or "") if row.get("source") != "ollama" else None
    if hit is None:
        return None
    from halo_harness.freetoken.bench import speed_word
    from halo_harness.freetoken.shape import of_row
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    host = host_from_card(host_name or "this host", card, facts=_facts_for(host_name),
                          speed=speed_word(state_dir, host_name, hit["name"]))
    return fit(of_row({**hit, "name": hit["name"]}), host, window=window, state_dir=state_dir)


def badge(row: dict, card: Optional[dict], window: int, *, host_name: str = "") -> dict:
    """models_library/rows.fit_for_row's shape for a FreeToken row: the level, `why` = the fit's one line."""
    got = for_row(row, card, host_name=host_name, window=window) if card else None
    base = {"at_window": int(window or DEFAULT_WINDOW), "gpu_window": None, "estimate": True, "host": host_name or None,
            "shape_source": "the parameter counts (freetoken/catalog.py)", "runtime": "freetoken"}
    if got is None:
        return {**base, "level": "unknown", "numbers": None,
                "why": f"no hardware card read for {host_name or 'this host'} yet (the Hosts page reads it)"}
    return {**base, "level": got["level"], "why": got["line"], "numbers": got["numbers"], "freetoken": got}
