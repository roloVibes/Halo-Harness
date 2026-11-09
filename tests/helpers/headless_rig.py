"""tests.helpers.headless_rig -- Halo 3.3.11.0 R2: a session with no terminal under a scratch home, for
tests/test_headless_session.py, tests/test_sessions_new_api.py and the Chrome driver tests/helpers/
studio_headless.py.

* a fake home (tests/helpers/fake_home.py) as `BRIDGE_TEST_HOME`, `BRIDGE_TEST_NO_BACKGROUND_NET=1`,
  `OLLAMA_HOST=http://127.0.0.1:9`, every `HALO_*` / `BRIDGE_STATE_DIR` scrubbed from the child's environment;
* the remote tests' fake upstream (tests/helpers/mock_openai.MockUpstream on 127.0.0.1:0) with one scenario,
  `mock/headless`: a turn whose user text says "please ask" calls Write (`headless-made.txt` in the project,
  which the default permission mode asks about) and then answers "made it"; any other turn answers "pong from headless";
* `start()` runs `python -m halo_harness --headless --session-for studio` as a child; `studio()` starts an
  in-process Studio whose own launcher spawns one (`spawn_env()` gives it the fake upstream); `entry()` waits
  for a registry row; `client()` connects.

`close()` ends every child it knows (a shutdown first, then a kill), and `survivors()` says which pids still run:
the tests check it is empty. No real model, no LAN address.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from tests.helpers.fake_home import build_fake_home
from tests.helpers.fleet_rig import text_step, tool_step, wait_for
from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish

REPO = Path(__file__).resolve().parents[2]
MODEL = "or:mock/headless"
REPLY = "pong from headless"
ASK_TEXT = "please ask"


def _texts(body) -> str:
    out = []
    for m in (body or {}).get("messages") or []:
        if isinstance(m, dict) and m.get("role") == "user":
            c = m.get("content")
            out.append(c if isinstance(c, str) else " ".join(str(p.get("text") or "") for p in c or [] if isinstance(p, dict)))
    return out[-1] if out else ""


def scenario(proj: Path):
    """`mock/headless`: "please ask" -> a Write in the project (the default mode asks), then "made it"."""
    def step(handler, body) -> None:
        msgs = (body or {}).get("messages") or []
        last = msgs[-1] if msgs and isinstance(msgs[-1], dict) else {}
        if last.get("role") == "tool":
            return _finish(handler, text_step("made it"))
        if ASK_TEXT in _texts(body):
            made = {"file_path": str(proj / "headless-made.txt"), "content": "made"}
            return _finish(handler, tool_step(("Write", made, "call_hl_1")))
        return _finish(handler, text_step(REPLY))
    return step


class HeadlessRig:
    _VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "HALO_FLEET_PRIVATE", "HALO_FLEET_PARENT")

    def __init__(self) -> None:
        self._saved = {k: os.environ.get(k) for k in self._VARS}
        fh = build_fake_home()
        self.home = Path(fh["home"])
        self.proj = Path(fh["proj"])
        self.state = self.home / ".halo"
        self.state.mkdir(parents=True, exist_ok=True)
        for k in self._VARS:
            os.environ.pop(k, None)
        os.environ.update(BRIDGE_TEST_HOME=str(self.home), BRIDGE_TEST_NO_BACKGROUND_NET="1")  # this process reads the same home
        SCENARIOS["headless"] = scenario(self.proj)
        self.mock = MockUpstream().start()
        self.procs: list = []
        self.pids: list = []
        self.clients: list = []
        self.servers: list = []

    def child_env(self) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "BRIDGE_", "OPENROUTER_", "ANTHROPIC_",
                                                                       "DATABRICKS_", "OPENAI_", "ROLO_CLAUDE_"))}
        env.update({"BRIDGE_TEST_HOME": str(self.home), "BRIDGE_TEST_NO_BACKGROUND_NET": "1",
                    "BRIDGE_OPENROUTER_BASE_URL": self.mock.base_url, "OPENROUTER_API_KEY": "test-key",
                    "OLLAMA_HOST": "http://127.0.0.1:9", "PYTHONPATH": str(REPO)})
        return env

    def argv(self, *extra: str) -> list:
        return [sys.executable, "-m", "halo_harness", "--headless", "--session-for", "studio", "--model", MODEL,
                "--permission-mode", "default", "--cwd", str(self.proj), *extra]

    def start(self, *extra: str) -> subprocess.Popen:
        log = open(self.home / f"headless-{len(self.procs)}.log", "w", encoding="utf-8")
        proc = subprocess.Popen(self.argv(*extra), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                env=self.child_env(), cwd=str(REPO))
        log.close()
        self.procs.append(proc)
        self.pids.append(proc.pid)
        return proc

    # ---- Studio: the in-process server that starts one (studio/sessions_new_api.py) ----------------------
    def studio(self):
        """An in-process Studio over this home; the children it spawns inherit `spawn_env()` from this process."""
        import threading
        from halo_harness.studio.server import start_server
        server = start_server(port=0, cwd=self.proj, state_dir=self.state)
        threading.Thread(target=server.serve_forever, daemon=True, name="headless-studio").start()
        self.servers.append(server)
        return server

    def stop_studio(self, server) -> None:
        for fn in (server.shutdown, server.server_close):
            try:
                fn()
            except Exception:
                pass

    def spawn_env(self) -> None:
        """What Studio's child needs from this process's environment (restored by close())."""
        for k in ("BRIDGE_OPENROUTER_BASE_URL", "OPENROUTER_API_KEY", "OLLAMA_HOST", "PYTHONPATH"):
            self._saved.setdefault(k, os.environ.get(k))
        os.environ.update({k: v for k, v in self.child_env().items()
                           if k in ("BRIDGE_OPENROUTER_BASE_URL", "OPENROUTER_API_KEY", "OLLAMA_HOST", "PYTHONPATH")})

    def asking_mode(self) -> None:
        """The fake home's settings.json in the `default` mode (it ships `auto`), so a child Studio starts without
        `--permission-mode` asks about the Write the way `start()`'s children do."""
        path = self.home / ".claude" / "settings.json"
        data = json.loads(path.read_text("utf-8"))
        data.setdefault("permissions", {})["defaultMode"] = "default"
        path.write_text(json.dumps(data, indent=2), "utf-8")

    @staticmethod
    def api(server, method: str, path: str, body=None):
        import http.client
        from halo_harness.studio.owner_proof import HEADER, header_for  # 3.3.14.0 R1: as the owner's own page asks
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=30)
        try:
            conn.request(method, "/api/" + path, body=json.dumps(body).encode("utf-8") if body is not None else None,
                         headers={"Authorization": "Bearer " + server.token, "Content-Type": "application/json",
                                  HEADER: header_for(server)})
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
        finally:
            conn.close()

    def rows(self) -> list:
        try:
            return json.loads((self.state / "run" / "sessions.json").read_text("utf-8")).get("sessions") or []
        except (OSError, ValueError):
            return []

    def entry(self, sid: str = "", timeout: float = 60.0):
        return wait_for(lambda: next((r for r in self.rows() if not sid or r.get("session_id") == sid), None), timeout, 0.1)

    def client(self, entry: dict):
        from halo_harness.remote import client as rclient
        c = rclient.ControlClient(entry["endpoint"], rclient.default_token_for(entry), timeout=10.0)
        self.clients.append(c)
        return c

    def idle(self, c, timeout: float = 30.0) -> bool:
        return bool(wait_for(lambda: not c.call("status")["result"].get("busy") and "idle", timeout, 0.2))

    def log_text(self, sid: str) -> str:
        found = list((self.state / "sessions").rglob(f"{sid}.jsonl"))
        return found[0].read_text("utf-8") if found else ""

    def child_log(self) -> str:
        return "\n".join(p.read_text("utf-8", "replace")[-1500:] for p in sorted(self.home.glob("headless-*.log")))

    def survivors(self) -> list:
        from halo_harness.bg_run import pid_alive
        return [p for p in self.pids if pid_alive(p)]

    def close(self) -> None:
        for c in self.clients:
            try:
                c.close()
            except Exception:
                pass
        for row in self.rows():
            if row.get("pid") in self.pids:
                try:
                    self.client(row).call("shutdown", by="test teardown", via="test", reason="teardown")
                except Exception:
                    pass
        for proc in self.procs:
            try:
                proc.wait(20)
            except Exception:
                proc.kill()
        from halo_harness.bg_run import pid_alive
        for pid in self.survivors():  # a child Studio started (not ours to wait on)
            try:
                from halo_harness.children_stop import terminate
                terminate(pid, timeout=5.0)
            except Exception:
                pass
        end = time.monotonic() + 10
        while time.monotonic() < end and any(pid_alive(p) for p in self.pids):
            time.sleep(0.1)
        for server in self.servers:
            self.stop_studio(server)
        self.mock.stop()
        SCENARIOS.pop("headless", None)
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def __enter__(self) -> "HeadlessRig":
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False
