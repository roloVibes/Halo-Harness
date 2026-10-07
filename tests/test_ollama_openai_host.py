"""tests.test_ollama_openai_host -- Halo 2.0.5 round 5: the optional
"dialect": "openai" on an `ollama.hosts` entry -- an OpenAI-dialect
gateway in front of Ollama (it serves only /v1/chat/completions and
/v1/models, with the entry's own api_key as the bearer) used as a real
`ol:` host. Pinned here: the config parse + the native fallback for an
unrecognized value, the doctor WARN line, the ModelRef flip (identity-
preserving, idempotent, never touching a native host), the per-dialect
enumeration path (/v1/models vs /api/tags), and two end-to-end
`halo -p` children against mocks on a random loopback port -- the
gateway child must POST /v1/chat/completions with the host entry's own
bearer (never /api/chat), the native control child must still POST
/api/chat. Never a literal LAN address in this file
(tests/test_privacy_scan.py).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_ollama import SCENARIOS as NATIVE_SCENARIOS
from tests.helpers.mock_ollama import MockUpstream as MockOllama
from tests.helpers.mock_openai import MockUpstream as MockOpenAI
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

_GATEWAY_MODELS = {"object": "list", "data": [{"id": "qwen3-coder:30b"}, {"id": "qwen3.8:27b"}]}
_GATEWAY_TOKEN = "host-entry-gateway-token"

_STATE_ENV_NAMES = ("BRIDGE_STATE_DIR", "BRIDGE_TEST_HOME", "OLLAMA_HOST", "OLLAMA_API_KEY",
                    "HF_HUB_CACHE", "BRIDGE_TEST_NO_BACKGROUND_NET")


class _StateEnv:
    """Scopes every in-process config read the way tests/test_local_models.py
    does: a fresh BRIDGE_STATE_DIR (get_config_value/set_config_value never
    touch the real ~/.halo), an unreachable synthesized-default OLLAMA_HOST,
    an empty HF_HUB_CACHE, background net off."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _STATE_ENV_NAMES}
        d = Path(tempfile.mkdtemp(prefix="ol-openai-host-"))
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["OLLAMA_HOST"] = "http://127.0.0.1:1"
        os.environ.pop("OLLAMA_API_KEY", None)
        os.environ["HF_HUB_CACHE"] = str(d / "empty-hf-cache")
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        self.state_dir = d / ".halo"
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _hermetic_child_env() -> dict:
    env = dict(os.environ)
    for k in [k for k in env if k.startswith(("HALO_", "OPENROUTER_", "OLLAMA_", "OPENAI_",
                                              "ANTHROPIC_", "DATABRICKS_", "BRIDGE_"))]:
        env.pop(k, None)
    return env


def _run_cli(fh, prompt, *, model, timeout=90):
    env = _hermetic_child_env()
    env.update({"BRIDGE_TEST_HOME": str(fh["home"]), "BRIDGE_TEST_NO_BACKGROUND_NET": "1",
                "PYTHONPATH": str(REPO_DIR)})
    args = [sys.executable, "-m", "halo_harness", "-p", prompt, "--model", model,
            "--cwd", str(fh["proj"]), "--permission-mode", "auto"]
    return subprocess.run(args, env=env, cwd=str(REPO_DIR), capture_output=True, text=True, timeout=timeout)


def _write_hosts(fh, hosts) -> None:
    cfg_path = fh["home"] / ".halo" / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    cfg["ollama"] = {"hosts": hosts}
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _posts(mock, suffix: str) -> list:
    return [r for r in mock.requests if r["method"] == "POST" and r["path"].rstrip("/").endswith(suffix)]


def _gets(mock, path: str) -> list:
    return [r for r in mock.requests if r["method"] == "GET" and r["path"] == path]


