"""tests.helpers.mission_seed -- the Halo 3.0.6.0 R7 mission tests' fleet and
fakes. No model is ever called: the lead and the judge are fakes, and the
worker session is a FakeSession with a REAL PermissionEngine, so the claim
guard runs exactly as it does in a real mission-worker.

    windows_host(identity)   the hub: Windows, RTX 4090, GridCraft + DeckCraft, ComfyUI
    kali_box(identity)       the member: Kali, nmap, a pentest tag, no GPU
    lead_answer(...)         the fake lead's fixed plan (the gridcraft part's harness left to the rules)
    FakeLead                 orchestra_fixtures' fake lead (records its prompts)
    worker(script)           a mission_worker.BUILD whose run writes files through the engine
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from tests.helpers.fleet_caps_seed import _tools, _who
from tests.helpers.orchestra_fixtures import FakeLead  # noqa: F401  (re-exported)


def windows_host(identity: dict) -> dict:
    return {"harness": _who(identity), "at": time.time(), "tags": ["studio", "gpu"],
            "mcp": [{"name": "gridcraft", "transport": "stdio", "tools": _tools(
                        ("write_range", "Write values and formulas into a spreadsheet range"),
                        ("insert_chart", "Insert a chart built from a range"))},
                    {"name": "deckcraft", "transport": "stdio", "tools": _tools(("add_slide", "Add a slide"))}],
            "skills": ["xlsx", "pptx"], "roles": [], "providers": [{"name": "OpenRouter", "id": "openrouter", "ok": True}],
            "models": [{"id": "or:anthropic/claude-fable-5", "provider": "openrouter", "best_for": ["design"]}],
            "craft_apps": ["gridcraft", "deckcraft"], "media": {"comfyui": True, "models": []},
            "hardware": {"os": "windows", "distro": "windows", "release": "11", "cpu": "AMD Ryzen 9", "cores": 24,
                         "ram_gb": 64, "gpu": [{"name": "NVIDIA GeForce RTX 4090", "vram_gb": 24}], "disk_free_gb": 400.0},
            "clis": {"git": "2.45.1", "python": "3.11.7", "nmap": None}, "projects": [],
            "integrations": {"signal": False}}


def kali_box(identity: dict) -> dict:
    return {"harness": _who(identity), "at": time.time(), "tags": ["pentest", "linux"], "mcp": [],
            "skills": [], "roles": [], "providers": [], "models": [], "craft_apps": [],
            "media": {"comfyui": False, "models": []},
            "hardware": {"os": "linux", "distro": "kali", "release": "2026.3", "cpu": "Intel Core i7", "cores": 8,
                         "ram_gb": 16, "gpu": [], "disk_free_gb": 80.0},
            "clis": {"git": "2.47.0", "python": "3.12.8", "nmap": "7.95"}, "projects": [{"name": "ledger", "repo": "ledger", "branch": "main"}],
            "integrations": {"signal": False}}


def lead_answer(*, repo: bool = False, overlap: bool = True, nobody: bool = True) -> str:
    parts = [{"id": "scan", "title": "Scan the lab network", "brief": "Run nmap over 198.51.100.0/24; save scan.xml.",
              "kind": "files", "harness": "", "reason": "", "needs": ["nmap"], "outputs": ["scan.xml"],
              "est_cost_usd": 0.2},
             {"id": "book", "title": "Build the findings workbook", "brief": "Turn scan.xml into findings.xlsx with a chart.",
              "kind": "files", "harness": "", "reason": "", "needs": ["gridcraft"], "depends_on": ["scan"],
              "outputs": ["findings.xlsx"], "est_cost_usd": 0.3}]
    if repo:
        parts.append({"id": "docs", "title": "Write the report page", "brief": "Write docs/report/index.md.", "kind": "repo",
                      "needs": [], "claims": ["docs/report/**"], "outputs": [], "est_cost_usd": 0.1})
        if overlap:
            parts.append({"id": "readme", "title": "Link the report from the docs", "brief": "Add a link in docs/report/links.md.",
                          "kind": "repo", "needs": [], "claims": ["docs/report/links.md"], "est_cost_usd": 0.1})
    if nobody:
        parts.append({"id": "exploit", "title": "Try the exploit", "brief": "Use metasploit.", "kind": "files",
                      "needs": ["metasploit"], "est_cost_usd": 0.1})
    order = [p["id"] for p in parts if p["kind"] == "repo"][::-1]
    return json.dumps({"parts": parts, "merge_order": order})


class FakeJudge:
    def __init__(self, text: str = "") -> None:
        self.calls = []
        self.text = text

    def __call__(self, hunks, goal, file):
        self.calls.append((file, len(hunks)))
        return {"text": self.text or "\n".join(h["ours"] + "\n" + h["theirs"] for h in hunks), "cost_usd": 0.001,
                "session_id": f"judge-{len(self.calls)}"}


def worker(script: dict, started: list, gates: "dict | None" = None):
    """A BUILD: part -> {writes: [rel], outside: [rel], cost, text, fail}; `gates[part]` holds a run until set."""
    from halo_harness.permissions import PermissionEngine
    from tests.helpers.fake_remote_session import FakeSession

    def build(cwd, home):
        n = Path(cwd).name if (Path(cwd) / ".git").exists() else None
        session = FakeSession(f"mw{time.time_ns():x}"[:32].ljust(32, "0"))
        session.permission_engine = PermissionEngine(mode="auto", cwd=cwd, print_mode=True)

        def run(prompt: str, handle=None) -> dict:
            part = n or prompt.split("part ", 1)[1].split(":", 1)[0].strip()
            started.append((part, time.time()))
            plan = script.get(part, {})
            gate = (gates or {}).get(part)
            if gate is not None:
                while not gate.is_set() and not session.abort.is_set():
                    time.sleep(0.05)
            if session.abort.is_set():
                return {"ok": False, "text": "interrupted", "cost_usd": 0.01, "error": "interrupted"}
            for rel in plan.get("outside", []):
                d = session.permission_engine.decide("Write", {"file_path": str(Path(cwd) / rel), "content": "x"})
                plan.setdefault("denied", []).append((rel, d.action, d.reason))
            for rel in plan.get("writes", []):
                d = session.permission_engine.decide("Write", {"file_path": str(Path(cwd) / rel), "content": "x"})
                if d.action == "allow":
                    target = Path(cwd) / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(plan.get("content", {}).get(rel, f"part {part}\n"), encoding="utf-8")
            return {"ok": not plan.get("fail"), "text": plan.get("text", f"part {part} done"),
                    "cost_usd": plan.get("cost", 0.01), "error": "it fell over" if plan.get("fail") else "",
                    "session_id": session.log.session_id}
        return session, run, lambda: None
    return build


def wait_state(home, mid: str, states, timeout: float = 30.0) -> dict:
    from halo_harness.fleet import mission_store as S
    end = time.time() + timeout
    doc = S.need(home, mid)
    while time.time() < end and doc["state"] not in states:
        time.sleep(0.1)
        doc = S.need(home, mid)
    return doc


def gate() -> threading.Event:
    return threading.Event()


def fleet(rig, **b_config):
    """The HubRig with both catalogs seeded (A the Windows host, B the Kali box), B joined with a live session
    and its catalog on the hub; `b_config` set on B first (fleet.allow_control, fleet.shared_dir ...)."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet.identity import harness
    from tests.helpers.fleet_caps_seed import seed
    from tests.helpers.fleet_hub_rig import wait_for
    seed(rig.home_a, windows_host(rig.hub.state.identity))
    seed(bridge_home(), kali_box(harness()))
    if b_config:
        rig.set_b(**b_config)
    rig.join()
    controller, act = rig.session()
    wait_for(lambda: rig.hub.state.caps.catalogs.get(rig.b_id), 20.0)
    return controller, act


def mission_ctx(rig, answer: str, script: dict, started: list, gates=None):
    """mission_api with the fake lead and the fake worker; the hub's Ctx."""
    from halo_harness.fleet import mission_api as A
    from halo_harness.fleet import mission_worker as W
    A.LEAD, A.JUDGE = FakeLead(answer), FakeJudge()
    W.BUILD = worker(script, started, gates)
    return A, A.Ctx(rig.home_a, rig.hub, by="alice@hub")


def reset_fakes() -> None:
    from halo_harness.fleet import mission_api as A
    from halo_harness.fleet import mission_worker as W
    A.LEAD = A.JUDGE = W.BUILD = None
