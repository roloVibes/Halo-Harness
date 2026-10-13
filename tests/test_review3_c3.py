"""tests.test_review3_c3 -- pins for the 3.0.2.0 review fix pass, round
C-studio-tools, part 3: Studio's lineup graph and the Paperclip install.

  * item 37   a hand-edited lineup or bio opens, with the validator's words
  * item 38   a Paperclip install is finished on its success line, a second
              POST is refused, two POSTs start one child
"""

from __future__ import annotations

import json
import shutil
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_review3_c import _Studio  # noqa: E402  (scopes the state dir the same way)
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
STATIC = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "static"


@test
def test_item37_a_hand_edited_lineup_still_opens(ctx: Ctx):
    from halo_harness import agents_yaml as A
    from halo_harness.studio import model as M
    raw = {"name": "handy", "agents": [
        {"agent": "orchestrator", "role": "main", "instances": "two", "use_for": "review"},
        {"agent": "reviewer", "role": "reviewer", "instances": True},
        {"agent": "implementer", "role": "subagent", "instances": 0},
        {"agent": "orchestrator", "role": "subagent", "instances": 3, "use_for": ["a", "b"]},
    ]}
    nodes = M.graph_for(raw, catalog={})["nodes"]
    ctx.check("a non-integer / bool / zero instances is 1 with the validator's sentence",
              [n["instances"] for n in nodes[:3]] == [1, 1, 1] and all('"instances" must be a positive integer' in n["problems"] for n in nodes[:3]))
    ctx.check("a good count is kept and not flagged", nodes[3]["instances"] == 3 and not any("instances" in p for p in nodes[3]["problems"]))
    ctx.check("use_for counts only as a list (a string is not split into characters)", nodes[0]["use_for"] == [] and nodes[3]["use_for"] == ["a", "b"])
    real = A.resolve_agent_bio
    A.resolve_agent_bio = lambda name, **kw: {"tools": ["Read", "Write"], "models": ["x"], "_source": "user", "kind": "main"}
    try:
        n = M.graph_for({"name": "t", "agents": [{"agent": "odd", "role": "main"}]}, catalog={})["nodes"][0]
    finally:
        A.resolve_agent_bio = real
    ctx.check("a bio spelling tools as a list does not raise; the node shows 0 tools", n["tools"] == 0 and n["model"] == "")


@test
def test_item37_the_lineup_route_answers_200_with_problems(ctx: Ctx):
    import urllib.request
    with _Studio() as s:
        teams = s.state / "teams"
        teams.mkdir(parents=True, exist_ok=True)
        (teams / "handy.yaml").write_text("name: handy\nagents:\n  - agent: orchestrator\n    role: main\n    instances: two\n", encoding="utf-8")
        req = urllib.request.Request(f"http://127.0.0.1:{s.port}/api/lineup/handy", headers={"Authorization": "Bearer " + s.srv.token})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        ctx.check("GET /api/lineup/handy is a 200 with a graph", r.status == 200 and len(data["graph"]["nodes"]) == 1)
        ctx.check(f"the validator's line is in problems, got {data['problems']}", any("instances" in p for p in data["problems"]))


class _FakeProc:
    """A stand-in for the npx child: prints, reports success, then keeps serving until released."""

    def __init__(self, release):
        self.release, self.returncode = release, None
        self.stdout = self._lines()

    def _lines(self):
        yield "installing paperclipai\n"
        yield "Server startup recovery complete\n"
        self.release.wait(20)
        yield "server stopped\n"

    def wait(self, timeout=None):
        self.returncode = 0
        return 0


@test
def test_item38_install_finishes_on_the_success_line(ctx: Ctx):
    from halo_harness.studio import paperclip_api as P
    release, popen_args, probe_gate = threading.Event(), [], threading.Event()
    real = (P.subprocess.Popen, P._client, shutil.which)

    class _Client:
        base_url, token = "http://127.0.0.1:3100", ""

        def health(self):
            return {"status": "ok"}

        def companies(self):
            return []

        def reachable(self):
            probe_gate.wait(10)
            return bool(popen_args)  # once the first install started the server is up

    def fake_popen(cmd, **kw):
        popen_args.append((cmd, kw))
        return _FakeProc(release)

    P.subprocess.Popen, P._client = fake_popen, lambda state_dir: _Client()
    shutil.which = lambda name, *a, **k: "/fake/" + name
    P._INSTALL.update(running=False, log=[], code=None)
    try:
        with _Studio() as s:
            from halo_harness.studio.api import Request
            post = lambda: P.install(Request(method="POST", path="pc/install", query={}, body={}, cwd=s.state, state_dir=s.state))  # noqa: E731
            first = {}
            t = threading.Thread(target=lambda: first.update(r=post()))
            t.start()
            deadline = time.time() + 5
            while not P._INSTALL["running"] and time.time() < deadline:
                time.sleep(0.01)
            ctx.check("running is set before the probe returns", P._INSTALL["running"] is True)
            ctx.check("a second POST during the probe is a 409 and starts nothing", post()[0] == 409 and not popen_args)
            probe_gate.set()
            t.join(timeout=10)
            ctx.check("the first POST is accepted and starts exactly one child", first["r"][0] == 202 and len(popen_args) == 1)
            deadline = time.time() + 5
            while P._INSTALL["code"] != 0 and time.time() < deadline:
                time.sleep(0.02)
            status, st = P.install(Request(method="GET", path="pc/install", query={}, body={}, cwd=s.state, state_dir=s.state))
            ctx.check(f"after the success line GET says running false, code 0, got {st['running']} {st['code']}", st["running"] is False and st["code"] == 0)
            ctx.check("the status route agrees", P.status(Request(method="GET", path="pc/status", query={}, body={}, cwd=s.state, state_dir=s.state))[1]["install"]["running"] is False)
            ctx.check("a POST now is refused because Paperclip answers, not because an install runs", post() == (409, {"error": "Paperclip is already running at http://127.0.0.1:3100"}))
            ctx.check("the child is launched in its own session on POSIX", sys.platform == "win32" or popen_args[0][1].get("start_new_session") is True)
            ctx.check("the log says the server outlives Studio", any("keeps running when Studio stops" in line for line in P._INSTALL["log"]))
    finally:
        release.set()
        time.sleep(0.2)
        P.subprocess.Popen, P._client, shutil.which = real
        P._INSTALL.update(running=False, log=[], code=None)
    org = (STATIC / "org.js").read_text(encoding="utf-8")
    ctx.check("the page also stops polling at code 0", "r.running && r.code !== 0" in org)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="review3 c3 tests"))
