"""tests.helpers.fake_flow -- fakes for the flow runner (Halo 3.0.4.0 R3):
a recording `one_shot`, a scripted marketing org whose Art Director is held
for approval through the flow's sink (an `edit` answer re-runs the position
with the instruction), scripted gate answers written through the same
`gates.write_answer` the CLI uses, and `make_adapters` wiring them to a
FakeComfy server. Models, ComfyUI and Postiz are never real here.
"""

from __future__ import annotations

import copy
from pathlib import Path

COPY = "X:\nShort post for X #halo\n\nInstagram:\nA longer caption for Instagram #halo #ai"


class FakeOneShot:
    def __init__(self, cost: float = 0.01, hook=None):
        self.calls: list = []
        self.cost, self.hook = cost, hook

    def __call__(self, role, prompt, model):
        self.calls.append({"role": role, "prompt": prompt, "model": model})
        if self.hook is not None:
            self.hook(role, prompt, model)
        return {"text": f"{role}: an answer about the brief", "cost_usd": self.cost, "ok": True, "error": ""}


class FakeOrg:
    """The marketing org: the Art Director's prompt goes through the approval sink."""

    def __init__(self, prompt: str = "a lighthouse at dusk, cinematic", cost: float = 0.05, gate: bool = True,
                 copy: str = COPY):
        self.prompt, self.cost, self.gate, self.copy = prompt, cost, gate, copy
        self.calls: list = []
        self.decisions: list = []

    def __call__(self, org_name, goal, budget_usd, on_event, approval_sink):
        self.calls.append({"org": org_name, "goal": goal, "budget_usd": budget_usd})
        on_event("Strategist started", {"agent_id": "a1"})
        text, spent = self.prompt, self.cost
        while self.gate:
            d = approval_sink({"id": f"req-{len(self.decisions) + 1}", "position": "Art Director", "text": text,
                               "is_error": False})
            self.decisions.append(dict(d))
            if d.get("action") == "edit":
                text = f"{text}, {d.get('instruction')}"
                spent += self.cost
                continue
            if d.get("action") == "stop":
                return {"text": "[approval gate] stopped", "cost_usd": spent, "positions": {}, "is_error": True}
            break
        on_event("Strategist finished", {"agent_id": "a1"})
        return {"text": "Campaign plan: tease 3.0.4", "cost_usd": spent, "is_error": False,
                "positions": {"Strategist": {"text": "Campaign plan: tease 3.0.4"},
                              "Copywriter": {"text": self.copy},
                              "Art Director": {"text": f"Prompt: {text}"}}}


class Answers:
    """`answer_gate`: pops one scripted answer per gate opened, keyed by step id."""

    def __init__(self, script: dict):
        self.script = {k: list(v) for k, v in script.items()}
        self.seen: list = []

    def __call__(self, gate: dict) -> None:
        from halo_harness.flows import gates
        self.seen.append(copy.deepcopy(gate))
        queue = self.script.get(gate["step"]) or []
        action, text = queue.pop(0) if queue else ("accept", "")
        ok, msg = gates.write_answer(gate["run_dir"], gate["step"], action, text)
        assert ok, msg


def make_adapters(comfy_url: str, *, one_shot=None, run_org=None, answers=None, auto_accept=False, model=None,
                  cwd=None, comfy_factory=None, feed=None):
    from halo_harness.flows.adapters import Adapters
    from halo_harness.media.comfy_client import ComfyClient
    return Adapters(model=model, auto_accept=auto_accept, poll_s=0.01, render_timeout_s=30, cwd=cwd,
                    one_shot=one_shot or FakeOneShot(), run_org=run_org or FakeOrg(), feed=feed,
                    comfy_client=comfy_factory or (lambda: ComfyClient(comfy_url, timeout=10)), answer_gate=answers)


def template_spec(**changes) -> dict:
    from halo_harness.flows.spec import load_flow, template_path
    spec = load_flow(template_path("social-post"))
    spec.update(changes)
    return spec


def uniq(prefix: str) -> str:
    """A project slug no earlier run in this (possibly reused) test home has."""
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:6]}"


def new_run(spec: dict, brief: str = "a one-line teaser for Halo Harness 3.0.4", **intake):
    from halo_harness.flows.state import new_run as _new
    values = {"brief": brief, "platforms": "x,instagram"}
    values.update(intake)
    if "project" in values:
        values["project"] = uniq(values["project"])
    return Path(_new(spec, values, source="test"))
