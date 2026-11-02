"""halo_harness.local_pool.recommend -- what to run on the pool (Halo 3.3.8.0 R1; docs/POOL.md "The recommendation";
plans/pooled-inference-model-candidates.md's decision rules).

    recommend(rows, *, allow_batch=False, catalog=None, state_dir=None) -> {rows, others, hidden, head, nodes, free_gb,
        allow_batch}
        rows: what fits the pool, the lowest active parameters first (a mixture of experts with few active ones is the
        pooled choice), then the single-node rows (one node holds it: run it there -- ranked last), each with `rank`;
        others: what does not fit, with its line; hidden: the batch-only models left out (`allow_batch` shows them,
        always tagged batch-only)
    verdict(name, rows, *, state_dir=None) -> one model's fit + its preview, or None for a name not in the catalog
    preview(v, model, rate) -> the honest preview before any download, e.g. "needs 53.6 GB -- 64.0 GB free across 2
        nodes; 32k Q8_0; one 2 GB routing table per node; download 46 GB, ~16 min at the assumed 50 MB/s -- nothing
        downloads until you press it"
    rate(state_dir) -> (bytes per second, where it came from): the last pull or download that ended well, else assumed

The download is the existing Hugging Face download + verify job (`repo`, `file`), offered as one button. 3.3.8.0 R4:
`speed_word` / `speed` are local_pool/speed.figures -- the pool's own measured tok/s and the penalty against the single
node that could hold the model once `halo local bench --host pool` wrote its card, "extrapolated" until then. 3.3.8.0 R3: a model
resident on a member counts as room (Warm pivots it out first; local_pool/preflight._room), said in the head.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.local_pool import catalog as C
from halo_harness.local_pool.fit import fit, k

ASSUMED_BPS = 50e6
GIB = 2 ** 30


def rate(state_dir=None) -> "tuple[float, str]":
    try:
        from halo_harness.studio import local_pull_job as J
        jobs = list(J.current()["jobs"]) + (J.read_file(state_dir) if state_dir is not None else [])
    except Exception:
        jobs = []
    from halo_harness.newest_first import newest_first
    done = newest_first((j for j in jobs if j.get("ok") and isinstance(j.get("speed"), (int, float)) and j["speed"] > 0),
                        lambda j: float(j.get("started") or 0))
    if done:
        s = float(done[0]["speed"])
        return s, f"your last measured {s / 1e6:.0f} MB/s ({done[0].get('kind') or 'pull'} of {done[0].get('name')})"
    return ASSUMED_BPS, f"the assumed {ASSUMED_BPS / 1e6:.0f} MB/s (no download measured yet)"


def _eta(seconds: float) -> str:
    return f"{seconds:.0f} s" if seconds < 90 else f"{seconds / 60:.0f} min" if seconds < 5400 else f"{seconds / 3600:.1f} h"


def _download(model: dict, r: "tuple[float, str]") -> dict:
    size = float(model["weights_gb"])
    secs = size * GIB / r[0]
    cli = " ".join(w for w in ("halo local download", model["repo"], model.get("file") or "") if w)
    return {"repo": model["repo"], "file": model.get("file") or "", "gb": size, "eta_s": round(secs), "eta": _eta(secs),
            "eta_from": r[1], "cli": cli}


def preview(v: dict, model: dict, r: "tuple[float, str]") -> str:
    d = _download(model, r)
    tail = f"download {d['gb']:g} GB, ~{d['eta']} at {d['eta_from']} -- nothing downloads until you press it"
    R = float(model["routing_table_gb"])
    if v["state"] == "pool":
        return (f"needs {v['need_gb']:.1f} GB -- {v['free_gb']:.1f} GB free across {v['nodes']} nodes; "
                f"{k(v['max_ctx_q8'])} Q8_0" + (f"; one {R:g} GB routing table per node" if R else "") + f"; {tail}")
    if v["state"] == "single":
        return (f"needs {v['need_gb']:.1f} GB -- {v['node']} has {v['free_gb']:.1f} GB free; {k(v['max_ctx_f16'])} F16 "
                f"there, no pool; {tail}")
    return f"needs {v['need_gb']:.1f} GB -- {v['free_gb']:.1f} GB free; does not fit, so nothing to download"


def _row(v: dict, model: dict, r, state_dir=None) -> dict:
    from halo_harness.local_pool.launch import run
    from halo_harness.local_pool.speed import figures  # 3.3.8.0 R4: the pool's own card, else extrapolated
    tags = (["batch-only"] if model.get("batch_only") else []) + ([f"b{model['min_build']}+"] if model.get("min_build")
                                                                    else [])
    f = figures(model, state_dir, run(state_dir))
    return {**v, "repo": model["repo"], "tags": tags, "preview": preview(v, model, r),
            "download": _download(model, r) if v["state"] != "no" else None, "speed_word": f["word"],
            "speed": {k: f[k] for k in ("measured", "tok_s", "ttft_ms", "cold_load_s", "at", "stale", "penalty_pct",
                                        "penalty_from", "vs", "extrapolated")}}


def recommend(rows: list, *, allow_batch: bool = False, catalog: Optional[dict] = None, state_dir=None) -> dict:
    from halo_harness.local_pool.preflight import _room  # 3.3.8.0 R3: a resident Ollama model is room Warm pivots out
    cat = C.CATALOG if catalog is None else catalog
    held = sum(float(x.get("resident_gb") or 0) for x in rows if x.get("resident"))
    rows = [_room(x) for x in rows]
    r = rate(state_dir)
    pooled, single, others, hidden = [], [], [], []
    for name, model in cat.items():
        v = _row(fit(model, rows), model, r, state_dir)
        if model.get("batch_only") and not allow_batch:
            hidden.append({"model": name, "line": f"{model['display']}: batch-only, left out (--batch shows it): "
                                                  f"{v['verdict']}"})
            continue
        (pooled if v["state"] == "pool" else single if v["state"] == "single" else others).append(v)
    key = lambda v: (float(v.get("active_b") or 0), float(v.get("weights_gb") or 0), v["model"])  # noqa: E731
    ranked = sorted(pooled, key=key) + sorted(single, key=key)
    for i, v in enumerate(ranked, start=1):
        v["rank"] = i
    for v in others:
        v["rank"] = None
    counted = [x for x in rows if isinstance(x.get("free_gb"), (int, float)) and x["free_gb"] > 0]
    free = round(sum(x["free_gb"] for x in counted), 1)
    def n(x: list, one: str, many: str) -> str:
        return f"{len(x)} {one if len(x) == 1 else many}"
    head = (f"{len(counted)} of {len(rows)} members with their VRAM read, {free:.1f} GB free; "
            f"{n(pooled, 'fits', 'fit')} the pool, {n(single, 'fits', 'fit')} one node, "
            f"{n(others, 'does', 'do')} not fit" + (f", {len(hidden)} batch-only left out" if hidden else "")
            + (f"; {held:.1f} GB of resident models counted as room (Warm pivots them out first)" if held else ""))
    return {"rows": ranked, "others": others, "hidden": hidden, "head": head, "nodes": len(counted), "free_gb": free,
            "allow_batch": allow_batch}


def verdict(name: str, rows: list, *, state_dir=None) -> Optional[dict]:
    from halo_harness.local_pool.preflight import _room
    model = C.get(name)
    if model is None:
        return None
    return _row(fit(model, [_room(x) for x in rows]), model, rate(state_dir), state_dir)
