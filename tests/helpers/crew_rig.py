"""tests.helpers.crew_rig -- the Agents tab's scratch world (Halo 3.6.0.0 R1): what tests/test_crew_try.py,
tests/test_builder_flows.py and the Studio driver tests/helpers/studio_crew.py stand on.

`CrewRig()` (a context manager) makes a scratch home (BRIDGE_TEST_HOME, its state dir `<home>/.halo`), a git repo
`shop` with two files and one commit, the repo's fake provider -- the mock upstream (tests/helpers/mock_openai.py) on
loopback with OpenRouter pointed at it, `model` = `or:mock/crew-try` -- whose scenario `crew-try` lists the .py files once
and answers TRY_REPLY, and the builder's model call replaced by a scripted fake (`script(...)`, crew/builder.py
CALLER) that answers by the request's words, each call priced at CALL_USD. `studio()` starts an in-process Studio on
loopback; `api(method, path, body)` asks it as the owner's page does. Everything touched is restored on close.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from tests.helpers.mock_openai import SCENARIOS, MockUpstream, ScriptedTurns
from tests.helpers.session_rig import text_step, tool_step

TRY_REPLY = "basket.py:2: the discount is never applied before tax. No other problems found."
CALL_USD = 0.012
DRAFT = "You are my-reviewer. Read the diff, list what would break, one line each.\nYou never change files."
KEPT = ("HALO_STUDIO_SLOW_MS", "HALO_CHROME")  # the latency flag reaches the rig's Studio; the browser stays named
_PREFIXES = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_")


def gate_args() -> dict:
    """What the builder's scripted model asks for on "make a security gate": every widening kind at once."""
    return {"name": "security-gate", "does": "Reads pull requests and says only what would break.",
            "uses": ["read", "mcp:github", "bash", "edit"], "careful": "own", "model": "auto"}


def scripted(model: str, system: str, user: str, *, state_dir=None) -> dict:
    """The builder's fake model: a tool call first, then a reply once the tool's line is in the text."""
    req = user.rsplit("REQUEST (data):", 1)[-1].split("\n\nTOOL", 1)[0].lower()
    done = "\n\nTOOL " in user

    def out(obj) -> dict:
        return {"text": obj if isinstance(obj, str) else json.dumps(obj), "input_tokens": 1000, "output_tokens": 100, "cost_usd": CALL_USD}
    if system.startswith("Write the instructions"):
        return out(DRAFT)
    if "security gate" in req:
        return out({"reply": "A new agent, security-gate. What lets it do more is listed and not ticked."} if done
                   else {"tool": "agent_make", "args": gate_args()})
    if "write the instructions for" in req:
        name = req.split("write the instructions for", 1)[1].split()[0]
        return out({"reply": "Drafted: read it in the preview."} if done else {"tool": "agent_draft_instructions", "args": {"name": name}})
    if "which reviewer" in req:
        return out({"reply": "Which one should review?", "question": {"text": "", "choices": ["my-reviewer (recommended: you have it)", "a new reviewer"]}})
    if "give yourself" in req:  # a pasted text asking for more power: the fake obeys it, the preview must not
        return out({"reply": "Changed."} if done else {"tool": "agent_change", "args": {"name": "my-reviewer", "fields": {
            "uses": ["read", "bash", "web"], "careful": "own", "more": {"max_usd": 50}}}})
    return out({"reply": "Nothing to change."})


class CrewRig:
    def __enter__(self) -> "CrewRig":
        self._saved = {k: v for k, v in os.environ.items() if k.startswith(_PREFIXES)}
        for k in list(os.environ):
            if k.startswith(_PREFIXES) and k not in KEPT:
                os.environ.pop(k)
        self.root = Path(tempfile.mkdtemp(prefix="crew-rig-"))
        self.mock = MockUpstream().start()
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), BRIDGE_TEST_NO_BACKGROUND_NET="1",
                          BRIDGE_OPENROUTER_BASE_URL=self.mock.base_url, OPENROUTER_API_KEY="test-key",
                          OLLAMA_HOST="http://127.0.0.1:9")
        self.state = self.root / ".halo"
        self.state.mkdir()
        (self.state / "config.json").write_text(json.dumps({"model": "or:mock/crew-try", "remote": {"enabled": False}}), encoding="utf-8")
        self.proj = self.root / "shop"
        self.proj.mkdir()
        (self.proj / "basket.py").write_text("def total(items):\n    return sum(i.price for i in items)\n", encoding="utf-8")
        (self.proj / "notes.md").write_text("# pricing\ndiscount before tax\n", encoding="utf-8")
        for args in (("init", "-q", "-b", "main"), ("config", "user.name", "t"), ("config", "user.email", "t@t"),
                     ("config", "commit.gpgsign", "false"), ("add", "-A"), ("commit", "-q", "-m", "basket")):
            subprocess.run(["git", *args], cwd=str(self.proj), capture_output=True, timeout=60, check=True)
        SCENARIOS["crew-try"] = ScriptedTurns([tool_step(("Glob", {"pattern": "*.py"}, "call_r1")), text_step(TRY_REPLY)])
        from halo_harness.crew import builder
        self._caller = builder.CALLER
        builder.CALLER = scripted
        self.server = None
        return self

    def studio(self):
        from halo_harness.studio.events import bridge_for
        from halo_harness.studio.server import start_server
        self.server = start_server(port=0, cwd=self.proj, state_dir=self.state)
        threading.Thread(target=self.server.serve_forever, daemon=True, name="crew-studio").start()
        bridge_for(self.server)
        return self.server

    def url(self, extra: str = "") -> str:
        from halo_harness.studio.server import url_for
        return url_for(self.server, "agents").replace("#t=", f"&tour=off{extra}#t=")

    def api(self, method: str, path: str, body=None, owner: bool = True):
        import http.client
        from halo_harness.studio.owner_proof import HEADER, header_for
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=60)
        heads = {"Authorization": "Bearer " + self.server.token, "Content-Type": "application/json"}
        if owner:
            heads[HEADER] = header_for(self.server)
        try:
            conn.request(method, "/api/" + path, body=json.dumps(body).encode("utf-8") if body is not None else None, headers=heads)
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
        finally:
            conn.close()

    def __exit__(self, *exc) -> bool:
        from halo_harness.crew import builder, trial
        builder.CALLER = self._caller
        builder.PENDING.clear()
        for proc, _rec in list(trial.RUNNING.values()):
            try:
                proc.kill()
            except Exception:
                pass
        if self.server is not None:
            for fn in (self.server.shutdown, self.server.server_close):
                try:
                    fn()
                except Exception:
                    pass
        self.mock.stop()
        SCENARIOS.pop("crew-try", None)
        for k in list(os.environ):
            if k.startswith(_PREFIXES):
                os.environ.pop(k)
        os.environ.update(self._saved)
        shutil.rmtree(self.root, ignore_errors=True)
        return False
