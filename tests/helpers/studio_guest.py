"""tests.helpers.studio_guest -- 3.6.0.25 G: a Claude Code session (halo_harness/guest) in Studio's Session section,
in headless Chrome on the driver base (tests/helpers/chrome_driver.Driver), over an in-process Studio on a scratch
home and an in-process guest bridge fed hook lines (no Claude Code, no model). tests/test_studio_session.py runs it:

    python -m tests.helpers.studio_guest guest   Session on the guest: the header says "Claude Code" and "watch only",
                                                 no Prompt box (the watch-only line instead), Steer and Screenshot
                                                 disabled, no Steer box, the registry row;
                                                 3.6.0.26 H: a hand-out worker's card under main (its goal, its
                                                 model, its cost, Pause off, Stop on: a press stops that job); the
                                                 Explore sub-agent's Stop stays off (watch only);
                                                 then the bridge ends: its row leaves the list

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). Nothing is started but the in-process
Studio and bridge, both ended here."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

Q = "document.querySelector"


def _lines(proj: Path) -> list:
    base = {"session_id": "s-guest", "cwd": str(proj)}
    return [{**base, "hook_event_name": "SessionStart", "source": "startup"},
            {**base, "hook_event_name": "UserPromptSubmit", "prompt": "Find why the login page is slow today"},
            {**base, "hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_use_id": "g1",
             "tool_input": {"description": "Measure the page", "subagent_type": "Explore"}},
            {**base, "hook_event_name": "SubagentStart", "agent_id": "a1", "agent_type": "Explore"},
            {**base, "hook_event_name": "PreToolUse", "tool_name": "Grep", "tool_use_id": "q1",
             "tool_input": {"pattern": "login"}, "agent_id": "a1", "agent_type": "Explore"}]


def look(c, server, bridge) -> dict:
    from halo_harness.studio.server import url_for
    c.go(url_for(server, "session").replace("#t=", f"&tour=off&session={bridge.act.session_id}&prompt=1#t="))
    words = f"{Q}('[data-testid=\"prompt-to\"]')?.textContent || ''"
    try:
        out = {"head": c.wait(f"({words}).includes('watch only') && {words}", 40)}
    except TimeoutError as e:
        seen = c.js("JSON.stringify({to: " + words + ", prompt: !!" + Q + "('[data-testid=\"prompt-detail\"]'), "
                    "url: location.search, text: document.body.innerText.slice(0, 600)})")
        raise TimeoutError(f"{e}; the page: {seen}") from None
    out["watch_line"] = c.wait(f"{Q}('[data-testid=\"prompt-watch-only\"]')?.textContent", 15)
    out["prompt_input"] = c.js(f"!!{Q}('[data-testid=\"prompt-input\"]')")
    out["steer_disabled"] = c.js(f"{Q}('[data-testid=\"session-live-steer-open\"]')?.disabled")
    out["shot_disabled"] = c.js(f"{Q}('[data-testid=\"session-live-screenshot\"]')?.disabled")
    out["steer_box"] = c.js(f"!!{Q}('[data-testid=\"session-live-steer\"]')")
    from halo_harness.remote import registry
    out["row"] = next((r for r in registry.list_live() if r.get("kind") == "guest"), None)
    return out


AGENT = "document.querySelector('[data-panel=session-agent]')"


def _hop_to(c, name: str) -> str:
    """J (Session's hop key) until the Agent panel shows the agent whose name starts so; its name, or ''."""
    import time
    for _ in range(8):
        got = c.js(f"{AGENT}?.querySelector('.fa-name')?.textContent || ''")
        if str(got).startswith(name):
            return got
        c.js("window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j', bubbles: true})); 1")
        time.sleep(0.6)
    return ""


def worker(c, server, bridge) -> dict:
    from halo_harness.studio.server import url_for
    c.go(url_for(server, "session").replace("#t=", f"&tour=off&mode=session&session={bridge.act.session_id}&open=session-agent#t="))
    c.wait(f"!!{AGENT}", 40)
    out = {"worker_name": _hop_to(c, "Halo:")}
    q = lambda sel: f"{AGENT}?.querySelector('{sel}')"  # noqa: E731
    out["worker_stop_disabled"] = c.js(f"{q('[data-testid=fleet-stop]')}?.disabled")
    out["worker_pause_disabled"] = c.js(f"{q('[data-testid=fleet-pause]')}?.disabled")
    out["worker_cost"] = c.js(f"{q('.fa-cost')}?.textContent || ''")
    out["worker_task"] = c.js(f"{q('.fa-task p')}?.textContent || ''")
    out["worker_model"] = c.js(f"{q('.fa-meta')}?.textContent || ''")
    if out["worker_stop_disabled"] is False:
        c.click_on(q("[data-testid=fleet-stop]"))
        c.wait("!!document.querySelector('[data-testid=fleet-confirm-yes]')", 10)
        c.click_on("document.querySelector('[data-testid=fleet-confirm-yes]')")
        from tests.helpers.session_rig import wait_for
        out["stopped"] = wait_for(lambda: bridge.stops[:1] or None, 20)
    out["sub_name"] = _hop_to(c, "Explore")
    out["sub_stop_disabled"] = c.js(f"{q('[data-testid=fleet-stop]')}?.disabled")
    return out


def ends(c, server, bridge) -> dict:
    bridge.close()
    from tests.helpers.session_rig import wait_for
    from halo_harness.remote import registry
    gone = wait_for(lambda: not any(r.get("kind") == "guest" for r in registry.list_live()) and "gone", 20)
    return {"row_gone": gone, "spool_gone": not bridge.spool.exists() and not bridge.on.exists()}


class GuestDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        home = Path(tempfile.mkdtemp(prefix="guest-studio-"))
        proj = home / "proj"
        proj.mkdir()
        saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET")}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        os.environ.update(BRIDGE_TEST_HOME=str(home), BRIDGE_TEST_NO_BACKGROUND_NET="1")
        server = bridge = None
        try:
            from halo_harness.guest import note
            from halo_harness.guest.bridge import GuestBridge
            from halo_harness.studio.server import start_server
            bridge = GuestBridge(os.getpid(), proj).start()
            for d in _lines(proj):
                note.write(json.dumps(d).encode(), bridge.dir, bridge.claude_pid)
            bridge.poll()
            from halo_harness.agent.agent_registry import tree_for
            from halo_harness.guest.hand_out import HandOuts, Job
            jobs = HandOuts(proj, sid=bridge.act.session_id, directory=bridge.dir, claude_pid=bridge.claude_pid,
                            tree=tree_for(bridge.handle.session), state_dir=home / ".halo")
            task = {"goal": "Count the login tests", "mode": "read_only", "acceptance": [], "files": [], "turns": 12,
                    "minutes": 10, "wait": True}
            job = Job(jobs, task, "ol:qwen3:30b", "ollama:default", {"goal": task["goal"], "mode": "read_only"})
            bridge.stops = []
            job.stop = lambda why, polite_s=None: bridge.stops.append(why) or "the stop is asked"
            jobs.jobs[job.id] = job
            jobs._row(job)  # its row as a running hand-out (no worker process: no model here)
            bridge.handle.hand_outs = jobs
            server = start_server(port=0, cwd=proj, state_dir=home / ".halo")
            threading.Thread(target=server.serve_forever, daemon=True, name="guest-studio").start()
            args = (c, server, bridge)
            yield ((look, args), (worker, args), (ends, args))
        finally:
            if bridge is not None:
                bridge.close()
            if server is not None:
                for fn in (server.shutdown, server.server_close):
                    try:
                        fn()
                    except Exception:
                        pass
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


if __name__ == "__main__":
    sys.exit(GuestDriver(sys.argv[1:]).main())
