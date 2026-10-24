"""halo_harness.fleet.cli_mission -- `halo fleet mission ...` (Halo 3.0.6.0
"Fleet Missions" round R7; the dispatcher is fleet/cli.py) and the TUI's
`/mission` (commands/builtins.py: the status table).

    halo fleet mission new "<goal>" [--prefer a,b] [--budget N] [--constraints "..."] [--test CMD] [--lineup NAME] [--no-repo] [--json]
    halo fleet mission plan <id> [--again] [--json]      the plan table with reasons (--again: the lead plans anew)
    halo fleet mission edit <id> <part> (--harness NAME | --drop) [--json]
    halo fleet mission approve <id> [--json]
    halo fleet mission run <id> [--no-follow] [--force] [--json]   approve + run + a live table of the parts by harness
    halo fleet mission status [id] [--json]
    halo fleet mission stop <id> [--reason TEXT] [--json]
    halo fleet mission report <id> [--json]
    halo fleet mission open <id> [--json]                the mission folder
    halo fleet mission coach <id> [--json]               the post-run coach's card (read only, this harness's folder)

Every verb goes to the running Studio (`/api/fleet/missions...`), else to a
`halo fleet serve` on this machine (its loopback `local/mission` route), else
runs here for this harness alone (`run` then follows in this process: the
mission runs while it does). Exit codes: 0 done, 1 could not (the reason on
stderr), 2 usage.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from halo_harness.fleet import identity
from halo_harness.remote import cli_common as C

VERBS = ("new", "plan", "edit", "approve", "run", "status", "stop", "report", "open", "coach")
USAGE = __doc__.split("\n\n")[1]
ROUTES = {"list": ("GET", "fleet/missions"), "new": ("POST", "fleet/missions"), "get": ("GET", "fleet/missions/{id}"),
          "plan": ("POST", "fleet/missions/{id}/plan"), "edit": ("POST", "fleet/missions/{id}/parts/{part}"),
          "approve": ("POST", "fleet/missions/{id}/approve"), "run": ("POST", "fleet/missions/{id}/run"),
          "stop": ("POST", "fleet/missions/{id}/stop"), "report": ("GET", "fleet/missions/{id}/report")}


def call(op: str, **fields) -> "tuple[int, dict, str]":
    """`(status, body, source)`; source: studio | hub | local."""
    home = identity.home()
    from halo_harness.studio.launch import api_call
    method, route = ROUTES[op]
    route = route.format(id=fields.get("id", ""), part=fields.get("part", ""))
    body = {k: v for k, v in fields.items() if k not in ("id", "part")} if method == "POST" else None
    slow = op in ("new", "plan")
    got = api_call(home, method, route, body, timeout=180.0 if slow else 40.0)
    if got is not None:
        return got[0], got[1] if isinstance(got[1], dict) else {}, "studio"
    from halo_harness.fleet.hub import running_call
    got = running_call(home, "POST", "local/mission", {"op": op, "cwd": os.getcwd(), **fields}, timeout=180.0 if slow else 40.0)
    if got:
        return got[0], got[1] if isinstance(got[1], dict) else {}, "hub"
    from halo_harness.fleet.mission_api import admin
    status, out = admin(home, None, {"op": op, "by": identity.fleet_name(), "cwd": os.getcwd(), **fields})
    return status, out, "local"


def _parser(verb: str, description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo fleet mission {verb}", description=description)
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    return p


def _done(a, status: int, body: dict, source: str, text) -> int:
    if status >= 300:
        return C.fail(a.json, "mission", f"halo fleet mission: {body.get('error') or status}", status=status,
                      problems=body.get("problems") or [])
    if a.json:
        C.emit_json({"ok": True, "source": source, **body})
    else:
        print(text(body) if callable(text) else text)
    return 0


def _table(body: dict) -> str:
    from halo_harness.fleet.mission_doc import plan_table
    return plan_table(body.get("mission") or {}, body.get("plan") or {})


def _status_text(body: dict) -> str:
    from halo_harness.fleet.mission_doc import status_table
    if "missions" in body:
        rows = body.get("missions") or []
        if not rows:
            return "No missions yet: `halo fleet mission new \"<goal>\"` drafts and plans one."
        return "\n".join(f"{m['id']}  {m['state']:<8}  {m['parts']} parts  ${float(m.get('cost_usd') or 0):.4f}  "
                         f"{', '.join(m.get('harnesses') or [])}  {str(m.get('goal'))[:70]}" for m in rows)
    return status_table(body.get("mission") or {})


def cmd_new(argv: list) -> int:
    p = _parser("new", "Draft a mission and have the hub's lead plan it across the fleet.")
    p.add_argument("goal", help="what the mission is for, in sentences")
    p.add_argument("--prefer", default="", help="harness names that break a tie, in order (a,b)")
    p.add_argument("--budget", type=float, default=None, help="the mission's budget in dollars")
    p.add_argument("--constraints", default="", help="what every part must respect")
    p.add_argument("--test", default="", help="a test command run on the merged branch after a judged conflict")
    p.add_argument("--lineup", default="", help="the lineup the mission is started with (halo teams list; a pack's "
                   "lineup adds its mission metadata)")
    p.add_argument("--no-repo", action="store_true", help="no repo parts even inside a git repo")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    fields = {"goal": a.goal, "prefer": [x for x in a.prefer.split(",") if x.strip()], "budget_usd": a.budget,
              "constraints": a.constraints, "test": a.test}
    if a.lineup.strip():  # 3.2.1.0 R1: it rides in the mission's metadata (fleet/mission_api.py create)
        fields["lineup"] = a.lineup.strip()
    if a.no_repo:
        fields["repo"] = False
    status, body, source = call("new", **fields)
    if status >= 300 and body.get("mission") and not a.json:
        print(_table(body))
    return _done(a, status, body, source, _table)


def _one(verb: str, description: str, argv: list, extra=None):
    p = _parser(verb, description)
    p.add_argument("id", nargs="?" if verb == "status" else None, help="the mission id (m-<yyyymmdd>-<4 hex>)")
    if extra:
        extra(p)
    return C.parse(p, argv)


def cmd_plan(argv: list) -> int:
    a, rc = _one("plan", "Print a mission's plan with each part's harness and why.", argv,
                 lambda p: p.add_argument("--again", action="store_true", help="ask the lead to plan it anew"))
    if a is None:
        return rc
    return _done(a, *call("plan" if a.again else "get", id=a.id), _table)


def cmd_edit(argv: list) -> int:
    def extra(p):
        p.add_argument("part", help="the part number")
        p.add_argument("--harness", default="", help="give the part to this harness")
        p.add_argument("--drop", action="store_true", help="drop the part")
    a, rc = _one("edit", "Reassign or drop one part; the plan is checked again in code.", argv, extra)
    if a is None:
        return rc
    if not a.drop and not a.harness:
        return C.fail(a.json, "usage", "halo fleet mission edit: give --harness NAME or --drop")
    fields = {"drop": True} if a.drop else {"harness": a.harness}
    return _done(a, *call("edit", id=a.id, part=a.part, **fields), _table)


def cmd_approve(argv: list) -> int:
    a, rc = _one("approve", "Approve a planned mission.", argv)
    return rc if a is None else _done(a, *call("approve", id=a.id), lambda b: f"Mission {a.id} approved.\n" + _table(b))


def cmd_status(argv: list) -> int:
    a, rc = _one("status", "Every mission, or one mission's parts by harness.", argv)
    if a is None:
        return rc
    return _done(a, *(call("get", id=a.id) if a.id else call("list")), _status_text)


def cmd_stop(argv: list) -> int:
    a, rc = _one("stop", "Stop a mission: every running part stops.", argv,
                 lambda p: p.add_argument("--reason", default="", help="why, for the report"))
    return rc if a is None else _done(a, *call("stop", id=a.id, reason=a.reason), _status_text)


def cmd_report(argv: list) -> int:
    a, rc = _one("report", "A mission's report: who did what, cost per harness and part, what failed.", argv)
    return rc if a is None else _done(a, *call("report", id=a.id), lambda b: b.get("markdown") or "")


def cmd_open(argv: list) -> int:
    a, rc = _one("open", "Print the mission's folder.", argv)
    if a is None:
        return rc
    from halo_harness.fleet import mission_store as S
    status, body, source = call("get", id=a.id)
    if status < 300:
        body = {"id": a.id, "folder": str(S.folder(identity.home(), a.id))}
    return _done(a, status, body, source, lambda b: b["folder"])


def cmd_run(argv: list) -> int:
    a, rc = _one("run", "Approve (when planned) and run a mission, then follow it.", argv,
                 lambda p: (p.add_argument("--no-follow", action="store_true", help="start it and return"),
                            p.add_argument("--force", action="store_true",
                                           help="run even when the lineup preflight finds problems")))
    if a is None:
        return rc
    status, body, source = call("run", id=a.id, **({"force": True} if a.force else {}))
    if status >= 300 or a.json or (a.no_follow and source != "local"):
        return _done(a, status, body, source, _status_text)
    last = ""
    try:
        while True:
            text = _status_text(body)
            if text != last:
                print(text + "\n", flush=True)
                last = text
            if (body.get("mission") or {}).get("state") in ("done", "failed", "stopped"):
                break
            time.sleep(1.0)
            status, body, _ = call("get", id=a.id)
            if status >= 300:
                return C.fail(False, "mission", f"halo fleet mission: {body.get('error') or status}")
    except KeyboardInterrupt:
        print("\n(stopped following; the mission " + ("stops with this process)" if source == "local" else "goes on)"))
        return 0
    return 0 if (body.get("mission") or {}).get("state") == "done" else 1


def cmd_mission(argv: list) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv else 2
    if argv[0] == "coach":  # 3.0.9.0 R3 (coach_cli.py)
        from halo_harness.coach_cli import cmd_mission_coach
        return cmd_mission_coach(argv[1:])
    if argv[0] in VERBS:
        return globals()["cmd_" + argv[0]](argv[1:])
    print(USAGE, file=sys.stderr)
    return 2


def slash_text(args: str) -> str:
    """`/mission [id]`: the missions, or one mission's parts by harness."""
    mid = (args or "").strip().split()[0] if (args or "").strip() else ""
    status, body, _ = call("get", id=mid) if mid else call("list")
    return _status_text(body) if status < 300 else f"/mission: {body.get('error') or status}"
