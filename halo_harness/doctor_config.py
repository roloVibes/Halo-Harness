"""halo_harness.doctor_config -- `halo doctor --config`: every file `halo
config where` lists, checked against the schema set (halo_harness/schemas/)
for shape and against the existing validators for meaning.

Reported: a file that does not parse; an unknown key (with the closest known
key); a wrong type; a lineup naming a bio that does not exist and every other
`validate_team_template` line; every `validate_agent_bio` line; a team file's
`validate_team` lines (a member's lineup that is not there among them, run
without the model-catalog preflight); `team:` in config.json naming a
lineup that is not there; a leftover section of a removed feature (in
config.json `orgs`, `paperclip`: one line each, "removed in 3.1.4.0, the
section is ignored"; in a lineup `org`: "org: removed in 3.1.4.0, ignored",
a warning, never a block); a leftover game-theme key or a saved game theme
(3.1.5.0, one warning line each); a repo `.halo/config.json` (Halo reads only the
home one); and the same key set in two files with different values, with
the file that wins (doctor_config_conflicts.py). Shipped templates are not
re-checked (the suite checks them).

A finding: `{"id", "check", "severity": "blocks" | "warns", "kind", "file",
"path", "key", "text", "fix", "lineups": [names it concerns]}`.
"""

from __future__ import annotations

import json
from pathlib import Path

from halo_harness.schemas import check_file_shape


def finding(check: str, severity: str, row_or_file, text: str, *, key: str = "", fix: str = "",
            lineups=(), kind: str = "") -> dict:
    row = row_or_file if isinstance(row_or_file, dict) else {"file": str(row_or_file), "path": str(row_or_file)}
    return {"id": f"{row['file']}:{check}:{key or text[:40]}", "check": check, "severity": severity,
            "kind": kind or row.get("kind", ""), "file": row["file"], "path": row["path"], "key": key,
            "text": text, "fix": fix, "lineups": list(lineups)}


def _shape(kind: str, data, row: dict, *, lineups=()) -> list:
    out = []
    for f in check_file_shape(kind, data):
        if f["check"] == "unknown-key":
            fix = f"rename it to {f['closest']}" if f["closest"] else "remove it"
            out.append(finding("unknown-key", "warns", row, f["text"], key=f["key"], fix=fix, lineups=lineups))
        else:
            out.append(finding(f["check"], "blocks", row, f["text"], key=f["key"],
                               fix="give it a value of the type named", lineups=lineups))
    return out


def _yaml(path: Path):
    import yaml
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")), ""
    except OSError as e:
        return None, f"cannot read it: {e}"
    except yaml.YAMLError as e:
        return None, f"is not valid YAML: {str(e).splitlines()[0]}"


def _file_row(row: dict, path: Path) -> dict:
    from halo_harness.where.rows import display
    return {**row, "file": display(path), "path": str(path)}


def _config_json(row: dict, state_dir: Path, cwd: Path) -> list:
    path = Path(row["path"])
    if not path.is_file():
        return []
    if not row["read"]:
        return [finding("unread-file", "warns", row, "Halo reads only ~/.halo/config.json; the keys here do nothing",
                        fix="move the keys into ~/.halo/config.json (halo config set)")]
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        return [finding("unreadable", "blocks", row, f"{row['file']} is not valid JSON: {e}", fix="fix or delete the file")]
    if path.name == "routes.json":
        return [] if isinstance(data, dict) else [finding("wrong-type", "blocks", row, "routes.json is a JSON object")]
    from halo_harness.schemas.config_json import REMOVED_SECTIONS, removed_line
    out = [f for f in _shape("config", data, row) if f["key"] not in REMOVED_SECTIONS]
    for section in sorted(REMOVED_SECTIONS):
        if isinstance(data, dict) and section in data:
            out.append(finding("removed-section", "warns", row, removed_line(section), key=section))
    out = _removed_theme_findings(out, data, row)
    team = data.get("team") if isinstance(data, dict) else None
    if isinstance(team, str) and team.strip():
        from halo_harness import teams_yaml as T
        if T.find_team_template_path(team.strip(), cwd=cwd, state_dir=state_dir) is None:
            known = ", ".join(T.list_team_templates(cwd=cwd, state_dir=state_dir)) or "none"
            out.append(finding("missing-lineup", "blocks", row, f"team: {team!r} names a lineup that is not there "
                               f"(known: {known})", key="team", fix="halo teams use <name>", lineups=[team.strip()]))
    return out


def _removed_theme_findings(found: list, data, row: dict) -> list:
    """3.1.5.0: a leftover game-theme key is one "removed" line (not an
    unknown key), and a saved game theme is one line naming the theme Halo
    uses instead (not a bad value)."""
    from halo_harness import theme as T
    from halo_harness.schemas.config_json import REMOVED_KEYS, removed_key_line
    if not isinstance(data, dict):
        return found
    game = data.get("theme") if data.get("theme") in T.REMOVED_THEMES else None
    out = [f for f in found if f["key"] not in REMOVED_KEYS and not (game and f["key"] == "theme")]
    out += [finding("removed-key", "warns", row, removed_key_line(key), key=key)
            for key in sorted(REMOVED_KEYS) if key in data]
    if game:
        using = T.resolve_theme(persisted_theme=game)
        out.append(finding("removed-theme", "warns", row, T.removed_theme_line(game, using), key="theme"))
    return out