@test
def test_host_entry_parses_dialect_and_unknown_falls_back(ctx: Ctx):
    from halo_harness.providers.ollama import (
        _host_from_dict, host_is_openai_dialect, openai_base_url_for_host,
    )
    plain = _host_from_dict({"name": "lan", "url": "http://127.0.0.1:11434"})
    ctx.check(f"no dialect field -> None (native), got {plain.dialect!r}", plain.dialect is None)
    ctx.check("native host is not openai dialect", host_is_openai_dialect(plain) is False)
    for raw, note in (('"openai"', "lowercase"), ('"OpenAI"', "case-insensitive")):
        h = _host_from_dict({"name": "lan", "url": "http://127.0.0.1:11435", "dialect": json.loads(raw)})
        ctx.check(f"{note} 'openai' accepted, got {h.dialect!r}", h.dialect == "openai")
        ctx.check(f"{note} host is openai dialect", host_is_openai_dialect(h) is True)
    weird = _host_from_dict({"name": "lan", "url": "http://127.0.0.1:11435", "dialect": "gateway-ish"})
    ctx.check(f"unknown value kept for doctor's WARN, got {weird.dialect!r}", weird.dialect == "gateway-ish")
    ctx.check("unknown value falls back to native", host_is_openai_dialect(weird) is False)
    openai_host = _host_from_dict({"name": "lan", "url": "http://127.0.0.1:11435", "dialect": "openai"})
    ctx.check(f"/v1 appended once, got {openai_base_url_for_host(openai_host)!r}",
              openai_base_url_for_host(openai_host) == "http://127.0.0.1:11435/v1")
    already = _host_from_dict({"name": "lan", "url": "http://127.0.0.1:11435/v1", "dialect": "openai"})
    ctx.check(f"a url already ending in /v1 is used verbatim, got {openai_base_url_for_host(already)!r}",
              openai_base_url_for_host(already) == "http://127.0.0.1:11435/v1")
    ctx.check("native host -> None (the caller keeps host.url)", openai_base_url_for_host(plain) is None)


@test
def test_apply_host_dialect_flips_only_openai_hosts(ctx: Ctx):
    from halo_harness.model import parse_model_ref
    from halo_harness.providers.ollama import apply_host_dialect
    from halo_harness.theme import set_config_value
    with _StateEnv():
        set_config_value("ollama.hosts", [
            {"name": "gateway", "url": "http://127.0.0.1:11435", "api_key": "k", "dialect": "openai"},
            {"name": "native", "url": "http://127.0.0.1:11434", "default": True},
        ])
        # parse stays pure routes-only: the native dialect, whatever the host says.
        ref = parse_model_ref("ol:qwen3-coder:30b@gateway")
        ctx.check(f"parse-time dialect stays native, got {ref.dialect!r}", ref.dialect == "ollama")
        flipped = apply_host_dialect(ref)
        ctx.check(f"an openai-dialect host flips the ref, got {flipped.dialect!r}",
                  flipped.dialect == "openai-chat")
        ctx.check("a flip is a fresh ref, never a mutation", flipped is not ref)
        ctx.check(f"raw/model/host survive the flip, got {flipped.raw!r}/{flipped.model!r}/{flipped.host!r}",
                  (flipped.raw, flipped.model, flipped.host) == (ref.raw, ref.model, ref.host))
        ctx.check("idempotent: a second application is identity-preserving",
                  apply_host_dialect(flipped) is flipped)
        nref = parse_model_ref("ol:qwen3:30b@native")
        ctx.check("a NATIVE host entry never flips (same object back)",
                  apply_host_dialect(nref) is nref)
        oref = parse_model_ref("or:qwen/qwen3-coder")
        ctx.check("a non-ol: ref passes through untouched", apply_host_dialect(oref) is oref)


@test
def test_doctor_names_dialect_and_warns_on_unknown(ctx: Ctx):
    from halo_harness.doctor import _check_ollama_hosts
    from halo_harness.theme import set_config_value
    with _StateEnv():
        gateway = MockOpenAI(path_prefix="/v1", expected_bearer=_GATEWAY_TOKEN).start()
        native = MockOllama().start()
        try:
            gateway.models_response = _GATEWAY_MODELS
            set_config_value("ollama.hosts", [
                {"name": "gateway", "url": f"http://127.0.0.1:{gateway.port}",
                 "api_key": _GATEWAY_TOKEN, "dialect": "openai"},
                {"name": "weird", "url": native.base_url, "dialect": "gateway-ish"},
                {"name": "native", "url": native.base_url, "default": True},
            ])
            entries = _check_ollama_hosts()
            ok_lines = [line for _c, line in entries if line.startswith("[OK]")]
            ctx.check("the gateway is probed via /v1/models and named openai dialect",
                      any("via /v1/models" in line and "(openai dialect)" in line for line in ok_lines))
            warn = [line for _c, line in entries if "unknown dialect" in line]
            ctx.check(f"exactly one WARN naming the value and the fallback, got {warn!r}",
                      len(warn) == 1 and "'gateway-ish'" in warn[0] and "falling back to the native" in warn[0])
            native_ok = [line for line in ok_lines if "version" in line]
            ctx.check(f"both native hosts stay on the native probe, got {native_ok!r}", len(native_ok) == 2)
            models_gets = _gets(gateway, "/v1/models")
            ctx.check(f"the gateway probe carried the host bearer, got {len(models_gets)}",
                      len(models_gets) >= 1
                      and models_gets[0]["headers"].get("authorization") == f"Bearer {_GATEWAY_TOKEN}")
        finally:
            gateway.stop()
            native.stop()


