"""tests.test_review2_round2 -- pins for the vibes/review.md findings fixed
in R5 (credentials + file safety; drafted by the local Ollama model,
corrected in-session -- the token-thrift offload flow):

  * f14  proxy launch file: 0600 atomic write (was umask-perms, truncate)
  * f15  env writer: atomic, preserves other keys, chmods only halo's dir
  * f16  redaction: password keys, Authorization/x-api-key headers, URL
        credentials, Slack webhooks, ghs_/sk_live_/xoxb-/AIza tokens, PEM
        blocks, quoted values with spaces -- and numeric usage keys (and
        the nodes carrying them) survive /export --sanitize
  * f16  bugreport harvests settings env + MCP env/headers values
  * f17  release.py: token in a 0600 curl -K config, never on argv, with
        --fail so a failed upload can't report success
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()

REPO = Path(__file__).resolve().parent.parent


# ---- finding 16: redaction battery ----


@test
def test_f16_redaction_battery(ctx: Ctx):
    from halo_harness.redact import sanitize_text
    out = sanitize_text('{"password": "hunter two seeks"}')
    ctx.check("password value with spaces fully redacted", "hunter" not in out and "<redacted>" in out)
    out = sanitize_text('Authorization: Token ghs_abc123def456ghi789')
    ctx.check("Authorization: Token header redacted", "<redacted>" in out and "ghs_abc" not in out)
    out = sanitize_text('x-api-key: ghs_abcdefgh12345678')
    ctx.check("x-api-key header redacted", "<redacted>" in out and "ghs_abcdef" not in out)
    out = sanitize_text('postgres://alice:s3cretpw@db.internal:5432/prod')
    ctx.check("postgres password redacted, host kept",
              "s3cretpw" not in out and "db.internal" in out and "<redacted>" in out)
    out = sanitize_text('https://hooks.slack.com/services/T123/B456/XYZSECRET')
    ctx.check("slack webhook secret redacted",
              "XYZSECRET" not in out and "hooks.slack.com/services/<redacted>" in out)
    ctx.check("slack bot token redacted", sanitize_text('xoxb-123456789-abcdef') == '<redacted>')
    ctx.check("gcp key redacted",
              sanitize_text('AIzaSyA1234567890abcdefghijklmnopqrstu') == '<redacted>')
    pem = '-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA1234abcd\n-----END RSA PRIVATE KEY-----'
    out = sanitize_text(pem)
    ctx.check("pem private key redacted", out.startswith('<redacted PEM key>') and "MIIEow" not in out)
    out = sanitize_text('"GITHUB_TOKEN": "ghp_abcdefghijklmnopqrstuvwx"')
    ctx.check("github token still redacted", "ghp_" not in out)
    ctx.check("bearer still redacted",
              "<redacted>" in sanitize_text('Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'))


# ---- finding 16: numeric usage keys survive --sanitize ----


@test
def test_f16_numeric_usage_keys_survive(ctx: Ctx):
    from halo_harness.redact import sanitize_node, sanitize_text
    t = sanitize_text('{"input_tokens": 12, "cache_read_input_tokens": 345, "output_tokens": 67}')
    ctx.check("usage json round-trips with values intact",
              json.loads(t) == {"input_tokens": 12, "cache_read_input_tokens": 345, "output_tokens": 67})
    node = {"type": "assistant", "usage": {"input_tokens": 12, "output_tokens": 40},
            "message": {"content": [{"type": "text", "text": "answer"}]}}
    out = sanitize_node(node)
    ctx.check("assistant node survives sanitize", out.get("type") == "assistant"
              and "_sanitize_error" not in out and out.get("usage") == node["usage"])


# ---- finding 14: write_private_atomic ----


@test
def test_f14_write_private_atomic(ctx: Ctx):
    from halo_harness.privateio import write_private_atomic
    tmpdir = Path(tempfile.mkdtemp())
    p = tmpdir / "launch-123.json"
    write_private_atomic(p, '{"token": "abc"}')
    ctx.check("file written", p.exists() and p.read_text() == '{"token": "abc"}')
    if os.name != "nt":
        ctx.check("0600 on POSIX", stat.S_IMODE(p.stat().st_mode) == 0o600)
    write_private_atomic(p, '{"token": "xyz"}')
    ctx.check("overwrite ok", p.read_text() == '{"token": "xyz"}')
    ctx.check("no temp files left behind", not list(tmpdir.glob(".*.tmp")))


# ---- finding 15: env writer atomic and preserving ----


@test
def test_f15_env_writer_atomic_and_preserving(ctx: Ctx):
    from halo_harness.init_cli import _write_env_var
    tmpdir = Path(tempfile.mkdtemp())
    p = tmpdir / "env"
    p.write_text("OPENROUTER_API_KEY=old\nDATABRICKS_TOKEN=keep\n", encoding="utf-8")
    _write_env_var(p, "OPENROUTER_API_KEY", "new")
    text = p.read_text(encoding="utf-8")
    ctx.check("key updated", "OPENROUTER_API_KEY=new" in text)
    ctx.check("other key preserved", "DATABRICKS_TOKEN=keep" in text)
    ctx.check("old value gone", "old" not in text)
    if os.name != "nt":
        ctx.check("file is 0600", stat.S_IMODE(p.stat().st_mode) == 0o600)
    _write_env_var(p, "ANTHROPIC_API_KEY", "sk-ant-testtesttesttest")
    ctx.check("new key appended",
              "ANTHROPIC_API_KEY=sk-ant-testtesttesttest" in p.read_text(encoding="utf-8"))


# ---- finding 17: release token off argv ----


@test
def test_f17_release_token_off_argv(ctx: Ctx):
    spec = importlib.util.spec_from_file_location("release_mod", REPO / "scripts" / "release.py")
    release_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release_mod)
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    out = release_mod.publish_github_release(
        "9.9.9", "notes", repo_dir=REPO, run_fn=fake_run, gh_path_fn=lambda: None,
        token_fn=lambda repo_dir=None, run_fn=None: "ghp_testtoken123456789abcdef")
    ctx.check("one curl call made (id-unreadable early return)", len(calls) == 1)
    argv = calls[0]
    ctx.check("token never appears on argv", not any("ghp_testtoken" in a for a in argv))
    ctx.check("-K config used", "-K" in argv)
    kcfg = Path(argv[argv.index("-K") + 1])
    ctx.check("config file deleted after", not kcfg.exists())
    ctx.check("--fail flag present", "-f" in argv)
    ctx.check("returns the id-unreadable message", "could not be read" in out)


# ---- finding 16: bugreport harvests settings env + MCP env/headers ----


@test
def test_f16_bugreport_mcp_harvest(ctx: Ctx):
    from halo_harness.bugreport import _collect_known_secret_values
    fake = SimpleNamespace(effective_env={"MY_SERVICE_API_KEY": "supersecretvalue123"})

    class FakeCfg:
        env = {"GITHUB_TOKEN": "ghp_mcpvalue123456789"}
        headers = {"Authorization": "token ghs_headervalue123456"}

    vals = _collect_known_secret_values(settings=fake, mcp_servers={"srv": FakeCfg()})
    ctx.check("settings env value harvested", "supersecretvalue123" in vals)
    ctx.check("mcp env value harvested", "ghp_mcpvalue123456789" in vals)
    ctx.check("mcp header value harvested", "token ghs_headervalue123456" in vals)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
