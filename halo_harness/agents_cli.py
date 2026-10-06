"""halo_harness.agents_cli -- Halo 2.0.4 round 4 (deliverable 6): `halo
agents list|show|validate|new <name> [--from <bio>]|edit <name>|
export <name>|import <file>` over `~/.halo/agents/<name>.yaml` (`.halo/
agents/` with `--project`) agent bios. Argparse + formatting only --
`agents_yaml.py`/`agents_md_bridge.py` do the real work, same split as
`roles_cli.py`."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys


def _cmd_list(rest: list) -> int:
    from halo_harness.agents_yaml import list_agent_bios
    argparse.ArgumentParser(prog="halo agents list", add_help=True).parse_args(rest)
    names = list_agent_bios()
    if not names:
        print("No agent bios found (not even a shipped template -- this shouldn't happen).")
        return 0
    for n in names:
        print(n)
    return 0


def _cmd_show(rest: list) -> int:
    from halo_harness.agents_yaml import resolve_agent_bio
    parser = argparse.ArgumentParser(prog="halo agents show", add_help=True)
    parser.add_argument("name")
    args = parser.parse_args(rest)
    bio = resolve_agent_bio(args.name)
    if bio is None:
        print(f"halo agents show: no such agent bio {args.name!r} (or it failed validation)", file=sys.stderr)
        return 1
    print(f"{bio['name']} ({bio.get('kind') or 'custom'}) -- {bio.get('description') or '(no description)'}")
    print(f"  source: {bio.get('_source')} ({bio.get('_path')})")
    if bio.get("extends"):
        print(f"  extends: {bio['extends']}")
    for section in ("models", "tools", "context", "limits", "output", "environment", "acceptance"):
        value = bio.get(section)
        if value:
            print(f"  {section}: {value}")
    return 0


def _cmd_validate(rest: list) -> int:
    from halo_harness.agents_yaml import list_agent_bios, load_agent_bio_raw, validate_agent_bio
    parser = argparse.ArgumentParser(prog="halo agents validate", add_help=True)
    parser.add_argument("name", nargs="?", help="omit to validate every bio")
    args = parser.parse_args(rest)
    names = [args.name] if args.name else list_agent_bios()
    any_problem = False
    for name in names:
        raw = load_agent_bio_raw(name)
        if raw is None:
            print(f"{name}: not found")
            any_problem = True
            continue
        problems = validate_agent_bio(raw, name=name)
        if problems:
            any_problem = True
            for p in problems:
                print(f"{name}: {p}")
        else:
            print(f"{name}: ok")
    return 1 if any_problem else 0


def _cmd_new(rest: list) -> int:
    from halo_harness.agents_yaml import new_agent_bio_from_template
    parser = argparse.ArgumentParser(prog="halo agents new", add_help=True)
    parser.add_argument("name")
    parser.add_argument("--from", dest="from_template", default=None, metavar="BIO")
    parser.add_argument("--project", action="store_true", help="write to .halo/agents/ instead of ~/.halo/agents/")
    args = parser.parse_args(rest)
    ok, problems = new_agent_bio_from_template(args.name, args.from_template, project=args.project)
    if not ok:
        print(f"halo agents new: {'; '.join(problems)}", file=sys.stderr)
        return 1
    print(f"Created agent bio {args.name!r}" + (f" from {args.from_template!r}" if args.from_template else "") + ".")
    return 0


def _run_editor(editor: str, path, *, label: str) -> int:
    """Same fix `roles_cli.py`/`org_cli.py`'s own `_run_editor` already
    apply -- `shlex.split` + resolve argv[0] through PATH, never a bare
    `subprocess.call([editor, path])` (crashes on `EDITOR="code --wait"`
    or an unresolved Windows shim)."""
    argv = shlex.split(editor) or [editor]
    argv[0] = shutil.which(argv[0]) or argv[0]
    try:
        return subprocess.call([*argv, str(path)])
    except OSError as e:
        print(f"{label}: could not launch {editor!r}: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


def _cmd_edit(rest: list) -> int:
    from halo_harness.agents_yaml import load_agent_bio_raw, save_agent_bio, user_agents_dir, validate_agent_bio
    parser = argparse.ArgumentParser(prog="halo agents edit", add_help=True)
    parser.add_argument("name")
    args = parser.parse_args(rest)
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        print("halo agents edit: no $VISUAL/$EDITOR set", file=sys.stderr)
        return 1
    if load_agent_bio_raw(args.name) is None:
        save_agent_bio(args.name, {"description": ""})
    path = user_agents_dir() / f"{args.name}.yaml"
    rc = _run_editor(editor, path, label="halo agents edit")
    if rc != 0:
        return rc
    import yaml
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        print(f"halo agents edit: could not re-read {path}: {e}", file=sys.stderr)
        return 1
    problems = validate_agent_bio(data, name=args.name)
    if problems:
        print(f"halo agents edit: saved file is invalid: {'; '.join(problems)}", file=sys.stderr)
        return 1
    print(f"Saved agent bio {args.name!r}.")
    return 0


def _cmd_export(rest: list) -> int:
    from halo_harness.agents_yaml import resolve_agent_bio
    parser = argparse.ArgumentParser(prog="halo agents export", add_help=True)
    parser.add_argument("name")
    parser.add_argument("file", nargs="?", default=None)
    parser.add_argument("--claude-md", action="store_true",
                         help="write .claude/agents/<name>.md frontmatter instead of plain YAML")
    args = parser.parse_args(rest)
    bio = resolve_agent_bio(args.name)
    if bio is None:
        print(f"halo agents export: no such agent bio {args.name!r}", file=sys.stderr)
        return 1
    if args.claude_md:
        from halo_harness.agents_md_bridge import export_agent_bio
        _ok, path = export_agent_bio(args.name, bio)
        print(f"Exported agent bio {args.name!r} to {path}.")
        return 0
    import yaml
    payload = {k: v for k, v in bio.items() if not k.startswith("_")}
    text = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, allow_unicode=True)
    if args.file:
        from pathlib import Path
        Path(args.file).write_text(text, encoding="utf-8")
        print(f"Exported agent bio {args.name!r} to {args.file}.")
    else:
        print(text, end="")
    return 0


def _cmd_import(rest: list) -> int:
    parser = argparse.ArgumentParser(prog="halo agents import", add_help=True)
    parser.add_argument("source", help="a .yaml file path, or (with --claude-md) a .claude/agents name")
    parser.add_argument("--claude-md", action="store_true", help="import from a discovered .claude/agents/*.md")
    args = parser.parse_args(rest)
    if args.claude_md:
        from halo_harness.agents_md_bridge import import_agent_bio
        bio, problems = import_agent_bio(args.source)
        if bio is None:
            print(f"halo agents import: {'; '.join(problems)}", file=sys.stderr)
            return 1
        from halo_harness.agents_yaml import save_agent_bio
        ok, save_problems = save_agent_bio(args.source, bio)
        if not ok:
            print(f"halo agents import: {'; '.join(save_problems)}", file=sys.stderr)
            return 1
        print(f"Imported agent bio {args.source!r} from .claude/agents/{args.source}.md.")
        return 0
    from pathlib import Path
    import yaml
    path = Path(args.source)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        print(f"halo agents import: {args.source} is not valid YAML: {e}", file=sys.stderr)
        return 1
    name = data.get("name") if isinstance(data, dict) else None
    if not isinstance(name, str) or not name.strip():
        name = path.stem
    from halo_harness.agents_yaml import save_agent_bio
    ok, problems = save_agent_bio(name, data)
    if not ok:
        print(f"halo agents import: {args.source} is not a valid agent bio:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"Imported agent bio {name!r} from {args.source}.")
    return 0


_SUBCOMMANDS = {"list": _cmd_list, "show": _cmd_show, "validate": _cmd_validate, "new": _cmd_new,
                "edit": _cmd_edit, "export": _cmd_export, "import": _cmd_import}


def cmd_agents(argv: list) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: halo agents list|show <name>|validate [name]|new <name> [--from BIO] [--project]|"
              "edit <name>|export <name> [file] [--claude-md]|import <file>|<name> [--claude-md]",
              file=sys.stderr)
        return 0 if argv else 2
    sub, rest = argv[0], argv[1:]
    fn = _SUBCOMMANDS.get(sub)
    if fn is None:
        print(f"halo agents: unknown subcommand {sub!r} (known: {', '.join(sorted(_SUBCOMMANDS))})",
              file=sys.stderr)
        return 2
    return fn(rest)
