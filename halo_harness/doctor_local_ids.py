"""halo_harness.doctor_local_ids -- Halo 3.3.6.0 R2: `halo doctor --local`'s two more checks
(plans/local-model-fit-brief.md D4 item 19).

    id_steps(state_dir, *, role_table=None, main_ref=None, versions=None, staged=None) -> [{step, ok, reason, elapsed_s, tag?}]

1. Every role's local model id resolved against its host's catalog (`/api/tags` through the Ollama panel's reader):
   a dead id FAILs and names the nearest equivalent ("`qwen3.8:27b` was deleted -- nearest `qwen3.8:27b-gpu`").
2. Ollama version drift per configured host: the version each runs (the hardware card, else `/api/version`)
   against the newest one any host runs or the knowledge knows (models_library/search_filters.NEWEST_KNOWN); on a
   Windows host this machine serves, an update staged under %LOCALAPPDATA%\\Ollama\\updates ("0.40.13 staged, 0.40.6
   running"). Drift is a WARN line (the exit stays 0); a catalog that does not answer is INFO.

`versions` ({host name: version}) and `staged` (fn(host) -> version | "") are the tests' seams.
"""

from __future__ import annotations

import difflib
import os
import re
from pathlib import Path
from typing import Callable, Optional


def _vt(v) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", str(v or ""))[:3]) or (0,)


def nearest(name: str, names: list) -> Optional[str]:
    """The catalog name closest to a dead id: the same model with another tag first, then the closest spelling."""
    base = name.split(":", 1)[0]
    same = sorted(n for n in names if n.split(":", 1)[0] == base or n.startswith(name))
    if same:
        return same[0]
    got = difflib.get_close_matches(name, names, n=1, cutoff=0.5)
    return got[0] if got else None


def _pairs(state_dir, role_table, main_ref) -> list:
    from halo_harness.roles import configured_role_table, role_value_parts
    table = dict(role_table if role_table is not None else configured_role_table())
    if main_ref is None:
        from halo_harness.doctor_local_roles import _main_ref
        main_ref = _main_ref(state_dir)
    return ([("main", main_ref)] if main_ref else []) + [(r, role_value_parts(v)[0]) for r, v in sorted(table.items())]


def _step(name: str, ok: bool, reason: str, tag: str = "") -> dict:
    out = {"step": name, "ok": ok, "reason": reason, "elapsed_s": 0.0}
    if tag:
        out["tag"] = tag
    return out


def _id_steps(state_dir, role_table, main_ref) -> list:
    from halo_harness.providers.model_card_purpose import parse_ref
    from halo_harness.providers.ollama import ollama_names_match, resolve_ollama_host
    from halo_harness.studio.ollama_hosts_view import catalog_of
    out, seen = [], {}
    for role, ref in _pairs(state_dir, role_table, main_ref):
        if not isinstance(ref, str) or not ref.startswith("ol:"):
            continue
        r = parse_ref(ref)
        host = resolve_ollama_host(getattr(r, "host", None))
        if host is None:
            out.append(_step(f"role {role} id", False, f"{ref}: no Ollama host named {getattr(r, 'host', '')!r}"))
            continue
        if host.url not in seen:
            seen[host.url] = [str(m.get("model") or m.get("name") or "") for m in catalog_of(host).get("models") or []
                              if isinstance(m, dict)]
        names = [n for n in seen[host.url] if n]
        if not names:
            out.append(_step(f"role {role} id", True, f"{ref}: {host.name}'s catalog did not answer", "INFO"))
        elif any(ollama_names_match(n, r.model) for n in names):
            out.append(_step(f"role {role} id", True, f"{ref}: on {host.name}"))
        else:
            near = nearest(r.model, [n[:-len(':latest')] if n.endswith(":latest") else n for n in names])
            out.append(_step(f"role {role} id", False, f"`{r.model}` was deleted from {host.name}" +
                             (f" -- nearest `{near}`: halo config set roles.{role} ol:{near}@{host.name}" if near else
                              " -- no model like it there: halo models browse --for-role " + role)))
    return out


def staged_update(host) -> str:
    """The version an Ollama update staged on this Windows machine waits to install, else ""."""
    try:
        from halo_harness.fleet.ollama_share import served_here
        if host is None or not served_here(host.url) or os.name != "nt":
            return ""
        root = Path(os.environ.get("LOCALAPPDATA") or "") / "Ollama" / "updates"
        found = [d.name for d in root.iterdir() if d.is_dir() and any(d.glob("*.exe"))] if root.is_dir() else []
        vers = sorted((v for v in found if re.match(r"^v?\d+\.\d+", v)), key=_vt)
        return vers[-1].lstrip("v") if vers else ("an update" if found else "")
    except OSError:
        return ""


def _version(host, versions: Optional[dict]) -> Optional[str]:
    if versions is not None:
        return versions.get(host.name)
    from halo_harness.providers.fit_meter import host_card_of
    card = host_card_of(host, read=True) or {}
    v = (card.get("server") or {}).get("version")
    if v:
        return str(v)
    from halo_harness.providers.ollama import probe_version
    got = probe_version(host) or {}
    return got.get("version")


def _drift_steps(versions: Optional[dict], staged: Optional[Callable]) -> list:
    from halo_harness.models_library.search_filters import NEWEST_KNOWN
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.providers.ollama_guard import skip_default
    hosts = [h for h in resolve_ollama_hosts() if versions is not None or not skip_default(h)]
    got = {h.name: _version(h, versions) for h in hosts}
    newest = max([NEWEST_KNOWN] + [v for v in got.values() if v], key=_vt)
    out = []
    for h in hosts:
        v, st = got.get(h.name), (staged or staged_update)(h)
        if not v:
            out.append(_step(f"ollama {h.name}", True, f"{h.name}: its version was not read (/api/version)", "INFO"))
        elif st and st != v and (st == "an update" or _vt(st) > _vt(v)):
            out.append(_step(f"ollama {h.name}", True, f"{h.name}: {st} staged, {v} running: quit Ollama and start it "
                                                       "again to run the staged update", "WARN"))
        elif _vt(v) < _vt(newest):
            out.append(_step(f"ollama {h.name}", True, f"{h.name}: Ollama {v}, {newest} is newer (the fixes between them "
                                                       "may matter: halo ollama crashes)", "WARN"))
        else:
            out.append(_step(f"ollama {h.name}", True, f"{h.name}: Ollama {v} (the newest known)"))
    return out


def id_steps(state_dir, *, role_table: Optional[dict] = None, main_ref: Optional[str] = None,
             versions: Optional[dict] = None, staged: Optional[Callable] = None) -> list:
    return _id_steps(state_dir, role_table, main_ref) + _drift_steps(versions, staged)