def _lineup_or_bio(kind: str, row: dict, cwd: Path, state_dir: Path) -> list:
    from halo_harness.agents_yaml import validate_agent_bio
    from halo_harness.teams_yaml import validate_team_template
    out = []
    for f in row["files"]:
        path = Path(f)
        name = path.stem
        frow = _file_row(row, path)
        tags = [name] if kind == "lineup" else []
        data, problem = _yaml(path)
        if problem:
            out.append(finding("unreadable", "blocks", frow, f"{frow['file']} {problem}", fix="fix the YAML", lineups=tags))
            continue
        if kind == "lineup":  # 3.1.4.0: a removed section is its own one line, not an unknown key
            from halo_harness.teams_yaml import REMOVED_SECTIONS, removed_section_warnings
            out += [f for f in _shape(kind, data, frow, lineups=tags) if f["key"] not in REMOVED_SECTIONS]
            out += [finding("removed-section", "warns", frow, line[len("warning: "):], key=line[len("warning: "):].split(":")[0],
                            lineups=tags) for line in removed_section_warnings(data)]
        else:
            out += _shape(kind, data, frow, lineups=tags)
        validate = validate_team_template if kind == "lineup" else validate_agent_bio
        for line in validate(data if data is not None else {}, name=name, cwd=cwd, state_dir=state_dir):
            missing = "no such agent bio" in line or "agent bio that does not exist" in line
            out.append(finding("missing-bio" if missing else "invalid", "blocks", frow, line, lineups=tags,
                               fix="halo agents new <name>, or name a bio halo agents lists" if missing else ""))
    return out


def _team(row: dict, cwd: Path, state_dir: Path) -> list:
    from halo_harness.team.spec import find_team_file, validate_team
    path = Path(row["path"])
    if not path.is_file():
        return []
    data, problem = _yaml(path)
    if problem:
        return [finding("unreadable", "blocks", row, f"{row['file']} {problem}", fix="fix the YAML")]
    out = _shape("team", data, row)
    found = find_team_file(cwd, state_dir)
    if found is None or Path(found[0]).resolve() != path.resolve():
        return out
    for line in validate_team(data if data is not None else {}, cwd=cwd, state_dir=state_dir, preflight=False):
        lineup = line.split("lineup `", 1)[1].split("`", 1)[0] if "does not exist" in line and "lineup `" in line else ""
        out.append(finding("missing-lineup" if lineup else "invalid", "blocks", row, line,
                           lineups=[lineup] if lineup else [], fix="halo teams lists the lineups" if lineup else ""))
    return out


def _active(state_dir: Path) -> list:
    from halo_harness.config_where import _active_lineup
    name = _active_lineup(state_dir)
    return [name] if name else []


def config_findings(cwd=None, *, state_dir=None, settings_flag=None, rows=None) -> list:
    """Every finding for the files `config where` lists here (an empty list: all clean)."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.config_where import where_rows
    from halo_harness.doctor_config_conflicts import conflict_findings
    cwd = Path(cwd if cwd is not None else Path.cwd()).resolve()
    state = Path(state_dir) if state_dir is not None else bridge_home()
    rows = rows if rows is not None else where_rows(cwd, state_dir=state, settings_flag=settings_flag)
    out: list = []
    for row in rows:
        kind, editable = row["kind"], row["scope"] not in ("shipped", "pack")  # a pack's files: the packs group
        if kind == "config":
            out += _config_json(row, state, cwd)
        elif kind == "lineup" and not row["exists"] and row["rank"] > 1:
            out.append(finding("missing-lineup", "blocks", row, row["note"], key="extends",
                               fix="name a lineup halo teams lists", lineups=list(row["sets"]) + _active(state)))
        elif kind in ("lineups", "bios") and editable:
            out += _lineup_or_bio("lineup" if kind == "lineups" else "bio", row, cwd, state)
        elif kind == "team":
            out += _team(row, cwd, state)
    from halo_harness.packs.doctor import config_findings as pack_findings  # 3.2.0.0 R1: the packs group
    return out + conflict_findings(rows, cwd=cwd) + pack_findings(cwd=cwd, state_dir=state)


def _prefilled_lines(cwd) -> list:
    """One line per provider the wizard would prefill but that is not set up: where the value came from."""
    try:
        from halo_harness.init_providers import TAB_LABEL, prefilled_line, tab_credential_state
        st = tab_credential_state("databricks", cwd=cwd)
        line = prefilled_line(st)
        return [f"{TAB_LABEL.get('databricks', 'Databricks')}: {line}"] if line else []
    except Exception:
        return []


def cmd_doctor_config(*, cwd=None, settings_flag=None, as_json: bool = False) -> int:
    """`halo doctor --config`: 0 when every file is clean, 1 when any finding."""
    from halo_harness.config_where import where_rows
    cwd = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()
    rows = where_rows(cwd, settings_flag=settings_flag)
    findings = config_findings(cwd, settings_flag=settings_flag, rows=rows)
    checked = sum(len(r["files"]) for r in rows if r["scope"] not in ("shipped", "pack") and r["read"])
    if as_json:
        print(json.dumps({"findings": findings, "files_checked": checked}, indent=2))
        return 1 if findings else 0
    print("halo doctor --config")
    print("  Every file `halo config where` lists, against Halo's schemas (unknown keys, wrong types) and its "
          "validators (missing bios and lineups), plus keys two files set to different values.")
    for line in _prefilled_lines(cwd):  # 3.3.5.0 R0 (g): where a prefilled provider value came from
        print(f"  {line}")
    for f in findings:
        tag = "[ERROR]" if f["severity"] == "blocks" else "[WARN]"
        text = f["text"] if f["text"].startswith(f["file"]) else f"{f['file']}: {f['text']}"
        print(f"  {tag} {text}" + (f" -> fix: {f['fix']}" if f["fix"] else ""))
    blocks = sum(1 for f in findings if f["severity"] == "blocks")
    print(f"RESULT: {len(findings)} finding(s) in {checked} file(s) checked ({blocks} error(s), "
          f"{len(findings) - blocks} warning(s)).")
    return 1 if findings else 0
