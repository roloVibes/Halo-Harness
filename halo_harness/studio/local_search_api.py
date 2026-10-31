"""halo_harness.studio.local_search_api -- Halo 3.3.6.0 R2: the search's routes beside Local -> Library's
(studio/models_library_api.dispatch_library sends `local/library/<these>` and `local/crashes` here). The same guard
as every Studio route; never a model call; nothing downloads until Download and verify is pressed.

    GET  local/library/presets                       the presets, each bundle expanded (models_library/presets.py)
    POST local/library/template {preset, model?, lineup?, bundle?}   Save as role template (the teams path)
    POST local/library/verify {host, name, role?}    Download and verify (studio/local_verify_job.py; `verify`,
                                                     `pull` and `probe` frames)
    GET  local/library/verifies                      the verify jobs running and the last ended ones
    POST local/library/assign {role, ref, lineup?}   the role offer accepted: the lineup's role gets the model
    GET  local/crashes?host=                         the crash fingerprints (ollama_steward/fingerprints.py)

    spec_of(query) -> the search spec GET local/library reads (preset, for_role, ask, need, exclude_crashed, edited
                      -- the page's bundle replaces the preset's -- and the fit and supply filters by name)
"""

from __future__ import annotations

FIT_KEYS = {"fits_at": bool, "fully_on_gpu": bool, "quant_max": str, "params_max": float, "disk_max_gb": float,
            "speed_min": float, "cold_load_max_s": float, "kv_efficiency": float}
SUPPLY_KEYS = {"licence": str, "gated": bool, "kind": str, "runs_here": bool, "ollama_supports": bool,
               "fresh_within_months": float}
TRUE = ("1", "true", "yes", "on")


def _val(kind, raw):
    s = str(raw).strip()
    if kind is bool:
        return s.lower() in TRUE if s.lower() in TRUE + ("0", "false", "no", "off") else None
    if kind is float:
        try:
            return float(s.replace(",", ""))
        except ValueError:
            return None
    return s or None


def spec_of(query: dict) -> dict:
    q = {k: v for k, v in (query or {}).items() if v not in (None, "")}
    spec: dict = {}
    for k, key in (("preset", "preset"), ("for_role", "for_role"), ("ask", "sentence"), ("role", "role")):
        if q.get(k):
            spec[key] = str(q[k]).strip()
    if q.get("need"):
        from halo_harness.models_library.search import norm_needs
        spec["needs"] = norm_needs(str(q["need"]))
    if str(q.get("exclude_crashed") or "").lower() in TRUE:
        spec["exclude_crashed"] = True
    if str(q.get("edited") or "").lower() in TRUE:  # the page's bundle, edited: it replaces the preset's
        spec["replace"] = True
        spec.setdefault("needs", {})
    fit = {k: v for k, kind in FIT_KEYS.items() if k in q and (v := _val(kind, q[k])) is not None}
    if "co_resides_with" in q:
        fit["co_resides_with"] = [x for x in str(q["co_resides_with"]).split(",") if x.strip()]
    supply = {("source" if k == "kind" else k): v for k, kind in SUPPLY_KEYS.items() if k in q
              and (v := _val(kind, q[k])) is not None}
    if fit:
        spec["fit"] = fit
    if supply:
        spec["supply"] = supply
    return spec


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def post_template(req):
    from halo_harness.models_library.presets import save_template
    b = _body(req)
    preset = str(b.get("preset") or "").strip()
    over = b.get("bundle") if isinstance(b.get("bundle"), dict) else None
    ok, lines, name = save_template(preset, state_dir=req.state_dir, model=str(b.get("model") or "").strip(),
                                    lineup=str(b.get("lineup") or "").strip(), bundle_over=over)
    return (200 if ok else 422), {"ok": ok, "lineup": name, "lines": lines, "say": "; ".join(lines),
                                  "cli": f"halo models browse --preset {preset} --save-template"}


def post_verify(req):
    from halo_harness.studio import local_verify_job as J
    from halo_harness.studio.local_control_api import _pub, _refused, _target
    b = _body(req)
    name, host_name = str(b.get("name") or "").strip(), str(b.get("host") or "").strip()
    if not name or not host_name:
        return 422, {"error": "verify takes {host, name}", "problems": ["host: the Ollama host", "name: what to pull"]}
    host, ctl, here = _target(req, host_name)
    if ctl is None:
        return 404, {"error": f"no host named {host_name!r} here"}
    if not ctl.get("ok"):
        return _refused(ctl)
    if not here or host is None:
        return 409, {"error": f"{host_name} is served by {ctl.get('via') or 'a fleet member'}: Pull, then Probe on its "
                              "Models row (each runs on that member)"}
    role = str(b.get("role") or "").strip()
    return 200, {**J.start(host, name, _pub(req), state_dir=req.state_dir, role=role),
                 "cli": f"halo models pull {name} --host {host_name} && halo models probe {name} --host {host_name}"}


def post_assign(req):
    from halo_harness.models_library.presets_save import assign
    b = _body(req)
    role, ref = str(b.get("role") or "").strip(), str(b.get("ref") or "").strip()
    if not role or not ref:
        return 422, {"error": "assign takes {role, ref}", "problems": ["role: the lineup role", "ref: ol:<model>@<host>"]}
    ok, lines, name = assign(role, ref, state_dir=req.state_dir, lineup=str(b.get("lineup") or "").strip())
    return (200 if ok else 422), {"ok": ok, "lineup": name, "lines": lines, "say": "; ".join(lines)}


def get_crashes(req):
    from halo_harness.ollama_steward.fingerprints import read
    host = str(req.query.get("host") or "").strip()
    return 200, {"crashes": read(req.state_dir, host=host or None)}


def dispatch_search(req):
    """The answer for a route of this file, else None."""
    from halo_harness.models_library.presets import all_bundles
    from halo_harness.studio.local_verify_job import current
    gets = {"local/library/presets": lambda r: (200, {"presets": all_bundles()}),
            "local/library/verifies": lambda r: (200, current()), "local/crashes": get_crashes}
    posts = {"local/library/template": post_template, "local/library/verify": post_verify,
             "local/library/assign": post_assign}
    if req.path in gets:
        return gets[req.path](req) if req.method == "GET" else (405, {"error": "method not allowed"})
    if req.path in posts:
        return posts[req.path](req) if req.method == "POST" else (405, {"error": "method not allowed"})
    return None
