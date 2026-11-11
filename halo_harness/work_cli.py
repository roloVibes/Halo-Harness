"""halo_harness.work_cli -- `halo work` (Halo 3.1.2.0 R1, docs/WORK.md).

    halo work [RUN] [--json]

Prints the units of any run of any kind -- an Orchestra run, a fleet
mission or the supervisor's queue -- as one table (work/report.py's rows).
RUN is a run folder, a run id, or an id prefix; with no RUN, the latest
Orchestra run of this repo, else the latest mission.
`--json` prints the rows. Read only: nothing is written, no model is called.
Exit codes: 0 the table, 1 no such run, 2 usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


def _resolve(ref: Optional[str], repo: Path) -> Optional[Path]:
    """The run folder `ref` names (a path, or a run id / prefix of any kind);
    with no `ref`, the latest run anywhere. A `ref` that matches nothing is None."""
    from halo_harness.work.store import run_kind
    if ref:
        p = Path(ref)
        if run_kind(p):
            return p
        for finder in (_orchestra, _mission, _supervise):
            hit = finder(ref, repo)
            if hit is not None:
                return hit
        return None
    for latest in (_latest_orchestra, _latest_mission, _latest_supervise):
        hit = latest(repo)
        if hit is not None:
            return hit
    return None


def _orchestra(ref, repo):
    from halo_harness.orchestra import goal as G
    return G.resolve_run(repo, ref)


def _mission(ref, repo):
    from halo_harness.peers import identity
    from halo_harness.packs import fleet_door  # 3.4.0.0 C: missions are the fleet pack's (none when it is off)
    M, S = fleet_door.module("fleet/mission.py"), fleet_door.module("fleet/mission_store.py")
    if M is not None and S is not None and M.valid_id(ref):
        folder = S.folder(identity.home(), ref)
        return folder if (folder / "mission.json").is_file() else None
    return None


def _latest_orchestra(repo):
    from halo_harness.orchestra import goal as G
    return G.resolve_run(repo, None)


def _latest_mission(repo):
    from halo_harness.peers import identity
    from halo_harness.packs import fleet_door  # 3.4.0.0 C: missions are the fleet pack's (none when it is off)
    S = fleet_door.module("fleet/mission_store.py")
    docs = S.all_docs(identity.home()) if S is not None else []
    return S.folder(identity.home(), docs[-1]["id"]) if docs else None


def _supervise(ref, repo):
    """`goals` or `supervise` names the whole queue; a goal id finds it too (3.1.8.0 R1)."""
    from halo_harness.supervise import queue
    folder = queue.root()
    if ref in ("goals", "supervise") or (queue.resolve(folder.parent, ref) is not None):
        return folder if (folder / queue.MARKER).is_file() else None
    return None


def _latest_supervise(repo):
    from halo_harness.supervise import queue
    folder = queue.root()
    return folder if (folder / queue.MARKER).is_file() and queue.all_goals(folder.parent) else None


def cmd_work(argv: list, repo: Optional[Path] = None) -> int:
    p = argparse.ArgumentParser(prog="halo work", description="The units of a run, as one table (docs/WORK.md).")
    p.add_argument("run", nargs="?", default=None, help="a run folder, a run id or an id prefix (default: the latest run)")
    p.add_argument("--json", action="store_true", help="the unit rows as JSON")
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    repo = Path(repo or Path.cwd())
    run_dir = _resolve(a.run, repo)
    if run_dir is None:
        print(f"halo work: no run {a.run!r}" if a.run else "halo work: no run here", file=sys.stderr)
        return 1
    from halo_harness.work.report import rows, table
    from halo_harness.work.store import UnitStore
    store = UnitStore(run_dir)
    unit_rows = rows(run_dir)
    if a.json:
        print(json.dumps({"run": Path(run_dir).name, "kind": store.run_kind, "units": unit_rows}, indent=2, default=str))
        return 0
    print(f"{store.run_kind} run {Path(run_dir).name}: {len(unit_rows)} unit(s)")
    print(table(unit_rows))
    return 0
