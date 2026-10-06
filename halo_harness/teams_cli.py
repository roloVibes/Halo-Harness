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
    # Halo 2.0.5 round 2 (deliverable 3): "about:" ("How the pieces work
    # together") -- printed under the SAME heading a member's own system
    # context gets it under (`teams_yaml.member_system_context_addition`).
    if template.get("about"):
        print("  How this team works:")
        for line in str(template["about"]).splitlines():
            print(f"    {line}")
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
    # Halo 2.0.5 round 5: the per-section enforcement state -- every
    # section this template sets prints ENFORCED (with the one behaviour
    # line naming what the live loop actually does) or its doctor marker,
    # so a reader never has to guess which parts are real.
    from halo_harness.teams_yaml import enforcement_lines
    lines = enforcement_lines(template)
    if lines:
        print("  enforcement (Halo 2.0.5: the live loop runs these):")
        for line in lines:
            print(line)
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
    # Halo 2.0.5 round 2 (deliverable 4): the SAME form module the
    # wizard's lineup editor and `/teams new` use.
    parser.add_argument("--form", action="store_true", help="open the TUI form instead of writing a starter file")
    args = parser.parse_args(rest)
    if args.form:
        from halo_harness.tui.dialogs.lineup_editor import run_lineup_editor_standalone
        saved = run_lineup_editor_standalone(args.name, project=args.project, is_new=True,
                                              from_template=args.from_template)
        if not saved:
            print("halo teams new: cancelled.", file=sys.stderr)
            return 1
        print(f"Created team template {saved!r}.")
        return 0
    ok, problems = new_team_template_from_template(args.name, args.from_template, project=args.project)
    if not ok:
        print(f"halo teams new: {'; '.join(problems)}", file=sys.stderr)
        return 1
    print(f"Created team template {args.name!r}" + (f" from {args.from_template!r}" if args.from_template else "")
          + ".")
    return 0


def _cmd_edit(rest: list) -> int:
    """Halo 2.0.5 round 2 (deliverable 4): `halo teams edit <name>
    [--form]` -- this command did not exist before this round (the
    starter-writing `new` plus hand-editing the YAML file directly was
    the only path); added here symmetrically with `agents_cli.py`'s own
    `edit` (same `$EDITOR`-or-`--form` split, same "create an empty one
    first if it doesn't exist yet" convenience)."""
    from halo_harness.teams_yaml import load_team_template_raw, save_team_template, user_teams_dir, \
        validate_team_template
    parser = argparse.ArgumentParser(prog="halo teams edit", add_help=True)
    parser.add_argument("name")
    parser.add_argument("--form", action="store_true", help="open the TUI form instead of $EDITOR")
    args = parser.parse_args(rest)
    if args.form:
        from halo_harness.tui.dialogs.lineup_editor import run_lineup_editor_standalone
        saved = run_lineup_editor_standalone(args.name, is_new=False)
        if not saved:
            print("halo teams edit: cancelled.", file=sys.stderr)
            return 1
        print(f"Saved team template {saved!r}.")
        return 0
    import os
    import shlex
    import shutil
    import subprocess
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        print("halo teams edit: no $VISUAL/$EDITOR set", file=sys.stderr)
        return 1
    if load_team_template_raw(args.name) is None:
        save_team_template(args.name, {"description": ""})
    path = user_teams_dir() / f"{args.name}.yaml"
    argv = shlex.split(editor) or [editor]
    argv[0] = shutil.which(argv[0]) or argv[0]
    try:
        rc = subprocess.call([*argv, str(path)])
    except OSError as e:
        print(f"halo teams edit: could not launch {editor!r}: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if rc != 0:
        return rc
    import yaml
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        print(f"halo teams edit: could not re-read {path}: {e}", file=sys.stderr)
        return 1
    problems = validate_team_template(data, name=args.name)
    if problems:
        print(f"halo teams edit: saved file is invalid: {'; '.join(problems)}", file=sys.stderr)
        return 1
    print(f"Saved team template {args.name!r}.")
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
                "edit": _cmd_edit, "use": _cmd_use, "export": _cmd_export, "import": _cmd_import}


def cmd_teams(argv: list) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: halo teams list|show <name>|validate [name]|"
              "new <name> [--from TEMPLATE] [--project] [--form]|edit <name> [--form]|"
              "use <name>|export <name> [file]|import <file>", file=sys.stderr)
        return 0 if argv else 2
    sub, rest = argv[0], argv[1:]
    fn = _SUBCOMMANDS.get(sub)
    if fn is None:
        print(f"halo teams: unknown subcommand {sub!r} (known: {', '.join(sorted(_SUBCOMMANDS))})",
              file=sys.stderr)
        return 2
    return fn(rest)
