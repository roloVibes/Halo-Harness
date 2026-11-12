"""tests.test_replay_waits -- Halo 3.4.1.1 defects 52 and 62: a permission card's wait in a session's record.

52: a session without a terminal (its cards answered from Studio's Attention) logs the tool call a card asked about a
moment AFTER the card opened, so the replay read "1 agent writing files" inside main's card instead of "waiting on you".
The card's whole span is waiting now (live/history.py `_with_asks`), whoever answered it.
62: the report card's "What waited on you" summed `0 s` for those cards (the states around them), and an older
session's 17 cards were left out of the total; a card's mark says its own figure ("answered allow after 30 s"), which
the card now takes first (live/report_card.py `wait_secs`), so the total is the sum of every listed wait.
Run: python -m tests.test_replay_waits
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.replay_seed import SID, T0, seed  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@contextlib.contextmanager
def _home():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    with tempfile.TemporaryDirectory(prefix="halo-waits-") as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        try:
            from halo_harness.config.paths import bridge_home
            yield bridge_home()
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _headless(state: Path) -> Path:
    """The seed with main's asked-about Bash call logged at +22, inside its card (+20 to +26), as a headless session's is."""
    path = seed(state)
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows.insert(3, {"type": "assistant", "ts": T0 + 22, "content": [{"type": "tool_use", "id": "b1", "name": "Bash",
                                                                      "input": {"command": "rm -rf build"}}]})
    rows.insert(4, {"type": "tool_result", "ts": T0 + 27, "tool_use_id": "b1", "tool": "Bash", "content": "ok"})
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def _at(states: list, aid: str, t: float) -> str:
    hit = [s for s in states if s["agent_id"] == aid and s["t"] <= t + 1e-6]
    return hit[-1]["state"] + ("/" + str(hit[-1].get("tool")) if hit[-1].get("tool") else "") if hit else ""


@test
def test_a_card_answered_from_studio_reads_waiting_on_you(ctx: Ctx):
    from halo_harness.live import history
    with _home() as state:
        h = history.read(_headless(state))
        got = {t: _at(h["states"], "main", T0 + t) for t in (21, 23, 25.5, 26.5)}
        ctx.check(f"inside the card (+20 to +26) main waits on you; at the answer the Bash call runs, got {got}",
                  got[21] == got[23] == got[25.5] == "waiting" and got[26.5] == "running/Bash")


@test
def test_the_report_card_sums_every_listed_wait(ctx: Ctx):
    from halo_harness.live import replay_file as RF
    from halo_harness.live import report_card as RC
    from halo_harness.live.report_card_text import waited
    with _home() as state:
        _headless(state)
        p = RF.build(state, SID)
        c = RC.card(p, f"session:{SID}")
        secs = [w["secs"] for w in c["waits"]]
        ctx.check(f"the card's own 6 s and the question's 10 s, got {secs} total {c['waited_s']}",
                  secs == [6.0, 10.0] and c["waited_s"] == 16.0)
        ctx.check(f"the total line, got {waited(c)!r}", waited(c) == "In all 16 s waiting on you.")
        older = dict(p, marks=[{"t": T0 + 20, "kind": "ask", "agent_id": "main", "name": "main",
                                "text": "a permission card (answered allow after 108 s)"}] * 17)
        c = RC.card(older, "file:older")
        ctx.check(f"an older session's 17 cards count (108 s each), got {c['waited_s']}", c["waited_s"] == 17 * 108.0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
