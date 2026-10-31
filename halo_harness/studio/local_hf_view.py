"""halo_harness.studio.local_hf_view -- Halo 3.3.5.0 R5: what Local -> Hugging Face lists (`GET local/hf/dirs`,
`halo local ls`): each `huggingface.model_dirs` folder and the models on disk in it, read from the files (never a
server, never a model call).

    dirs(state_dir, *, host="", window=None) -> {dirs: [{path, exists, size, models: [model], partial: [part]}],
        host, hosts, window, servers: [the servers Halo started]}
    model {key (its path), path, dir, repo, file, model (the id it is served under), kind gguf | mlx | safetensors,
           size, parts, hub (the hub cache's layout), card, fit (at the window, on the host picked), fits {host:
           {level, why}}, served [{id, port, url, ready, alive, kind}], ref (`hf:local/<model>` while served), cli
           {serve, rm}, sources {field: where it came from}}
    part  {repo, bytes, files}: a download stopped part-way (`.part` files in the repo's blobs/; Download resumes)

A GGUF quant split in shards is one model (its first shard is what llama-server loads; the sizes summed). The host
picked is `host`, else this machine's (the first host it serves with a hardware card), else the first with a card;
the window is `window`, else that host's max_ctx, else 32,768. The card and the fit are the Library's
(models_library/rows.py) with the shape read from the file's own header. `reset()` drops the short cache (a
download that lands, a delete).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

TTL_S = 20.0
_LOCK = threading.Lock()
_CACHE: dict = {}


def _sig(root: Path) -> tuple:
    """The folder's shape cheaply: its own mtime and its repos' snapshot and blob folders' (a download or a delete
    from another process moves one of them)."""
    out = []
    for p in [root, *root.glob("models--*"), *root.glob("models--*/snapshots/*"), *root.glob("models--*/blobs")]:
        try:
            out.append(p.stat().st_mtime_ns)
        except OSError:
            pass
    return tuple(out)


def reset() -> None:
    with _LOCK:
        _CACHE.clear()


def hub_of(path: Path, root: Path) -> "tuple[str, str, str]":
    """(repo, file within the snapshot, commit) for a path in a `models--<org>--<name>/snapshots/<commit>/` tree."""
    from halo_harness.providers.huggingface_hub_cache import _repo_id_from_dirname
    try:
        parts = Path(path).relative_to(root).parts
    except ValueError:
        return "", "", ""
    for i, p in enumerate(parts[:-2]):
        if p.startswith("models--") and parts[i + 1] == "snapshots":
            return _repo_id_from_dirname(p), "/".join(parts[i + 3:]), parts[i + 2]
    return "", "", ""


def _partials(root: Path) -> list:
    out = []
    for repo_dir in sorted(root.glob("models--*")):
        parts = [p for p in (repo_dir / "blobs").glob("*.part") if p.is_file()]
        if parts:
            from halo_harness.providers.huggingface_hub_cache import _repo_id_from_dirname
            out.append({"repo": _repo_id_from_dirname(repo_dir.name), "bytes": sum(p.stat().st_size for p in parts), "files": len(parts)})
    return out


def models_in(root: Path) -> list:
    from halo_harness.models_library.hf_hub import SHARD
    from halo_harness.providers.local_model_dirs import scan_model_dirs
    from halo_harness.providers.local_use import model_id_for_path
    groups: dict = {}
    for e in scan_model_dirs([root]):
        k = (str(e.path.parent), SHARD.sub(".gguf", e.path.name)) if e.format == "gguf" else (str(e.path), "")
        g = groups.setdefault(k, {"paths": [], "size": 0, "kind": e.format})
        g["paths"].append(e.path)
        g["size"] += e.size_bytes
    out = []
    for g in groups.values():
        path = sorted(g["paths"])[0]
        repo, file, commit = hub_of(path, root)
        out.append({"path": path, "dir": str(root), "kind": g["kind"], "size": g["size"], "parts": len(g["paths"]),
                    "repo": repo, "file": file if g["kind"] == "gguf" else "", "commit": commit, "hub": bool(repo),
                    "model": model_id_for_path(path, g["kind"])})
    return sorted(out, key=lambda r: (r["repo"] or "~", str(r["path"])))


def _cards(want: str, here: str):
    """[(host, its card or None)]: the host wanted (else this machine's) read through the panel's 60 s cache, the
    others as that cache has them (no request for a host nobody picked)."""
    from halo_harness.ollama_steward.fit import card_budget
    from halo_harness.providers.fit_meter import host_card_of
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.providers.ollama_guard import skip_default
    from halo_harness.studio.ollama_hosts_view import card_of
    hosts = [h for h in resolve_ollama_hosts() if not skip_default(h)]
    pick = next((h for h in hosts if want and h.name.lower() == want.lower()), None) or next((h for h in hosts if h.name == here), None)
    out = []
    for h in hosts:
        c = card_of(h) if pick is None or h is pick else host_card_of(h)
        out.append((h, c if c and card_budget(c)["budget"] > 0 else None))
    return out


def _row(raw: dict, picked, cards, window: int, served: list) -> dict:
    from halo_harness.models_library.browse import _view
    from halo_harness.models_library.hf_hub import quant_of_file
    from halo_harness.models_library.row_builders import hf_file_row
    from halo_harness.models_library.rows import fit_for_row
    from halo_harness.providers.local_fit import read_fit_inputs_for_path, trained_context_from_model_info
    info, quant, weights = read_fit_inputs_for_path(raw["path"], fmt=raw["kind"])
    if raw["kind"] == "gguf" and raw["parts"] > 1:
        weights = raw["size"]
    trained = trained_context_from_model_info(info)
    name = raw["file"] or Path(raw["path"]).name
    repo = {"id": raw["repo"] or raw["model"], "kind": "mlx" if raw["kind"] == "mlx" else "gguf", "context": trained,
            "arch": (info or {}).get("general.architecture") or "", "tags": [], "pipeline_tag": ""}
    lib = hf_file_row(repo, {"file": name, "size": weights or raw["size"], "parts": raw["parts"],
                             "quant": quant or quant_of_file(name)}, shape=info or None)
    lib["sources"] = {**lib["sources"], "size_bytes": f"the file{'s' if raw['parts'] > 1 else ''} on disk ({raw['parts']})",
                      "context": "the file's header (context_length)" if trained else "unknown",
                      "quant": "the file's header (file_type)" if quant else lib["sources"].get("quant", "unknown")}
    h, hc = picked if picked else (None, None)
    v = _view(lib, hc, window, h.name if h else "")
    fits = {}
    for host, card in cards:
        if card is not None and (h is None or host.name != h.name):
            f = fit_for_row(lib, card, window, host_name=host.name)
            fits[host.name] = {"level": f["level"], "why": f["why"]}
    if h is not None:
        fits[h.name] = {"level": v["fit"]["level"], "why": v["fit"]["why"]}
    mine = [s for s in served if Path(str(s.get("model_path") or "")).resolve() == Path(raw["path"]).resolve()]
    on = [{k: s.get(k) for k in ("id", "port", "ready", "alive", "kind")} | {"url": f"http://127.0.0.1:{s.get('port')}"} for s in mine]
    live = any(s["alive"] for s in on)
    return {"key": str(raw["path"]), "path": str(raw["path"]), "dir": raw["dir"], "repo": raw["repo"], "file": raw["file"],
            "model": raw["model"], "kind": raw["kind"], "size": raw["size"], "parts": raw["parts"], "hub": raw["hub"],
            "quant": lib.get("quant") or "", "context": trained, "card": v["card"], "fit": v["fit"], "fits": fits,
            "served": on, "ref": f"hf:local/{raw['model']}" if live else None, "sources": lib["sources"],
            "cli": {"serve": f"halo local serve {raw['path']}", "rm": f"halo local rm {raw['path']}"}}


def dirs(state_dir, *, host: str = "", window: Optional[int] = None) -> dict:
    from halo_harness.models_library.rows import window_default
    from halo_harness.providers.local_model_dirs import resolve_model_dirs
    from halo_harness.providers.local_server import servers
    from halo_harness.providers.local_server_cmd import this_machine_card
    _card, here = this_machine_card()
    cards = _cards(host, here)
    picked = next((c for c in cards if host and c[0].name.lower() == host.lower()), None) or next(
        (c for c in cards if c[0].name == here), None) or next((c for c in cards if c[1] is not None), None)
    window = int(window) if isinstance(window, int) and window > 0 else window_default(picked[0] if picked else None)
    served = servers(state_dir)
    roots = resolve_model_dirs()
    ck = (tuple((str(r), _sig(r)) for r in roots), picked[0].name if picked else "", window, tuple((s["id"], s["alive"]) for s in served))
    with _LOCK:
        hit = _CACHE.get(ck)
    if hit and time.monotonic() - hit[0] < TTL_S:
        return hit[1]
    out = []
    for root in roots:
        ok = root.is_dir()
        rows = [_row(r, picked, cards, window, served) for r in models_in(root)] if ok else []
        out.append({"path": str(root), "exists": ok, "size": sum(r["size"] for r in rows), "models": rows,
                    "partial": _partials(root) if ok else []})
    answer = {"dirs": out, "window": window, "host": picked[0].name if picked else None,
              "hosts": [{"name": h.name, "card": c is not None, "here": h.name == here} for h, c in cards],
              "servers": [{k: s.get(k) for k in ("id", "model", "kind", "port", "ready", "alive", "keep", "model_path", "flags", "log")}
                          for s in served]}
    with _LOCK:
        _CACHE[ck] = (time.monotonic(), answer)
    return answer


def on_disk() -> dict:
    """{repo (lower case): [(file in the snapshot, lower case; "" for a folder), the model folder]} of the hub-layout
    downloads in every huggingface.model_dirs folder (the Library's "on disk in <folder>")."""
    from halo_harness.providers.local_model_dirs import resolve_model_dirs
    out: dict = {}
    for root in resolve_model_dirs():
        if root.is_dir():
            for r in models_in(root):
                if r["repo"]:
                    out.setdefault(r["repo"].lower(), []).append((r["file"].lower(), str(root)))
    return out


def mark_on_disk(rows: list) -> None:
    """Each hub row's `on_disk` [folders]: a file row when that file (or its quant's first shard) is there, a repo
    row when any of its files is."""
    from halo_harness.models_library.hf_hub import SHARD
    have = on_disk() if any(r.get("source") == "hf" for r in rows) else {}
    for row in rows:
        if row.get("source") != "hf":
            continue
        want = SHARD.sub(".gguf", str(row.get("tag_or_file") or "")).lower()
        got = have.get(str(row.get("id") or "").lower(), [])
        row["on_disk"] = sorted({d for f, d in got if not want or SHARD.sub(".gguf", f) == want})


__all__ = ["dirs", "hub_of", "mark_on_disk", "models_in", "on_disk", "reset"]
