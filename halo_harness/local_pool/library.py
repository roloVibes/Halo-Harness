"""halo_harness.local_pool.library -- the Library's "Pool" preset (Halo 3.3.8.0 R1; docs/STUDIO-local.md "Library").

    mark(answer, state_dir) -> answer   when the search's preset is `pool`: the rows are the pool catalog's models as
        Hugging Face GGUF rows (models_library/row_builders.hf_file_row: their card, their fit on the host picked),
        each with `pool` {state, badge, verdict, preview, lines, tags, speed_word, rank} -- the badge "pool: fits (2
        nodes, 32k Q8_0)" / "pool: 1 node holds it" / "pool: no"; ranked as `halo pool recommend --batch` ranks them
        (what fits the pool, then one node, then what does not fit). Their Download is the hub row's existing one (the
        licence card first, then the download + verify job); there is no Pull to an Ollama host on a pool row.
    pool_row(model, v, host_card, window, host_name) -> the library row

A pool catalog row is a library row with pool facts; any other preset leaves the answer as it was.
"""

from __future__ import annotations

GIB = 2 ** 30
PRESET = "pool"


def pool_row(model: dict, v: dict, host_card, window: int, host_name: str) -> dict:
    from halo_harness.models_library.browse import _view
    from halo_harness.models_library.row_builders import hf_file_row
    quant = model.get("file") or ("MXFP4" if "gpt-oss" in model["name"] else "")
    repo = {"id": model["repo"], "kind": "gguf", "params_total": int(float(model["total_b"]) * 1e9)}
    f = {"file": model.get("file") or "", "quant": quant, "size": int(float(model["weights_gb"]) * GIB)}
    row = hf_file_row(repo, f)
    row.update(name=model["display"], key=f"pool/{model['name']}", estimate=False,
               pull_line=" ".join(w for w in ("halo local download", model["repo"], model.get("file") or "") if w),
               description=model.get("single_node") or "")
    row["sources"] = {**row.get("sources", {}), "size_bytes": f"the pool catalog's {model['weights_gb']:g} GB, counted as the host "
                      "cards count (2^30 bytes a GB): this column's decimal GB read higher",
                      "params": f"the pool catalog: {model['total_b']:g}B total, {model['active_b']:g}B active"}
    view = _view(row, host_card, window, host_name)
    view.update(pull_target="", installed=[],
                pool={"state": v["state"], "badge": v["badge"], "verdict": v["verdict"], "preview": v["preview"],
                      "lines": v["lines"], "tags": v["tags"], "speed_word": v["speed_word"], "rank": v.get("rank"),
                      "model": model["name"], "download": v.get("download")})
    return view


def mark(answer: dict, state_dir=None) -> dict:
    if ((answer.get("search") or {}).get("preset") or "") != PRESET:
        return answer
    from halo_harness.local_pool import catalog as C
    from halo_harness.local_pool.budget import budgets
    from halo_harness.local_pool.recommend import recommend
    from halo_harness.models_library.browse import _host, _host_card
    name = ((answer.get("host") or {}).get("name")) or ""
    h, _hosts = _host(name)
    hc = _host_card(h)
    rec = recommend(budgets(state_dir=state_dir), allow_batch=True, state_dir=state_dir)
    window = int(answer.get("window") or 32768)
    rows = [pool_row(C.CATALOG[v["model"]], v, hc, window, name) for v in rec["rows"] + rec["others"]]
    try:
        from halo_harness.studio.local_hf_view import mark_on_disk
        mark_on_disk(rows)
    except Exception:
        pass
    answer.update(rows=rows, total=len(rows), page=1, pages=1, pool={"head": rec["head"], "nodes": rec["nodes"],
                                                                    "free_gb": rec["free_gb"]})
    return answer
