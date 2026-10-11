"""halo_harness.design.cli -- `halo design` (Halo 3.0.1.0).

    halo design new <name> [--model M]          a project under ~/.halo/design/<slug>/
    halo design list                             every project
    halo design show <slug>                      artboards, versions, comments, the system
    halo design run <slug> "<prompt>" [--model M] [--budget USD]   one design turn
    halo design sync <slug> [PATH|URL]           a design system from a codebase or a page
    halo design comment <slug> <artboard> "<text>" [--at X,Y]
    halo design restore <slug> <artboard> <version>
    halo design export <slug> --as html|pdf|png|svg|folder [--out DIR]
    halo design handoff <slug> [--out DIR]       the bundle a Halo or Claude Code session continues from
    halo design doctor [--probe]                 which craft apps are registered (and answer)
"""

from __future__ import annotations

import argparse
from pathlib import Path

from halo_harness.design.store import Project


def _open(slug: str) -> Project:
    p = Project.open(slug)
    if p is None:
        names = ", ".join(x["slug"] for x in Project.list()) or "none yet"
        raise SystemExit(f"halo design: no project named {slug!r} (projects: {names})")
    return p


def cmd_new(args) -> int:
    p = Project.create(args.name, model=args.model or "")
    print(f"created {p.path}  (slug {p.slug}" + (f", model {args.model}" if args.model else "") + ")")
    print(f"next: halo design run {p.slug} \"a landing page for ...\"")
    return 0


def cmd_list(args) -> int:
    rows = Project.list()
    if not rows:
        print("no design projects yet: halo design new <name>")
        return 0
    for r in rows:
        print(f"{r['slug']:<28} {r['artboards']:>2} artboard(s)  {r['model'] or '(session model)':<30} {r['name']}")
    return 0


def cmd_show(args) -> int:
    p = _open(args.slug)
    meta = p.meta()
    print(f"{meta.get('name')}  ({p.slug})  model {meta.get('model') or '(session model)'}  {p.path}")
    for a in p.artboards():
        print(f"  {a['id']:<24} {a['kind']:<9} {a.get('app') or '-':<12} v{a['latest']}  {a.get('render') or '(no render yet)'}"
              + (f"  knobs {len(a['controls'])}" if a.get("controls") else ""))
    pins = [c for c in p.comments() if not c.get("resolved")]
    if pins:
        print(f"  {len(pins)} open comment(s): " + "; ".join(f"{c['artboard']}: {c['text'][:40]}" for c in pins[:5]))
    sysd = p.system()
    if sysd:
        print("  design system: " + ", ".join(f"{g} {len(v)}" for g, v in (sysd.get("tokens") or {}).items()) + f"; {len(sysd.get('components') or [])} components")
    hist = p.history()
    if hist:
        spent = sum(float(h.get("cost") or 0) for h in hist)
        print(f"  {len(hist)} turn(s), ${spent:.3f} so far")
    return 0


