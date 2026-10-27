"""tests.helpers.studio_fleet_rig -- Halo 3.0.5.0 "Fleet" R3: what the Studio
Fleet tests and tools/capture_fleet.py look at. One scratch home (the
shipped lineups, halo-dev-cycle active) with:

* an in-process Studio (the real routes and feed) running the fleet hub on
  loopback;
* this harness's REAL session (agent.loop.Session behind the real Controller
  and control socket, the scripted mock model of tests/helpers/fleet_rig.py)
  in a git repo `shop` on branch feature/basket: the main agent spawns an
  `implementer` (A) and a `researcher` (B); each writes a line, runs one tool
  and then waits in its next model call until the test opens its gate, so
  three agents are live as long as the test needs. B's third model call is
  recorded, so a steer typed in Studio is seen reaching B;
* a member harness `kali@lab` injected through the hub's own state
  (members.json + an announce), its link answering the hub's commands in a
  thread (tail, follow, steer, stop, pause, resume are recorded): one session
  on the same repo with its main agent waiting on a question and a reviewer
  that finished (R4: and an approval card it lets the hub answer);
* (R4) a finished past session of this harness, `PAST_SID`, with a reviewer
  sub-agent, in the state directory (studio_fleet_parts.seed_past).

Five agents in three states (running, waiting, done) across two harness
boxes. Every touched variable is restored and the home removed on close.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from tests.helpers.fleet_rig import text_step, tool_step, wait_for  # noqa: F401  (re-exported)
from tests.helpers.mock_openai import SCENARIOS, MockUpstream, ScriptedTurns
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.helpers.studio_fleet_member import MEMBER, MEMBER_SID, announce_body, answer, ask_frames, seed_caps
from tests.helpers.studio_fleet_parts import PAST_SID, held, make_session, quiet_health, recorded, said_then_tool, seed_past, spawn  # noqa: F401

ensure_default_provider_credentials()
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "HALO_FLEET_PRIVATE", "HALO_FLEET_PARENT")
STEER_SEEN = "focus on the discount rules"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, encoding="utf-8", errors="replace", timeout=60, check=True)


class StudioFleetRig:
    member_id = MEMBER
    rail = "&rail=open"  # 3.3.2.0 R1: the drivers read the Fleet tree, which lives in the expanded rail; captures set ""
    def __init__(self) -> None:
        self._saved = {k: os.environ.get(k) for k in _VARS}
        for k in ("BRIDGE_STATE_DIR", "HALO_FLEET_PRIVATE", "HALO_FLEET_PARENT"):
            os.environ.pop(k, None)
        self.root = Path(tempfile.mkdtemp(prefix="studio-fleet-"))
        os.environ["BRIDGE_TEST_HOME"] = str(self.root)
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        self.closers: list = []
        self.gates = {"a": threading.Event(), "b": threading.Event()}
        self.seen: dict = {"a": [], "b": [], "b3": []}
        self.member_cmds: list = []
        self._stop = threading.Event()
        from halo_harness.fleet import identity
        from halo_harness.providers.config import default_state_dir
        from halo_harness.teams_yaml import ensure_builtin_team_templates
        from halo_harness.theme import set_config_value
        self.state = Path(default_state_dir())
        self.state.mkdir(parents=True, exist_ok=True)
        ensure_builtin_team_templates(state_dir=self.state)
        for k, v in (("team", "halo-dev-cycle"), ("roles.enabled", True), ("agents.max_depth", 2), ("remote.enabled", False),
                     ("fleet.name", "you@studio")):
            set_config_value(k, v)
        identity.forget_cache()
        self.proj = self.root / "shop"
        self.proj.mkdir()
        (self.proj / "basket.py").write_text("def total(items):\n    return sum(i.price for i in items)\n", encoding="utf-8")
        (self.proj / "notes.md").write_text("# pricing\ndiscount before tax\n", encoding="utf-8")
        for args in (("init", "-q", "-b", "feature/basket"), ("config", "user.name", "t"), ("config", "user.email", "t@t"),
                     ("config", "commit.gpgsign", "false"), ("remote", "add", "origin", "git@github.com:acme/shop.git"),
                     ("add", "-A"), ("commit", "-q", "-m", "basket")):
            _git(self.proj, *args)
        self.past = seed_past(self.state, self.proj)
        self.closers.append(quiet_health())  # R4b: the Health panel's provider probes answer here
        self.mock = MockUpstream().start()
        self.closers.append(self.mock.stop)
        self._studio()
        self._member()
        self._session()

    # ---- Studio and its hub --------------------------------------------------
    def _studio(self) -> None:
        from halo_harness.studio.fleet_hub_api import start_hub
        from halo_harness.studio.server import start_server
        self.server = start_server(port=0, cwd=self.proj, state_dir=self.state)
        threading.Thread(target=self.server.serve_forever, daemon=True, name="rig-studio").start()
        self.closers.append(self.server.server_close)
        self.closers.append(self.server.shutdown)
        self.hub = start_hub(self.server, home=self.state, port=0, bind="127.0.0.1", name="studio-hub", tls_on=False)
        self.closers.append(self.hub.stop)

    def url(self, mode: str = "fleet", extra: str = "") -> str:
        from halo_harness.studio.server import url_for
        return url_for(self.server, mode).replace("#t=", f"&tour=off{self.rail}{extra}#t=")

    def api(self, method: str, path: str, body=None):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=30)
        try:
            conn.request(method, "/api/" + path, body=json.dumps(body).encode("utf-8") if body is not None else None,
                         headers={"Authorization": "Bearer " + self.server.token, "Content-Type": "application/json"})
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
        finally:
            conn.close()

    # ---- the member: kali@lab, injected through the hub's state ----------------
    def _member(self) -> None:
        from halo_harness import __version__
        rec = {"id": MEMBER, "name": "kali@lab", "host": "kali", "user": "kali", "version": __version__, "os": "linux",
               "share": "full", "allow_control": "all"}
        self.hub.pairing.add_member(rec, os.urandom(32))
        self.hub.state.reload(force=True)
        self.hub.state.announce(MEMBER, announce_body(rec))
        self.hub.state.frames(MEMBER, {"link": "rig-link", "frames": ask_frames()})  # R4: what its two cards ask
        link = self.hub.state.members[MEMBER].link("rig-link")
        link.streams = 1  # its SSE stream counts as open: the hub sends it commands

        def respond() -> None:
            while not self._stop.is_set():
                try:
                    doc = link.queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                if doc.get("type") != "command":
                    continue
                self.member_cmds.append(doc)
                self.hub.state.commands.reply(MEMBER, {"cid": doc["cid"], "state": "done", "result": answer(doc)})
        threading.Thread(target=respond, daemon=True, name="rig-member").start()
        seed_caps(self.hub, self.state, rec)  # 3.0.6.0 R6: both catalogs; the hub asks the member for its own

    # ---- this harness's session ---------------------------------------------------
    def _session(self) -> None:
        from halo_harness.controller import Controller
        from halo_harness.remote import runtime
        from tests.helpers.fake_remote_session import FakeRegistry
        g, s = self.gates, self.seen
        m_a = self.script("glm-5-coder", [said_then_tool("Reading the basket before I change the discount.", ("Bash", {"command": "git log --oneline -1", "description": "the last commit"}, "call_a1")),
                                          held(g["a"], tool_step(("Bash", {"command": "git status --short", "description": "what changed"}, "call_a2")), s["a"]),
                                          text_step("A done")])
        m_b = self.script("kimi-k3-research", [said_then_tool("Checking the pricing notes for the tax rule.", ("Bash", {"command": "git grep -n discount", "description": "where the discount is"}, "call_b1")),
                                               held(g["b"], tool_step(("Bash", {"command": "git show --stat HEAD", "description": "the last change"}, "call_b2")), s["b"]),
                                               recorded(text_step("Discount applies before tax; the notes agree."), s["b3"])])
        m_main = self.script("qwen3-lead", [tool_step(spawn("implementer", "Implement: apply the discount before tax in basket.py", m_a, "call_m1"),
                                                      spawn("researcher", "Research: what the pricing notes say about tax", m_b, "call_m2")),
                                            text_step("Both parts are in: the discount now applies before tax.")])
        self.session = self._make_session(m_main)
        self.controller = Controller(session=self.session, cwd=self.proj, registry=FakeRegistry()).start()
        self.closers.append(self._quit)
        self.act = runtime.start_for_controller(self.controller)
        self.controller.submit("Ship the basket discount fix")
        ok = wait_for(lambda: len([a for a in self.agents() if a.get("state") == "running" and a.get("agent_id") != "main"]) >= 2 and len(s["a"]) and len(s["b"]), 30)
        if not ok:
            raise RuntimeError(f"the rig's agents did not start: {self.agents()}")

    def script(self, name: str, steps: list) -> str:
        SCENARIOS[name] = ScriptedTurns(steps)
        self.closers.append(lambda: SCENARIOS.pop(name, None))
        return f"or:mock/{name}"

    def _make_session(self, model: str):
        return make_session(self.root, self.proj, self.mock, model)

    def agents(self) -> list:
        """This harness's agent tree, over the session's own socket."""
        from halo_harness.remote.client import ControlClient
        c = ControlClient(self.act.endpoint, self.act.server.token, timeout=5)
        try:
            return (c.call("agents").get("result") or {}).get("agents") or []
        finally:
            c.close()

    def agent(self, prefix: str) -> dict:
        return next((a for a in self.agents() if (a.get("task") or "").startswith(prefix)), {})

    def key(self, prefix: str) -> str:
        from halo_harness.fleet.identity import harness
        return f"{harness()['id']}|{self.act.session_id}|{self.agent(prefix).get('agent_id')}"

    def release(self, which: str) -> None:
        self.gates[which].set()

    def member_spawn(self, aid: str = "w3r4k5e6") -> None:
        """The member's lead spawns a verifier: an `agent_state` frame through the hub's own frame path (D13)."""
        row = {"agent_id": aid, "parent": "main", "name": "verifier", "role": "custom", "bio": "verifier", "lineup": "halo-dev-cycle",
               "model": "or:deepseek/deepseek-v4-flash", "kind": "member", "task": "Verify: run the basket suite", "since": time.time(),
               "state": "running", "turns": 0, "cost_usd": 0.0, "current": "Bash: pytest -q", "last_text": ""}
        self.hub.state.frames(MEMBER, {"link": "rig-link", "frames": [{"session_id": MEMBER_SID, "event": "agent_state", "agent_id": aid,
                                                                     "data": row, "ts": time.time()}]})

    # ---- teardown ---------------------------------------------------------------
    def _quit(self) -> None:
        for gate in self.gates.values():
            gate.set()
        try:
            self.controller.quit()
        except Exception:
            pass

    def close(self) -> None:
        from halo_harness.fleet import identity
        from halo_harness.remote import runtime
        self._stop.set()
        for gate in self.gates.values():
            gate.set()
        try:
            runtime.stop()
        except Exception:
            pass
        runtime._private_flag = None
        runtime._reopeners[:] = []
        for fn in reversed(self.closers):
            try:
                fn()
            except Exception:
                pass
        identity.forget_cache()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        time.sleep(0.2)
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> "StudioFleetRig":
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False
