"""halo_harness.teams_cli -- Halo 2.0.4 round 4 (deliverable 7): `halo
teams list|show|validate|new <name> [--from <template>]|use <name>|
export|import` over `~/.halo/teams/<name>.yaml` team templates
("lineups"). Argparse + formatting only -- `teams_yaml.py` does the real
work, same split as `agents_cli.py`/`roles_cli.py`."""

from __future__ import annotations

import argparse
import sys


def _cmd_list(rest: list) -> int:
    from halo_harness.teams_yaml import ensure_builtin_team_templates, list_team_templates
    argparse.ArgumentParser(prog="halo teams list", add_help=True).parse_args(rest)
    ensure_builtin_team_templates()
    names = list_team_templates()
    if not names:
        print("No team templates found (not even a shipped one -- this shouldn't happen).")
        return 0
    for n in names:
        print(n)
    return 0


def _cmd_show(rest: list) -> int:
    from halo_harness.teams_yaml import resolve_org, resolve_role_table, resolve_team_template
    parser = argparse.ArgumentParser(prog="halo teams show", add_help=True)
    parser.add_argument("name")
    args = parser.parse_args(rest)
    template = resolve_team_template(args.name)
    if template is None:
        print(f"halo teams show: no such team template {args.name!r} (or it failed validation)", file=sys.stderr)
        return 1
    print(f"{template['name']} -- {template.get('description') or '(no description)'}")
    print(f"  source: {template.get('_source')} ({template.get('_path')})")
    for entry in template.get("agents") or []:
        label = entry.get("as") or entry.get("role")
        extra = f" x{entry['instances']}" if entry.get("instances", 1) != 1 else ""
        print(f"  {entry.get('role')} ({label}){extra}: agent={entry.get('agent')}")
    role_table, notes = resolve_role_table(template)
    print("  resolved role table:")
    for k, v in sorted(role_table.items()):
        print(f"    {k}: {v if isinstance(v, str) else v.get('model')}")
    for n in notes:
        print(f"    (note) {n}")
    org, org_notes = resolve_org(template)
    if org is not None:
        print(f"  org: {len(org['positions'])} position(s)")
        for n in org_notes:
            print(f"    (note) {n}")
    return 0


def _cmd_validate(rest: list) -> int:
    from halo_harness.teams_yaml import list_team_templates, load_team_template_raw, validate_team_template
    parser = argparse.ArgumentParser(prog="halo teams validate", add_help=True)
    parser.add_argument("name", nargs="?", help="omit to validate every team template")
    args = parser.parse_args(rest)
    names = [args.name] if args.name else list_team_templates()
    any_problem = False
    for name in names:
        raw = load_team_template_raw(name)
        if raw is None:
            print(f"{name}: not found")
            any_problem = True
            continue
        problems = validate_team_template(raw, name=name)
        if problems:
            any_problem = True
            for p in problems:
                print(f"{name}: {p}")
        else:
            print(f"{name}: ok")
    return 1 if any_problem else 0


def _cmd_new(rest: list) -> int:
    from halo_harness.teams_yaml import new_team_template_from_template
    parser = argparse.ArgumentParser(prog="halo teams new", add_help=True)
    parser.add_argument("name")
    parser.add_argument("--from", dest="from_template", default=None, metavar="TEMPLATE")
    parser.add_argument("--project", action="store_true", help="write to .halo/teams/ instead of ~/.halo/teams/")
    args = parser.parse_args(rest)
    ok, problems = new_team_template_from_template(args.name, args.from_template, project=args.project)
    if not ok:
        print(f"halo teams new: {'; '.join(problems)}", file=sys.stderr)
        return 1
    print(f"Created team template {args.name!r}" + (f" from {args.from_template!r}" if args.from_template else "")
          + ".")
    return 0


def _cmd_use(rest: list) -> int:
    """Halo 2.0.4 round 4 (refinement 2): "the active team is one config
    key (`team: <template name>`...)". Refuses an unknown/invalid name
    outright -- never points the active team at nothing."""
    from halo_harness.teams_yaml import resolve_team_template, validate_team_template
    parser = argparse.ArgumentParser(prog="halo teams use", add_help=True)
    parser.add_argument("name")
    args = parser.parse_args(rest)
    template = resolve_team_template(args.name)
    if template is None:
        print(f"halo teams use: no such team template {args.name!r}", file=sys.stderr)
        return 1
    problems = validate_team_template(template, name=args.name)
    if problems:
        print(f"halo teams use: {args.name!r} has problems: {'; '.join(problems)}", file=sys.stderr)
        return 1
    from halo_harness.theme import set_config_value
    set_config_value("team", args.name)
    print(f"Active team: {args.name!r}.")
    return 0


def _cmd_export(rest: list) -> int:
    from halo_harness.teams_yaml import resolve_team_template
    parser = argparse.ArgumentParser(prog="halo teams export", add_help=True)
    parser.add_argument("name")
    parser.add_argument("file", nargs="?", default=None)
    args = parser.parse_args(rest)
    template = resolve_team_template(args.name)
    if template is None:
        print(f"halo teams export: no such team template {args.name!r}", file=sys.stderr)
        return 1
    import yaml
    payload = {k: v for k, v in template.items() if not k.startswith("_") and k != "roles"}
    text = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, allow_unicode=True)
    if args.file:
        from pathlib import Path
        Path(args.file).write_text(text, encoding="utf-8")
        print(f"Exported team template {args.name!r} to {args.file}.")
    else:
        print(text, end="")
    return 0


def _cmd_import(rest: list) -> int:
    from pathlib import Path

    import yaml
    parser = argparse.ArgumentParser(prog="halo teams import", add_help=True)
    parser.add_argument("file")
    args = parser.parse_args(rest)
    path = Path(args.file)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        print(f"halo teams import: {args.file} is not valid YAML: {e}", file=sys.stderr)
        return 1
    name = data.get("name") if isinstance(data, dict) else None
    if not isinstance(name, str) or not name.strip():
        name = path.stem
    from halo_harness.teams_yaml import save_team_template
    ok, problems = save_team_template(name, data)
    if not ok:
        print(f"halo teams import: {args.file} is not a valid team template:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"Imported team template {name!r} from {args.file}.")
    return 0


_SUBCOMMANDS = {"list": _cmd_list, "show": _cmd_show, "validate": _cmd_validate, "new": _cmd_new,
                "use": _cmd_use, "export": _cmd_export, "import": _cmd_import}


def cmd_teams(argv: list) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: halo teams list|show <name>|validate [name]|new <name> [--from TEMPLATE] [--project]|"
              "use <name>|export <name> [file]|import <file>", file=sys.stderr)
        return 0 if argv else 2
    sub, rest = argv[0], argv[1:]
    fn = _SUBCOMMANDS.get(sub)
    if fn is None:
        print(f"halo teams: unknown subcommand {sub!r} (known: {', '.join(sorted(_SUBCOMMANDS))})",
              file=sys.stderr)
        return 2
    return fn(rest)
