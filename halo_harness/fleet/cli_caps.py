"""halo_harness.fleet.cli_caps -- `halo fleet capabilities | who` (Halo 3.0.6.0
"Fleet Missions" round R6; the dispatcher is cli.py) and the TUI's
`/fleet who <query>` / `/fleet capabilities [name]` (commands/builtins.py):

    halo fleet capabilities [name] [--refresh] [--tools] [--json]
        a spec sheet per harness: hardware, models, craft apps, MCP servers with their tool counts
        (--tools lists every tool), skills, CLIs, projects, providers, roles, integrations, tags
    halo fleet who "<query>" [--json]
        the harnesses ranked for the query (fleet/capabilities_who.py), each with what matched and why

The catalogs come from the running Studio (`GET /api/fleet/capabilities`),
else from a `halo fleet serve` on this machine, else this harness alone (its
cached catalog, gathered when missing or older than an hour). Computed in
code, no model call. Exit codes: 0 done, 1 could not (the reason on stderr),
2 usage.
"""

from __future__ import annotations

import argparse
from typing import Optional
from urllib.parse import quote

from halo_harness.fleet import identity
from halo_harness.remote import cli_common as C


def _parser(verb: str, description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo fleet {verb}", description=description)
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    return p


def entries(name: str = "", refresh: bool = False) -> "tuple[list, str, Optional[str]]":
    """`(rows, source, error)`; source: studio | hub | local."""
    home = identity.home()
    query = "?" + "&".join(x for x in ((f"harness={quote(name)}" if name else ""), ("refresh=1" if refresh else "")) if x)
    from halo_harness.studio.launch import api_call
    got = api_call(home, "GET", "fleet/capabilities" + (query if query != "?" else ""), timeout=45.0 if refresh else 15.0)
    if got is not None:
        status, body = got
        if status == 200 and isinstance(body, dict):
            return body.get("harnesses") or [], "studio", None
        return [], "studio", str((body or {}).get("error") or f"Studio answered {status}")
    from halo_harness.fleet.hub import running_call
    from halo_harness.fleet.hub_capabilities import entry
    from halo_harness.fleet.capabilities import current
    hub = running_call(home, "GET", "local/capabilities", timeout=8.0)
    if hub and hub[0] == 200 and isinstance(hub[1], dict):
        rows = hub[1].get("harnesses") or []
        member = next((r for r in _pick(rows, name)[0] if not r.get("local")), None) if refresh and name else None
        if member is not None:  # the hub asks that member now
            got = running_call(home, "GET", f"local/capabilities?harness={quote(str(member.get('harness')))}&refresh=1",
                               timeout=40.0)
            if not got or got[0] != 200:
                return [], "hub", str(((got or (0, {}))[1] or {}).get("error") or "the hub could not ask it")
            return _pick(got[1].get("harnesses") or [], name)
        if refresh:  # this machine's own catalog
            fresh = current(home, refresh_now=True)
            rows = [entry({"id": r.get("harness"), "name": r.get("name"), "local": True, "online": True}, fresh)
                    if r.get("local") else r for r in rows]
        return _pick(rows, name)
    me = identity.harness()
    rows = [entry({**me, "local": True, "online": True}, current(home, refresh_now=refresh))]
    return _pick(rows, name, source="local")


def _pick(rows: list, name: str, source: str = "hub") -> "tuple[list, str, Optional[str]]":
    if not name:
        return rows, source, None
    low = name.lower()
    hit = [r for r in rows if (low == "local" and r.get("local")) or str(r.get("harness")) == name
           or str(r.get("name") or "").lower() == low]
    return hit, source, (None if hit else f"no harness {name!r} here (harnesses: "
                                         f"{', '.join(str(r.get('name')) for r in rows) or 'none'})")


def spec_text(rows: list, *, tools: bool = False) -> str:
    from halo_harness.fleet.capabilities_view import spec_lines
    out = []
    for r in rows:
        if r.get("catalog"):
            out += spec_lines(r["catalog"], tools=tools, name=r.get("name"))
        else:
            out.append(f"{r.get('name')}  {r.get('summary') or ''}".rstrip())
            out.append(f"  {r.get('note') or 'no catalog yet'}")
        out.append("")
    return "\n".join(out).rstrip() or "No harness in this fleet."


def who_text(q: str) -> str:
    from halo_harness.fleet import capabilities_who as who
    rows, _source, err = entries()
    if err:
        return f"fleet who: {err}"
    ranked = who.rank([{"harness": r.get("harness"), "name": r.get("name"), "catalog": r.get("catalog")} for r in rows], q)
    return "\n".join(who.lines(ranked, q))


def cmd_capabilities(argv: list) -> int:
    p = _parser("capabilities", "What each harness can do: hardware, models, craft apps, MCP servers, skills, tags.")
    p.add_argument("name", nargs="?", default="", help="one harness (its name or id; `local` for this one)")
    p.add_argument("--refresh", action="store_true", help="gather the catalog afresh (a member is asked now)")
    p.add_argument("--tools", action="store_true", help="list every MCP tool with its description")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    rows, source, err = entries(a.name, a.refresh)
    if err:
        return C.fail(a.json, "not_found", f"halo fleet capabilities: {err}")
    if a.json:
        C.emit_json({"ok": True, "source": source, "harnesses": rows})
        return 0
    print(spec_text(rows, tools=a.tools))
    return 0


def cmd_who(argv: list) -> int:
    p = _parser("who", "Which harness can do something: ranked over tools, skills, tags, models, apps, CLIs, hardware.")
    p.add_argument("query", nargs="+", help="what to look for, e.g. gridcraft, \"make a spreadsheet\", 4090")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.fleet import capabilities_who as who
    q = " ".join(a.query)
    if not who.query_words(q):
        return C.fail(a.json, "usage", f"halo fleet who: \"{q}\" has no word to look for")
    rows, source, err = entries()
    if err:
        return C.fail(a.json, "unavailable", f"halo fleet who: {err}")
    ranked = who.rank([{"harness": r.get("harness"), "name": r.get("name"), "local": r.get("local"),
                        "catalog": r.get("catalog")} for r in rows], q)
    if a.json:
        C.emit_json({"ok": True, "source": source, "q": q, "words": who.query_words(q), "results": ranked})
        return 0
    print("\n".join(who.lines(ranked, q)))
    return 0 if ranked else 1


def slash_text(args: str) -> Optional[str]:
    """`/fleet who <query>` and `/fleet capabilities [name]` in the TUI and `halo -p`; None: not ours."""
    verb, _, rest = (args or "").strip().partition(" ")
    if verb == "who":
        return who_text(rest) if rest.strip() else "Usage: /fleet who <what you need, e.g. gridcraft, a 4090, nmap>"
    if verb in ("capabilities", "caps", "specs"):
        rows, _source, err = entries(rest.strip())
        return f"fleet capabilities: {err}" if err else spec_text(rows)
    return None
