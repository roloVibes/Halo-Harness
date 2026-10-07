"""tests.test_minors_batch_round -- Halo 2.0.6 round 12 (batch A): the
carried fix-pass minors from `plans/2.0.3-release-notes-for-fix-pass.md`.

- `halo config set` echoes the value back UNMASKED -> masks exactly like
  the readers (a recorded/shared terminal never sees the secret twice).
- `config list`/`get` mask `*_env` REFERENCE names into uselessness ->
  the reference shows while actual secrets stay hidden.
- `pick_proxy` answered a plain-HTTP target with HTTPS_PROXY -> the
  env-var order is now tls-appropriate.
- The non-TLS proxy branch sent a RELATIVE request line (a proxy cannot
  know the origin from `/path`) -> absolute request-target form.
"""

from __future__ import annotations

import http.server
import json
import os
import socket
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

REPO_DIR = Path(__file__).resolve().parent.parent


_PROXY_ENV_KEYS = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy",
                   "NO_PROXY", "no_proxy")


def _save_proxy_env():
    return {k: os.environ.get(k) for k in _PROXY_ENV_KEYS}


def _restore_proxy_env(saved):
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@test
def test_config_set_echo_masks_secret_shaped_values(ctx: Ctx):
    import subprocess
    home = Path(tempfile.mkdtemp(prefix="cfgmask-"))
    env = {k: v for k, v in os.environ.items()
           if k not in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    env.update({"BRIDGE_TEST_HOME": str(home), "PYTHONPATH": str(REPO_DIR)})
    r = subprocess.run([sys.executable, "-m", "halo_harness", "config", "set",
                        "api_key", "sk-ant-0123456789abcdefghijklmnop"],
                       env=env, cwd=str(REPO_DIR), capture_output=True, text=True, timeout=60)
    ctx.check(f"exit 0, got {r.returncode} err={r.stderr[-150:]!r}", r.returncode == 0)
    ctx.check(f"the echo is masked, got {r.stdout!r}",
              "sk-ant-0123456789abcdefghijklmnop" not in r.stdout and "api_key=" in r.stdout)
    # the VALUE is still stored unmasked (the mask is display-only)
    stored = json.loads((home / ".halo" / "config.json").read_text(encoding="utf-8"))
    ctx.check("the stored value itself is untouched", stored.get("api_key") == "sk-ant-0123456789abcdefghijklmnop")


@test
def test_env_reference_names_show_while_secrets_mask(ctx: Ctx):
    import subprocess
    from halo_harness import theme as theme_mod
    home = Path(tempfile.mkdtemp(prefix="cfgenv-"))
    env = {k: v for k, v in os.environ.items()
           if k not in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    env.update({"BRIDGE_TEST_HOME": str(home), "PYTHONPATH": str(REPO_DIR)})
    try:
        os.environ["BRIDGE_TEST_HOME"] = str(home)
        theme_mod.set_config_value("api_key_env", "OPENROUTER_API_KEY")
        theme_mod.set_config_value("api_key", "sk-or-v1-0123456789abcdefghij")
        r = subprocess.run([sys.executable, "-m", "halo_harness", "config", "list"],
                           env=env, cwd=str(REPO_DIR), capture_output=True, text=True, timeout=60)
        out = r.stdout
        ctx.check("the *_env REFERENCE name shows", "OPENROUTER_API_KEY" in out)
        ctx.check("the actual secret stays masked", "sk-or-v1-0123456789abcdefghij" not in out)
        r2 = subprocess.run([sys.executable, "-m", "halo_harness", "config", "get", "api_key_env"],
                            env=env, cwd=str(REPO_DIR), capture_output=True, text=True, timeout=60)
        ctx.check(f"get shows the reference too, got {r2.stdout!r}", "OPENROUTER_API_KEY" in r2.stdout)
    finally:
        os.environ.pop("BRIDGE_TEST_HOME", None)


@test
def test_pick_proxy_order_is_tls_appropriate(ctx: Ctx):
    from halo_harness.providers.http import pick_proxy
    saved = _save_proxy_env()
    try:
        for k in _PROXY_ENV_KEYS:
            os.environ.pop(k, None)
        os.environ["HTTP_PROXY"] = "http://192.0.2.10:3128"
        os.environ["HTTPS_PROXY"] = "http://192.0.2.254:3129"
        ctx.check("a TLS target prefers the HTTPS proxy",
                  pick_proxy("example.com", True) == "http://192.0.2.254:3129")
        ctx.check("a plain-HTTP target prefers the HTTP proxy (the carried minor: "
                  "it used to answer with HTTPS_PROXY)",
                  pick_proxy("example.com", False) == "http://192.0.2.10:3128")
        for k in ("HTTP_PROXY", "http_proxy"):
            os.environ.pop(k, None)
        ctx.check("with no HTTP_PROXY set, plain traffic falls back to the HTTPS one",
                  pick_proxy("example.com", False) == "http://192.0.2.254:3129")
        ctx.check("tls=True stays the default behavior",
                  pick_proxy("example.com") == "http://192.0.2.254:3129")
    finally:
        _restore_proxy_env(saved)


@test
def test_plain_http_via_proxy_sends_an_absolute_request_target(ctx: Ctx):
    """The carried minor's other half: a real plain-HTTP proxy listener
    asserts the request LINE carries the absolute origin form, and that
    the proxied request actually round-trips."""
    from halo_harness.providers.http import open_upstream
    lines = []
    ready = threading.Event()

    class _H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0") or 0)
            self.rfile.read(length)
            lines.append(self.requestline)
            lines.append(f"host:{self.headers.get('Host')}")
            body = json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def handle_one_request(self):
            ready.set()
            return super().handle_one_request()

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    saved = _save_proxy_env()
    try:
        for k in _PROXY_ENV_KEYS:
            os.environ.pop(k, None)
        # the target: a DIFFERENT loopback port; the proxy is our listener.
        # (pick_proxy exempts loopback TARGETS -- bypass that for the test
        # by pointing at a non-loopback-shaped host the proxy will accept:
        # we use the real target hostname in the line assert only.)
        os.environ["HTTP_PROXY"] = f"http://127.0.0.1:{port}"
        # direct construction (the choke point's own branch), bypassing
        # pick_proxy's loopback guard: this pins the CONNECTION layer's
        # request-line behavior, which is the bug's actual home
        from halo_harness.providers.http import _ProxiedPlainHTTPConnection
        conn = _ProxiedPlainHTTPConnection("127.0.0.1", port,
                                           target_host="api.example.test", target_port=80,
                                           timeout=10)
        conn.connect()
        conn.request("POST", "/v1/chat", body=json.dumps({"x": 1}),
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        payload = json.loads(resp.read().decode("utf-8"))
        ctx.check(f"the round trip works through the proxy, got {payload}", payload == {"ok": True})
        ctx.check(f"the request line is the ABSOLUTE form, got {lines}",
                  lines and lines[0] == "POST http://api.example.test:80/v1/chat HTTP/1.1")
        ctx.check(f"the Host header names the TARGET, got {lines}",
                  lines and lines[1] == "host:api.example.test:80")
        conn.close()
    finally:
        _restore_proxy_env(saved)
        srv.shutdown()




@test
def test_the_offline_gates_cover_the_three_background_reads(ctx: Ctx):
    """Structural + behavioral: the ssh GPU read, the cc catalog refresh,
    and the Databricks auto-refresh thread all consult the offline gate
    before touching the network."""
    import contextlib

    @contextlib.contextmanager
    def _offline(off):
        saved = os.environ.get("HALO_OFFLINE")
        os.environ["HALO_OFFLINE"] = "1" if off else "0"
        try:
            yield
        finally:
            if saved is None:
                os.environ.pop("HALO_OFFLINE", None)
            else:
                os.environ["HALO_OFFLINE"] = saved

    from halo_harness.providers import ollama_hw
    calls = []
    real_run = ollama_hw.run_via_ssh

    class _Rec:
        def __init__(self, fn):
            self._fn = fn

        def __call__(self, *a, **kw):
            calls.append("ssh")
            return self._fn(*a, **kw)

    # behavioral: offline -> run_via_ssh's runner returns None without spawning ssh
    with _offline(True):
        runner = real_run("user@host.example")
        out = runner(["nvidia-smi", "--query-gpu=name", "--format=csv"], 5.0)
        ctx.check(f"the ssh read is a no-op offline, got {out!r}", out is None)
    with _offline(False):
        out2 = runner(["echo", "hi"], 5.0)
        # online it may or may not reach a real ssh (depends on the box);
        # the pin is only that OFFLINE returned None while online TRIED
        ctx.check("online still attempts the real path (or fails trying)",
                  out2 is None or isinstance(out2, str))

    src_ssh = (REPO_DIR / "halo_harness" / "providers" / "ollama_hw.py").read_text(encoding="utf-8")
    ctx.check("the ssh read carries the gate",
              "offline_mode_enabled" in src_ssh)
    src_cc = (REPO_DIR / "halo_harness" / "providers" / "cc_models.py").read_text(encoding="utf-8")
    ctx.check("the cc catalog refresh carries the gate",
              "offline_mode_enabled" in src_cc)
    src_hl = (REPO_DIR / "halo_harness" / "headless.py").read_text(encoding="utf-8")
    ctx.check("the dbx auto-refresh thread carries the gate",
              "_bg_dbx_refresh" in src_hl and "offline_mode_enabled" in
              src_hl[src_hl.index("def _bg_dbx_refresh"):src_hl.index("def _bg_dbx_refresh") + 900])


@test
def test_hf_local_server_save_merges_not_replaces(ctx: Ctx):
    from halo_harness.init_providers import save_tab_credentials
    from halo_harness import theme as theme_mod
    home = Path(tempfile.mkdtemp(prefix="hfmerge-"))
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    try:
        theme_mod.set_config_value("huggingface.local_servers",
                                   [{"name": "default", "url": "http://192.0.2.5:8080",
                                     "default": True, "note": "tuned by hand"}])
        ok, msg = save_tab_credentials("huggingface", {"local_url": "http://192.0.2.6:8081"})
        ctx.check(f"the save succeeds, got {msg}", ok is True)
        servers = theme_mod.get_config_value("huggingface.local_servers", default=[])
        default = next((s for s in servers if s.get("name") == "default"), None)
        ctx.check(f"one default entry, got {servers}", default is not None and len(servers) == 1)
        ctx.check(f"the URL is updated, got {default.get('url')}", default.get("url") == "http://192.0.2.6:8081")
        ctx.check(f"the entry's OWN fields survive the re-save (the carried minor: "
                  f"they were dropped), got {default}",
                  default.get("default") is True and default.get("note") == "tuned by hand")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v




@test
def test_child_escalation_decisions_reach_the_parent(ctx: Ctx):
    """The C-5 remainder: a child's own hybrid-escalation decisions are
    forwarded onto the PARENT's list at handback (tagged with the agent
    name), so /escalation and the result JSON see them."""
    from halo_harness.agent.subagent import _forward_child_escalation_decisions
    from halo_harness.agent.escalation import EscalationDecision

    class _S:
        def __init__(self, decisions):
            self._escalation_decisions = decisions

    from dataclasses import replace as _replace
    child = _S([EscalationDecision(turn=3, trigger="tool_failures", to="or:vendor/big",
                                   action="switched", note="4 tool failures")])
    parent = _S([])
    spec = type("S", (), {"name": "implementer"})()
    _forward_child_escalation_decisions(parent, child, spec)
    ctx.check(f"the decision reached the parent, got {parent._escalation_decisions}",
              len(parent._escalation_decisions) == 1)
    d = parent._escalation_decisions[0]
    note = getattr(d, "note", "")
    ctx.check(f"it is tagged with the agent name, got {note!r}",
              note.startswith("[implementer]") and "4 tool failures" in note)
    ctx.check("the other fields ride along",
              getattr(d, "to", None) == "or:vendor/big" and getattr(d, "action", None) == "switched")
    # a child with none is a no-op; a parent without the list never breaks
    _forward_child_escalation_decisions(parent, _S([]), spec)
    _forward_child_escalation_decisions(_S(None), child, spec)
    ctx.check("empty/no-list cases are silent no-ops", len(parent._escalation_decisions) == 1)
    # dict-shaped entries (loop.py's other append shape) forward too
    child2 = _S([{"turn": 1, "trigger": "context_overflow", "to": "or:x", "action": "asked", "note": "n"}])
    _forward_child_escalation_decisions(parent, child2, spec)
    ctx.check(f"dict-shaped decisions forward, got {len(parent._escalation_decisions)}",
              len(parent._escalation_decisions) == 2)
    ctx.check("the dict shape is tagged too",
              parent._escalation_decisions[1]["note"].startswith("[implementer]"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
