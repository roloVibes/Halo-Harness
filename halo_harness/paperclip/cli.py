"""halo_harness.paperclip.cli -- `halo paperclip` (Halo 2.2.0 round C1/C3)
and `halo paperclip-run` (C2).

    halo paperclip status                  health, companies, the Halo link
    halo paperclip install                 npx paperclipai onboard --yes (Node >= 24)
    halo paperclip open                    the Paperclip UI in the browser
    halo paperclip link [--url U] [--token T] [--company ID|NAME]
    halo paperclip sync <lineup> [--company ID|NAME | --new NAME] [--cwd DIR]
    halo paperclip pull <lineup> [--company ID|NAME] [--project]
    halo paperclip org [--company ID|NAME]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

from halo_harness.paperclip.client import DEFAULT_URL, Paperclip, PaperclipError, load_config, save_config


def _client() -> Paperclip:
    return Paperclip.from_config()


def _company_id(client: Paperclip, ref: str) -> str:
    cfg = load_config()
    ref = ref or str(cfg.get("company_id") or "")
    companies = client.companies()
    if not ref:
        if len(companies) == 1:
            return companies[0]["id"]
        raise SystemExit("halo paperclip: which company? pass --company <id|name> (or `halo paperclip link --company ...`)")
    for c in companies:
        if c.get("id") == ref or c.get("name") == ref or str(c.get("id", "")).startswith(ref):
            return c["id"]
    raise SystemExit(f"halo paperclip: no company matches {ref!r}; `halo paperclip status` lists them")


def cmd_mode(args) -> int:
    """`halo paperclip on|off`: the Org mode switch (paperclip/mode.py)."""
    from halo_harness.paperclip.mode import EXPLAINER, mode_line, set_org_mode
    res = set_org_mode(args.cmd == "on", client=_client())
    print(mode_line(res["enabled"]))
    if res["agents"]:
        print(f"  {'resumed' if res['enabled'] else 'paused'}: {', '.join(res['agents'])}")
    if res["note"]:
        print(f"  {res['note']}")
    if not res["enabled"]:
        print("  " + EXPLAINER)
    return 0


def cmd_status(args) -> int:
    from halo_harness.paperclip.mode import mode_line
    cfg = load_config()
    client = _client()
    print(mode_line())
    print(f"Paperclip at {client.base_url}" + (" (token set)" if client.token else " (no token: loopback trusted mode)"))
    try:
        h = client.health()
    except PaperclipError as e:
        print(f"  not reachable: {e.message}")
        print("  `halo paperclip install` sets it up; `npx paperclipai run` starts an installed one")
        return 1
    print(f"  version {h.get('version')} · mode {h.get('deploymentMode')} · auth {'ready' if h.get('authReady') else 'not ready'}")
    try:
        companies = client.companies()
    except PaperclipError as e:
        print(f"  companies: {e.message}")
        return 1
    for c in companies:
        mark = " (linked)" if c.get("id") == cfg.get("company_id") else ""
        print(f"  company {c.get('name')}  {c.get('id', '')[:8]}  {c.get('status')}{mark}")
    if not companies:
        print("  no company yet: open the UI (`halo paperclip open`) or `halo paperclip sync <lineup> --new <name>`")
    return 0


def cmd_install(args) -> int:
    node = shutil.which("node")
    ver = ""
    if node:
        try:
            ver = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            ver = ""
    major = int(ver.lstrip("v").split(".")[0]) if ver.lstrip("v").split(".")[0].isdigit() else 0
    if major < 24:
        print(f"halo paperclip install: Paperclip needs Node.js 24 or newer (found {ver or 'none'}); install Node 24 first")
        return 1
    npx = shutil.which("npx") or "npx"
    cmd = [npx, "--yes", "--registry", "https://registry.npmjs.org", "paperclipai@latest", "onboard", "--yes"]
    print("Running:", " ".join(cmd))
    print("(this downloads Paperclip, creates ~/.paperclip with an embedded database and starts the server; Ctrl+C stops it)")
    try:
        return subprocess.call(cmd)
    except OSError as e:
        print(f"halo paperclip install: cannot run npx: {e}")
        return 1


def cmd_open(args) -> int:
    url = _client().base_url
    print(url)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    return 0


def cmd_link(args) -> int:
    cfg = load_config()
    if args.url:
        cfg["base_url"] = args.url
    if args.token:
        cfg["token"] = args.token
    client = Paperclip(str(cfg.get("base_url") or DEFAULT_URL), str(cfg.get("token") or ""))
    if args.company:
        cfg["company_id"] = _company_id(client, args.company)
    path = save_config(cfg)
    print(f"saved {path}: url {cfg.get('base_url', DEFAULT_URL)}, token {'set' if cfg.get('token') else 'none'}, company {cfg.get('company_id', 'none')}")
    return 0


def cmd_sync(args) -> int:
    from halo_harness.paperclip.sync import org_tree_lines, sync_lineup
    client = _client()
    if args.new:
        company = client.create_company(args.new, f"Halo lineup {args.lineup}")
        cid = company["id"]
        print(f"created company {args.new} ({cid[:8]})")
        cfg = load_config()
        cfg["company_id"] = cid
        save_config(cfg)
    else:
        cid = _company_id(client, args.company)
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    print(f"syncing lineup {args.lineup} -> company {cid[:8]} (agents run `halo paperclip-run` in {cwd})")
    try:
        agents = sync_lineup(client, cid, args.lineup, cwd=cwd, command=args.command)
    except (ValueError, PaperclipError) as e:
        print(f"halo paperclip sync: {e}")
        return 1
    print(f"{len(agents)} agent(s) in Paperclip. Org chart:")
    for line in org_tree_lines(client.org(cid)):
        print("  " + line)
    return 0


def cmd_pull(args) -> int:
    from halo_harness.paperclip.sync import pull_reporting_lines
    client = _client()
    cid = _company_id(client, args.company)
    try:
        org = pull_reporting_lines(client, cid, args.lineup, project=True if args.project else None, out=sys.stdout)
    except (ValueError, PaperclipError) as e:
        print(f"halo paperclip pull: {e}")
        return 1
    print(f"wrote org.positions into lineup {args.lineup}: {len(org.get('positions') or [])} position(s)")
    return 0


def cmd_org(args) -> int:
    from halo_harness.paperclip.sync import org_tree_lines
    client = _client()
    cid = _company_id(client, args.company)
    lines = org_tree_lines(client.org(cid))
    print("\n".join(lines) if lines else "(no agents)")
    return 0


def cmd_paperclip(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="halo paperclip", description="Paperclip: your lineups as a company of agents.")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("status", help="Org mode, health, companies, the Halo link").set_defaults(fn=cmd_status)
    sub.add_parser("on", help="turn Org mode on: Paperclip wakes the company's Halo agents (resumes them)").set_defaults(fn=cmd_mode)
    sub.add_parser("off", help="turn Org mode off (the default): heartbeats answer idle, agents paused").set_defaults(fn=cmd_mode)
    sub.add_parser("install", help="npx paperclipai onboard --yes").set_defaults(fn=cmd_install)
    sub.add_parser("open", help="open the Paperclip UI").set_defaults(fn=cmd_open)
    p = sub.add_parser("link", help="store the URL, a board token and the default company")
    p.add_argument("--url"), p.add_argument("--token"), p.add_argument("--company")
    p.set_defaults(fn=cmd_link)
    p = sub.add_parser("sync", help="create or update the company's agents from a lineup")
    p.add_argument("lineup"), p.add_argument("--company"), p.add_argument("--new", help="create a company with this name")
    p.add_argument("--cwd", help="the project directory the agents work in (default: here)")
    p.add_argument("--command", default="halo", help=argparse.SUPPRESS)
    p.set_defaults(fn=cmd_sync)
    p = sub.add_parser("pull", help="write the company's reporting lines into the lineup's org section")
    p.add_argument("lineup"), p.add_argument("--company"), p.add_argument("--project", action="store_true")
    p.set_defaults(fn=cmd_pull)
    p = sub.add_parser("org", help="print the company's org chart")
    p.add_argument("--company")
    p.set_defaults(fn=cmd_org)
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 0
    return args.fn(args)


def cmd_paperclip_run(argv: list) -> int:
    """`halo paperclip-run`: the command Paperclip's process adapter spawns."""
    from halo_harness.paperclip.adapter import run_heartbeat
    return run_heartbeat(dict(os.environ))
