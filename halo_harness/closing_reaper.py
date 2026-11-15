"""halo_harness.closing_reaper -- the tiny process that ends what a hard-killed Halo started (Halo 3.6.0.0 R10, POSIX).

    python -I closing_reaper.py <owner pid> <owner start> <marker> <state dir> <package parent>

closing.ensure_reaper starts it (its own session, so a closed terminal or Ctrl+C never reaches it) at the owner's
first long-lived spawn. It waits for the owner -- its parent pid changes the moment the owner is gone, however it
went -- then stops the owner's ledger children that were not asked to stay and every process that carries the
owner's `HALO_OWNER` marker, and exits. The owner's own closing procedure kills it first on every way out that runs
Python, so it only ever acts after a hard kill. Never a pid that is not the owner's: a ledger entry is checked by
pid and start time, a marker match by its start time again before the kill.
"""

import os
import sys
import time


def main(argv: list) -> int:
    owner_pid, owner_start, mark, state_dir, parent = int(argv[0]), argv[1] or None, argv[2], argv[3], argv[4]
    if parent and parent not in sys.path:
        sys.path.insert(0, parent)
    while os.getppid() == owner_pid:
        time.sleep(0.2)
    from halo_harness import children as C
    from halo_harness import closing
    closing._STATE["me_pid"], closing._STATE["me_start"] = owner_pid, owner_start  # act as the owner's ledger reader
    try:
        rows = [e for e in closing._entries(state_dir) if e.get("owner_pid") == owner_pid
                and (not owner_start or not e.get("owner_start") or e.get("owner_start") == owner_start)
                and not closing.kept(e)]
        for e in rows:
            if C.provably_same(e["pid"], e.get("start_time")):
                closing._signal_tree(e["pid"], hard=False)
        closing._wait(rows, 0.8)
        for e in rows:
            if C.provably_same(e["pid"], e.get("start_time")):
                closing._signal_tree(e["pid"], hard=True)
        closing._wait(rows, 0.4)
        C.unregister([e["pid"] for e in rows if not C.alive(e) and e.get("source") != "local-servers"],
                     state_dir=state_dir)
    except Exception:
        pass
    closing.kill_marked(mark, bound_s=1.0)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
