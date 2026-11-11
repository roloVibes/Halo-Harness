"""The coach pack's knowledge writer (Halo 3.1.8.0 R4 as knowledge/writers.py `applied`; the coach pack's own since
3.4.0.0 B2): the coach's Apply -> a decision, what changed on which bio, lineup or plan, why, and the Undo id (by
coach). It writes through the core's knowledge store (`knowledge.writers`' `enabled`, the store's `write`), so
`knowledge.write: false` turns it off like every other writer; it never raises and returns the entries it wrote.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.ext import core


def applied(result: dict, s: dict, run_dir, row: dict, state_dir=None) -> list:
    W = core.module("knowledge.writers")
    if not W.enabled():
        return []
    try:
        return _applied(result, s, run_dir, row, state_dir) or []
    except Exception:  # the Apply goes on without its knowledge entry
        return []


def _applied(result: dict, s: dict, run_dir, row: dict, state_dir=None) -> list:
    one_line = core.get("knowledge.store", "one_line")
    write = core.get("knowledge.store", "write")
    from .coach_citations import shown
    a = s.get("apply") or {}
    changes = [c for c in (a.get("changes") or []) if isinstance(c, dict)] if a.get("target") == "overlay" else [a]
    what = "; ".join(shown(c) for c in changes[:3]) + (f" (+{len(changes) - 3} more)" if len(changes) > 3 else "")
    files = ", ".join(Path(f.strip()).name for f in str(row.get("file") or "").split(", ") if f.strip())
    undo = row.get("apply_id") or ""
    why = [str(w) for w in s.get("why") or []]
    body = (f"What: the coach's Apply changed {what}" + (f" (written to {files})" if files else "") + ".\n\n"
            f"Why: {one_line(s.get('text'), 600)}" + (f" -- {'; '.join(why[:4])}" if why else "") + "\n\n"
            f"Undo: `halo coach --undo {undo}` puts it back" + (f"; library entry {row['entry']}." if row.get("entry") else "."))
    try:
        from .coach import run_kind
        from .coach_experience import project_of
        repo = project_of(run_dir, run_kind(run_dir) or "").get("name") or ""
    except Exception:
        repo = ""
    return [write("decision", f"coach: {what}", body=body, evidence=why, by="coach", run=str(result.get("run") or ""),
                  repo=repo, alternatives=["leave it as it was"], tags=["coach", "apply", s.get("kind") or ""],
                  state_dir=state_dir)]
