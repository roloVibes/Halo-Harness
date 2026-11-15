"""Studio: `GET doctor/config` (Halo 3.1.1.0 round R2) -- the rows `halo
doctor --config` prints, for this Studio's folder and state dir.

    GET doctor/config                -> {"findings": [...], "files_checked": n}

A finding is the `doctor_config.finding` shape: `{id, check, severity
("blocks" | "warns"), kind, file, path, key, text, fix, lineups}`
(3.6.0.0 R5d: `?lineup=` went with the lineups; `lineups` stays empty).
"""

from __future__ import annotations

from .api import Request


def get_doctor_config(req: Request):
    from halo_harness.config_where import where_rows
    from halo_harness.doctor_config import config_findings
    rows = where_rows(req.cwd, state_dir=req.state_dir)
    findings = config_findings(req.cwd, state_dir=req.state_dir, rows=rows)
    checked = sum(len(r["files"]) for r in rows if r["scope"] not in ("shipped", "pack") and r["read"])
    return 200, {"findings": findings, "files_checked": checked}


ROUTES = [("GET", r"^doctor/config$", get_doctor_config)]
