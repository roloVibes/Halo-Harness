"""halo_harness.local_refresh_cli -- `halo local refresh` and `halo host refresh` (Halo 3.3.7.0 R4; docs/COMMANDS-local.md,
docs/COMMANDS-host.md; the plan is host/refresh_plan.py, the run host/refresh.py).

    halo local refresh [--dry] [--host H] [--json]      a machine with no halo host: the plan, then each model in turn
                                                         (the battery, the quick bench), stopping at the first call
    halo host refresh status [--json]                    the plan ("next: ..."), the window, the last run
    halo host refresh now [--json]                       the running host starts it at its next tick (the window
                                                         aside; never during a session); no host running: here
    halo host refresh off | on [--json]                  host.refresh.enabled
Nothing runs while a session uses the card; the battery and the bench load the model in Ollama, never in this process.
"""

from __future__ import annotations

import argparse
import json
import sys


def _hosts(name=None) -> list:
    from halo_harness.host.state import served_hosts
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.providers.ollama_guard import skip_default
    hs = served_hosts() or [h for h in resolve_ollama_hosts() if not skip_default(h)]
    return [h for h in hs if not name or h.name.lower() == name.lower()]


def _home():
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def run_here(hosts: list, *, dry: bool = False, say=print, runners=None) -> dict:
    from halo_harness.host.refresh import run_one
    from halo_harness.host.refresh_plan import plan, settings
    from halo_harness.ollama_steward.idle import idle_since
    home = _home()
    p = plan(home, hosts, settings_={**settings(home), "enabled": True})
    say(p["line"])
    for row in p["rows"] if dry else []:
        say(f"  would: {row['model']} on {row['host']} ({row['why']}: {row['says']}), ~{row['minutes']} min")
    done = []
    for row in [] if dry else p["rows"]:
        host = next(h for h in hosts if h.name == row["host"])
        idle = idle_since(home, host)
        if idle["busy"]:
            say(f"  {row['model']}: waits -- {idle['busy']}")
            break
        got = run_one(home, host, row, runners=runners, why="by hand")
        say(f"  {got['line']}")
        done.append(got)
        if got.get("stopped"):
            break
    return {"plan": p, "done": done, "dry": dry}


def cmd_refresh(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="halo local refresh", description=(
        "Re-measure what went stale on this machine's Ollama hosts: the capability battery and the quick bench, one "
        "model at a time (drifted tags first, then never probed, then the oldest), stopping the moment a call arrives. "
        "For a machine with no halo host; on one, `halo host refresh` does it off-hours."))
    ap.add_argument("--dry", action="store_true", help="say the plan, run nothing")
    ap.add_argument("--host", default=None, help="only this Ollama host")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    a = ap.parse_args(argv)
    hosts = _hosts(a.host)
    if not hosts:
        print("halo local refresh: no Ollama host here to refresh", file=sys.stderr)
        return 1
    got = run_here(hosts, dry=a.dry, say=(lambda s: None) if a.json else print)
    if a.json:
        print(json.dumps(got, indent=2, default=str))
    return 0


def cmd_host_refresh(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="halo host refresh", description=(
        "The off-hours refresh on this host: the battery and the quick bench for models whose profile is unverified, "
        "older than host.refresh.max_age_days or drifted, inside host.refresh.window once the card has been idle "
        "host.refresh.idle_min minutes; never during a session."))
    ap.add_argument("verb", nargs="?", default="status", choices=("status", "now", "off", "on"))
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    a = ap.parse_args(argv)
    from halo_harness.host import refresh as R
    from halo_harness.host.state import read_info
    home = _home()
    if a.verb in ("off", "on"):
        from halo_harness.fleet import identity
        from halo_harness.theme import set_config_value
        set_config_value("host.refresh.enabled", a.verb == "on")
        identity.forget_cache()
        line = f"the off-hours refresh is {a.verb} (host.refresh.enabled {str(a.verb == 'on').lower()})"
        print(json.dumps({"ok": True, "line": line}) if a.json else line)
        return 0
    if a.verb == "now":
        if read_info(home):
            R.request_now(home)
            line = ("asked the running halo host: it starts the refresh at its next tick (within a few seconds) once "
                    "no session or call is on the card")
            print(json.dumps({"ok": True, "line": line, "via": "host"}) if a.json else line)
            return 0
        got = run_here(_hosts(), say=(lambda s: None) if a.json else print)
        if a.json:
            print(json.dumps(got, indent=2, default=str))
        return 0
    st = R.status(home, _hosts())
    if a.json:
        print(json.dumps(st, indent=2, default=str))
        return 0
    s = st["settings"]
    print(f"halo host refresh: {'on' if s['enabled'] else 'off'}, window {s['window']}, idle {s['idle_min']} min, "
          f"re-verify after {s['max_age_days']} days")
    print(f"  {st['line']}")
    for r in st["plan"]["rows"][1:6]:
        print(f"    then {r['model']} on {r['host']} ({r['why']}), ~{r['minutes']} min")
    print(f"  {st['last_line']}")
    if st.get("review"):
        print(f"  roster review: {(st['review'].get('lines') or ['-'])[0]}")
    return 0
