"""halo_harness.local_sched.fit_st -- the fit for a Strata server: FreeToken's RAM + link rule (local_sched/fit_ft.py)
with Strata's own figures (Halo 3.3.9.2; docs/MODELS-strata.md "The fit"). One deterministic line per set and host.

Strata's statements (docs/MODELS.md "Pick by memory", "Will it fit?", the Unsloth, Gyro, NVFP4, Qwen3.6 and DeepSeek
tables; docs/TERMINAL_LAUNCH.md "Parallel requests": from the source, unverified against a live run):
- Flash-Next (ISTA-DASLab, the Coder, Swift): shard 1's experts go into RAM, the rest onto the card, and the 29 GB
  n-gram table stays on the SSD; it fits when RAM is at least the experts plus about 10 GB; short of that Strata maps
  the experts from the model files and reads what RAM cannot hold from the SSD ("works and is much slower");
- Unsloth and NVFP4: every expert in RAM needs the stated RAM figure; with less Strata keeps what fits and reads the
  rest from the SSD; NVFP4 runs on NVIDIA only;  Gyro: the stated VRAM + RAM together;
- Qwen3.6-35B-A3B: the RAM setup plans for; the experts the card cannot hold run on the CPU (no Mac engine);
- DeepSeek V4.1-Flash: a 12 GB card or more, 46 GB of RAM at least (64 GB the tested comfortable size), the rest read
  from an NVMe SSD, one request at a time, an 8K window;
- the VRAM guide for `--parallel`: 12 GB runs 1, 20 GB 2, 24 GB 3, 32 GB and more 4.

    slots(vram_gb) -> the guide's parallel requests       host_for(name, card, *, os_name, speed=None) -> host
    fit(row, host) -> {level, line, numbers, slots, strategy, runtime: "strata"}   level: fits | tight | no | unknown
    here_line(row, state_dir) -> "fit here: ..." for this machine          badge(row, card, window, *, host_name="")
Reads only: nothing loads, nothing is measured here (`halo local bench --host strata` measures the speed).
"""

from __future__ import annotations

from typing import Optional

GIB = 2 ** 30  # a "64 GB" RAM kit and a "24 GB" card count binary GB, as the hardware card does
SPARE_GB, TIGHT_GB = 10.0, 6.0  # "the experts plus about 10 GB"; under 6 GB left the server warns (serve/server.py)


def slots(vram_gb) -> int:
    v = round(float(vram_gb or 0))
    return 4 if v >= 32 else 3 if v >= 24 else 2 if v >= 20 else 1


def host_for(name: str, card: Optional[dict], *, os_name: str = "", speed=None) -> dict:
    gpus = [g for g in (card or {}).get("gpus") or [] if isinstance(g, dict)]
    libs = {str(g.get("library") or "").lower() for g in gpus}
    unified = bool((card or {}).get("unified")) or "metal" in libs
    return {"name": name, "gpu": (gpus[0].get("name") if gpus else None), "gpus": len(gpus),
            "vram_gb": max((int(g.get("total_bytes") or 0) for g in gpus), default=0) / GIB,
            "ram_gb": int((card or {}).get("ram_bytes") or 0) / GIB, "unified": unified, "nvidia": "cuda" in libs,
            "os": os_name or ("macos" if unified else ""), "speed": speed, "read": bool(card)}


def _g(v) -> str:
    return f"{v:.0f} GB" if v >= 10 else f"{v:.1f} GB"


def _expect(row: dict, host: dict) -> str:
    if host.get("speed"):
        return str(host["speed"])
    from halo_harness.strata.catalog import measured_for
    got = measured_for(row, host.get("vram_gb"))
    return (f"expect {got[0]} tok/s class (Strata's table: {got[1]}), not measured here yet" if got else
            "Strata states no speed for this set, not measured here yet")


def _ram_level(row: dict, host: dict) -> "tuple[str, str]":
    ram, vram, rule = host["ram_gb"], host["vram_gb"], row["rule"]
    exp = row.get("experts_gb")
    if rule == "experts":
        if ram >= exp + SPARE_GB:
            return "fits", f"{_g(exp)} of experts in {_g(ram)} of RAM"
        if ram >= exp + TIGHT_GB:
            return "tight", f"{_g(exp)} of experts in {_g(ram)} of RAM, little left for the rest of the machine"
        if ram >= exp / 2 or (vram >= 24 and row["set"] in ("Q2_0", "IQ2_XS", "IQ1_M")):
            return "tight", (f"slower: {_g(exp)} of experts against {_g(ram)} of RAM, so Strata maps them from the model "
                             "files and reads what RAM cannot hold from the SSD")
        return "no", f"needs {_g(exp)} of experts plus about 10 GB in RAM, {_g(ram)} here"
    if rule == "all-experts":
        if ram >= row["ram_gb"]:
            return "fits", f"every expert ({_g(exp)}) in {_g(ram)} of RAM"
        if ram >= exp / 2:
            return "tight", (f"slower: every expert needs ~{_g(row['ram_gb'])} of RAM, {_g(ram)} here, so Strata keeps "
                             "what fits and reads the rest from the SSD")
        return "no", f"needs ~{_g(row['ram_gb'])} of RAM for its experts, {_g(ram)} here"
    if rule == "memory":
        both = ram + (0 if host["unified"] else vram)
        level = "fits" if both >= row["memory_gb"] + SPARE_GB else "tight" if both >= row["memory_gb"] + TIGHT_GB else "no"
        return level, (f"needs {_g(row['memory_gb'])} of VRAM + RAM together plus about 10 GB, {_g(both)} here"
                       if level == "no" else f"{_g(row['memory_gb'])} of VRAM + RAM together, {_g(both)} here")
    if rule == "plan":
        level = "fits" if ram >= row["ram_gb"] else "tight" if ram + vram >= row["ram_gb"] else "no"
        return level, f"Strata plans {_g(row['ram_gb'])} of RAM, {_g(ram)} here"
    if vram < 12 and not host["unified"]:
        return "no", f"needs a 12 GB card or more, {_g(vram)} on {_card(host)}"
    level = "fits" if ram >= 64 else "tight" if ram >= 46 else "no"
    return level, (f"{_g(ram)} of RAM (46 GB at least, 64 GB the tested size); what does not fit is read from the "
                   f"SSD -- keep about {row['download_gb']:g} GB free on an NVMe")


