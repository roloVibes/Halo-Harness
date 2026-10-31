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
    for line in ensure_builtin_team_templates():
        print(f"halo: {line}", file=sys.stderr)
    names = list_team_templates()
    if not names:
        print("No lineups found.")
        return 0
    from halo_harness.packs.roles import list_lines  # 3.2.0.0 R2: one group per pack, a shadowed name says so
    for n in list_lines("lineups", names):
        print(n)
    return 0


def _cmd_show(rest: list) -> int:
    from halo_harness.teams_yaml import resolve_role_table, resolve_team_template
    parser = argparse.ArgumentParser(prog="halo teams show", add_help=True)
    parser.add_argument("name")
    args = parser.parse_args(rest)
    template = resolve_team_template(args.name)
    if template is None:
        print(f"halo teams show: no lineup named {args.name!r}, or its file has problems (`halo teams validate` says what)", file=sys.stderr)
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
    from halo_harness.models_auto_spawn import pool_words  # 3.1.9.0 R2: an `auto` card's model is picked at spawn
    for entry in template.get("agents") or []:
        label = entry.get("as") or entry.get("role")
        extra = f" x{entry['instances']}" if entry.get("instances", 1) != 1 else ""
        print(f"  {entry.get('role')} ({label}){extra}: agent={entry.get('agent')}{pool_words(template, entry)}")
    # 3.1.6.0 R1: one line per tier -- its members, max_parallel, its own
    # model and its trigger (teams_tier_fields.tier_lines).
    from halo_harness.teams_tier_fields import tier_lines
    for line in tier_lines(template):
        print(line)
    from halo_harness.packs.lineup_run import workflow_lines  # 3.2.1.0 R2: the workflows as `halo workflow run` names them
    for line in workflow_lines(template):
        print(line)
    role_table, notes = resolve_role_table(template)
    print("  resolved role table:")
    for k, v in sorted(role_table.items()):
        shown = v if isinstance(v, str) else v.get("model")
        print(f"    {k}: {shown}{' (picked at spawn)' if shown == 'auto' else ''}")
    for n in notes:
        print(f"    (note) {n}")
    from halo_harness.config.paths import bridge_home  # 3.3.6.0 R1: two models that cannot share one card
    from halo_harness.providers.placement_apply import lineup_pivots
    for p in lineup_pivots(role_table, bridge_home()):
        print(f"    (pivot) {p['line']}")
    from halo_harness.models_library.role_gaps import gaps  # 3.3.6.0 R2: find a model for this role
    for g in gaps(role_table, bridge_home(), [e.get("as") or e.get("role") for e in template.get("agents") or []]):
        print(f"    (gap) {g['why']}: find a model for this role: {g['cli']} (Studio: Local -> Library)")
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
        from halo_harness.teams_tiers import tier_warnings
        from halo_harness.teams_yaml import removed_section_warnings
        for w in tier_warnings(raw) + removed_section_warnings(raw):
            print(f"{name}: {w}")
    return 1 if any_problem else 0


def _cmd_new(rest: list) -> int:
    from halo_harness.teams_yaml import new_team_template_from_template
    parser = argparse.ArgumentParser(prog="halo teams new", add_help=True)
    parser.add_argument("name")
    parser.add_argument("--from", dest="from_template", default=None, metavar="TEMPLATE")
    parser.add_argument("--project", action="store_true", help="write to .halo/teams/ instead of ~/.halo/teams/")
    # Halo 3.1.1.0 R3: Studio is the one editor of lineups -- --studio
    # writes the starter file, then opens the lineup in Studio's inspector.
    parser.add_argument("--studio", action="store_true", help="then open the new lineup in Studio's inspector")
    args = parser.parse_args(rest)
    ok, problems = new_team_template_from_template(args.name, args.from_template, project=args.project)
    if not ok:
        print(f"halo teams new: {'; '.join(problems)}", file=sys.stderr)
        return 1
    print(f"Created lineup {args.name!r}" + (f" from {args.from_template!r}" if args.from_template else "")
          + ".")
    if args.studio:
        from halo_harness.studio_edit_cli import open_in_studio
        return open_in_studio("lineup", args.name, no_open=False, prog="halo teams new")
    return 0


def _cmd_edit(rest: list) -> int:
    """Halo 2.0.5 round 2 (deliverable 4): `halo teams edit <name>`,
    symmetric with `agents_cli.py`'s own `edit` ("create an empty one
    first if it doesn't exist yet"). 3.1.1.0 R3: it opens the lineup in
    Studio (the editor of lineups); `--no-open` prints the URL, `--yaml`
    opens `$EDITOR` on the file instead."""
    from halo_harness.teams_yaml import load_team_template_raw, save_team_template, user_teams_dir, \
        validate_team_template
    from halo_harness.studio_edit_cli import add_studio_flags, open_in_studio
    parser = argparse.ArgumentParser(prog="halo teams edit", add_help=True,
                                     description="Open the lineup in Studio's inspector (Studio is the editor of lineups).")
    parser.add_argument("name")
    add_studio_flags(parser, "lineup")
    args = parser.parse_args(rest)
    if not args.yaml:
        if load_team_template_raw(args.name) is None:
            ok, problems = save_team_template(args.name, {"description": ""})
            if not ok:
                print(f"halo teams edit: {'; '.join(problems)}", file=sys.stderr)
                return 1
            print(f"Created lineup {args.name!r}.")
        return open_in_studio("lineup", args.name, no_open=args.no_open, prog="halo teams edit")
    import os
    import shlex
    import shutil
    import subprocess
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        print("halo teams edit: --yaml needs $EDITOR (or $VISUAL) set to your text editor; without --yaml the "
              "lineup opens in Studio", file=sys.stderr)
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
        print(f"halo teams edit: could not read {path} again: {e}", file=sys.stderr)
        return 1
    problems = validate_team_template(data, name=args.name)
    if problems:
        print(f"halo teams edit: the saved file has problems: {'; '.join(problems)}", file=sys.stderr)
        return 1
    print(f"Saved lineup {args.name!r}.")
    return 0


