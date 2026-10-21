"""halo_harness.start.fresh -- is this a fresh home (Halo 3.1.1.0 R1)? Studio
shows its "Start here" overlay on one.

A home is fresh while it has no lineup of its own (only the shipped lineups
or their untouched copies, and none active) and no run (no Orchestra run in
Studio's repo, no `halo start` sample repo under `~/.halo/start/`). "Just
look around" is remembered for the home in `~/.halo/start/dismissed.json`,
so every browser and every Studio on this home stays quiet after it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

DISMISSED = "dismissed.json"


def start_root(state_dir) -> Path:
    return Path(state_dir) / "start"


def dismissed(state_dir) -> bool:
    return (start_root(state_dir) / DISMISSED).is_file()


def dismiss(state_dir) -> None:
    root = start_root(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / DISMISSED).write_text(json.dumps({"ts": round(time.time(), 3)}), encoding="utf-8")


def own_lineups(cwd, state_dir) -> "list[str]":
    """The lineups that are yours: not shipped and not an untouched copy of a shipped one."""
    from halo_harness import teams_yaml as T
    from halo_harness.packs.names import read_only_source
    from halo_harness.studio import model as M
    out = []
    for name in T.list_team_templates(cwd=cwd, state_dir=state_dir):
        row = M.lineup_summary(name, cwd=cwd, state_dir=state_dir) or {}
        if row and not read_only_source(row.get("scope")) and not row.get("shipped_copy"):  # 3.2.0.0 R1: packs too
            out.append(name)
    return out


def sample_repos(state_dir) -> "list[Path]":
    try:
        return sorted(p for day in start_root(state_dir).iterdir() if day.is_dir()
                      for p in day.iterdir() if p.is_dir() and p.name.startswith("basket"))
    except OSError:
        return []


def orchestra_runs(cwd) -> int:
    from halo_harness.orchestra.goal import list_runs
    from halo_harness.studio.orchestra_model import repo_of
    try:
        return len(list_runs(repo_of(cwd)))
    except Exception:
        return 0


def active_team() -> str:
    from halo_harness.theme import get_config_value
    return str(get_config_value("team", "") or "")


def status(cwd, state_dir) -> dict:
    """`{fresh, dismissed, show, own_lineups, active_team, runs, starts}`; `show` = fresh and not dismissed."""
    own = own_lineups(cwd, state_dir)
    team = active_team()
    runs = orchestra_runs(cwd)
    starts = len(sample_repos(state_dir))
    fresh = not own and not team and runs == 0 and starts == 0
    gone = dismissed(state_dir)
    return {"fresh": fresh, "dismissed": gone, "show": fresh and not gone, "own_lineups": own, "active_team": team,
            "runs": runs, "starts": starts}
