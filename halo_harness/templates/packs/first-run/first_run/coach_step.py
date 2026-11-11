"""The guided first run's coach lines in step 6 (Halo 3.4.0.0 B2: the coach left the core for the coach pack).

While the coach pack is enabled with its verb (`cli:coach`), step 6 runs the pack's own verb as a child, `halo coach
<run> --json`, and prints one line per suggestion with how to see and apply the cards; with the pack off it prints
one line saying the coach is a pack and how to turn it on. The first-run pack never imports the coach pack.
"""

from __future__ import annotations

import json
import subprocess

from . import steps as S


def coach_on() -> bool:
    from halo_harness.ext import is_granted
    try:
        return is_granted("coach", "cli:coach")
    except Exception:
        return False


def _lines(run) -> "list[str]":
    from halo_harness.ext import host
    p = subprocess.run(host.halo_command() + ["coach", str(run.run_dir), "--json"], capture_output=True, text=True,
                       cwd=str(run.repo or run.run_dir), timeout=120, env=host.child_env())
    if p.returncode != 0:
        last = ((p.stderr or p.stdout).strip().splitlines() or ["no card"])[-1]
        return [f"coach: {last}"]
    run.coach = json.loads(p.stdout or "{}")
    rows = [s for s in run.coach.get("suggestions") or [] if isinstance(s, dict)]
    return [f"coach: {len(rows)} suggestion(s) (halo coach {run.run_dir} shows the cards)"] + \
        [f"  [{s.get('id')}] {s.get('text') or s.get('title') or ''}" for s in rows]


def card(run) -> "list[str]":
    """The lines after the report: the coach's, or the one line that it is a pack."""
    if not coach_on():
        return ["", S.COACH_OFF]
    try:
        return [""] + _lines(run) + ["", S.COACH_APPLY]
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        return ["", f"coach: {e}", "", S.COACH_APPLY]
