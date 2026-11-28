"""tests.helpers.studio_guest -- 3.6.0.25 G: a Claude Code session (halo_harness/guest) in Studio's Session section,
in headless Chrome on the driver base (tests/helpers/chrome_driver.Driver), over an in-process Studio on a scratch
home and an in-process guest bridge fed hook lines (no Claude Code, no model). tests/test_studio_session.py runs it:

    python -m tests.helpers.studio_guest guest   Session on the guest: the header says "Claude Code" and "watch only",
                                                 no Prompt box (the watch-only line instead), Steer and Screenshot
                                                 disabled, the cost "not known", the agent rows of the bridge's tree;
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
    c.go(url_for(server, "session").replace("#t=", f"&tour=off&session={bridge.act.session_id}#t="))
    words = f"{Q}('[data-testid=\"prompt-to\"]')?.textContent || ''"
    out = {"head": c.wait(f"({words}).includes('watch only') && {words}", 40)}
    out["watch_line"] = c.wait(f"{Q}('[data-testid=\"prompt-watch-only\"]')?.textContent", 15)
    out["prompt_input"] = c.js(f"!!{Q}('[data-testid=\"prompt-input\"]')")
    out["steer_disabled"] = c.js(f"{Q}('[data-testid=\"session-live-steer-open\"]')?.disabled")
    out["shot_disabled"] = c.js(f"{Q}('[data-testid=\"session-live-screenshot\"]')?.disabled")
    out["steer_box"] = c.js(f"!!{Q}('[data-testid=\"session-live-steer\"]')")
    out["cost"] = c.js(f"{Q}('[data-testid=\"session-cost-guest\"]')?.textContent || ''")
    from halo_harness.remote import registry
    out["row"] = next((r for r in registry.list_live() if r.get("kind") == "guest"), None)
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
            server = start_server(port=0, cwd=proj, state_dir=home / ".halo")
            threading.Thread(target=server.serve_forever, daemon=True, name="guest-studio").start()
            args = (c, server, bridge)
            yield ((look, args), (ends, args))
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
