"""tests.test_offline_promise -- Halo 3.3.7.0 R2 deliverable 7, G15: the session's offline promise
(agent/offline_promise.py) on `/cost`, `halo session show` and Studio's `GET local/offline`:

1. every call to this machine's own server: "100 % local -- 0 tokens left this machine";
2. local calls to a LAN server: "100 % local -- 2 calls left this machine, all on the LAN: pc x 2";
3. a cloud call too: "67 % local -- 1 call left this machine: openrouter x 1"; each local call's line names its host;
4. `/cost` carries the line; `halo session show <id>` prints it and the per-call lines; `local/offline` answers it.
Run: python -m tests.test_offline_promise
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home, line  # noqa: E402

test, TESTS = new_registry()
HERE = {"name": "box", "url": "http://127.0.0.1:11999"}
LAN = {"name": "pc", "url": "http://192.0.2.10:11434"}


def _log(state: Path, sid: str, models: list) -> Path:
    p = state / "sessions" / "proj" / f"{sid}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"type": "meta", "cwd": "."}] + [{"type": "usage", "usage": {"input_tokens": 10}, "model": m,
                                              "route": m.split("/", 1)[0] if not m.startswith("ol:") else "ollama"}
                                             for m in models]
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return p


def _calls(home, host: dict, n: int, sid: str) -> None:
    home.calls(*[line(host=host, model="qwen3.5:9b", session=sid, ago=60 - i) for i in range(n)])


@test
def test_the_three_lines(ctx: Ctx):
    from halo_harness.agent.offline_promise import promise
    with Home(hosts=(HERE, LAN)) as home:
        log = _log(home.state, "s-here", ["ol:qwen3.5:9b@box"] * 2)
        _calls(home, HERE, 2, "s-here")
        got = promise(home.state, "s-here", log_path=log)
        ctx.check(f"all here, got {got['line']!r}", got["line"] == "100 % local -- 0 tokens left this machine")
        ctx.check(f"each call names its host, got {got['per_call']}", got["per_call"]
                  and all("-> box (this machine)" in x for x in got["per_call"]))
        log = _log(home.state, "s-lan", ["ol:qwen3.5:9b@pc"] * 2)
        _calls(home, LAN, 2, "s-lan")
        got = promise(home.state, "s-lan", log_path=log)
        ctx.check(f"on the LAN, got {got['line']!r}", got["line"] == "100 % local -- 2 calls left this machine, all on the LAN: pc x 2")
        log = _log(home.state, "s-mix", ["ol:qwen3.5:9b@box", "ol:qwen3.5:9b@box", "openrouter/qwen/qwen3-coder"])
        _calls(home, HERE, 2, "s-mix")
        got = promise(home.state, "s-mix", log_path=log)
        ctx.check(f"a cloud call, got {got['line']!r}", got["line"] == "67 % local -- 1 call left this machine: openrouter x 1")


@test
def test_cost_session_show_and_studio(ctx: Ctx):
    from halo_harness.agent.offline_promise import badge_line
    from halo_harness.session_trace_cli import cmd_session
    with Home(hosts=(HERE,)) as home:
        log = _log(home.state, "s-show", ["ol:qwen3.5:9b@box"])
        _calls(home, HERE, 1, "s-show")
        session = SimpleNamespace(session_id="s-show", log=SimpleNamespace(path=log, session_id="s-show"))
        ctx.check(f"/cost's line, got {badge_line(session)!r}", badge_line(session) ==
                  "Offline promise: 100 % local -- 0 tokens left this machine")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_session(["show", "s-show"])
        ctx.check(f"halo session show, got {out.getvalue()!r}", rc == 0 and "100 % local" in out.getvalue()
                  and "-> box (this machine)" in out.getvalue())
        from halo_harness.studio.api import Request, dispatch
        code, got = dispatch(Request(method="GET", path="local/offline", query={"session": "s-show"}, body={},
                                     cwd=home.root, state_dir=home.state, server=None))
        ctx.check(f"local/offline, got {code} {got.get('line')!r}", code == 200 and got["line"].startswith("100 % local"))
        empty = SimpleNamespace(session_id="s-none", log=SimpleNamespace(path=home.state / "nope.jsonl", session_id="s-none"))
        ctx.check("no call yet: no line", badge_line(empty) == "")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
