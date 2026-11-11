"""The coach pack's doctor row (`contributes.doctor`, Halo 3.4.0.0 B2): `halo doctor` shows it under "From packs"
while the pack is enabled and granted `doctor`. One row: what the coach has and what it uses -- the applies it keeps,
the improvement library's entries, the model /improve drafts with -- or what is missing first: the Studio grants the
Coach panel needs (its module and its routes).
"""

from __future__ import annotations

from pathlib import Path


def _count(folder: Path, pattern: str) -> int:
    try:
        return sum(1 for _ in folder.glob(pattern))
    except OSError:
        return 0


def rows(ctx) -> list:
    from halo_harness.ext import is_granted
    from .improve.config import load_improve_config
    missing = [g for g in ("studio-script", "studio-routes") if not is_granted("coach", g)]
    if missing:
        return [{"ok": False, "text": f"the Coach panel in Studio waits for {' and '.join(missing)}",
                 "fix": "halo pack enable coach " + " ".join(f"--grant {g}" for g in missing)}]
    from .engine.coach_record import applies, folder
    base = folder(ctx.state_dir)
    cfg = load_improve_config()
    improve = (f"/improve drafts with {cfg.model or 'the small model'} over {cfg.since_days} days"
               if cfg.enabled else "/improve is off (packs.settings.coach.improve.enabled)")
    kept = [a for a in applies(ctx.state_dir) if not a.get("undone")]
    return [f"the coach is on: {len(kept)} apply(s) kept, {_count(base / 'library', '*/EXPERIENCE.md')} library "
            f"entry(s); {improve}"]