def _cmd_use(rest: list, *, verb: str = "use") -> int:
    """`halo teams apply|use <name> [--one-model]`: the same result as the
    wizard's Team step -- writes the lineup's roles and `team:`, turns
    custom roles on (off for `standard` / `--one-model`), then prints the
    roles now in force. An unknown or invalid lineup changes nothing."""
    from halo_harness.teams_cli_views import apply_lineup
    from halo_harness.teams_yaml import resolve_team_template
    parser = argparse.ArgumentParser(prog=f"halo teams {verb}", add_help=True)
    parser.add_argument("name", nargs="?", default=None)
    parser.add_argument("--one-model", action="store_true",
                        help="use one model for everything (same as applying `standard`)")
    args = parser.parse_args(rest)
    name = "standard" if args.one_model else args.name
    if not name:
        print(f"halo teams {verb}: say which lineup, e.g. `halo teams {verb} balanced` "
              f"(`halo teams` lists them).", file=sys.stderr)
        return 2
    # 2.0.7 ollama polish (rolo's single-GPU reality): a lineup whose
    # worker/verify lanes are DIFFERENT local models that cannot co-reside
    # pays a full model swap on every implement->verify transition. Warn at
    # ACTIVATION, when the fix is cheapest.
    template = resolve_team_template(name)
    ok, lines, notes = apply_lineup(name)
    if not ok:
        print(f"halo teams {verb}: could not use {name!r}:", file=sys.stderr)
        for line in lines:
            print(f"  - {line}", file=sys.stderr)
        return 1
    try:
        if template is not None:
            _warn_single_gpu_swaps(template)
    except Exception:
        pass
    from halo_harness.teams_apply_answer import apply_answer  # 3.3.5.0 R0 (h): one line, the notes indented
    head, details = apply_answer(name, notes)
    print(head)
    for note in details:
        print(f"    {note}")
    for line in lines:
        print(line)
    return 0


def _cmd_apply(rest: list) -> int:
    return _cmd_use(rest, verb="apply")


def _cmd_preview(rest: list) -> int:
    from halo_harness.teams_cli_views import preview_text
    parser = argparse.ArgumentParser(prog="halo teams preview", add_help=True)
    parser.add_argument("name")
    args = parser.parse_args(rest)
    found, lines = preview_text(args.name)
    for line in lines:
        print(line, file=sys.stdout if found else sys.stderr)
    return 0 if found else 1


def _cmd_diff(rest: list) -> int:
    from halo_harness.teams_cli_views import diff_lines
    parser = argparse.ArgumentParser(prog="halo teams diff", add_help=True)
    parser.add_argument("a")
    parser.add_argument("b")
    args = parser.parse_args(rest)
    ok, lines = diff_lines(args.a, args.b)
    for line in lines:
        print(line, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


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
        print(f"halo teams export: no lineup named {args.name!r}", file=sys.stderr)
        return 1
    import yaml
    payload = {k: v for k, v in template.items() if not k.startswith("_") and k != "roles"}
    text = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, allow_unicode=True)
    if args.file:
        from pathlib import Path
        Path(args.file).write_text(text, encoding="utf-8")
        print(f"Exported lineup {args.name!r} to {args.file}.")
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
        print(f"halo teams import: {args.file} is not a readable YAML file: {e}", file=sys.stderr)
        return 1
    name = data.get("name") if isinstance(data, dict) else None
    if not isinstance(name, str) or not name.strip():
        name = path.stem
    from halo_harness.teams_yaml import save_team_template
    ok, problems = save_team_template(name, data)
    if not ok:
        print(f"halo teams import: {args.file} is not a usable lineup:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"Imported lineup {name!r} from {args.file}.")
    return 0


_SUBCOMMANDS = {"list": _cmd_list, "show": _cmd_show, "validate": _cmd_validate, "new": _cmd_new,
                "edit": _cmd_edit, "use": _cmd_use, "apply": _cmd_apply,
                "preview": _cmd_preview, "diff": _cmd_diff, "export": _cmd_export, "import": _cmd_import}


def cmd_teams(argv: list) -> int:
    if not argv:
        from halo_harness.teams_cli_views import overview_lines
        for line in overview_lines():
            print(line)
        return 0
    if argv[0] in ("-h", "--help"):
        print("usage: halo teams                                  show the active lineup and the others\n"
              "       halo teams list|show <name>|validate [name]\n"
              "       halo teams preview <name>                   the lineup as a tree\n"
              "       halo teams apply <name> [--one-model]       use a lineup (`use` does the same)\n"
              "       halo teams diff <a> <b>                     compare two lineups role by role\n"
              "       halo teams new <name> [--from TEMPLATE] [--project] [--studio]\n"
              "       halo teams edit <name> [--no-open] [--yaml]\n"
              "       halo teams export <name> [file]|import <file>\n"
              "GUI:   halo studio --mode roles                    lineups and bios as an editable graph (Halo Studio; /roles in the TUI)",
              file=sys.stderr)
        return 0
    sub, rest = argv[0], argv[1:]
    fn = _SUBCOMMANDS.get(sub)
    if fn is None:
        print(f"halo teams: {sub!r} is not a command (try: {', '.join(sorted(_SUBCOMMANDS))}).",
              file=sys.stderr)
        return 2
    return fn(rest)
