"""halo_harness.knowledge.cli -- `halo knowledge` (Halo 3.1.8.0 R4,
docs/COMMANDS-supervise.md "halo knowledge", docs/KNOWLEDGE.md).

    halo knowledge add finding|decision "<title>" [--body FILE|-] [--evidence L] [--alternative A] [--tag T] [--json]
    halo knowledge list [finding|decision] [--all] [--json]
    halo knowledge show <id> [--json]
    halo knowledge search <words> [--k N] [--json]
    halo knowledge forget <id> [--json]
    halo knowledge supersede <id> "<title>" [--body FILE|-] [--evidence L] [--alternative A] [--tag T] [--json]
    halo knowledge fetch <harness> <id> | <harness> --all finding|decision [--json]

`--evidence`, `--alternative` and `--tag` repeat. `add` and `supersede`
write `by: user`; `list` leaves superseded entries out unless `--all`;
`show` adds "reused by" (the agent tasks whose evidence cites the id,
outcomes.jsonl). Exit 0 done, 1 nothing there / refused, 2 a usage error,
3 no hub to fetch through.
"""

from __future__ import annotations

import argparse
import json
import sys

VERBS = ("add", "list", "show", "search", "forget", "supersede", "fetch")


def _writes(p: argparse.ArgumentParser) -> None:
    p.add_argument("title", help="one line: what was found or decided")
    p.add_argument("--body", metavar="FILE", help="the body (what / where / why) from a file, or - for stdin")
    p.add_argument("--evidence", action="append", default=[], metavar="L", help="an evidence line (repeat it)")
    p.add_argument("--alternative", action="append", default=[], metavar="A", help="a decision's alternative (repeat it)")
    p.add_argument("--tag", action="append", default=[], metavar="T", help="a tag (repeat it)")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo knowledge", description="Findings and decisions that outlive a session.")
    sub = p.add_subparsers(dest="verb")
    add = sub.add_parser("add", help="write a finding or a decision")
    add.add_argument("kind", choices=("finding", "decision"))
    _writes(add)
    ls = sub.add_parser("list", help="the entries, newest first")
    ls.add_argument("kind", nargs="?", choices=("finding", "decision"))
    ls.add_argument("--all", action="store_true", help="superseded entries too")
    sub.add_parser("show", help="one entry, with what reused it").add_argument("id")
    se = sub.add_parser("search", help="the entries that rank for some words (recall, else a word match)")
    se.add_argument("words", nargs="+")
    se.add_argument("--k", type=int, default=8)
    sub.add_parser("forget", help="remove an entry (recall's index prunes it)").add_argument("id")
    sup = sub.add_parser("supersede", help="write a new entry that replaces an older one")
    sup.add_argument("id")
    _writes(sup)
    fe = sub.add_parser("fetch", help="take a fleet member's entry (or every one of a kind) through the hub")
    fe.add_argument("harness", help="its name or id (halo fleet who)")
    fe.add_argument("id", nargs="?", help="the entry id (halo recall --fleet shows it as ref)")
    fe.add_argument("--all", choices=("finding", "decision"), metavar="KIND", help="every current entry of this kind")
    for sp in sub.choices.values():
        sp.add_argument("--json", action="store_true", help="print JSON")
    return p


def _body(arg) -> str:
    if not arg:
        return ""
    if arg == "-":
        return sys.stdin.read()
    with open(arg, encoding="utf-8") as fh:
        return fh.read()


def _row(e: dict) -> str:
    gone = f"  (superseded by {e['superseded_by']})" if e.get("superseded_by") else ""
    return (f"  {e['id']}  {e['kind']:<8}  {e['by'][:18]:<18}  {e['when'][:10]}  {(e.get('confidence') or '-'):<7}  "
            f"{e['title']}{gone}")


