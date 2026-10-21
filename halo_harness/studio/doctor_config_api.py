"""Studio: `GET doctor/config` (Halo 3.1.1.0 round R2) -- the rows `halo
doctor --config` prints, for this Studio's folder and state dir.

    GET doctor/config                -> {"findings": [...], "files_checked": n, "lineup": null}
    GET doctor/config?lineup=<name>  -> only the findings about that lineup
                                        and the lineups it extends

A finding is the `doctor_config.finding` shape: `{id, check, severity
("blocks" | "warns"), kind, file, path, key, text, fix, lineups}`. Roles'
Problems panel shows the `?lineup=` answer for the open lineup under its
Config group.
"""

from __future__ import annotations

from .api import Request


def _chain(name: str, req: Request) -> list:
    from halo_harness import teams_yaml as T
    chain = []
    while name and name not in chain:
        chain.append(name)
        raw = T.load_team_template_raw(name, cwd=req.cwd, state_dir=req.state_dir) or {}
        parent = raw.get("extends")
        name = parent.strip() if isinstance(parent, str) else ""
    return chain


def get_doctor_config(req: Request):
    from halo_harness.config_where import where_rows
    from halo_harness.doctor_config import config_findings
    rows = where_rows(req.cwd, state_dir=req.state_dir)
    findings = config_findings(req.cwd, state_dir=req.state_dir, rows=rows)
    lineup = str(req.query.get("lineup") or "").strip()
    if lineup:
        names = set(_chain(lineup, req))
        findings = [f for f in findings if names.intersection(f.get("lineups") or [])]
    checked = sum(len(r["files"]) for r in rows if r["scope"] not in ("shipped", "pack") and r["read"])
    return 200, {"findings": findings, "files_checked": checked, "lineup": lineup or None}


ROUTES = [("GET", r"^doctor/config$", get_doctor_config)]
