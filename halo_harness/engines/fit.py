"""halo_harness.engines.fit -- the two fit rules the engines need, driven by each descriptor's `fit` figures and the
models' sizes (engines/models.py). One deterministic line per model and host; reads only, nothing loads.

- `vram` (TensorFold): the checkpoint held whole in the card's memory (the Mac's unified memory on Metal): its size
  plus the engine's reserve (a share of RAM or VRAM, with a floor) must fit the card's budget, the rest holds the
  window's KV and the streams; a model qualified on two machines is out on one; NVFP4 on the fallback cards is slower.
- `paged-moe` (FreeToken, Strata): RAM and the disk link, not VRAM: the experts live in host RAM (with the engine's
  spare), the dense part on the card; short of RAM an engine that maps its experts from disk still runs, slower;
  under WSL2 a pinned-memory cap makes it slower.

    host_for(name, card, *, facts=None, speed=None) -> host     fit(engine, row, host, *, window=None) -> {level, line,
    numbers, runtime}   level: fits | tight | no | unknown      badge(lib_row, card, window, *, host_name="") -> the
    Library's fit      here_line(engine, row, window=None) -> "fit here: ..." for this machine
"""

from __future__ import annotations

import re
from typing import Optional

from halo_harness.engines.descriptors import get

GIB = 2 ** 30


def _g(v) -> str:
    v = float(v or 0)
    return f"{v:.0f} GB" if v >= 10 else f"{v:.1f} GB"


def _sm(name: str) -> Optional[int]:
    n = str(name or "").upper()
    for rx, sm in ((r"RTX\s*50\d\d|B\d00|GB10|RTX PRO 6000", 120), (r"H100|H200|GH200", 90),
                   (r"RTX\s*40\d\d|\bL4\b|L40|ADA", 89), (r"RTX\s*30\d\d|A10\b|A40|A6000", 86), (r"A100|A30\b", 80)):
        if re.search(rx, n):
            return sm
    return None


def host_for(name: str, card: Optional[dict], *, facts: Optional[dict] = None, speed=None) -> dict:
    from halo_harness.ollama_steward.fit import card_budget
    gpus = [g for g in (card or {}).get("gpus") or [] if isinstance(g, dict)]
    libs = {str(g.get("library") or "").lower() for g in gpus}
    unified = bool((card or {}).get("unified")) or "metal" in libs
    backend = "metal" if unified else "cuda" if "cuda" in libs else "rocm" if libs & {"rocm", "hip"} else None
    f, gpu = facts or {}, (gpus[0].get("name") if gpus else None)
    return {"name": name, "gpu": gpu, "gpus": len(gpus), "unified": unified, "backend": backend,
            "vram": max((int(g.get("total_bytes") or 0) for g in gpus), default=0) / GIB,
            "ram": int((card or {}).get("ram_bytes") or 0) / GIB,
            "budget": (card_budget(card)["budget"] if card else 0) / GIB, "os": f.get("os") or ("macos" if unified else ""),
            "arch": f.get("arch") or "", "wsl": bool(f.get("wsl")), "sm": _sm(gpu) if backend == "cuda" else None,
            "speed": speed, "read": bool(card)}


def _card(h: dict) -> str:
    g = str(h.get("gpu") or "the GPU")
    for p in ("NVIDIA GeForce RTX ", "NVIDIA GeForce ", "AMD Radeon ", "NVIDIA "):
        if g.startswith(p):
            return "the " + g[len(p):]
    return g if g.startswith(("the ", "a ", "an ")) else f"the {g}"


def _out(d: dict, level: str, line: str, nums=None) -> dict:
    return {"level": level, "line": line, "numbers": nums, "runtime": d["id"]}


