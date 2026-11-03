"""halo_harness.local_sched.fit_tf -- the fit for a TensorFold server (Halo 3.3.9.3; docs/MODELS-tensorfold.md "The fit"):
the ordinary VRAM rule with TensorFold's own figures. TensorFold holds a dense or MoE checkpoint whole in the card's
memory -- the Mac's unified memory on Metal, VRAM on CUDA -- so the checkpoint's size (the README's table) plus
TensorFold's reserve must fit the card, and what is left holds the window's KV and the streams. One deterministic line
per model and host.

TensorFold's statements (README "Pick a model", docs/api.md on memory, from the source, unverified against a live run):
a discrete card's window is sized from its free memory less a reserve of a 32nd of the card, at least 1 GiB; a unified
GPU's from available memory less a tenth, at least 4 GiB (Halo applies that one to the Mac too: Metal's own reserve is
not stated); NVFP4 checkpoints on cards without thread-block clusters (sm_80 to sm_89: RTX 30 / 40, A100, L40) run a
fallback path; models qualified on two machines are not served by one; Gemma 4 refuses M1-M4 Macs.

    host_for(name, card, *, os_name="") -> host      fit(row, host, window=None) -> {level, line, numbers, runtime}
    here_line(row, window=None) -> "fit here: ..."   badge(row, card, window, *, host_name="") -> the Library's fit
    level: fits | tight | no | unknown. Reads only: nothing loads, nothing is measured here.
"""

from __future__ import annotations

import re
from typing import Optional

GIB = 2 ** 30
DEFAULT_WINDOW = 32768


def _sm(name: str) -> Optional[int]:
    n = str(name or "").upper()
    if re.search(r"RTX\s*50\d\d|B\d00|GB10|RTX PRO 6000", n):
        return 120
    if re.search(r"H100|H200|GH200", n):
        return 90
    if re.search(r"RTX\s*40\d\d|\bL4\b|L40|ADA", n):
        return 89
    if re.search(r"RTX\s*30\d\d|A10\b|A40|A6000", n):
        return 86
    return 80 if re.search(r"A100|A30\b", n) else None


def host_for(name: str, card: Optional[dict], *, os_name: str = "") -> dict:
    from halo_harness.ollama_steward.fit import card_budget
    gpus = [g for g in (card or {}).get("gpus") or [] if isinstance(g, dict)]
    libs = {str(g.get("library") or "").lower() for g in gpus}
    unified = bool((card or {}).get("unified")) or "metal" in libs
    gpu = gpus[0].get("name") if gpus else None
    b = card_budget(card) if card else {"budget": 0}
    return {"name": name, "gpu": gpu, "gpus": len(gpus), "unified": unified, "nvidia": "cuda" in libs,
            "vram": max((int(g.get("total_bytes") or 0) for g in gpus), default=0),
            "ram": int((card or {}).get("ram_bytes") or 0), "budget": int(b.get("budget") or 0),
            "os": os_name or ("macos" if unified else ""), "sm": _sm(gpu) if "cuda" in libs else None, "read": bool(card)}


def _g(nbytes) -> str:
    v = nbytes / GIB
    return f"{v:.0f} GB" if v >= 10 else f"{v:.1f} GB"


def _card(host: dict) -> str:
    g = str(host.get("gpu") or "the GPU")
    for p in ("NVIDIA GeForce RTX ", "NVIDIA GeForce ", "NVIDIA "):
        if g.startswith(p):
            return "the " + g[len(p):]
    return g if g.startswith(("the ", "a ", "an ")) else f"the {g}"


def _refused(row: dict, host: dict, where: str) -> Optional[str]:
    title = row["title"]
    backend = "metal" if host["unified"] else "cuda" if host["nvidia"] else ""
    if not backend:
        return (f"does not fit: TensorFold runs on Apple Silicon (Metal) and NVIDIA cards (CUDA); {where} has "
                f"{_card(host) if host['gpus'] else 'no GPU on its card'}")
    if backend not in row["backends"]:
        only = "CUDA" if backend == "metal" else "Metal (a Mac)"
        return f"does not fit: TensorFold qualifies {title} on {only} only ({row['scope']})"
    if row["machines"] > 1:
        return f"does not fit: TensorFold qualifies {title} across two machines ({row['scope']}), not on one"
    m = re.search(r"Apple M(\d)", str(host.get("gpu") or ""))
    if "M1-M4 refused" in row["scope"] and m and int(m.group(1)) < 5:
        return f"does not fit: TensorFold refuses {title} on an M1-M4 Mac ({row['scope']})"
    return None


