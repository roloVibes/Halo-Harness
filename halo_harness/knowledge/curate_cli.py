"""halo_harness.knowledge.curate_cli -- `halo knowledge list` and `halo knowledge prune` (Halo 3.3.16.2,
knowledge/curate.py; docs/KNOWLEDGE.md "Keeping it useful").

    list  [finding|decision] [--kind gate|finding|decision] [--project .|all|NAME] [--all]
    prune --kind gate|finding|decision --older-than 7d [--project .|all|NAME] [--dry-run] [--yes]

`prune` prints what it would remove and the count first; only `--yes` (without `--dry-run`) removes them.
"""

from __future__ import annotations

import sys


def _scope_words(a) -> str:
    project = getattr(a, "project", "all") or "all"
    return "every project" if project == "all" else ("this folder's project" if project == "." else f"project {project}")


def list_or_prune(a, out) -> int:
    from halo_harness.knowledge import curate
    from halo_harness.knowledge.store import KnowledgeError
    kind = getattr(a, "kind_opt", None) or getattr(a, "kind", None)
    if a.verb == "list":
        rows = curate.select(kind=kind, project=a.project, everything=bool(a.all))
        text = "\n".join(curate.row_line(e) for e in rows) or (
            f"no {kind or 'finding or decision'} entries here for {_scope_words(a)}")
        return out(a, {"entries": rows}, text, 0 if rows else 1)
    try:
        age = curate.parse_age(a.older_than)
    except KnowledgeError as e:
        print(f"halo knowledge prune: {e}", file=sys.stderr)
        return 2
    rows = curate.select(kind=kind, project=a.project, older_than_s=age)
    what = f"{len(rows)} {kind} entr{'y' if len(rows) == 1 else 'ies'} older than {a.older_than} ({_scope_words(a)})"
    lines = [curate.row_line(e) for e in rows]
    if not rows:
        return out(a, {"would_remove": [], "removed": []}, f"nothing to prune: no {kind} entry older than "
                   f"{a.older_than} ({_scope_words(a)})", 0)
    if a.dry_run or not a.yes:
        tail = "dry run: nothing removed" if a.dry_run else "add --yes to remove them"
        return out(a, {"would_remove": [e["id"] for e in rows], "removed": []},
                   "\n".join([f"would remove {what}:"] + lines + [tail]), 0)
    removed = curate.prune(rows)
    return out(a, {"would_remove": [e["id"] for e in rows], "removed": removed},
               "\n".join([f"removing {what}:"] + lines + [f"removed {len(removed)}"]), 0)
