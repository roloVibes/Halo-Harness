"""halo_harness.ollama_steward.tag_digests -- the digest each installed tag had when Halo last read its host's catalog
(Halo 3.3.7.0 R4; plans/local-model-fit-brief.md G14: "tags are mutable and disposable"). The drift and deletion rules
(rules_drift.py) read it; the speed card's readers (local_sched/swap_cost.py, so Auto's pick too) compare with it.

    observe(state_dir, host_name, rows, *, now=None) -> {changed: [{model, was, now, at}], gone: [{model, was}]}
        `<state>/ollama/digests.json` {"<host>|<model>": {digest, first, seen, was?, changed_at?}}: a new tag is
        stored, a changed digest keeps the old one as `was` with `changed_at`, a tag missing from a full catalog read is
        `gone` (and dropped). The fit store's window truth (the learned cap) with no digest gets this one: the first
        read stores it
    current(state_dir, host_name, model) -> digest | None         changed(state_dir, host_name, model) -> row | None
    stale_records(state_dir, host_name, model, digest, *, host_url=None) -> [{what, line, at}]
        what was measured on an older build of this tag: the battery profile, the speed card, the window truth, the
        crash fingerprints (written before `changed_at`)
WORD = "measured on an older build of this tag" -- the stale mark the speed card and the drift finding say.
No request: the rows are the caller's catalog read.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

FILE = "digests.json"
WORD = "measured on an older build of this tag"


def _path(state_dir) -> Path:
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir) / FILE


def _key(host_name: str, model: str) -> str:
    from halo_harness.ollama_steward.profiles import short_model
    return f"{str(host_name or '').lower()}|{short_model(model)}"


def read(state_dir) -> dict:
    try:
        got = json.loads(_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def observe(state_dir, host_name: str, rows: list, *, now: Optional[float] = None) -> dict:
    now = time.time() if now is None else now
    out: dict = {"changed": [], "gone": []}
    if state_dir is None or not rows:
        return out
    data, pre = read(state_dir), f"{str(host_name).lower()}|"
    present, dirty = set(), False
    for r in rows:
        name, digest = (r or {}).get("model") or (r or {}).get("name"), (r or {}).get("digest")
        if not name or not digest:
            continue
        k = _key(host_name, name)
        present.add(k)
        old = data.get(k) if isinstance(data.get(k), dict) else None
        if old is None:
            data[k], dirty = {"digest": digest, "first": now, "seen": now}, True
        elif old.get("digest") != digest:
            data[k], dirty = {"digest": digest, "first": now, "seen": now, "was": old.get("digest"), "changed_at": now}, True
            out["changed"].append({"model": k[len(pre):], "was": old.get("digest"), "now": digest, "at": now})
        elif now - float(old.get("seen") or 0) > 3600:
            old["seen"], dirty = now, True
    for k in [k for k in data if k.startswith(pre) and k not in present]:
        out["gone"].append({"model": k[len(pre):], "was": (data.pop(k) or {}).get("digest")})
        dirty = True
    if not dirty:
        return out
    try:
        p = _path(state_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=1), encoding="utf-8")
    except OSError:
        pass
    _stamp_window(state_dir, host_name, rows)
    return out


def _stamp_window(state_dir, host_name: str, rows: list) -> None:
    """The learned cap's entry with no digest gets the tag's current one (the first read stores it)."""
    try:
        from halo_harness.filelock import file_lock
        from halo_harness.providers import ollama_calibrate as C
        from halo_harness.providers.ollama import ollama_names_match, resolve_ollama_hosts
        url = next((h.url for h in resolve_ollama_hosts() if h.name.lower() == str(host_name).lower()), None)
        if not url:
            return
        with file_lock(C._fit_store_path(state_dir)):
            store = C.load_fit_store(state_dir)
            hit = False
            for e in store.get("entries") or []:
                if e.get("host_url") == url and not e.get("digest"):
                    row = next((r for r in rows if ollama_names_match(r.get("model") or r.get("name"), e.get("model"))), None)
                    if row and row.get("digest"):
                        e["digest"], hit = row["digest"], True
            if hit:
                C.save_fit_store(state_dir, store)
    except Exception:
        pass


def current(state_dir, host_name: str, model: str) -> Optional[str]:
    row = read(state_dir).get(_key(host_name, model)) if state_dir is not None else None
    return row.get("digest") if isinstance(row, dict) else None


def changed(state_dir, host_name: str, model: str) -> Optional[dict]:
    row = read(state_dir).get(_key(host_name, model)) if state_dir is not None else None
    return row if isinstance(row, dict) and row.get("changed_at") else None


def _day(t) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(t)) if isinstance(t, (int, float)) else "?"


def stale_records(state_dir, host_name: str, model: str, digest: Optional[str], *, host_url: Optional[str] = None) -> list:
    """Every record of this host and model measured on another digest than `digest` (or before the change)."""
    from halo_harness.providers.local_bench_runs import load
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.providers.ollama_capability import profile_for
    if not digest:
        return []
    ch = changed(state_dir, host_name, model) or {}
    since = float(ch.get("changed_at") or 0)
    out = []
    p = profile_for(state_dir, model, host_name) or {}
    if p.get("digest") and p["digest"] != digest:
        out.append({"what": "its battery profile", "at": p.get("probed_at"), "line": f"its battery profile ({_day(p.get('probed_at'))})"})
    sc = load(state_dir, host_name, model) or {}
    if sc.get("digest") and sc["digest"] != digest:
        out.append({"what": "its speed card", "at": sc.get("at"), "line": f"its speed card ({_day(sc.get('at'))})"})
    if host_url:
        from halo_harness.providers.ollama_calibrate import _find_entry, load_fit_store
        e = _find_entry(load_fit_store(state_dir)["entries"], host_url=host_url, model=model) or {}
        if e.get("digest") and e["digest"] != digest or (since and float(e.get("measured_at") or 0) and
                                                          float(e.get("measured_at") or 0) < since and not e.get("digest")):
            cap = e.get("max_full_gpu_ctx")
            out.append({"what": "its window truth", "at": e.get("measured_at"),
                        "line": "its window truth (the learned cap" + (f" {cap:,})" if isinstance(cap, int) else ")")})
    if since:
        from halo_harness.ollama_steward.fingerprints import _t, read as fps
        n = sum(1 for f in fps(state_dir, host=host_name) if not f.get("from") and ollama_names_match(f.get("model"), model)
                and 0 < _t(f.get("at")) < since)
        if n:
            out.append({"what": "its crash fingerprints", "at": None, "line": f"{n} crash fingerprint{'s' * (n != 1)}"})
    return out
