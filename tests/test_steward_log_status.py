"""tests.test_steward_log_status -- Halo 3.3.6.0 R3 deliverable 2, "is logging live" (ollama_steward/log_status.py;
plans/local-model-fit-brief.md D3 item 16), with fixture ledgers and logs:

1. live (the newest line newer than the newest call minus 60 s), stale (calls the log never saw), quiet (nothing in
   15 minutes), missing (no log where Ollama writes it), unreadable (an ssh host whose read did not answer);
2. `debug: on` when debug-level lines appear; the debug window is a stated action Halo never takes;
3. the hardware card carries it (`log`, `log_path`, `readable`) and `halo ollama hardware` prints the line;
4. the Hosts page's card has the line with the path; the Logs page's groups mark each line.
Run: python -m tests.test_steward_log_status
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.logs_rig import LogsHome, T  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BOX = {"name": "box", "url": "http://127.0.0.1:9"}


def _box():
    from halo_harness.providers.ollama import resolve_ollama_hosts
    return next(h for h in resolve_ollama_hosts() if h.name == "box")


@test
def test_each_state(ctx: Ctx):
    from halo_harness.ollama_steward.log_status import status
    got = {}
    with LogsHome(hosts=[BOX, {"name": "pc", "url": "http://192.0.2.10:11434", "ssh": "example@192.0.2.10"}]) as h:
        got["missing"] = status(h.state, _box(), platform="win32")
        h.write_local(f'time={T(100)} level=INFO msg="a line"\n')
        h.call(BOX, "qwen3:8b", time.time() - 30)
        got["live"] = status(h.state, _box(), platform="win32")
        h.write_local(f'time={T(-600)} level=INFO msg="an old line"\n')
        os.utime(h.local_log, (time.time() - 900, time.time() - 900))
        got["stale"] = status(h.state, _box(), platform="win32")
        h.write_local(f'time={T(-1800)} level=INFO msg="older"\n')
        Path(h.state / "ollama" / "traffic.jsonl").unlink()
        got["quiet"] = status(h.state, _box(), platform="win32")
        from halo_harness.providers.ollama import resolve_ollama_hosts
        pc = next(x for x in resolve_ollama_hosts() if x.name == "pc")
        got["never"] = status(h.state, pc)
        fake = h.remote("pc", "linux-off")  # answers neither sh nor PowerShell: the ssh read failed
        got["unreadable"] = status(h.state, pc, read=True)
        _ = fake
    ctx.check(f"missing: no log where Ollama writes it, got {got['missing']['line']!r}", got["missing"]["state"] == "missing"
              and "no server log at" in got["missing"]["why"])
    ctx.check(f"live: a line newer than the call, got {got['live']['line']!r}", got["live"]["state"] == "live"
              and "last line" in got["live"]["line"] and "server.log" in got["live"]["path"])
    ctx.check(f"stale: the ledger has a call the log never saw, got {got['stale']['line']!r}", got["stale"]["state"] == "stale"
              and "the ledger has calls the log never saw" in got["stale"]["why"])
    ctx.check(f"quiet: nothing in 15 minutes, got {got['quiet']['line']!r}", got["quiet"]["state"] == "quiet")
    ctx.check(f"an ssh host never read says so, got {got['never']['line']!r}", got["never"]["state"] == "unreadable"
              and "not read yet" in got["never"]["why"])
    ctx.check(f"unreadable: the ssh read did not answer, got {got['unreadable']['line']!r}", got["unreadable"]["state"]
              == "unreadable" and "did not answer" in got["unreadable"]["why"])
    ctx.check(f"the tail command and the halo line, got {got['live']['tail_cli']!r}",
              got["live"]["tail_cli"].startswith("Get-Content -Wait -Tail 50") and got["live"]["halo_cli"]
              == "halo ollama log --host box --follow")


@test
def test_debug_is_said_and_never_set(ctx: Ctx):
    from halo_harness.ollama_steward.log_status import status
    with LogsHome(hosts=[BOX]) as h:
        h.write_local(f'time={T(100)} level=DEBUG source=sched.go:1 msg="a debug line"\n')
        st = status(h.state, _box(), platform="win32")
        env = dict(os.environ)
    ctx.check(f"debug: on when debug lines appear, got {st['line']!r}", st["debug"] is True and "debug: on" in st["line"])
    ctx.check(f"the debug window is a stated action, got {st['debug_action']!r}",
              st["debug_action"].startswith("set OLLAMA_DEBUG=1 and restart Ollama on box") and "request bodies" in
              st["debug_action"] and "turn it off after" in st["debug_action"])
    ctx.check("Halo never sets OLLAMA_DEBUG", "OLLAMA_DEBUG" not in env)


@test
def test_the_card_and_halo_ollama_hardware(ctx: Ctx):
    from halo_harness.ollama_steward.cli import cmd_ollama_hardware
    from halo_harness.ollama_steward.hardware import format_card, hardware_card
    with LogsHome(hosts=[BOX]) as h:
        log = h.write_local(f'time={T(100)} level=INFO msg="a line"\n')
        card = hardware_card(_box(), api=lambda p: None, runner=lambda argv, t: None)
        lines = format_card(card, host_name="box")
        code, out = h.cli(cmd_ollama_hardware, "--host", "box")
    ctx.check(f"the card carries the status, got {card.get('log')}", (card.get("log") or {}).get("state") in ("live", "quiet")
              and card.get("readable") is True and card.get("log_path") == str(log))
    ctx.check(f"format_card prints the line, got {[x for x in lines if x.startswith('log:')]}",
              any(x.startswith("log: ") and str(log) in x for x in lines))
    ctx.check(f"halo ollama hardware prints it, got {out!r}", code == 0 and "log: " in out)


@test
def test_the_hosts_card_and_the_groups(ctx: Ctx):
    from halo_harness.ollama_steward.log_status import group_of
    from halo_harness.studio.local_hosts_view import hosts
    with LogsHome(hosts=[BOX]) as h:
        h.write_local(f'time={T(100)} level=INFO msg="a line"\n')
        view = hosts(h.state)
    card = next((x for x in view["hosts"] if x["name"] == "box"), {})
    ctx.check(f"the Hosts page's card has the line with the path, got {card.get('log')}", (card.get("log") or {}).get("line")
              and "server.log" in card["log"]["path"])
    groups = {k: group_of(v) for k, v in {"fit": "load_tensors: offloaded 49/49 layers to GPU", "headroom":
              'msg="gpu memory" id=0 available="20.6 GiB"', "truncation": 'msg="truncating input prompt" limit=1',
              "failure": "CUDA error: an illegal memory access was encountered", "none": 'msg="a line"'}.items()}
    ctx.check(f"each line's group, got {groups}", groups == {"fit": "fit", "headroom": "headroom", "truncation": "truncation",
                                                            "failure": "failure", "none": None})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
