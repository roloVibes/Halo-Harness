"""halo_harness.freetoken.link -- the host link's bandwidth, the number FreeToken's MoE speed rides on (Halo 3.3.9.1;
docs/MODELS-freetoken.md "The fit"), measured with `ft bench bw` through the bench seam.

`ft bench bw [--model <checkpoint>]` measures host RAM against PCIe with FreeToken's real cpu / offload MoE kernels and
prints, per MoE layer kind, the CPU-MoE and the PCIe-gather GB/s, and the ceilings line "ceilings: CPU STREAM read X |
PCIe linear H2D Y  D2H Z  GB/s"; it writes its own profile under ~/.cache/freetoken/benchbw/ (moe/benchbw.py and
docs/cli.md: from the source, unverified against a live run). Halo reads its printed lines, never that file.

    estimate(model=None) -> {seconds, line}   the cost line first: "local: ~N s on this machine (the GPU and the CPU
        are busy for it), writes FreeToken's bandwidth profile and Halo's link.json; no tokens, no network"
    run(*, model=None, state_dir=None, binary=None) -> {ok, gather_gbs, h2d_gbs, cpu_gbs, rows, line, say}
        SEAMS["run"](argv) -> (rc, text) is the tests' runner; the real one runs the command with a time limit
    parse(text) -> {gather_gbs, h2d_gbs, d2h_gbs, cpu_gbs, rows [{format, cpu_gbs, gather_gbs, backend}]}
    measured(state_dir=None) -> {gbs, from, at} | None   the newest saved run (<state>/freetoken/link.json)
    link_words(state_dir=None) -> (gbs | None, "PCIe at 28 GB/s measured" | "PCIe at 32-64 GB/s extrapolated (...)")

The fit uses the PCIe-gather figure (what an expert miss really costs), else the linear H2D ceiling.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

SEAMS: dict = {}
RUN_S = 120  # the bench's own run is about a minute (an assumption until a live run times it)
LIMIT_S = 900
EXTRAPOLATED = (32.0, 64.0)  # docs/models.md: "PCIe's ~32-64 GB/s" (from the source, unverified against a live run)
COST = ("local: ~{s} s on this machine (the GPU and the CPU are busy for it), writes FreeToken's bandwidth profile "
        "and Halo's link.json; no tokens, no network")
_CEIL = re.compile(r"ceilings: CPU STREAM read ([\d.]+)\s*\|\s*PCIe linear H2D ([\d.]+)\s+D2H ([\d.]+)")
_ROW = re.compile(r"^\s{2,}(\S+)\s+([\d.]+) MB\s+(?:([\d.]+) GB/s|n/a)\s+(?:([\d.]+) GB/s|n/a)\s+\S+\s+(\S+)\s*$")


def _file(state_dir=None) -> Path:
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    return Path(state_dir) / "freetoken" / "link.json"


def estimate(model: Optional[str] = None) -> dict:
    s = RUN_S * (2 if model else 1)
    return {"seconds": s, "line": COST.format(s=s)}


def parse(text: str) -> dict:
    out = {"gather_gbs": None, "h2d_gbs": None, "d2h_gbs": None, "cpu_gbs": None, "rows": []}
    for line in str(text or "").splitlines():
        if m := _CEIL.search(line):
            out.update(cpu_gbs=float(m.group(1)), h2d_gbs=float(m.group(2)), d2h_gbs=float(m.group(3)))
        elif m := _ROW.match(line):
            out["rows"].append({"format": m.group(1), "cpu_gbs": float(m.group(3)) if m.group(3) else None,
                                "gather_gbs": float(m.group(4)) if m.group(4) else None, "backend": m.group(5)})
    gathers = [r["gather_gbs"] for r in out["rows"] if r["gather_gbs"]]
    out["gather_gbs"] = round(min(gathers), 1) if gathers else None
    return out


def _run(argv: list) -> "tuple[int, str]":
    if "run" in SEAMS:
        return SEAMS["run"](list(argv))
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=LIMIT_S)
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run(*, model: Optional[str] = None, state_dir=None, binary: Optional[list] = None) -> dict:
    if binary is None:
        from halo_harness.freetoken.requirements import binary as find
        binary, _src = find()
    if not binary:
        from halo_harness.freetoken import INSTALL_LINE
        return {"ok": False, "say": f"ft is not on PATH: {INSTALL_LINE}"}
    argv = list(binary) + ["bench", "bw"] + (["--model", str(model)] if model else [])
    t0 = time.time()
    rc, text = _run(argv)
    got = parse(text)
    gbs = got["gather_gbs"] or got["h2d_gbs"]
    if rc != 0 or gbs is None:
        tail = [x for x in str(text or "").splitlines() if x.strip()][-1:] or ["no output"]
        return {"ok": False, "argv": argv, "say": f"ft bench bw did not measure the link (exit {rc}): {tail[0][:160]}"}
    row = {**got, "gbs": gbs, "from": "PCIe-gather" if got["gather_gbs"] else "PCIe linear H2D", "at": time.time(),
           "took_s": round(time.time() - t0, 1), "model": model, "argv": argv}
    p = _file(state_dir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(row, indent=2), encoding="utf-8")
    except OSError:
        pass
    line = (f"the link: PCIe-gather {got['gather_gbs']} GB/s" if got["gather_gbs"] else f"the link: {gbs} GB/s") + (
        f" (linear H2D {got['h2d_gbs']}, CPU STREAM read {got['cpu_gbs']} GB/s)" if got["h2d_gbs"] else "")
    return {"ok": True, **row, "line": line, "say": line}


def measured(state_dir=None) -> Optional[dict]:
    try:
        got = json.loads(_file(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) and isinstance(got.get("gbs"), (int, float)) else None


def link_words(state_dir=None, *, gbs: Optional[float] = None) -> "tuple[Optional[float], str]":
    if gbs is None:
        m = measured(state_dir)
        gbs = float(m["gbs"]) if m else None
    if gbs is not None:
        return gbs, f"PCIe at {gbs:g} GB/s measured"
    lo, hi = EXTRAPOLATED
    return None, f"PCIe at {lo:g}-{hi:g} GB/s extrapolated (FreeToken's figure; halo local bench --host freetoken --bw measures it)"
