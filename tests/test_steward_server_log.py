"""tests.test_steward_server_log -- Halo 3.3.4.0 R2: the server-log tail
and the events (halo_harness/ollama_steward/server_log.py, server_rules.py,
server_context.py, server_events.py).

1. a fixture with every rule's line -> one event per rule, R1's corrections
   in: the window sent parsed from `limit=` (4,096 for 2,050), a 500 beside
   "srv stop: cancel task" is `cancel-task`, a 500 after "no user query" is
   that event's own, the aborted load + "Load failed ... context canceled" +
   499 are one `client-gave-up`, three 500s in 3 minutes are a `retry-loop`;
2. R1's Windows / Linux journal / Mac fixtures -> their startups (the
   journald prefix tolerated);
3. fake `/api/ps` sequences through `watch` -> loaded, reloaded at a new
   window, unloaded, a spill; three failed `/api/version` -> server-down;
   a stalled request and a slow load from the clock;
4. the tail: the first read starts at the end, `from_start` at the top, a
   rotation finishes the old file then reads the new one; journald through
   a fake runner (`--since`, then `--after-cursor`);
5. the quiet period: every event written, `notify` once per kind per 10 min.
Never a real server; the PC's log is never read here.
Run: python -m tests.test_steward_server_log
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FIX = Path(__file__).resolve().parent / "fixtures" / "ollama_steward"


def _events(name: str) -> list:
    from halo_harness.ollama_steward.server_context import Rules
    rules = Rules()
    lines = (FIX / name).read_text(encoding="utf-8").splitlines()
    return [e for line in lines for e in rules.feed(line)] + rules.flush()


def _home() -> Path:
    return Path(tempfile.mkdtemp(prefix="l2_srvlog-")) / ".halo"


@test
def test_every_rule_fires_once_with_r1s_corrections(ctx: Ctx):
    evs = _events("every-rule.txt")
    kinds = [e["kind"] for e in evs]
    want = ["startup", "cpu-spill", "cpu-spill", "slow-load", "prompt-trimmed", "reply-cut", "window-full",
            "no-user-query", "cancel-task", "retry-loop", "client-gave-up", "load-failed", "gpu-memory", "queue-full",
            "other-error", "http-500"]
    ctx.check(f"one event per rule, got {kinds}", kinds == want)
    by = {e["kind"]: e for e in evs}
    t = by.get("prompt-trimmed", {})
    ctx.check(f"prompt-trimmed: limit 2050 is a 4,096 window sent, got {t.get('data')}",
              t.get("data", {}).get("window_sent") == 4096 and t["data"]["prompt"] == 23536
              and "bigger" in t.get("say", "") and "smaller window" not in t.get("say", ""))
    ctx.check("cpu-spill keeps the numbers", evs[1]["data"] == {"offloaded": 40, "layers": 49}
              and evs[2]["data"]["overflowing"] == 3)
    c = by.get("cancel-task", {})
    ctx.check(f"cancel-task: the client's timeout, not a server error, got {c.get('say')!r}",
              "not a server error" in c.get("say", "") and c.get("data", {}).get("seconds") == 28.46)
    g = by.get("client-gave-up", {})
    ctx.check(f"client-gave-up: one event during the load, a fast retry never helps, got {g.get('data')}",
              g.get("data", {}).get("during_load") is True and g["data"].get("status") == 499
              and "never helps" in g.get("say", "") and kinds.count("client-gave-up") == 1)
    ctx.check("the context-canceled Load failed is part of it; the runner's own is load-failed",
              kinds.count("load-failed") == 1 and "exit status 2" in by["load-failed"]["say"])
    ctx.check(f"retry-loop names the model, got {by.get('retry-loop')}",
              by.get("retry-loop", {}).get("model") == "qwen3.8:27b" and by["retry-loop"]["data"]["count"] == 3)
    ctx.check("every event has kind, severity, say, evidence", all(
        e["severity"] in ("info", "warn", "error") and e["say"] and e["evidence"] for e in evs))
    ctx.check("severities: a 500 is an error, a trim a warning, a startup info",
              by["http-500"]["severity"] == "error" and t["severity"] == "warn" and by["startup"]["severity"] == "info")


@test
def test_r1s_fixtures_give_their_startups_and_the_journald_prefix_is_read(ctx: Ctx):
    from halo_harness.ollama_steward.server_rules import classify, strip_prefix
    win = [e["kind"] for e in _events("windows-server.txt")]
    ctx.check(f"Windows: two starts, got {win}", win.count("startup") == 2)
    lin = [e["kind"] for e in _events("linux-journal.txt")]
    ctx.check(f"Linux journal: its start, got {lin}", lin.count("startup") == 1)
    mac = [e["kind"] for e in _events("mac-server.txt")]
    ctx.check(f"Mac: its start, got {mac}", mac == ["startup"])
    j = "Oct 26 08:00:09 gpubox ollama[812]: [GIN] 2026/10/26 - 08:00:09 | 499 |    4.2s |  192.0.2.30 | POST \"/api/chat\""
    ev = classify(j)
    ctx.check(f"a journald [GIN] 499 line, got {ev and ev['kind']}", ev is not None and ev["kind"] == "client-gave-up"
              and not strip_prefix(j).startswith("Oct"))


def _ps(*rows) -> dict:
    return {"models": [{"model": m, "size": s, "size_vram": v, "context_length": c, "expires_at": "x"}
                       for m, s, v, c in rows]}


@test
def test_ps_deltas_server_down_stall_and_slow_load_through_watch(ctx: Ctx):
    from halo_harness.ollama_steward import server_log
    from halo_harness.ollama_steward.server_events import read_events
    home = _home()
    log = home.parent / "server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("start\n", encoding="utf-8")
    g = 2 ** 30
    seq = [_ps(), _ps(("qwen3.8:27b", 20 * g, 20 * g, 32768)), _ps(("qwen3.8:27b", 21 * g, 19 * g, 65536)),
           _ps(), None, None, None, None]
    calls = {"n": 0}
    clock = {"t": 1_000_000.0}
    stop = threading.Event()

    def api(path):
        i = calls["n"]
        if path == "/api/ps":
            calls["n"] += 1
            if calls["n"] >= len(seq):
                stop.set()
            return seq[i] if i < len(seq) else None
        return {"version": "0.40.6"} if i < 4 else None

    def tick():
        clock["t"] += 30.0
        return clock["t"]

    host = type("H", (), {"name": "pc", "url": "http://127.0.0.1:11434"})()
    seen = []
    server_log.watch(home, host, stop, path=log, api=api, on_event=seen.append, tail_s=0, poll_s=0, clock=tick)
    kinds = [e["kind"] for e in seen]
    ctx.check(f"loaded, reloaded at a new window, a spill, unloaded, server-down, got {kinds}",
              kinds == ["loaded", "reloaded", "cpu-spill", "unloaded", "server-down"])
    rel = next((e for e in seen if e["kind"] == "reloaded"), {})
    ctx.check(f"the reload keeps both windows, got {rel.get('data')}",
              rel.get("data", {}).get("previous_context_length") == 32768 and rel["data"]["context_length"] == 65536)
    ctx.check("every event is in events.jsonl with the host", [e["kind"] for e in read_events(home)] == kinds
              and all(e["host"] == "pc" for e in read_events(home)))
    from halo_harness.ollama_steward.server_context import Rules
    r = Rules()
    r.feed('time=2026-10-26T09:00:00.000-05:00 level=INFO msg="starting llama-server" cmd="x"')
    t0 = r.clock
    ctx.check("no slow-load before 3 minutes", r.tick(t0 + 170) == [])
    ctx.check("a load still running past 3 minutes is slow-load, once",
              [e["kind"] for e in r.tick(t0 + 190)] == ["slow-load"] and r.tick(t0 + 200) == [])
    r.feed("slot launch_slot_: id  0 | task 7 | processing task, is_child = 0")
    ctx.check("a request with no progress for 5 minutes is a stall",
              [e["kind"] for e in r.tick(t0 + 301)] == ["stall"])


@test
def test_the_tail_starts_at_the_end_reads_from_the_top_and_follows_a_rotation(ctx: Ctx):
    from halo_harness.ollama_steward.server_log import rotated_path, tail, tail_journal
    d = Path(tempfile.mkdtemp(prefix="l2_tail-"))
    log = d / "server.log"
    log.write_text("first start\nline a\n", encoding="utf-8")
    lines, st = tail(log, {})
    ctx.check(f"the first read starts at the end, got {lines}", lines == [])
    ctx.check("from the top with from_start", tail(log, {}, from_start=True)[0] == ["first start", "line a"])
    with open(log, "a", encoding="utf-8") as f:
        f.write("line b\npartial")
    lines, st = tail(log, st)
    ctx.check(f"then only the new whole lines, got {lines}", lines == ["line b"])
    with open(log, "a", encoding="utf-8") as f:
        f.write(" end\nline c\n")
    log.replace(rotated_path(log))
    log.write_text("second start\nline d\n", encoding="utf-8")
    lines, st = tail(log, st)
    ctx.check(f"a rotation: the old file's rest, then the new file, got {lines}",
              lines == ["partial end", "line c", "second start", "line d"])
    calls = []

    def runner(argv, timeout):
        calls.append(argv)
        return "line x\nline y\n-- cursor: s=abc;i=2\n" if len(calls) == 1 else "-- cursor: s=abc;i=3\n"

    lines, jst = tail_journal({}, runner=runner)
    ctx.check(f"journald: the unit's lines through the seam, got {lines}", lines == ["line x", "line y"]
              and calls[0][:3] == ["journalctl", "-u", "ollama"] and "--since" in calls[0])
    tail_journal(jst, runner=runner)
    ctx.check(f"then from the cursor, got {calls[1][-2:]}", calls[1][-2:] == ["--after-cursor", "s=abc;i=2"])


@test
def test_the_quiet_period_is_for_notifying_only(ctx: Ctx):
    from halo_harness.ollama_steward.server_events import QUIET_S, read_events, record_events
    from halo_harness.ollama_steward.server_rules import event
    home = _home()
    quiet: dict = {}
    t = 2_000_000_000.0
    a = record_events(home, [event("http-500", "x", "e", at=t), event("http-500", "y", "e", at=t + 60),
                             event("cpu-spill", "z", "e", at=t + 61)], host="pc", quiet=quiet)
    b = record_events(home, [event("http-500", "w", "e", at=t + QUIET_S + 1)], host="pc", quiet=quiet)
    ctx.check(f"notify: the first of a kind, not the second within 10 min, another kind, then again after, got "
              f"{[r['notify'] for r in a + b]}", [r["notify"] for r in a + b] == [True, False, True, True])
    rows = read_events(home)
    ctx.check(f"every event is written, got {len(rows)}", len(rows) == 4)
    ctx.check("filters: kind", [r["say"] for r in read_events(home, kind="cpu-spill")] == ["z"])
    raw = (home / "ollama" / "events.jsonl").read_text(encoding="utf-8")
    ctx.check("one JSON object per line, LF endings", "\r" not in raw
              and all(json.loads(x)["host"] == "pc" for x in raw.splitlines()))


if __name__ == "__main__":
    os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
