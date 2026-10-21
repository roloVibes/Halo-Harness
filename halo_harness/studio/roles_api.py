"""Studio: the reads the Roles section's model picker adds (Halo 3.0.7.0
round R2; 3.1.9.0 R1 "what each model is good at").

`GET gym` -- the model gym's scores on this machine (`halo gym`'s result
files under ~/.halo/gym, read from disk, no model call): `{scores: {ref:
{score, tokens_per_second}}}` for every catalog ref the gym measured (the gym
runs local models, so only `ol:` and `hf:` refs are looked up).

`GET models/best-for` -- what each catalog model is best at: `{ref: [kind,
...]}`, strongest first, the kinds of its `best_at` (models_best_at: the
same answer `halo models analyze` prints; a yes/no capability counts at any
score, a ranked strength past its floor).

`POST models/analyze` -- rebuild the best-at cache from the catalog now (what
`halo models analyze` does): `{rows, kinds: {kind: count}, best: {kind:
{cheapest, strongest}}, built}`.
"""
from __future__ import annotations

from .api import Request


def get_gym(req: Request):
    from halo_harness.gym import find_results_for_model, iter_results, overall_score
    from . import model as M
    results = iter_results(req.state_dir)
    out: dict = {}
    if results:
        for row in M.model_rows(req.state_dir, getattr(req, "cwd", None)):
            ref = str(row.get("ref") or "")
            if not ref.startswith(("ol:", "hf:")):
                continue
            found = find_results_for_model(req.state_dir, ref, results=results)
            score = overall_score(found[0]) if found else None
            if score is not None:
                tps = found[0].get("tokens_per_second")
                out[ref] = {"score": round(score, 3), "tokens_per_second": tps if isinstance(tps, (int, float)) else None}
    return 200, {"scores": out}


def get_best_for(req: Request):
    from . import model as M
    out: dict = {}
    for row in M.model_rows(req.state_dir, getattr(req, "cwd", None)):
        kinds = (row.get("best_at") or {}).get("kinds") or []
        if kinds:
            out[row["ref"]] = list(kinds)
    return 200, out


def post_models_analyze(req: Request):
    from halo_harness.capabilities import KINDS
    from halo_harness.models_best_at import rebuild
    from . import model as M
    cache = rebuild(req.state_dir, M.catalog_rows(req.state_dir, getattr(req, "cwd", None)))
    rows = cache.get("rows") or {}
    kinds = {kind: sum(1 for e in rows.values() if kind in (e.get("kinds") or [])) for kind in KINDS}
    return 200, {"rows": len(rows), "kinds": {k: n for k, n in kinds.items() if n}, "best": cache.get("best") or {},
                 "built": cache.get("built")}


ROUTES: list = [
    ("GET", r"^gym$", get_gym),
    ("GET", r"^models/best-for$", get_best_for),
    ("POST", r"^models/analyze$", post_models_analyze),
]