def _where_runs(d: dict, row: dict, h: dict) -> Optional[str]:
    """The `no` line when the engine (or this model on it) does not run on this host, else None."""
    where, label = h["name"], d["label"]
    if d["os"] and h["os"] and h["os"] not in d["os"]:
        return f"does not fit: {label} runs on {', '.join(d['os'])} ({where} is {h['os']})"
    if d["arch"] and h["arch"] and h["arch"] not in d["arch"]:
        return f"does not fit: {label} runs on {d['arch'][0]} ({where} is {h['arch']})"
    if h["backend"] not in d["backends"]:
        return (f"does not fit: {label} runs on {' / '.join(d['backends'])}; {where} has "
                f"{_card(h) if h['gpus'] else 'no GPU on its card'}")
    if row.get("backends") and h["backend"] not in row["backends"]:
        return f"does not fit: {label} runs {row['name']} on {' / '.join(row['backends'])} only"
    if row.get("machines", 1) > 1:
        return f"does not fit: {label} qualifies {row['name']} across {row['machines']} machines, not on one"
    m = re.search(r"Apple M(\d)", str(h.get("gpu") or ""))
    if row.get("apple_min") and m and int(m.group(1)) < row["apple_min"]:
        return f"does not fit: {label} refuses {row['name']} on an M1-M{row['apple_min'] - 1} Mac"
    if row.get("min_vram_gb") and not h["unified"] and h["vram"] < row["min_vram_gb"]:
        return f"does not fit: {row['name']} needs a {row['min_vram_gb']:g} GB card or more, {_g(h['vram'])} on {_card(h)}"
    return None


def _vram(d: dict, row: dict, h: dict, window) -> dict:
    f, where = d["fit"], h["name"]
    floor, share = f["reserve_unified"] if h["unified"] else f["reserve_discrete"]
    reserve = max(floor, (h["ram"] if h["unified"] else h["vram"]) * share)
    size, left = row["size_gb"], h["budget"] - reserve - row["size_gb"]
    level = "fits" if left >= max(2.0, size / 10) else "tight" if left > 0 else "no"
    mem = f"{_g(h['budget'])} of unified memory for the GPU" if h["unified"] else f"{_card(h)}'s {_g(h['budget'])}"
    nums = {"size_gb": round(size, 1), "budget_gb": round(h["budget"], 1), "reserve_gb": round(reserve, 1),
            "left_gb": round(left, 1), "window": window, "backend": h["backend"]}
    if level == "no":
        return _out(d, "no", f"does not fit: {row['name']} ({_g(size)}) needs {_g(size + reserve)} with {d['label']}'s "
                             f"{_g(reserve)} reserve; {where} has {mem}", nums)
    lo, hi = f.get("fallback_sm") or (0, -1)
    slow = (f"; NVFP4 on {_card(h)} (sm_{h['sm']}) runs {d['label']}'s fallback path: slower"
            if row.get("nvfp4") and h.get("sm") and lo <= h["sm"] <= hi else "")
    return _out(d, level, f"{'fits' if level == 'fits' else 'fits, tight'}: {row['name']} ({_g(size)}) on {where}: "
                          f"{mem}, less {d['label']}'s {_g(reserve)} reserve, leaves {_g(left)} for the {window:,}-token "
                          f"window's KV and its streams{slow}; the download: {row['pull']} (yours to run)", nums)


