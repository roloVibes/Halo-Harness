"""tests.helpers.policy_session -- Halo 3.3.10.0 R2: a real `agent.loop.Session` inside a PacksHome (the packs
home stays the session's home: `turn_session.new_session` points BRIDGE_TEST_HOME at a new folder), against the
OpenAI-shaped mock upstream, with the `policy-fence` fixture pack installed, enabled with hooks and its mode on.

    with fenced_home(HALO_POLICY_TEST_ASK=1, after=True) as h:   # the fixture's seams set inside the home
        with Upstream("pg-x", [tool_step("Write", {...}), text_step("done")]) as up:
            s = session_in(h, up)
            evs = list(s.turn("write it"))

`after=True` turns on the fixture's post-call verdict (its copy's pack.yaml gains `after: true`, and `Read` and
`Bash` join `when.tools`). Nothing here reaches past 127.0.0.1.
"""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path

from tests.helpers.mock_openai import MockUpstream, SCENARIOS
from tests.helpers.packs_home import PacksHome
from tests.helpers.turn_session import Calls

PACK = "policy-fence"


class Upstream:
    def __init__(self, scenario: str, steps: list):
        self.scenario, self.steps = scenario, steps

    def __enter__(self):
        self.mock = MockUpstream().start()
        SCENARIOS[self.scenario] = Calls(self.steps)
        self.model = f"or:mock/{self.scenario}"
        return self

    def __exit__(self, *exc):
        self.mock.stop()
        SCENARIOS.pop(self.scenario, None)

    @property
    def requests(self) -> list:
        return list(self.mock.requests)


def session_in(h, up: Upstream, *, mode: str = "default", interactive: bool = False, hook_runner=None,
               agents: bool = False):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-test-default")  # PacksHome takes every provider name out
    found = {}
    if agents:
        from halo_harness.config.agents_md import discover_agents
        found = discover_agents(h.repo, settings=None)
    state = h.home / "session-state"
    state.mkdir(exist_ok=True)
    s = Session(cwd=h.repo, model_ref=parse_model_ref(up.model), model_profile=ModelProfile(),
                creds=ProviderCreds(base_url=up.mock.base_url, api_key="k"), state_dir=state, model_label=up.model,
                session_context=SessionContext(cwd=h.repo, model_label=up.model, bare=True),
                openrouter_base_url=up.mock.base_url, max_turns=10, hook_runner=hook_runner,
                permission_engine=PermissionEngine(mode=mode, cwd=h.repo), agents=found, routes={})
    s.interactive = interactive
    return s


def _after_copy(src: Path) -> None:
    y = src / "pack.yaml"
    text = y.read_text(encoding="utf-8")
    text = text.replace("when: {tools: [Write, Edit], modes: [fenced]}", "when: {tools: [Write, Edit, Read, Bash], modes: [fenced]}")
    text = text.replace("      on_error: deny\n", "      on_error: deny\n      after: true\n")
    y.write_text(text, encoding="utf-8")


@contextmanager
def fenced_home(*, armed: bool = True, after: bool = False, install: bool = True, **env):
    """A PacksHome with the fixture installed, enabled with hooks and (armed) its mode on; `env` (the fixture's
    HALO_POLICY_TEST_* seams) set inside the home, which takes every HALO_* variable back on exit."""
    from halo_harness.packs import mode_state as M
    from halo_harness.packs import policy as P
    with PacksHome() as h:
        os.environ.update({k: str(v) for k, v in env.items()})
        if install:
            src = h.source(PACK)
            if after:
                _after_copy(src)
            h.install(src, enable=True, grants=["hooks"])
            if armed:
                ok, lines = M.set_mode(PACK, "fenced", True, cwd=h.repo)
                assert ok, lines
        try:
            yield h
        finally:
            P.stop_all()


def policy_rows(at: str = "") -> list:
    from halo_harness.packs.events_log import since
    rows = [e["data"] for e in since(f"{PACK}:policy")]
    return [r for r in rows if not at or r.get("at") == at]


def outside(h) -> Path:
    """A path outside the project folder (h.repo), inside the scratch home."""
    return h.home / "outside" / "x.txt"


def rewrite_hook(h, path: Path):
    """A HookRunner with one PreToolUse command hook on Write that rewrites the call's file_path to `path`."""
    from halo_harness.hooks import HookDef, HookRunner
    script = h.home / "rewrite_hook.py"
    script.write_text("import json, sys\nprint(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', "
                      "'updatedInput': {'file_path': sys.argv[1], 'content': 'x'}}}))\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("HALO_") and k != "BRIDGE_STATE_DIR"}
    hooks = {"PreToolUse": [HookDef(type="command", matcher="Write", args=[sys.executable, str(script), str(path)])]}
    return HookRunner(hooks, cwd=h.repo, session_id="policy-gate-test", transcript_path=str(h.repo / "t.jsonl"),
                      effective_env=env)