def fit(row: Optional[dict], host: dict, window: Optional[int] = None) -> dict:
    base = {"level": "unknown", "numbers": None, "runtime": "tensorfold"}
    where = host.get("name") or "this machine"
    if row is None:
        return {**base, "line": f"on {where}: not a model TensorFold's table names (tensorfold info <repo> names its "
                                "memory floor once it is pulled)"}
    title = row["title"]
    if not host.get("read"):
        return {**base, "line": f"{title} on {where}: no hardware card read yet (the Hosts page or halo ollama hardware "
                                "reads it)"}
    no = _refused(row, host, where)
    if no:
        return {**base, "level": "no", "line": no}
    win = int(window or row.get("context") or DEFAULT_WINDOW)
    pull = f"; the download: {row['pull']} (yours to run)"
    if not row.get("size_bytes"):
        return {**base, "line": f"{title} on {where}: TensorFold publishes no size for it (tensorfold info "
                                f"{row['repo']} names the memory floor after the pull){pull}"}
    size, unified = row["size_bytes"], host["unified"]
    reserve = max(4 * GIB, host["ram"] // 10) if unified else max(GIB, host["vram"] // 32)
    room = host["budget"] - reserve
    left = room - size
    level = "fits" if left >= max(2 * GIB, size // 10) else "tight" if left > 0 else "no"
    mem = (f"{_g(host['budget'])} of unified memory for the GPU" if unified else
           f"{_card(host)}'s {_g(host['budget'])}")
    nums = {"size_gb": round(size / GIB, 1), "budget_gb": round(host["budget"] / GIB, 1),
            "reserve_gb": round(reserve / GIB, 1), "left_gb": round(left / GIB, 1), "window": win,
            "backend": "metal" if unified else "cuda"}
    slow = ""
    if row.get("nvfp4") and host.get("sm") and 80 <= host["sm"] <= 89:
        slow = f"; NVFP4 on {_card(host)} (sm_{host['sm']}, no thread-block clusters) runs TensorFold's fallback path: slower"
        nums["fallback"] = True
    if level == "no":
        return {**base, "level": "no", "numbers": nums, "line": f"does not fit: {title} ({row['size_words']}) needs "
                f"{_g(size + reserve)} with TensorFold's {_g(reserve)} reserve; {where} has {mem}"}
    word = "fits" if level == "fits" else "fits, tight"
    win_os = " (the Windows build is from source: docs/WINDOWS.md)" if host.get("os") == "windows" else ""
    line = (f"{word}: {title} ({row['size_words']}) on {where}: {mem}, less TensorFold's {_g(reserve)} reserve, leaves "
            f"{_g(left)} for the {win:,}-token window's KV and its streams (the startup line says how many; up to 8 "
            f"with --parallel auto){slow}{win_os}{pull}")
    return {**base, "level": level, "numbers": nums, "line": line}


def here_line(row: Optional[dict], window: Optional[int] = None) -> str:
    from halo_harness.providers.local_server_cmd import this_machine_card
    from halo_harness.tensorfold.requirements import os_word
    card, _name = this_machine_card()
    return "fit here: " + fit(row, host_for("this machine", card, os_name=os_word()), window=window)["line"]


def badge(row: dict, card: Optional[dict], window: int, *, host_name: str = "") -> dict:
    from halo_harness.tensorfold.catalog import get
    hit = get(str(row.get("id") or "").removeprefix("tensorfold:"))
    base = {"at_window": int(window or DEFAULT_WINDOW), "gpu_window": None, "estimate": True, "host": host_name or None,
            "shape_source": "TensorFold's table (tensorfold/catalog.py)", "runtime": "tensorfold"}
    if not card or hit is None:
        return {**base, "level": "unknown", "numbers": None,
                "why": f"no hardware card read for {host_name or 'this host'} yet (the Hosts page reads it)"}
    got = fit(hit, host_for(host_name or "this host", card), window=window)
    return {**base, "level": got["level"], "why": got["line"], "numbers": got["numbers"], "tensorfold": got}
