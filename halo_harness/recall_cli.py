"""halo_harness.recall_cli -- `halo recall` (Halo 2.0.7; 3.1.2.0 R3 moved it out
of recall.py and added `--fleet`).

    halo recall <query> [--k N] [--no-refresh] [--build-only] [--fleet] [--json]

Without `--fleet`: this harness's own index (recall.py), one line per hit
with its score, kind, title and path. With `--fleet`: the hub this machine
runs (or the hub it joined) fans the query out to every online member, each
answers from its own index, and the merged hits print as one table: score,
harness, title, excerpt (recall_fleet.py). Exit 0 with hits, 1 with none,
2 when unconfigured (local search) or on a usage error, 3 when there is no
fleet to ask.
"""
from __future__ import annotations

import json
import sys

USAGE = "usage: halo recall <query> [--k N] [--no-refresh] [--build-only] [--fleet] [--json]"
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
    out = {"k": 8, "refresh": True, "build_only": False, "fleet": False, "json": False, "rest": []}
    while args:
        a = args.pop(0)
        if a == "--k" and args:
            try:
                out["k"] = max(1, int(args.pop(0)))
            except ValueError:
                pass
        elif a == "--no-refresh":
            out["refresh"] = False
        elif a == "--build-only":
            out["build_only"] = True
        elif a == "--fleet":
            out["fleet"] = True
        elif a == "--json":
            out["json"] = True
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


def cmd_recall(argv: list) -> int:
    a = _parse(argv)
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
