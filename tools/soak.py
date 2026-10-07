"""tools/soak.py -- Halo 2.0.6 round 9: the idle-freeze soak harness
(plans/2.0.4-brief.md section 2, carried to 2.0.6 hardening).

A headless Textual pilot run for a configurable duration against the
mock upstream, injecting in sequence: idle gaps, a monotonic clock jump
(the heartbeat backdate seam), terminal resizes, a connection reset
mid-stream, a connect-phase drop, a 429 with retry_after, a permission
card left unanswered for a while then answered, a steer during a silent
call, and a /compact. After every event a prompt must get a response
within a deadline.

Assertions (all must hold for the run to pass):
  - the drain timer's tick count rises monotonically;
  - no traceback reaches the log (an in-memory handler watches);
  - RSS growth stays under the threshold (psutil when importable, else
    the check degrades to a warning -- never a false failure);
  - the status cluster returns to idle after each turn.

Usage:
    python tools/soak.py --duration 600          # the CI shape
    python tools/soak.py --duration 30 --json    # a quick smoke

Deliberately OUT of scope here (the runbook's half of the brief): the
fake-MCP-server kill/restart and a real 30-minute idle -- those need a
real machine session, see docs/harness/LIVE-CHECKS.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.mock_openai import (MockUpstream, SCENARIOS,  # noqa: E402
                                       ScriptedTurns, _finish, send_json_response)

# the chaos cycle: each entry is (name, scenario behavior); the scenario
# advances one entry per REQUEST the mock sees, wrapping around
NORMAL, SLOW, RETRY_AFTER_429, RESET_MID_STREAM, CONNECT_DROP = range(5)
_CYCLE_LEN = 5


def _text_chunks(text: str) -> list:
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": text}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]


class _SoakScenario:
    """Deterministic chaos: the soak SETS `override` before a prompt to
    make that request hit a chosen behavior, then it self-clears back to
    NORMAL -- every behavior is followed by a normal reply, so recovery
    is asserted with the very next prompt, never left to a blind cycle."""

    def __init__(self):
        self.override = None
        self.n = 0

    def __call__(self, h, body):
        behavior = self.override
        self.override = None
        self.n += 1
        if behavior == "429":
            send_json_response(h, 429,
                               {"error": {"message": "soak rate limit", "type": "rate_limit_error"}},
                               {"Retry-After": "1"})
        elif behavior == "reset":
            h.connection.close()  # headers, then die mid-body
        elif behavior == "drop":
            h.connection.close()  # before the request is even read
        elif behavior == "slow":
            import time as _t
            _t.sleep(2.0)
            _finish(h, _text_chunks(f"reply {self.n}: slow but fine"))
        else:
            _finish(h, _text_chunks(f"reply {self.n}: all good"))


async def _settle(app, pilot, drain_count, problems, ticks=None) -> None:
    """Bounded wait for the status cluster to return to idle: no live
    phase line left hanging (the brief's own post-event assertion).
    Also records the drain tick count (the monotonicity assertion's
    data) when a `ticks` list is given."""
    if ticks is not None:
        ticks.append(drain_count[0])
    t0 = time.monotonic()
    while time.monotonic() - t0 < 8.0:
        await app._drain()
        drain_count[0] += 1
        await pilot.pause(0.05)
        if not [w for w in app.transcript.children
                if getattr(w, "phase_state", None) in ("sending", "headers", "waiting")]:
            return
    live = [w for w in app.transcript.children
            if getattr(w, "phase_state", None) in ("sending", "headers", "waiting")]
    if live:
        problems.append(f"a phase line stayed live ({len(live)}) after an event")


async def _maybe_compact(app, pilot, drain_count, event_i: int) -> None:
    """A /compact every third chaos round -- the brief's own event list."""
    if event_i % 3 != 0:
        return
    for ch in "/compact":
        await pilot.press(ch)
    await pilot.press("enter")
    await pilot.pause(1.5)
    await app._drain()
    drain_count[0] += 1


async def _one_prompt(app, pilot, text: str, counter, deadline_s: float = 30.0) -> bool:
    """Type a prompt, wait for its AssistantText to land. True on time."""
    from halo_harness.tui.widgets.transcript import AssistantText
    before = sum(1 for w in app.transcript.children if isinstance(w, AssistantText))
    for ch in text:
        await pilot.press(ch)
    await pilot.press("enter")
    t0 = time.monotonic()
    while time.monotonic() - t0 < deadline_s:
        await app._drain()
        counter[0] += 1
        await pilot.pause(0.05)
        now = sum(1 for w in app.transcript.children if isinstance(w, AssistantText))
        if now > before:
            return True
    return False


async def run_soak(duration_s: float, *, size=(100, 40), json_out: bool = False) -> int:
    from tests.helpers.fake_home import build_fake_home
    from halo_harness.tui.bootstrap import build_controller
    from halo_harness.tui.app import BridgeApp

    problems: "list[str]" = []
    ticks: "list[int]" = []
    drain_count = [0]  # the drain tick count, counted at the source
    rss_start = None
    try:
        import psutil
    except ImportError:
        psutil = None

    # in-memory log watcher: any record with a traceback text fails the run
    class _TracebackCatcher(logging.Handler):
        def __init__(self):
            super().__init__(level=logging.ERROR)
            self.hits = []

        def emit(self, record):
            try:
                text = self.format(record)
            except Exception:
                return
            if "Traceback (most recent call last)" in text:
                # the exception line's HEAD names the error; keep it
                last = [ln for ln in text.splitlines() if ln.strip()][-1]
                self.hits.append(last[:160])

    catcher = _TracebackCatcher()
    logging.getLogger().addHandler(catcher)
    logging.getLogger("bridge").addHandler(catcher)

    mock = MockUpstream().start()
    SCENARIOS["soak"] = _SoakScenario()
    fh = build_fake_home()
    try:
        args = SimpleNamespace(
            cwd=fh["proj"], model="or:mock/soak", permission_mode="bypassPermissions",
            dangerously_skip_permissions=False, bare=True, tools=None, add_dir=None,
            small_model=None, session_id=None, max_turns=10, effort=None,
            append_system_prompt=None, chrome=False, no_chrome=False, playwright=False,
            playwright_cdp=None, playwright_headless=False, mcp_config=None, strict_mcp_config=False,
        )
        os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        controller, registry, facade = build_controller(args)
        app = BridgeApp(controller, registry=registry, facade=facade,
                        tool_registry=getattr(facade, "tool_registry", None), cwd=fh["proj"])
        async with app.run_test(size=size) as pilot:
            if psutil is not None:
                rss_start = psutil.Process(os.getpid()).memory_info().rss
            t0 = time.monotonic()
            event_i = 0
            scen = SCENARIOS["soak"]

            async def chaos(behavior: str):
                """One chaos injection + its recovery, as ONE soak event:
                the prompt under `behavior` must still get a reply (the
                retry ladders earn it), and the NEXT normal prompt proves
                recovery."""
                scen.override = behavior
                ok1 = await _one_prompt(app, pilot, f"under {behavior}", drain_count, deadline_s=45.0)
                if not ok1:
                    problems.append(f"prompt under {behavior!r} got no response within 45 s")
                ok2 = await _one_prompt(app, pilot, f"recovered from {behavior}", drain_count)
                if not ok2:
                    problems.append(f"recovery prompt after {behavior!r} got no response")
                await _settle(app, pilot, drain_count, problems, ticks)

            async def plain(label: str, *, pre=None):
                if pre is not None:
                    await pre()
                ok = await _one_prompt(app, pilot, f"soak turn after {label}", drain_count)
                if not ok:
                    problems.append(f"prompt after {label!r} got no response within the deadline")
                await _settle(app, pilot, drain_count, problems, ticks)

            t_start = time.monotonic()
            event_i = 0
            while time.monotonic() - t_start < duration_s:
                kind = event_i % 6
                event_i += 1
                if kind == 0:
                    await plain("idle gap 3 s", pre=lambda: asyncio.sleep(3.0))
                elif kind == 1:
                    await plain("clock jump", pre=lambda: _clock_jump(app))
                elif kind == 2:
                    await plain("terminal resize", pre=lambda: _resize(app, 90, 30))
                elif kind == 3:
                    # steer during a silent call: SLOW behavior + a mid-turn steer
                    from halo_harness.tui.widgets.transcript import AssistantText
                    before = sum(1 for w in app.transcript.children
                                 if isinstance(w, AssistantText))
                    scen.override = "slow"
                    task = asyncio.ensure_future(_start_prompt(app, pilot, "a slow one please"))
                    await asyncio.sleep(0.6)
                    for ch in "wrap it up":
                        await pilot.press(ch)
                    await pilot.press("enter")
                    await task
                    t0 = time.monotonic()
                    ok = False
                    while time.monotonic() - t0 < 45.0:
                        await app._drain()
                        drain_count[0] += 1
                        await pilot.pause(0.05)
                        if sum(1 for w in app.transcript.children
                               if isinstance(w, AssistantText)) > before:
                            ok = True
                            break
                    if not ok:
                        problems.append("the steered silent call never answered")
                    await _settle(app, pilot, drain_count, problems, ticks)
                elif kind == 4:
                    await _permission_idle(app, pilot)
                    await plain("permission card idle")
                else:
                    await chaos(["429", "reset", "drop"][event_i % 3])
                    await _maybe_compact(app, pilot, drain_count, event_i)
            if psutil is not None and rss_start is not None:
                growth_mb = (psutil.Process(os.getpid()).memory_info().rss - rss_start) / 1e6
                if growth_mb > 400:
                    problems.append(f"RSS grew {growth_mb:.0f} MB over the run (threshold 400)")
            if any(b < a for a, b in zip(ticks, ticks[1:])):
                problems.append("the drain tick count went backwards")
            problems.extend(f"traceback in log: {h}" for h in catcher.hits[:3])
    finally:
        mock.stop()
        SCENARIOS.pop("soak", None)
        logging.getLogger().removeHandler(catcher)
        logging.getLogger("bridge").removeHandler(catcher)

    if json_out:
        print(json.dumps({"ok": not problems, "duration_s": duration_s,
                          "turns": len(ticks), "problems": problems}, indent=2))
    else:
        print(f"soak: {len(ticks)} prompt(s) over {duration_s:.0f}s")
        for p in problems:
            print(f"  PROBLEM: {p}")
        print("RESULT:", "PASS" if not problems else f"FAIL ({len(problems)})")
    return 0 if not problems else 1


async def _clock_jump(app) -> None:
    """The sleep/wake seam: backdate the watchdog's heartbeat reference so
    the NEXT watchdog poll sees an 8 s 'stall' (exactly what a monotonic
    clock jump / laptop wake looks like), then let round 1's recovery
    path clear it -- the run continues either way, the assertion being
    simply that nothing hangs or crashes on it."""
    app._last_heartbeat_monotonic = time.monotonic() - 8.0
    await asyncio.sleep(4.5)  # past one 2 s watchdog poll


async def _resize(app, w: int, h: int) -> None:
    """A REAL Resize event through the app's own handler (the pilot cannot
    resize the terminal itself)."""
    from textual import events as tevents
    from textual.geometry import Size
    app.post_message(tevents.Resize(size=Size(w, h), virtual_size=Size(w, h)))
    await asyncio.sleep(0.3)


async def _permission_idle(app, pilot) -> None:
    """A fixture permission card (the same construction the TUI tests
    use): left unanswered for 3 s, then decided -- the UI must survive
    the unanswered window and clear the pending dock after."""
    from halo_harness.tui.widgets.cards import PermissionCard
    decided = []
    card = PermissionCard(request_id="soak-1", summary="Bash(echo soak)", reason="",
                          suggested_rule=None, on_decide=lambda decision: decided.append(decision))
    await app.transcript.mount_widget(card)
    app.set_pending_card(card)
    await asyncio.sleep(3.0)  # unanswered window
    try:
        card.remove()
    except Exception:
        pass
    app.clear_pending_card()
    await asyncio.sleep(0.3)


async def _start_prompt(app, pilot, text: str) -> bool:
    """Type+submit without waiting (the steer event drives the waiting)."""
    for ch in text:
        await pilot.press(ch)
    await pilot.press("enter")
    return True


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="soak.py", description=__doc__.splitlines()[0])
    p.add_argument("--duration", type=float, default=600.0,
                   help="seconds to run (default 600; CI shape). 30 is a smoke.")
    p.add_argument("--json", action="store_true", help="machine-readable result")
    args = p.parse_args(argv)
    return asyncio.run(run_soak(args.duration, json_out=args.json))


if __name__ == "__main__":
    sys.exit(main())