def cmd_run(args) -> int:
    from halo_harness.design.session import run_turn
    p = _open(args.slug)

    def on_event(ev: dict) -> None:
        t = ev.get("type")
        if t == "assistant":
            for block in (ev.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    print(block.get("text", ""), flush=True)
                elif isinstance(block, dict) and block.get("type") == "tool_use":
                    print(f"  -> {block.get('name')}", flush=True)
        elif t == "halo_design":
            vs = ", ".join(f"{a} v{n}" for a, n in ev.get("versions") or []) or "no artboard changed"
            print(f"turn done (exit {ev.get('code')}, cost {'$%.4f' % ev['cost'] if ev.get('cost') is not None else '?'}): {vs}")
    r = run_turn(p, args.prompt, model=args.model or "", on_event=on_event, max_budget_usd=args.budget)
    return 0 if r["code"] == 0 else 1


def cmd_sync(args) -> int:
    from halo_harness.design.sync import capture_url, scan_codebase, write_system
    p = _open(args.slug)
    src = args.source or "."
    system = capture_url(src) if src.startswith(("http://", "https://")) else scan_codebase(Path(src).resolve())
    merged = write_system(p, system)
    n = sum(len(v) for v in merged["tokens"].values())
    print(f"design system: {n} token(s) in {len(merged['tokens'])} group(s), {len(merged['components'])} component(s); sources: {len(merged['sources'])}")
    return 0


def cmd_comment(args) -> int:
    p = _open(args.slug)
    x, y = 0.0, 0.0
    if args.at:
        try:
            x, y = (float(v) for v in args.at.split(","))
        except ValueError:
            raise SystemExit("halo design comment: --at takes X,Y as percentages, e.g. --at 40,12")
    c = p.add_comment(args.artboard, args.text, x=x, y=y)
    print(f"comment {c['id']} on {args.artboard}; the next `halo design run` addresses it")
    return 0


def cmd_restore(args) -> int:
    p = _open(args.slug)
    ok = p.restore(args.artboard, int(args.version))
    print(f"{args.artboard}: restored v{args.version}" if ok else f"{args.artboard}: no version v{args.version}")
    return 0 if ok else 1


def cmd_export(args) -> int:
    from halo_harness.design.export import export_project
    p = _open(args.slug)
    out = export_project(p, args.as_, Path(args.out) if args.out else None, artboard=args.artboard)
    for line in out:
        print(line)
    return 0


def cmd_handoff(args) -> int:
    from halo_harness.design.export import handoff_bundle
    p = _open(args.slug)
    path = handoff_bundle(p, Path(args.out) if args.out else None)
    print(f"handoff bundle: {path}\nstart the next session there: halo --cwd \"{path}\" \"continue from HANDOFF.md\"")
    return 0


def cmd_doctor(args) -> int:
    from halo_harness.design.crafts import APPS
    from halo_harness.design.crafts_probe import craft_server_configs, probe_crafts, probe_lines
    configs = craft_server_configs()
    for app, spec in APPS.items():
        print(f"  {app:<12} {'registered' if app in configs else 'not registered':<15} {spec['for'][:70]}")
    print(f"{len(configs)} of {len(APPS)} craft apps registered; a design turn allows every present one as tools")
    if not args.probe:
        print("add --probe to spawn each one and check its tools and render step")
        return 0
    rows = probe_crafts(configs)
    print("\n".join(probe_lines(rows)) if rows else "  nothing to probe")
    bad = [r for r in rows if r["state"] != "connected" or not r["render_present"]]
    return 1 if bad else 0


def cmd_design(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="halo design", description="Halo Design: designs, prototypes, pages and decks on your own craft apps.")
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("new", help="create a project"); p.add_argument("name"); p.add_argument("--model"); p.set_defaults(fn=cmd_new)
    sub.add_parser("list", help="every project").set_defaults(fn=cmd_list)
    p = sub.add_parser("show", help="a project's artboards and state"); p.add_argument("slug"); p.set_defaults(fn=cmd_show)
    p = sub.add_parser("run", help="one design turn"); p.add_argument("slug"); p.add_argument("prompt"); p.add_argument("--model"); p.add_argument("--budget", type=float); p.set_defaults(fn=cmd_run)
    p = sub.add_parser("sync", help="a design system from a codebase path or a URL"); p.add_argument("slug"); p.add_argument("source", nargs="?"); p.set_defaults(fn=cmd_sync)
    p = sub.add_parser("comment", help="pin a comment on an artboard"); p.add_argument("slug"); p.add_argument("artboard"); p.add_argument("text"); p.add_argument("--at"); p.set_defaults(fn=cmd_comment)
    p = sub.add_parser("restore", help="restore an artboard version"); p.add_argument("slug"); p.add_argument("artboard"); p.add_argument("version"); p.set_defaults(fn=cmd_restore)
    p = sub.add_parser("export", help="export artboards"); p.add_argument("slug"); p.add_argument("--as", dest="as_", default="folder", choices=["html", "pdf", "png", "svg", "folder"]); p.add_argument("--out"); p.add_argument("--artboard"); p.set_defaults(fn=cmd_export)
    p = sub.add_parser("handoff", help="the bundle a Halo or Claude Code session continues from"); p.add_argument("slug"); p.add_argument("--out"); p.set_defaults(fn=cmd_handoff)
    p = sub.add_parser("doctor", help="which craft apps are registered"); p.add_argument("--probe", action="store_true", help="spawn each app's server and check its tools"); p.set_defaults(fn=cmd_doctor)
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 0
    return args.fn(args)
