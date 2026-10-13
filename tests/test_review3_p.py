"""tests.test_review3_p -- pins for the 3.0.2.0 review fix pass, round
P-design-paperclip, the Paperclip and design-turn items (review items 39,
42, 43; 44 and the design items are in test_review3_p2):

  * 39  the Paperclip client goes through urlopen_tls: a cross-host redirect
        drops the Bearer token, offline mode is honoured
  * 42  the heartbeat prompt travels on stdin (not argv) and a runner crash
        still ends in the failure comment and exit 1
  * 43  run_turn enforces its timeout while the child holds stdout open
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.fake_paperclip import FakePaperclip  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Sink:
    """A tiny JSON server; `redirect_to()` makes /api/health answer 302."""

    def __init__(self, redirect_to=None):
        self.seen: list = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.seen.append({k.lower(): v for k, v in self.headers.items()})
                if redirect_to:
                    self.send_response(302)
                    self.send_header("Location", redirect_to())
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                body = b'{"status": "ok"}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def _offline(value):
    saved = os.environ.get("HALO_OFFLINE")
    if value is None:
        os.environ.pop("HALO_OFFLINE", None)
    else:
        os.environ["HALO_OFFLINE"] = value
    return saved


# ---- 39 -----------------------------------------------------------------------

@test
def test_i39_cross_host_redirect_drops_the_bearer_token(ctx: Ctx):
    from halo_harness.paperclip.client import Paperclip
    target = _Sink()
    first = _Sink(redirect_to=lambda: f"http://localhost:{target.port}/api/health")
    try:
        Paperclip(f"http://127.0.0.1:{first.port}", "board-token-xyz").health()
        ctx.check("the first hop got the token", first.seen[0].get("authorization") == "Bearer board-token-xyz")
        ctx.check(f"the other host did not, got {sorted(target.seen[0])}", "authorization" not in target.seen[0])
    finally:
        first.close()
        target.close()


@test
def test_i39_offline_mode_refuses_a_remote_paperclip_but_not_loopback(ctx: Ctx):
    from halo_harness.paperclip.client import Paperclip, PaperclipError
    fake = FakePaperclip()
    saved = _offline("1")
    try:
        try:
            Paperclip("http://paperclip.example:3100", "t").health()
            ctx.check("a remote base URL is refused offline", False)
        except PaperclipError as e:
            ctx.check(f"refused as status 0, got {e}", e.status == 0 and "paperclip.example" in e.message)
        ctx.check("the loopback default still works offline", Paperclip(fake.base_url).reachable())
    finally:
        _offline(saved)
        fake.close()


# ---- 42 -----------------------------------------------------------------------

@test
def test_i42_prompt_goes_on_stdin_and_a_spawn_failure_is_a_result(ctx: Ctx):
    import subprocess
    from halo_harness.paperclip import adapter
    real, seen = subprocess.run, {}

    def fake_run(cmd, **kw):
        seen.update(cmd=cmd, **kw)
        return subprocess.CompletedProcess(cmd, 0, "ok", "")
    subprocess.run = fake_run
    try:
        prompt = "漢" * 50_000  # 150 kB in UTF-8, one argv string would not fit on Linux
        code, text = adapter.run_halo(prompt, "m", os.getcwd(), {})
        ctx.check("the prompt is stdin input", seen.get("input") == prompt)
        ctx.check("and not any argv entry", all(len(a) < 1000 for a in seen["cmd"]) and "-p" in seen["cmd"])
        ctx.check("the result passes through", (code, text) == (0, "ok"))

        def too_long(cmd, **kw):
            raise OSError(7, "Argument list too long")
        subprocess.run = too_long
        code, text = adapter.run_halo("x", "", os.getcwd(), {})
        ctx.check(f"OSError becomes (1, message), got {code}", code == 1 and "Argument list too long" in text)
    finally:
        subprocess.run = real


@test
def test_i42_prompt_is_capped_in_bytes_and_a_runner_crash_is_commented(ctx: Ctx):
    from halo_harness.paperclip.adapter import MAX_PROMPT_BYTES, build_prompt, run_heartbeat
    from halo_harness.theme import set_config_value
    p = build_prompt({"issue": {"title": "t", "description": "\U0001f600" * 50_000}}, {}, {})
    ctx.check("the UTF-8 size is capped", len(p.encode("utf-8")) <= MAX_PROMPT_BYTES)
    set_config_value("paperclip.enabled", True)
    fake = FakePaperclip()
    try:
        agent = fake.add_agent("worker")
        issue = fake.add_issue("Crash", assignee=agent["id"])
        env = {"PAPERCLIP_API_URL": fake.base_url, "PAPERCLIP_API_KEY": "k", "PAPERCLIP_AGENT_ID": agent["id"],
               "PAPERCLIP_COMPANY_ID": fake.company["id"], "PAPERCLIP_RUN_ID": "run-1", "PATH": "x"}

        def boom(*a):
            raise RuntimeError("runner exploded")
        code = run_heartbeat(env, runner=boom, out=io.StringIO())
        ctx.check("exit 1, not a traceback", code == 1)
        ctx.check("the failure is commented", fake.comments and "runner exploded" in fake.comments[-1]["body"])
        ctx.check("the issue stays in progress", fake.issues[issue["id"]]["status"] == "in_progress")
    finally:
        fake.close()
        set_config_value("paperclip.enabled", False)


# ---- 43 -----------------------------------------------------------------------

@test
def test_i43_run_turn_kills_a_child_that_hangs_with_stdout_open(ctx: Ctx):
    import subprocess
    import time
    from halo_harness.design import session
    from halo_harness.design.store import Project
    p = Project.create("Hang turn")
    real = subprocess.Popen
    script = "import time; print('{\"type\": \"system\"}', flush=True); time.sleep(120)"

    def popen(cmd, **kw):
        return real([sys.executable, "-c", script], **kw)
    subprocess.Popen = popen
    started = time.monotonic()
    try:
        out = session.run_turn(p, "hang", entries={}, registered=set(), timeout=2)
    finally:
        subprocess.Popen = real
    ctx.check(f"returned near the deadline, took {time.monotonic() - started:.1f}s", time.monotonic() - started < 30)
    ctx.check(f"code 124, got {out['code']}", out["code"] == 124)
    ctx.check("lines read before the deadline were handled", any(e.get("type") == "system" for e in out["events"]))


@test
def test_i43_a_normal_child_still_returns_its_exit_code_and_lines(ctx: Ctx):
    import subprocess
    from halo_harness.design import session
    from halo_harness.design.store import Project
    p = Project.create("Quick turn")
    real = subprocess.Popen
    script = "import sys; print('{\"type\": \"result\", \"result\": \"hi\"}'); print('plain text'); sys.exit(3)"
    subprocess.Popen = lambda cmd, **kw: real([sys.executable, "-c", script], **kw)
    try:
        out = session.run_turn(p, "go", entries={}, registered=set(), timeout=30)
    finally:
        subprocess.Popen = real
    ctx.check(f"exit code kept, got {out['code']}", out["code"] == 3)
    ctx.check("result text and a plain line both arrive", out["text"] == "hi" and any(e.get("text") == "plain text" for e in out["events"]))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="review3 p tests"))