def _card(host: dict) -> str:
    g = str(host.get("gpu") or "the GPU")
    for p in ("NVIDIA GeForce RTX ", "NVIDIA GeForce ", "AMD Radeon ", "NVIDIA "):
        if g.startswith(p):
            return "the " + g[len(p):]
    return g if g.startswith(("the ", "a ", "an ")) else f"the {g}"


def fit(row: Optional[dict], host: dict) -> dict:
    base = {"level": "unknown", "numbers": None, "slots": None, "strategy": None, "runtime": "strata"}
    where = host.get("name") or "this machine"
    if row is None:
        return {**base, "line": f"on {where}: not a set Strata names (halo models search strata lists them)"}
    title = f"{row['model']} {row['set']}"
    if not host.get("read"):
        return {**base, "line": f"{title} on {where}: no hardware card read yet (the Hosts page or halo ollama hardware "
                                "reads it)"}
    os_name = host.get("os") or ""
    if os_name == "macos" and not row["mac"]:
        return {**base, "level": "no", "line": f"does not fit: Strata's Mac engine does not run {title}"}
    if row["nvidia_only"] and not host["nvidia"]:
        return {**base, "level": "no", "line": f"does not fit: {title} runs on NVIDIA cards only ({where} has "
                                                f"{_card(host) if host['gpus'] else 'no GPU'})"}
    if not host["gpus"] and not host["unified"]:
        return {**base, "level": "no", "line": f"does not fit: Strata runs on a graphics card ({where} has none on its "
                                                "card: NVIDIA RTX 20-50, AMD Radeon RX 7000 / 9000, Apple Silicon)"}
    level, ram_words = _ram_level(row, host)
    n = 1 if row["family"] == "deepseek41" else slots(host["vram_gb"])
    nums = {"vram_gb": round(host["vram_gb"], 1), "ram_gb": round(host["ram_gb"], 1), "experts_gb": row["experts_gb"],
            "download_gb": row["download_gb"], "ssd_gb": row["ssd_gb"], "slots": n, "rule": row["rule"]}
    if level == "no":
        return {**base, "level": "no", "numbers": nums, "slots": n, "line": f"does not fit: {title} {ram_words}"}
    guide = ("DeepSeek answers one at a time" if row["family"] == "deepseek41" else
             f"the VRAM guide: {round(host['vram_gb'])} GB runs {n}")
    gpu = "unified memory" if host["unified"] else _card(host)
    ssd = (f", its {row['ssd_gb']:g} GB n-gram table streams from the SSD" if row["ssd_gb"] and
           row["family"] != "deepseek41" else "")
    dl = f"; the first launch downloads {row['download_gb']:g} GB (yours to run)" if row["download_gb"] else ""
    word = "fits" if level == "fits" else "fits, tight" if "slower" not in ram_words else "fits, slower"
    ram_words = ram_words.removeprefix("slower: ")
    line = (f"{word}: {title} on {where}: {n} slot{'s' if n != 1 else ''} on {gpu} ({guide}), {ram_words}{ssd}; "
            f"{_expect(row, host)}{dl}")
    return {**base, "level": level, "numbers": nums, "slots": n,
            "strategy": "mapped" if word == "fits, slower" else "ram", "line": line}


def _speed(state_dir, host_name: str, row: dict) -> Optional[str]:
    try:
        from halo_harness.freetoken.bench import speed_word  # strata/bench.py keeps a card under the set's name
        from halo_harness.strata.catalog import set_name
        return speed_word(state_dir, host_name, set_name(row), runtime="strata")
    except Exception:
        return None


def here_line(row: dict, state_dir=None) -> str:
    from halo_harness.providers.local_server_cmd import this_machine_card
    from halo_harness.strata.requirements import os_word
    card, _name = this_machine_card()
    got = fit(row, host_for("this machine", card, os_name=os_word(), speed=_speed(state_dir, "strata", row)))
    return "fit here: " + got["line"]


def badge(row: dict, card: Optional[dict], window: int, *, host_name: str = "") -> dict:
    from halo_harness.strata.catalog import parse
    hit = parse(str(row.get("id") or "").removeprefix("strata:"))
    base = {"at_window": int(window or 32768), "gpu_window": None, "estimate": True, "host": host_name or None,
            "shape_source": "Strata's tables (strata/catalog.py)", "runtime": "strata"}
    if not card or hit is None:
        return {**base, "level": "unknown", "numbers": None,
                "why": f"no hardware card read for {host_name or 'this host'} yet (the Hosts page reads it)"}
    got = fit(hit, host_for(host_name or "this host", card))
    return {**base, "level": got["level"], "why": got["line"], "numbers": got["numbers"], "strata": got}
