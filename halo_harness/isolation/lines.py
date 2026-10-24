"""halo_harness.isolation.lines -- the one line each opt-in shows (Halo 3.1.8.0 R5).

    isolation: container (halo-harness-worker:<version>)    isolation: user (halo-worker)
    secrets: 1password (3 refs)
    tools: read, edit, bash (by bio reviewer)

A lane that declares any of them gets, in `lanes/<n>.json`, `isolation:
{mode, image | user}`, `secrets: {broker, refs}` (a count, never a value),
`tools: {capabilities, by}` and `opt_ins` (the lines). The run report keeps
`opt_ins: [{lane, lines}]` and prints a line per lane; `halo goal show`,
Studio's Orchestra run view and the Agent panel show the same lines.
"""

from __future__ import annotations

from pathlib import Path


def isolation_line(iso) -> str:
    if not iso:
        return ""
    if iso.get("mode") == "user":
        return f"isolation: user ({iso.get('user') or '?'})"
    return f"isolation: container ({iso.get('image') or '?'})"


def lane_record(opt) -> dict:
    """The lane file's fields for an OptIns (isolation/spec.py) that declares something."""
    from halo_harness.isolation.capabilities import line as tools_line
    from halo_harness.isolation.secrets import line as secrets_line
    out: dict = {}
    lines = []
    if opt.isolation:
        iso = opt.isolation
        out["isolation"] = {"mode": iso.get("mode"), **({"user": iso.get("user")} if iso.get("mode") == "user"
                                                         else {"image": iso.get("image")}), "by": opt.isolation_by}
        lines.append(isolation_line(iso))
    if opt.secrets:
        out["secrets"] = {"broker": opt.secrets.get("broker") or "", "refs": len(opt.secrets.get("refs") or []),
                          "by": opt.secrets.get("by") or ""}
        lines.append(secrets_line(opt.secrets))
    if opt.caps is not None:
        out["tools"] = {"capabilities": list(opt.caps), "by": opt.caps_by}
        lines.append(tools_line(opt.caps, opt.caps_by))
    out["opt_ins"] = lines
    return out


def report_lanes(lanes) -> dict:
    """`{"opt_ins": [{lane, lines}]}` for the report when any lane declared one, else {}."""
    rows = []
    for lane in lanes:
        data = lane.data() if hasattr(lane, "data") else dict(lane)
        if data.get("opt_ins"):
            rows.append({"lane": int(data.get("lane") or getattr(lane, "n", 0)), "lines": list(data["opt_ins"])})
    return {"opt_ins": rows} if rows else {}


def report_text(report: dict) -> "list[str]":
    """The report's printed lines: `  lane 2: isolation: container (...)`."""
    return [f"  lane {r.get('lane')}: {ln}" for r in report.get("opt_ins") or [] for ln in r.get("lines") or []]


def run_lines(run_dir) -> "list[str]":
    """`halo goal show`: the same lines from the run's lane files (the report may not be written yet)."""
    from halo_harness.orchestra import jsonl
    out = []
    for p in sorted((Path(run_dir) / "lanes").glob("*.json"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0):
        data = jsonl.read_json(p, {}) if p.stem.isdigit() else {}
        for ln in (data or {}).get("opt_ins") or []:
            out.append(f"lane {p.stem}: {ln}")
    return out
