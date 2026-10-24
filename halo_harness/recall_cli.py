"""halo_harness.recall_cli -- `halo recall` (Halo 2.0.7; 3.1.2.0 R3 moved it out
of recall.py and added `--fleet`; 3.2.0.0 R5 added `--namespace`, `--provenance`
and `prune`).

    halo recall <query> [--k N] [--no-refresh] [--build-only] [--fleet] [--json]
    halo recall [<query>] --namespace <pack>/<name> [--provenance] [--json]
    halo recall prune [--json]

Without `--fleet`: this harness's own index (recall.py), one line per hit
with its score, kind, title and path. With `--fleet`: the hub this machine
runs (or the hub it joined) fans the query out to every online member, each
answers from its own index, and the merged hits print as one table: score,
harness, title, excerpt (recall_fleet.py). `--namespace` reads one pack
namespace (packs/memory.py) and what other packs share with it; with
`--provenance` each entry shows its `_meta.json` (source, run, stage,
written, retention, shared; packs/memory_meta.py), and without a query it
lists the entries (no embedding model needed). `prune` removes every
`retention: days:<n>` entry older than its days. Exit 0 with hits, 1 with
none, 2 when unconfigured (local search) or on a usage error, 3 when there
is no fleet to ask.
"""
from __future__ import annotations

import json
import sys

USAGE = ("usage: halo recall <query> [--k N] [--no-refresh] [--build-only] [--fleet] [--json] "
         "[--namespace <pack>/<name>] [--provenance] | halo recall prune")
ICONS = {"memory": "memo", "session": "sess", "coach_library": "lib"}  # 3.1.6.0 R3: a coach library entry


def _format(hits: list) -> str:
    if not hits:
        return "no matches (is the embedding model pulled? index built?)"
    lines = []
    for h in hits:
        icon = ICONS.get(h["kind"], "sess")
        lines.append(f"  {h['score']:+.3f} [{icon}] {h['title']}  ({h['id']})")
    return "\n".join(lines)


def _parse(argv: list) -> dict:
    args = list(argv)
    out = {"k": 8, "refresh": True, "build_only": False, "fleet": False, "json": False, "rest": [],
           "namespace": None, "provenance": False}
    while args:
        a = args.pop(0)
        if a == "--k" and args:
            try:
                out["k"] = max(1, int(args.pop(0)))
            except ValueError:
                pass
        elif a == "--namespace" and args:
            out["namespace"] = args.pop(0)
        elif a in ("--no-refresh", "--build-only", "--fleet", "--json", "--provenance"):
            out[{"--no-refresh": "refresh", "--build-only": "build_only"}.get(a, a[2:])] = a != "--no-refresh"
        else:
            out["rest"].append(a)
    out["query"] = " ".join(out["rest"]).strip()
    return out


def _fleet(a: dict) -> int:
    from halo_harness import recall_fleet as RF
    if not a["query"]:
        print(USAGE, file=sys.stderr)
        return 2
    status, body = RF.ask(a["query"], a["k"])
    if a["json"]:
        print(json.dumps({"ok": status == 200, **body}, indent=2, ensure_ascii=False, default=str))
    elif status != 200:
        print(f"halo recall --fleet: {body.get('error')}", file=sys.stderr)
    else:
        print(RF.table(body.get("hits") or [], body.get("harnesses") or []))
    if status != 200:
        return 3
    return 0 if body.get("hits") else 1


def _meta_line(meta: dict) -> str:
    bits = [meta.get("source") or "user"] + [f"{k} {meta[k]}" for k in ("run", "stage") if meta.get(k)]
    bits += [f"written {meta['written']}"] if meta.get("written") else []
    bits += [f"retention {meta.get('retention') or 'keep'}"]
    bits += [f"shared with {', '.join(meta['shared'])}"] if meta.get("shared") else []
    return "; ".join(bits)


def _namespace(a: dict) -> int:
    """3.2.0.0 R5: one pack namespace (and what is shared with it), with each entry's provenance."""
    from halo_harness.packs.memory_meta import meta_of, readable
    try:
        rows = readable(a["namespace"])
    except ValueError as e:
        print(f"halo recall: {e}", file=sys.stderr)
        return 2
    if a["query"]:
        from halo_harness.providers.embeddings import embeddings_enabled
        from halo_harness.recall import search
        if not embeddings_enabled():
            print("recall: embeddings are not configured (embeddings.model in ~/.halo/config.json); "
                  "without a query --namespace lists the entries")
            return 2
        hits = search(a["query"], k=a["k"], refresh=a["refresh"], namespace=a["namespace"])
        rows = [dict(h, meta=meta_of(h["id"])) for h in hits]
    else:
        rows = [{"id": str(r["path"]), "title": r["name"], "namespace": r["namespace"], "meta": r["meta"]} for r in rows]
    if a["json"]:
        print(json.dumps({"ok": True, "namespace": a["namespace"], "entries": rows}, indent=2, default=str))
        return 0 if rows else 1
    if not rows:
        print(f"no entries in {a['namespace']} (nor shared with it)")
        return 1
    for r in rows:
        score = f"{r['score']:+.3f} " if "score" in r else ""
        print(f"  {score}{r['title']}  ({r['id']})")
        if a["provenance"]:
            print(f"      {_meta_line(r['meta'])}")
    return 0


def _prune(a: dict) -> int:
    from halo_harness.packs.memory_meta import prune
    gone = prune()
    if a["json"]:
        print(json.dumps({"ok": True, "removed": [str(e["path"]) for e in gone]}, indent=2))
    else:
        print(f"recall prune: {len(gone)} entr{'y' if len(gone) == 1 else 'ies'} past their days removed"
              + "".join(f"\n  {e['namespace']}: {e['name']} ({e['meta'].get('retention')})" for e in gone))
    return 0


def cmd_recall(argv: list) -> int:
    a = _parse(argv)
    if a["rest"] == ["prune"] and not a["namespace"]:
        return _prune(a)
    if a["namespace"]:
        return _namespace(a)
    if a["fleet"]:
        return _fleet(a)
    from halo_harness.providers.embeddings import embeddings_enabled
    from halo_harness.recall import build_index, search
    if not embeddings_enabled():
        print("recall: embeddings are not configured -- set embeddings.model in "
              "~/.halo/config.json (e.g. \"nomic-embed-text\", pulled on the default "
              "Ollama host) and retry")
        return 2
    if a["build_only"]:
        report = build_index(force=True)
        print(f"recall: index rebuilt -- {report['total']} entries "
              f"({report['embedded']} re-embedded, {report['pruned']} pruned)")
        return 0
    if not a["query"]:
        print(USAGE, file=sys.stderr)
        return 2
    hits = search(a["query"], k=a["k"], refresh=a["refresh"])
    if a["json"]:
        print(json.dumps({"ok": True, "query": a["query"], "hits": hits}, indent=2, ensure_ascii=False))
    else:
        print(_format(hits))
    return 0 if hits else 1