def _paged(d: dict, row: dict, h: dict) -> dict:
    f, where, need = d["fit"], h["name"], row["ram_gb"]
    if f.get("gpu_share") and row.get("gpu_gb") and row["gpu_gb"] > h["budget"] * f["gpu_share"]:
        return _out(d, "no", f"does not fit: {row['name']} needs {_g(row['gpu_gb'])} on {_card(h)}, "
                             f"{_g(h['budget'] * f['gpu_share'])} usable on {where}")
    both = row.get("pool") == "ram+vram" and not h["unified"]
    ram = h["ram"] + (h["vram"] if both else 0.0)
    if need + f["spare_gb"] <= ram * f["fit_share"]:
        level, word = "fits", "fits"
    elif need + f["tight_gb"] <= ram * f["tight_share"]:
        level, word = "tight", "fits, tight"
    elif f.get("map_share") and not both and need <= ram * f["map_share"] and ram >= row.get("min_ram_gb", 0):
        level, word = "tight", "fits, slower"
    else:
        level, word = "no", ""
    nums = {"ram_gb": round(ram, 1), "need_gb": round(need, 1), "spare_gb": f["spare_gb"], "vram_gb": round(h["vram"], 1)}
    pool = "VRAM + RAM together" if both else "RAM"
    if level == "no":
        return _out(d, "no", f"does not fit: {row['name']} needs {_g(need + f['spare_gb'])} of {pool}, {_g(ram)} on "
                             f"{where}", nums)
    pin = f.get("wsl_pin_share")
    if pin and h["wsl"] and need > h["ram"] * pin:
        level, word = "tight", "fits, slower"
        tail = f"; under WSL about {_g(h['ram'] * pin)} pins, the rest decodes on the CPU"
    else:
        tail = "; what RAM cannot hold is read from the SSD" if word == "fits, slower" else ""
    slots = next((n for v, n in f.get("slots") or () if round(h["vram"]) >= v), None)
    slots = row.get("slots", slots)
    head = (f"{word}: {row['name']} on {where}: {_g(need)} of experts in {_g(ram)} of {pool} over {f['link']}"
            + (f", {_g(row['gpu_gb'])} on {_card(h)}" if row.get("gpu_gb") else "")
            + (f", {slots} slot{'s' if slots != 1 else ''} by the VRAM guide" if slots else "")
            + (f", {row['ssd_gb']:g} GB streamed from the SSD" if row.get("ssd_gb") else "") + tail)
    speed = h.get("speed") or (f"expect {row['speed']} by {d['label']}'s table, not measured here yet" if row.get("speed")
                               else "speed not measured yet")
    dl = f"; the download: {row['pull']} ({_g(row['size_gb'])}, yours to run)" if row.get("size_gb") else ""
    return _out(d, level, f"{head}; {speed}{dl}", {**nums, "slots": slots})


def fit(engine: str, row: Optional[dict], host: dict, *, window: Optional[int] = None) -> dict:
    d = get(engine)
    where = host.get("name") or "this machine"
    if row is None:
        return _out(d, "unknown", f"on {where}: not a model {d['label']} names (docs/MODELS-engines.md)")
    if not host.get("read"):
        return _out(d, "unknown", f"{row['name']} on {where}: no hardware card read yet (the Hosts page or halo ollama "
                                  "hardware reads it)")
    no = _where_runs(d, row, host)
    if no:
        return _out(d, "no", no)
    size = row["size_gb"] if d["fit"]["rule"] == "vram" else row["ram_gb"]
    if size is None:
        tables = (f"; its {row['ssd_gb']:g} GB of tables stream from the SSD" if row.get("ssd_gb") else "") + (
            f"; {row['extra_gb']:g} GB stay in RAM" if row.get("extra_gb") else "")
        return _out(d, "unknown", f"{row['name']} on {where}: {d['label']} publishes no size for it (download it: its "
                                  f"files size it){tables}")
    if d["fit"]["rule"] == "vram":
        return _vram(d, row, host, int(window or row.get("context") or 32768))
    return _paged(d, row, host)


def badge(lib_row: dict, card: Optional[dict], window: int, *, host_name: str = "") -> dict:
    from halo_harness.engines.models import match
    engine = str(lib_row.get("kind") or "")
    hit = match(engine, lib_row.get("id"))
    base = {"at_window": int(window or 32768), "gpu_window": None, "estimate": True, "host": host_name or None,
            "shape_source": f"{get(engine)['label']}'s own figures (engines/models.py)", "runtime": engine}
    if not card or hit is None:
        return {**base, "level": "unknown", "numbers": None,
                "why": f"no hardware card read for {host_name or 'this host'} yet (the Hosts page reads it)"}
    from halo_harness.engines.bench import speed_word
    got = fit(engine, hit, host_for(host_name or "this host", card, speed=speed_word(None, host_name, hit["id"], engine)),
              window=window)
    return {**base, "level": got["level"], "why": got["line"], "numbers": got["numbers"], "engine": got}


def here_line(engine: str, row: Optional[dict], window: Optional[int] = None) -> str:
    from halo_harness.engines.adapter import facts
    from halo_harness.providers.local_server_cmd import this_machine_card
    card, _name = this_machine_card()
    return "fit here: " + fit(engine, row, host_for("this machine", card, facts=facts()), window=window)["line"]
