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
    # 2.0.7 ollama polish (rolo's single-GPU reality): a lineup whose
    # worker/verify lanes are DIFFERENT local models that cannot co-reside
    # pays a full model swap (~a minute of dead load on a 24 GB card) on
    # every implement->verify transition. Warn at ACTIVATION, when the fix
    # (same model for both, or a smaller second lane) is cheapest. Measured
    # via fits_beside_main -- never a guess; unknown (remote host, nothing
    # loaded yet) stays silent.
    try:
        _warn_single_gpu_swaps(template)
    except Exception:
        pass
    from halo_harness.theme import set_config_value
    set_config_value("team", args.name)
    print(f"Active team: {args.name!r}.")
    return 0


def _warn_single_gpu_swaps(template: dict) -> None:
    """One plain warning per LOCAL model pair in the lineup that measured
    as unable to co-reside on the default Ollama host. `ol:` refs only;
    non-local and unknown-fit pairs stay silent (benefit of the doubt)."""
    from halo_harness.providers.ollama import resolve_ollama_host
    from halo_harness.providers.ollama_hw import fits_beside_main
    host = resolve_ollama_host(None)
    if host is None:
        return
    # The distinct ol: models this lineup references (roles shorthand or
    # full agents list).
    refs = set()
    roles = template.get("roles") or {}
    if isinstance(roles, dict):
        for v in roles.values():
            if isinstance(v, str) and v.startswith("ol:"):
                refs.add(v[3:].split("@")[0])
            elif isinstance(v, dict) and isinstance(v.get("model"), str) and v["model"].startswith("ol:"):
                refs.add(v["model"][3:].split("@")[0])
    for entry in template.get("agents") or []:
        if isinstance(entry, dict):
            m = entry.get("model") or ""
            if isinstance(m, str) and m.startswith("ol:"):
                refs.add(m[3:].split("@")[0])
    refs = {r for r in refs if r}
    if len(refs) < 2:
        return
    import itertools
    for a, b in itertools.combinations(sorted(refs), 2):
        if fits_beside_main(host, main_model=a, candidate_model=b, catalog=None) is False:
            print(f"  [!] {a} + {b} cannot co-reside on this GPU -- every switch between their roles "
                  f"pays a full model swap (~1 min on a 24 GB card). Consider one model for both "
                  f"lanes, or a smaller second lane.", file=sys.stderr)


def _cmd_export(rest: list) -> int:
    from halo_harness.teams_yaml import resolve_team_template
    parser = argparse.ArgumentParser(prog="halo teams export", add_help=True)
    parser.add_argument("name")
    parser.add_argument("file", nargs="?", default=None)
    # 2.0.6 round 13: the lineup WITH its bios as one folder
    parser.add_argument("--bundle", default=None, metavar="DIR",
                        help="export the team plus every non-shipped bio it references as one "
                             "importable folder (see `halo teams import <dir>`)")
    args = parser.parse_args(rest)
    if args.bundle:
        from halo_harness.teams_bundle import bundle_export
        ok, lines = bundle_export(args.name, args.bundle)
        for line in lines:
            print(line)
        return 0 if ok else 1
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
    # 2.0.6 round 13: importing a bundle FOLDER (a directory carrying
    # bundle.json) applies the whole lineup; --force overwrites colliding
    # user-scope bios instead of skipping them.
    parser.add_argument("--force", action="store_true",
                        help="with a bundle folder: overwrite user-scope bios that already exist")
    args = parser.parse_args(rest)
    path = Path(args.file)
    if path.is_dir():
        from halo_harness.teams_bundle import bundle_import
        ok, lines = bundle_import(path, force=args.force)
        for line in lines:
            print(line)
        return 0 if ok else 1
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