@test
def test_enumeration_path_per_dialect(ctx: Ctx):
    from halo_harness.providers.local_models import build_local_view
    from halo_harness.theme import set_config_value
    with _StateEnv() as e:
        gateway = MockOpenAI(path_prefix="/v1", expected_bearer=_GATEWAY_TOKEN).start()
        native = MockOllama().start()
        try:
            gateway.models_response = _GATEWAY_MODELS
            set_config_value("ollama.hosts", [
                {"name": "gateway", "url": f"http://127.0.0.1:{gateway.port}",
                 "api_key": _GATEWAY_TOKEN, "dialect": "openai"},
                {"name": "bench", "url": native.base_url},
            ])
            rows = build_local_view(env=dict(os.environ), state_dir=e.state_dir)
            refs = {r.ref for r in rows if r.ref}
            ctx.check(f"gateway models listed from /v1/models, got {sorted(refs)!r}",
                      "ol:qwen3-coder:30b@gateway" in refs and "ol:qwen3.8:27b@gateway" in refs)
            ctx.check("native models still listed from /api/tags", "ol:qwen3:30b@bench" in refs)
            models_gets = _gets(gateway, "/v1/models")
            ctx.check(f"gateway enumeration hit /v1/models with the bearer, got {len(models_gets)}",
                      len(models_gets) >= 1
                      and models_gets[0]["headers"].get("authorization") == f"Bearer {_GATEWAY_TOKEN}")
            tags_gets = _gets(native, "/api/tags")
            ctx.check(f"native enumeration still hits /api/tags, got {len(tags_gets)}", len(tags_gets) >= 1)
        finally:
            gateway.stop()
            native.stop()


@test
def test_gateway_host_end_to_end_child(ctx: Ctx):
    fh = build_fake_home()
    gateway = MockOpenAI(path_prefix="/v1", expected_bearer=_GATEWAY_TOKEN).start()
    try:
        gateway.models_response = _GATEWAY_MODELS
        # the entry's url is the bare host:port -- openai_base_url_for_host
        # must add the /v1 segment for the chat path.
        _write_hosts(fh, [{"name": "gateway", "url": f"http://127.0.0.1:{gateway.port}",
                           "api_key": _GATEWAY_TOKEN, "dialect": "openai", "default": True}])
        result = _run_cli(fh, "Reply with exactly one word: pong", model="ol:qwen3-coder:30b@gateway")
        ctx.check(f"exit 0, got {result.returncode} stderr={result.stderr[-600:]!r}", result.returncode == 0)
        ctx.check(f"the reply is the gateway's text, got {result.stdout[-300:]!r}", "pong" in result.stdout)
        chats = _posts(gateway, "/chat/completions")
        ctx.check(f"the chat went to the OpenAI path, got {len(chats)}", len(chats) >= 1)
        if chats:
            req = chats[0]
            ctx.check(f"bearer is the HOST entry's own key, got {req['headers'].get('authorization')!r}",
                      req["headers"].get("authorization") == f"Bearer {_GATEWAY_TOKEN}")
            ctx.check(f"the ol: model id is on the wire, got {req['body'].get('model')!r}",
                      req["body"].get("model") == "qwen3-coder:30b")
        stray = [r for r in gateway.requests if "/api/" in r["path"]]
        ctx.check(f"no recorded request touched a native /api/* path, got {stray!r}", not stray)
    finally:
        gateway.stop()


@test
def test_native_host_child_control_still_posts_api_chat(ctx: Ctx):
    fh = build_fake_home()
    native = MockOllama(scenarios={"qwen3:30b": NATIVE_SCENARIOS["plain-text"]}).start()
    try:
        _write_hosts(fh, [{"name": "bench", "url": native.base_url, "default": True}])
        result = _run_cli(fh, "say hi", model="ol:qwen3:30b@bench")
        ctx.check(f"exit 0, got {result.returncode} stderr={result.stderr[-600:]!r}", result.returncode == 0)
        ctx.check(f"native reply printed, got {result.stdout[-300:]!r}", "Hello" in result.stdout)
        chats = _posts(native, "/api/chat")
        ctx.check(f"the native dialect still posts /api/chat, got {len(chats)}", len(chats) >= 1)
        v1 = [r for r in native.requests if r["path"].startswith("/v1")]
        ctx.check(f"no /v1 OpenAI path was used by the native dialect, got {v1!r}", not v1)
    finally:
        native.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