def _show(e: dict, reused: list) -> str:
    lines = [f"{e['id']}  {e['kind']}: {e['title']}", f"  when {e['when']}  by {e['by']}"
             + (f"  run {e['run']}" if e["run"] else "") + (f"  repo {e['repo']}" if e["repo"] else "")]
    if e.get("confidence"):
        lines.append(f"  confidence {e['confidence']}")
    if e.get("supersedes"):
        lines.append(f"  supersedes {e['supersedes']}")
    if e.get("superseded_by"):
        lines.append(f"  superseded by {e['superseded_by']}")
    if e.get("read_only"):
        m = e.get("meta") or {}
        lines.append(f"  fetched from {m.get('harness_name') or m.get('from')} ({m.get('from')}) {m.get('fetched')}: read-only")
    for title, items in (("evidence", e["evidence"]), ("alternatives", e["alternatives"]), ("tags", e["tags"])):
        if items:
            lines.append(f"  {title}:" + "".join(f"\n    - {x}" for x in items))
    if e["body"]:
        lines.append("\n" + e["body"])
    lines.append("\n  reused by: " + ("; ".join(f"{r['task']} of {r['run']} ({r.get('bio') or '?'}, {r['outcome']})"
                                                for r in reused) if reused else "no agent task cited it yet"))
    return "\n".join(lines)


def _out(a, data: dict, text: str, rc: int = 0) -> int:
    print(json.dumps(dict({"ok": rc == 0}, **data), indent=2, ensure_ascii=False, default=str) if a.json else text)
    return rc


def _write(a, verb: str) -> int:
    from halo_harness.knowledge import store
    try:
        fields = dict(body=_body(a.body), evidence=a.evidence, alternatives=a.alternative, tags=a.tag, by="user")
        e = (store.write(a.kind, a.title, **fields) if verb == "add" else store.supersede(a.id, a.title, **fields))
    except (store.KnowledgeError, OSError) as err:
        print(f"halo knowledge {verb}: {err}", file=sys.stderr)
        return 1
    return _out(a, {"entry": e}, f"{e['kind']} {e['id']} written: {e['path']}"
                + (f" (confidence {e['confidence']})" if e.get("confidence") else ""))


def _fetch(a) -> int:
    from halo_harness.knowledge.share import fetch
    rc, out = fetch(a.harness, a.id or "", kind=a.all or "", all_kind=bool(a.all and not a.id))
    if rc != 0 and not a.json:
        print(f"halo knowledge fetch: {out.get('error')}", file=sys.stderr)
        return rc
    text = (f"fetched {len(out.get('written') or [])} from {out.get('from')}: " + ", ".join(out.get("written") or [])
            + (f"; already here: {', '.join(out['skipped'])}" if out.get("skipped") else "")
            + (f"; {out['left_out']} left out (over 256 KB)" if out.get("left_out") else ""))
    return _out(a, out, text, rc)


def cmd_knowledge(argv: list) -> int:
    from halo_harness.knowledge import store
    p = _parser()
    a = p.parse_args(argv)
    if not a.verb:
        p.print_help()
        return 2
    if a.verb in ("add", "supersede"):
        return _write(a, a.verb)
    if a.verb == "fetch":
        return _fetch(a)
    if a.verb == "list":
        rows = store.entries(kind=a.kind) if a.all else store.current(kind=a.kind)
        return _out(a, {"entries": rows}, "\n".join(_row(e) for e in rows) or "no findings or decisions here yet",
                    0 if rows else 1)
    if a.verb == "search":
        from halo_harness.knowledge.search import search
        hits = search(" ".join(a.words), k=max(1, a.k))
        text = "\n".join(f"  {h['score']:+.3f} [{h['kind']}] {h['id']}  {h['title']}  ({h['by']}, {h['when'][:10]})"
                         for h in hits) or "no finding or decision matches"
        return _out(a, {"hits": hits}, text, 0 if hits else 1)
    e = store.read(a.id) if store.valid_id(a.id) else None
    if e is None:
        print(f"halo knowledge {a.verb}: no knowledge entry {a.id!r} here (halo knowledge list shows them)", file=sys.stderr)
        return 1
    if a.verb == "forget":
        store.forget(a.id)
        return _out(a, {"forgotten": a.id, "path": e["path"]}, f"{a.id} forgotten ({e['path']} removed)")
    from halo_harness.knowledge.cite import reused_by
    e["superseded_by"] = next((r["id"] for r in store.entries(kind=e["kind"]) if r["supersedes"] == a.id), "")
    reused = reused_by(a.id)
    return _out(a, {"entry": e, "reused_by": reused}, _show(e, reused))
