"""halo_harness.ollama_steward.dead_tag -- one line for a tag that is gone (Halo 3.3.7.0 R4; plans/local-model-fit-
brief.md G14; the 2026-10-07 dead-model-id bug is the same class). Every place that names a model on a host -- a role,
a lineup lane, a `warm:` entry, a placement (`host_for`) -- speaks this one line: `halo doctor --local`, `halo teams
use`, `halo local warm`, the swap preview, the Roles page's Problems.

    check(ref, *, state_dir=None, catalog=None, card=None, window=None, role=None) -> Dead
    Dead = {dead, judged, known, model, host, near (ref | None), near_why, line, point}
        dead: the host's catalog answered and the tag is not in it; known: Halo has a record of it there (a profile, a
        speed card, a shelf line, a ledger call), so it "was deleted"; else it "is not on <host>"
    line(ref, **kw) -> "" | "`qwen3.8:27b` was deleted from pc -- nearest equivalent `qwen3.8:27b-gpu` (same family,
                            same quant, fits the same window): halo roles point coder ol:qwen3.8:27b-gpu@pc"
    point(role, to) -> {ok, line, from, to}    "point the role at it": `roles.<role>` in config.json, Halo-side only
The nearest equivalent is models_library/nearest.py's (family, size, quant, the window, the profile); with nothing like
it the closest spelling (doctor_local_ids.nearest) is named as such. No request but the cached catalog read.
"""

from __future__ import annotations

from typing import Optional


def _split(ref) -> "tuple[str, Optional[str]]":
    s = str(ref or "").strip()
    s = s[3:] if s.startswith("ol:") else s
    model, _, host = s.partition("@")
    return model.strip(), (host.strip() or None)


def _host(name: Optional[str]):
    try:
        from halo_harness.providers.ollama import resolve_ollama_host, resolve_ollama_hosts
        if name:
            return next((h for h in resolve_ollama_hosts() if h.name.lower() == name.lower()), None)
        return resolve_ollama_host(None)
    except Exception:
        return None


def _library_row(model: str) -> Optional[dict]:
    """What the packaged library snapshot says the tag was (family, parameters, quant, size), else None."""
    try:
        from halo_harness.models_library.snapshot import manifest_of
        base, _, tag = model.partition(":")
        m = manifest_of(base, tag or "latest")
    except Exception:
        m = None
    if not m:
        return None
    return {"size": m.get("total"), "details": {"family": m.get("family"), "parameter_size": f"{m.get('params')}B",
                                                "quantization_level": m.get("quant")}}


def _known(state_dir, host_name: str, model: str) -> "tuple[bool, Optional[dict], Optional[dict]]":
    """(Halo saw it there, the last row it kept (size, digest), its profile)."""
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.providers.ollama_capability import profile_for
    p = profile_for(state_dir, model, host_name) if state_dir is not None else None
    row = _library_row(model)
    if p and isinstance(p.get("size_gb"), (int, float)):
        row = {**(row or {}), "size": int(p["size_gb"] * 1e9)}
    try:
        from halo_harness.models_library.shelf import read_lines
        for s in reversed(read_lines(state_dir) if state_dir is not None else []):
            if s.get("host") == host_name and ollama_names_match(s.get("model"), model) and s.get("retired_at"):
                return True, {"size": s.get("size"), "digest": s.get("digest")}, p
    except Exception:
        pass
    if p:
        return True, row, p
    try:
        from halo_harness.ollama_steward.ledger import read_calls
        if read_calls(state_dir, since=30 * 86400.0, host=host_name, model=model):
            return True, row, p
    except Exception:
        pass
    return False, row, p


def check(ref, *, state_dir=None, catalog: Optional[dict] = None, card=None, window: Optional[int] = None,
          role: Optional[str] = None) -> dict:
    from halo_harness.providers.ollama import ollama_names_match
    model, hname = _split(ref)
    out = {"dead": False, "judged": False, "known": False, "model": model, "host": hname, "near": None,
           "near_why": "", "line": "", "point": ""}
    host = _host(hname)
    if not model or host is None:
        return out
    out["host"] = host.name
    from halo_harness.studio import ollama_hosts_view as V
    cat = catalog if catalog is not None else V.catalog_of(host)
    rows = [r for r in (cat or {}).get("models") or [] if isinstance(r, dict)]
    if not rows:
        return out
    out["judged"] = True
    names = [str(r.get("model") or r.get("name") or "") for r in rows]
    if any(ollama_names_match(n, model) for n in names):
        return out
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    known, gone_row, prof = _known(state_dir, host.name, model)
    from halo_harness.models_library.nearest import nearest
    from halo_harness.providers.ollama_capability import all_profiles
    near = nearest(model, rows, gone_row=gone_row, card=card if card is not None else V.card_of(host),
                   window=window or (prof or {}).get("window_used") or (prof or {}).get("num_ctx"), profile=prof,
                   profiles=all_profiles(state_dir))
    if near is None:
        from halo_harness.doctor_local_ids import nearest as spelled
        got = spelled(model, [n[:-len(":latest")] if n.endswith(":latest") else n for n in names if n])
        near = {"name": got, "line": "the closest spelling; nothing shares its family or size"} if got else None
    out.update(dead=True, known=known)
    head = f"`{model}` was deleted from {host.name}" if known else \
        f"`{model}` is not on {host.name} (deleted, or never pulled there)"
    if near:
        to = f"ol:{near['name']}@{host.name}"
        out.update(near=to, near_why=near["line"],
                   point=f"halo roles point {role} {to}" if role else "")
        out["line"] = f"{head} -- nearest equivalent `{near['name']}` ({near['line']})" + (
            f": {out['point']}" if out["point"] else "")
    else:
        out["line"] = f"{head} -- no model like it there" + (f": halo models browse --for-role {role}" if role else "")
    return out


def line(ref, **kw) -> str:
    try:
        return check(ref, **kw)["line"]
    except Exception:
        return ""


def point(role: str, to: str) -> dict:
    """`roles.<role>` -> `to` (its effort kept): the role write, nothing else."""
    from halo_harness.roles import assign_role, configured_role_table, role_value_parts
    old = configured_role_table().get(role)
    frm = role_value_parts(old)[0]
    if isinstance(old, dict):
        from halo_harness.theme import set_config_value
        set_config_value(f"roles.{role}", {**old, "model": to})
        ok, why = True, []
    else:
        ok, why = assign_role(role, to)
    line = (f"roles.{role}: {frm or '(session model)'} -> {to} (config.json; nothing pulled, nothing loaded)" if ok
            else f"roles.{role} was not written: {'; '.join(why)}")
    return {"ok": ok, "line": line, "from": frm, "to": to}


def cmd_point(argv: list) -> int:
    """`halo roles point <role> <model> [--json]`: the role write after a dead-tag line (or by hand)."""
    import argparse
    import json
    ap = argparse.ArgumentParser(prog="halo roles point", description=(
        "Point a role at a model (roles.<role> in config.json, Halo-side only: nothing is pulled or loaded). The "
        "dead-tag line names the nearest equivalent: `halo roles point coder ol:qwen3.8:27b-gpu@pc`."))
    ap.add_argument("role")
    ap.add_argument("model", help="a model reference (ol:<model>@<host>, or any route)")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    a = ap.parse_args(argv)
    got = point(a.role, a.model)
    print(json.dumps(got) if a.json else got["line"])
    return 0 if got["ok"] else 1
