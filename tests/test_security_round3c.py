"""tests.test_security_round3c -- 2.0.10 round 3, security fix pass 1, the
credential finding 17 of docs/harness/SECURITY-REVIEW-2.0.10.md (section
D): both redactors catch the real shapes (JSON-in-JSON pairs, URL
credentials, backslash and numeric values, header dicts, log lines).
Findings 18-20 are pinned in tests/test_security_round3d.py. Secret-shaped
values are assembled at run time so no key-shaped literal sits in the repo.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="halo-sec3c-home-"))

OR_KEY = "sk-" + "or-v1-" + "0123456789abcdef0123456789abcdef"  # fake, built at run time


@contextlib.contextmanager
def _env(**values):
    saved = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---- 17: the redactors ---------------------------------------------------


@test
def test_f17_pair_inside_a_tool_result_is_redacted(ctx: Ctx):
    from halo_harness.redact import sanitize_node
    secret = "tok_live_a1b2c3d4e5f6g7h8"
    excerpt = '{\n  "env": {\n    "MY_SERVICE_TOKEN": "' + secret + '"\n  }\n}'
    node = {"type": "user", "message": {"content": [{"type": "tool_result", "content": excerpt}]}}
    out = json.dumps(sanitize_node(node))
    ctx.check("the value is gone", secret not in out)
    ctx.check("the node is still a node", "_sanitize_error" not in out)


@test
def test_f17_url_credentials_any_scheme(ctx: Ctx):
    from halo_harness.redact import sanitize_text
    for url in ("https://alice:hunter2pass@git.example.com/x.git", "http://u:p4ssw0rd@pypi.example.com/simple",
                "ssh://git:t0k3nvalue@host.example.com/r", "postgres://u:dbpass12@db/x"):
        out = sanitize_text("remote: " + url)
        ctx.check(f"credential removed from {url.split('@')[1]}", "@" in out and url.split(":")[2].split("@")[0] not in out)
    ctx.check("a URL without credentials is untouched", sanitize_text("see https://example.com/a?b=c") == "see https://example.com/a?b=c")


@test
def test_f17_backslash_and_numeric_values(ctx: Ctx):
    from halo_harness.redact import sanitize_node, sanitize_text
    out = sanitize_text("PASSWORD=ab\\cd\\ef9 next")
    ctx.check(f"whole backslash value redacted, got {out!r}", "ef9" not in out and "cd" not in out)
    out = sanitize_text("PIN=123456")
    ctx.check(f"all-digit PIN redacted, got {out!r}", "123456" not in out)
    out = sanitize_text('{"input_tokens": 12, "max_tokens": 4096}')
    ctx.check("token COUNTS stay readable", out == '{"input_tokens": 12, "max_tokens": 4096}')
    node = sanitize_node({"type": "assistant", "usage": {"input_tokens": 12, "api_key": 99887766}, "pin": 5})
    ctx.check(f"a numeric api_key is redacted and the node stays valid, got {node}",
              "99887766" not in json.dumps(node) and node.get("type") == "assistant")


@test
def test_f17_known_secret_values_with_json_escapes(ctx: Ctx):
    from halo_harness.redact import redact_for_bugreport
    secret = 'pa"ss\\word-9'
    line = json.dumps({"detail": "login with " + secret})
    out = redact_for_bugreport(line, known_secret_values=(secret,))
    ctx.check(f"escaped spelling of the known value is gone, got {out}", "word-9" not in out)


@test
def test_f17_log_formatter_redacts_real_request_and_log_shapes(ctx: Ctx):
    from halo_harness.providers.config import RedactingFormatter
    fmt = RedactingFormatter("%(message)s")

    def render(msg, *args):
        rec = logging.LogRecord("bridge", logging.WARNING, __file__, 1, msg, args, None)
        return fmt.format(rec)

    key = OR_KEY
    cases = {
        "header line": "Authorization: Bearer " + key,
        "header dict": "headers=%r" % {"Authorization": "Bearer " + key},
        "query": "GET /v1/x?api_key=" + key + " HTTP/1.1",
        "dict key": "cfg=%r" % {"api_key": key},
        "env line": "OPENROUTER_API_KEY=" + key,
        "upstream body": "Incorrect API key provided: " + key,
        "url credential": "fetching https://bob:s3cretpw@host.example.com/x",
    }
    for label, text in cases.items():
        out = render("%s", text)
        ctx.check(f"{label}: nothing key-shaped survives, got {out!r}",
                  key not in out and key[:20] not in out and "s3cretpw" not in out)
    ctx.check("an ordinary line is unchanged", render("started on port %d", 8080) == "started on port 8080")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
