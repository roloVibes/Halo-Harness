"""halo_harness.models_library.shelf -- Halo 3.3.6.0 R4: the model shelf
(plans/local-model-fit-brief.md Part G8): what each installed model costs and
whether anything uses it, Retire (the existing delete, with a note left) and
Re-pull (the existing pull job).

    facts(state_dir, host, rows, *, now=None) -> {model: {last_used, size, picked, never_used, idle_days, hint}}
        last_used: the ledger's newest answered call of it on this host; picked: a role called it (a small /
        compaction / repair call in the ledger, or a role, lineup or the default naming it: studio/local_uses.py)
    hint(f) -> "not used in 30 days, 17 GB" | "never used, 17 GB" | ""
    retire(host, model, *, state_dir, why="", force=False, cwd=None) -> {ok, say, line?, uses, status}
        the uses card first (studio/local_uses.uses_of): a live session on it -> 409, a use and no force -> 422;
        then providers/ollama_control.delete, the twin record forgotten, and one line in <state>/ollama/shelf.jsonl
        {model, digest, size, host, retired_at, why, repull}
    shelf(state_dir, host=None) -> the retired models still off the host, newest first (a re-pull takes it off)
    repull_line(state_dir, host, model, row=None) -> "ollama pull <model>" | the twin's recipe

Nothing deletes without the button or the command; no request is sent but the delete itself.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

SHELF_FILE = "shelf.jsonl"
IDLE_DAYS = 30
ROLE_KINDS = ("small", "compaction", "repair")


def shelf_path(state_dir) -> Path:
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir) / SHELF_FILE


def _gb(n) -> str:
    return f"{n / 1e9:.1f} GB" if isinstance(n, (int, float)) and n else ""


def _named_by_config(model: str, host_name: str) -> bool:
    try:
        from halo_harness.studio.local_uses import uses_of
        u = uses_of(f"ol:{model}@{host_name}")
        return bool(u.get("lineups") or u.get("roles") or u.get("default_model") or u.get("compaction"))
    except Exception:
        return False


def facts(state_dir, host, rows: list, *, now: Optional[float] = None, config_uses: bool = True) -> dict:
    from halo_harness.ollama_steward.ledger import parse_at, read_calls
    from halo_harness.providers.ollama import ollama_names_match
    name, now = getattr(host, "name", host), now or time.time()
    calls = [x for x in read_calls(state_dir, host=name) if x.get("status") == 200] if state_dir is not None else []
    out = {}
    for r in rows or []:
        m = (r or {}).get("model") or (r or {}).get("name")
        if not m:
            continue
        mine = [x for x in calls if x.get("model") and ollama_names_match(x["model"], m)]
        last = max((parse_at(x.get("at")) or 0 for x in mine), default=0) or None
        picked = any(x.get("kind") in ROLE_KINDS for x in mine) or (config_uses and _named_by_config(m, name))
        f = {"last_used": last, "size": r.get("size"), "picked": picked, "never_used": not mine,
             "idle_days": int((now - last) // 86400) if last else None}
        f["hint"] = hint(f)
        out[m] = f
    return out


def hint(f: dict) -> str:
    size = _gb(f.get("size"))
    if f.get("never_used"):
        return "never used" + (f", {size}" if size else "")
    if isinstance(f.get("idle_days"), int) and f["idle_days"] >= IDLE_DAYS:
        return f"not used in {f['idle_days']} days" + (f", {size}" if size else "")
    return ""


def repull_line(state_dir, host, model: str, row: Optional[dict] = None) -> str:
    try:
        from halo_harness.providers.ollama_tune_store import lookup_twin_record
        tw = lookup_twin_record(state_dir, host_url=getattr(host, "url", ""), twin=model) if state_dir else None
    except Exception:
        tw = None
    if tw:
        return f"halo models twin {tw['origin']} --window {tw.get('window')} --host {getattr(host, 'name', host)}"
    return f"ollama pull {model}"


def _append(state_dir, line: dict) -> None:
    from halo_harness.filelock import file_lock
    path = shelf_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path, timeout=2.0):
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def read_lines(state_dir) -> list:
    out = []
    try:
        with open(shelf_path(state_dir), "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("model"):
                    out.append(row)
    except OSError:
        return []
    return out


def shelf(state_dir, host: Optional[str] = None) -> list:
    """The retired models, newest first, one per host and model; a `repulled` line takes one off."""
    seen, out = set(), []
    for row in reversed(read_lines(state_dir)):
        k = (row.get("host"), row.get("model"))
        if k in seen or (host and row.get("host") != host):
            continue
        seen.add(k)
        if not row.get("repulled_at"):
            out.append(row)
    return out


def retire(host, model: str, *, state_dir, why: str = "", force: bool = False, cwd=None, row=None) -> dict:
    from halo_harness.providers.ollama_control import delete
    from halo_harness.providers.ollama_tune_store import forget_twin
    from halo_harness.studio.local_uses import uses_of
    name = getattr(host, "name", "?")
    u = uses_of(f"ol:{model}@{name}", cwd=cwd, state_dir=state_dir)
    if u.get("live"):
        return {"ok": False, "status": 409, "uses": u, "say": u["line"] + ": retire it once they end or move"}
    if u.get("any") and not force:
        return {"ok": False, "status": 422, "uses": u, "say": u["line"]}
    repull = repull_line(state_dir, host, model, row)
    got = delete(host, model)
    if not got.get("ok"):
        return {**got, "status": 404 if got.get("missing") else 502, "uses": u}
    forget_twin(state_dir, host_url=host.url, twin=model)
    from halo_harness.ollama_steward.ledger import now_iso
    line = {"model": model, "digest": (row or {}).get("digest"), "size": (row or {}).get("size"), "host": name,
            "retired_at": now_iso(), "why": why or "retired by hand", "repull": repull}
    _append(state_dir, line)
    size = _gb(line["size"])
    return {"ok": True, "status": 200, "uses": u, "line": line,
            "say": f"retired {model} from {name}" + (f" ({size} freed)" if size else "") + f"; re-pull: {repull}"}


def mark_repulled(state_dir, host_name: str, model: str) -> None:
    from halo_harness.ollama_steward.ledger import now_iso
    _append(state_dir, {"model": model, "host": host_name, "repulled_at": now_iso()})
