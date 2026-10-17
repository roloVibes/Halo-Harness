"""Studio: the two reads the Roles section's model picker adds (Halo 3.0.7.0
round R2).

`GET gym` -- the model gym's scores on this machine (`halo gym`'s result
files under ~/.halo/gym, read from disk, no model call): `{scores: {ref:
{score, tokens_per_second}}}` for every catalog ref the gym measured (the gym
runs local models, so only `ol:` and `hf:` refs are looked up).

`GET models/best-for` -- what each catalog model is good for, from
`capabilities.score` (the same ranking `halo models --best-for` prints):
`{ref: [kind, ...]}`, the kinds it scores above 0 for, best first.
"""
from __future__ import annotations

from .api import Request


def get_gym(req: Request):
    from halo_harness.gym import find_results_for_model, iter_results, overall_score
    from . import model as M
    results = iter_results(req.state_dir)
    out: dict = {}
    if results:
        for row in M.model_rows(req.state_dir):
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
    from halo_harness.capabilities import KINDS, score
    from . import model as M
    out: dict = {}
    for row in M.model_rows(req.state_dir):
        ranked = []
        for kind in KINDS:
            try:
                s, _reason = score(row, kind)
            except Exception:
                continue
            if s > 0:
                ranked.append((s, kind))
        if ranked:
            out[row["ref"]] = [k for _s, k in sorted(ranked, key=lambda t: (-t[0], t[1]))]
    return 200, out


ROUTES: list = [
    ("GET", r"^gym$", get_gym),
    ("GET", r"^models/best-for$", get_best_for),
]
