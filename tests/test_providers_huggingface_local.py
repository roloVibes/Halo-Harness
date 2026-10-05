"""tests.test_providers_huggingface_local -- Halo 2.0.3 round 5: `hf:
local/*` ref parsing, `huggingface.local_servers` config resolution,
credential resolution (manual entry, never cross-wired with HF_TOKEN or
an `huggingface.endpoints` token), enablement, and the print-mode
end-to-end run against a fake server configured by URL (a manual entry --
see tests/test_providers_huggingface_local_probe.py for auto-detection
itself).
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
from tests.helpers.mock_openai import MockUpstream
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

_PROVIDER_ENV_VARS = (
    "HF_TOKEN", "OPENROUTER_API_KEY", "DATABRICKS_HOST", "DATABRICKS_TOKEN",
    "ANTHROPIC_API_KEY", "TYPESAFE_API_KEY", "BRIDGE_TEST_CC_AUTH_STATUS", "OLLAMA_HOST",
)


class _Env:
    """Same pattern as tests/test_providers_huggingface.py's own `_Env`."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in
                       (("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_ENV_FILE") + _PROVIDER_ENV_VARS)}
        d = Path(tempfile.mkdtemp(prefix="hf-local-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["BRIDGE_ENV_FILE"] = str(d / "no-env-file")
        for k in _PROVIDER_ENV_VARS:
            os.environ.pop(k, None)
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": False})
        self.home = d
        self.state_dir = d / ".halo"
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---- ref parsing ------------------------------------------------------------

@test
def test_hf_local_bare_ref_parses_model_host_none_local_true(ctx: Ctx):
    from halo_harness.model import parse_model_ref
    with _Env():
        ref = parse_model_ref("hf:local/qwen3-30b")
        ctx.check(f"provider huggingface, got {ref.provider!r}", ref.provider == "huggingface")
        ctx.check(f"dialect openai-chat, got {ref.dialect!r}", ref.dialect == "openai-chat")
        ctx.check(f"model is the bare id, got {ref.model!r}", ref.model == "qwen3-30b")
        ctx.check(f"host is None (default server), got {ref.host!r}", ref.host is None)
        ctx.check("local flag is True", ref.local is True)


@test
def test_hf_local_named_ref_parses_server_name_into_host(ctx: Ctx):
    from halo_harness.model import parse_model_ref
    with _Env():
        ref = parse_model_ref("hf:local/qwen3-30b@my-server")
        ctx.check(f"model is the bare id (never the server name), got {ref.model!r}", ref.model == "qwen3-30b")
        ctx.check(f"host carries the server name, got {ref.host!r}", ref.host == "my-server")
        ctx.check("local flag is True", ref.local is True)


@test
def test_hf_local_bare_prefix_refused(ctx: Ctx):
    from halo_harness.model import parse_model_ref
    from halo_harness.providers.routing import InvalidModelError
    with _Env():
        try:
            parse_model_ref("hf:local/")
            ctx.check("hf:local/ alone must raise InvalidModelError", False)
        except InvalidModelError as e:
            ctx.check(f"message names the local/<model> shape, got {e!s}", "local/" in str(e))


@test
def test_hf_endpoint_and_router_refs_still_have_local_false(ctx: Ctx):
    """Regression guard: adding `local` must never flip it on for the two
    pre-existing `hf:` shapes."""
    from halo_harness.model import parse_model_ref
    with _Env():
        ctx.check("router ref local=False", parse_model_ref("hf:Qwen/Qwen3-32B").local is False)
        ctx.check("endpoint ref local=False", parse_model_ref("hf:endpoint/my-prod").local is False)


# ---- huggingface.local_servers config resolution ---------------------------

@test
def test_resolve_local_servers_empty_by_default(ctx: Ctx):
    from halo_harness.providers.huggingface import resolve_huggingface_local_servers
    with _Env():
        ctx.check("no entries configured", resolve_huggingface_local_servers() == [])


@test
def test_resolve_local_server_named_selection_among_several(ctx: Ctx):
    from halo_harness.providers.huggingface import resolve_huggingface_local_server
    from halo_harness.theme import set_config_value
    with _Env():
        set_config_value("huggingface.local_servers", [
            {"name": "a", "url": "http://127.0.0.1:11111/v1", "api_key": "key-a"},
            {"name": "b", "url": "http://127.0.0.1:22222/v1", "api_key": "key-b", "default": True},
        ])
        a = resolve_huggingface_local_server("a")
        b = resolve_huggingface_local_server("b")
        bare = resolve_huggingface_local_server(None)
        ctx.check(f"named 'a' resolves its own url, got {a.url!r}", a.url == "http://127.0.0.1:11111/v1")
        ctx.check(f"bare resolves the default=True entry 'b', got {bare.name!r}", bare.name == "b")
        ctx.check("the two entries' keys never cross-wire", a.api_key == "key-a" and b.api_key == "key-b")


@test
def test_resolve_local_server_unknown_name_is_none(ctx: Ctx):
    from halo_harness.providers.huggingface import resolve_huggingface_local_server
    from halo_harness.theme import set_config_value
    with _Env():
        set_config_value("huggingface.local_servers", [{"name": "a", "url": "http://127.0.0.1:11111/v1"}])
        ctx.check("a typo'd name resolves to None, never falling back to 'a'",
                  resolve_huggingface_local_server("not-configured") is None)


@test
def test_local_server_malformed_entry_logged_by_name_only(ctx: Ctx):
    """Fix pass C-1 (review finding 17): the DEBUG line for a skipped
    `huggingface.local_servers` entry must name it, never `%r` the whole
    dict -- a malformed entry can still carry a real `api_key`."""
    import logging
    from halo_harness.providers.huggingface import resolve_huggingface_local_servers
    from halo_harness.theme import set_config_value

    class _Capture(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []

        def emit(self, record):
            self.records.append(record.getMessage())

    logger = logging.getLogger("bridge")
    handler = _Capture()
    logger.addHandler(handler)
    old_level = logger.level
    logger.setLevel(logging.DEBUG)
    try:
        with _Env():
            set_config_value("huggingface.local_servers", [{"name": "broken-local", "api_key": "fake-secret-456"}])
            resolve_huggingface_local_servers()
            joined = "\n".join(handler.records)
            ctx.check(f"the entry's name is in the debug line, got {handler.records!r}", "broken-local" in joined)
            ctx.check("the api_key value never appears in the debug line", "fake-secret-456" not in joined)
    finally:
        logger.setLevel(old_level)
        logger.removeHandler(handler)


@test
def test_local_server_api_key_env_reference_resolves_and_plaintext_still_works(ctx: Ctx):
    """Fix pass C-1 (review finding 16): `api_key_env` resolves to the
    real value from the process environment; an older plaintext
    `api_key` value still works unchanged."""
    from halo_harness.providers.huggingface import resolve_huggingface_local_server
    from halo_harness.theme import set_config_value
    with _Env():
        os.environ["HALO_SECRET_HF_LOCAL_ENVREF"] = "the-real-local-secret"
        set_config_value("huggingface.local_servers", [
            {"name": "envref", "url": "http://192.0.2.22:8080", "api_key_env": "HALO_SECRET_HF_LOCAL_ENVREF"},
            {"name": "legacy", "url": "http://192.0.2.23:8080", "api_key": "still-works-plaintext",
             "default": True},
        ])
        ctx.check("api_key_env resolves to the real env value",
                  resolve_huggingface_local_server("envref").api_key == "the-real-local-secret")
        ctx.check("a legacy plaintext api_key still resolves unchanged",
                  resolve_huggingface_local_server("legacy").api_key == "still-works-plaintext")


# ---- bare ref resolution by served model id (review fix pass finding 11) --

_STUB_ALIAS_AWARE = '''
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(sys.argv[sys.argv.index("--port") + 1])
alias = sys.argv[sys.argv.index("--alias") + 1] if "--alias" in sys.argv else "stub-model"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            body = json.dumps({"object": "list", "data": [{"id": alias}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


HTTPServer(("127.0.0.1", port), H).serve_forever()
'''


def _write_alias_aware_stub() -> Path:
    d = Path(tempfile.mkdtemp(prefix="hf-local-alias-stub-"))
    p = d / "stub_runtime.py"
    p.write_text(_STUB_ALIAS_AWARE, encoding="utf-8")
    return p


@test
def test_resolve_local_server_bare_ref_picks_the_server_actually_serving_that_model_id(ctx: Ctx):
    """Review fix pass (finding 11): two managed servers running at
    once, each confirmed (via its own `--alias`-reported `/v1/models`,
    A12's own fix) to serve a DIFFERENT model id -- a bare `hf:local/
    <model>` ref must resolve to the one that actually serves THAT id,
    never "whichever started most recently" (the only rule a bare ref
    ever had before this fix)."""
    from halo_harness.providers.local_runtime import start_managed_server, stop_all_managed_servers_except_kept
    from halo_harness.providers.huggingface_local_resolve import resolve_local_server
    with _Env() as e:
        stub = _write_alias_aware_stub()
        entry_a, reason_a = start_managed_server(model="model-a", runtime="llama-server",
                                                  binary_argv=[sys.executable, str(stub)], model_path="a.gguf",
                                                  state_dir=e.state_dir, startup_timeout=10.0)
        entry_b, reason_b = start_managed_server(model="model-b", runtime="llama-server",
                                                  binary_argv=[sys.executable, str(stub)], model_path="b.gguf",
                                                  state_dir=e.state_dir, startup_timeout=10.0)
        try:
            ctx.check(f"both started, got a={reason_a!r} b={reason_b!r}",
                      entry_a is not None and entry_b is not None)
            os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"  # never let auto-detect touch the real network
            resolved_a = resolve_local_server(None, dict(os.environ), model="model-a", state_dir=e.state_dir)
            resolved_b = resolve_local_server(None, dict(os.environ), model="model-b", state_dir=e.state_dir)
            ctx.check(f"model-a resolves to its OWN server, got {resolved_a}",
                      resolved_a is not None and resolved_a.base_url == entry_a.base_url)
            ctx.check(f"model-b resolves to its OWN server (never model-a's, even though it started "
                      f"SECOND and would win the old 'most recent' rule), got {resolved_b}",
                      resolved_b is not None and resolved_b.base_url == entry_b.base_url)
        finally:
            stop_all_managed_servers_except_kept(state_dir=e.state_dir)


@test
def test_resolve_local_server_falls_back_to_default_when_no_server_serves_the_model(ctx: Ctx):
    """A `model` that NO running server actually reports must still fall
    back to "the default server" (here: the most-recently-started
    registry entry, nothing else configured) -- the id-aware match is an
    ADDITION in front of the old rule, never a replacement that refuses
    outright when it finds no exact match."""
    from halo_harness.providers.local_runtime import start_managed_server, stop_all_managed_servers_except_kept
    from halo_harness.providers.huggingface_local_resolve import resolve_local_server
    with _Env() as e:
        stub = _write_alias_aware_stub()
        entry, reason = start_managed_server(model="the-only-one", runtime="llama-server",
                                              binary_argv=[sys.executable, str(stub)], model_path="only.gguf",
                                              state_dir=e.state_dir, startup_timeout=10.0)
        try:
            ctx.check(f"started, got {reason!r}", entry is not None)
            os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
            resolved = resolve_local_server(None, dict(os.environ), model="nobody-serves-this",
                                             state_dir=e.state_dir)
            ctx.check(f"still falls back to the default (the only registry entry), got {resolved}",
                      resolved is not None and resolved.base_url == entry.base_url)
        finally:
            stop_all_managed_servers_except_kept(state_dir=e.state_dir)


# ---- credential resolution: never cross-wired ------------------------------

@test
def test_resolve_creds_local_named_uses_its_own_key_never_hf_token_or_endpoint_token(ctx: Ctx):
    from halo_harness.headless import _resolve_creds
    from halo_harness.model import parse_model_ref
    from halo_harness.theme import set_config_value
    with _Env():
        os.environ["HF_TOKEN"] = "router-token-must-never-appear"
        set_config_value("huggingface.endpoints",
                          [{"name": "my-server", "url": "https://endpoint.example/v1", "token": "endpoint-token"}])
        set_config_value("huggingface.local_servers",
                          [{"name": "my-server", "url": "http://127.0.0.1:9999/v1", "api_key": "local-only-key"}])
        creds = _resolve_creds(parse_model_ref("hf:local/qwen3-30b@my-server"))
        ctx.check("local creds resolve", creds is not None)
        ctx.check(f"base_url is the LOCAL entry's own url, got {creds.base_url!r}",
                  creds.base_url == "http://127.0.0.1:9999/v1")
        ctx.check(f"api_key is the LOCAL entry's own key, never HF_TOKEN or the endpoint's token, "
                  f"got {creds.api_key!r}", creds.api_key == "local-only-key")


@test
def test_resolve_creds_local_entry_with_no_api_key_sends_empty_string(ctx: Ctx):
    from halo_harness.headless import _resolve_creds
    from halo_harness.model import parse_model_ref
    from halo_harness.theme import set_config_value
    with _Env():
        set_config_value("huggingface.local_servers", [{"name": "open", "url": "http://127.0.0.1:9999/v1"}])
        creds = _resolve_creds(parse_model_ref("hf:local/qwen3-30b@open"))
        ctx.check(f"api_key is empty, never None, got {creds.api_key!r}", creds.api_key == "")


@test
def test_resolve_creds_local_named_unconfigured_is_none_never_falls_back(ctx: Ctx):
    from halo_harness.headless import _resolve_creds
    from halo_harness.model import parse_model_ref
    with _Env():
        ctx.check("a named local ref with nothing configured resolves to no creds",
                  _resolve_creds(parse_model_ref("hf:local/qwen3-30b@nope")) is None)


@test
def test_resolve_creds_local_bare_with_nothing_configured_or_detected_is_none(ctx: Ctx):
    from halo_harness.headless import _resolve_creds
    from halo_harness.model import parse_model_ref
    with _Env():
        saved = os.environ.get("BRIDGE_TEST_NO_BACKGROUND_NET")
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        try:
            ctx.check("bare local ref with no manual entry and auto-detect gated off resolves to no creds",
                      _resolve_creds(parse_model_ref("hf:local/qwen3-30b")) is None)
        finally:
            if saved is None:
                os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
            else:
                os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = saved


@test
def test_bill_to_header_never_applies_to_a_local_ref(ctx: Ctx):
    """Round 5 fix pass for the `X-HF-Bill-To` gate -- a BARE local ref also
    leaves `host` unset, which must never be mistaken for a router ref."""
    from halo_harness.model import parse_model_ref
    with _Env():
        ref = parse_model_ref("hf:local/qwen3-30b")
        ctx.check("host is None (shared with a router ref)", ref.host is None)
        ctx.check("but local=True must gate the bill-to header off", ref.local is True)


# ---- enablement -------------------------------------------------------------

@test
def test_enablement_local_server_alone_enables_no_token_needed(ctx: Ctx):
    from halo_harness.providers.enablement import credentials_present
    from halo_harness.theme import set_config_value
    with _Env():
        ctx.check("not detected with nothing configured", credentials_present("huggingface") is False)
        set_config_value("huggingface.local_servers", [{"name": "a", "url": "http://127.0.0.1:9999/v1"}])
        ctx.check("detected via a local server entry alone", credentials_present("huggingface") is True)


# ---- print-mode end-to-end, a manual entry configured by URL --------------

def _hermetic_child_env() -> dict:
    env = dict(os.environ)
    env.pop("BRIDGE_STATE_DIR", None)
    for k in [k for k in env if k.startswith("HALO_")]:
        env.pop(k, None)
    env.pop("HF_TOKEN", None)
    env.pop("OLLAMA_HOST", None)
    return env


def _run_cli(fh, prompt, *, model: str, extra_env=None, timeout=30):
    env = _hermetic_child_env()
    env.update({"BRIDGE_TEST_HOME": str(fh["home"]), "BRIDGE_TEST_NO_BACKGROUND_NET": "1",
                "PYTHONPATH": str(REPO_DIR)})
    env.update(extra_env or {})
    args = [sys.executable, "-m", "halo_harness", "-p", prompt, "--model", model, "--cwd", str(fh["proj"])]
    return subprocess.run(args, env=env, cwd=str(REPO_DIR), capture_output=True, text=True, timeout=timeout)


def _seed_config(fh, key: str, value) -> None:
    old_home = os.environ.get("BRIDGE_TEST_HOME")
    old_state_dir = os.environ.get("BRIDGE_STATE_DIR")
    os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
    os.environ.pop("BRIDGE_STATE_DIR", None)
    try:
        from halo_harness.theme import set_config_value
        set_config_value(key, value)
    finally:
        if old_home is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = old_home
        if old_state_dir is not None:
            os.environ["BRIDGE_STATE_DIR"] = old_state_dir


@test
def test_local_end_to_end_manual_entry_configured_by_url_uses_its_own_bearer(ctx: Ctx):
    fh = build_fake_home()
    mock = MockUpstream(path_prefix="/v1", expected_bearer="local-server-token").start()
    try:
        _seed_config(fh, "huggingface.local_servers",
                     [{"name": "bench", "url": mock.base_url, "api_key": "local-server-token"}])
        result = _run_cli(fh, "say hi please", model="hf:local/mock/model@bench",
                           extra_env={"HF_TOKEN": "a-router-token-that-must-never-be-sent-here"})
        ctx.check(f"exit 0, got {result.returncode} stderr={result.stderr[-500:]!r}", result.returncode == 0)
        ctx.check(f"the scenario's reply reached stdout, got {result.stdout!r}", "pong" in result.stdout)

        chats = [r for r in mock.requests if r["method"] == "POST"]
        ctx.check(f"exactly one chat call recorded, got {len(chats)}", len(chats) == 1)
        req = chats[0]
        ctx.check(f"model on the wire, got {req['body'].get('model')!r}", req["body"].get("model") == "mock/model")
        ctx.check(f"bearer is the LOCAL entry's own key, got {req['headers'].get('authorization')!r}",
                  req["headers"].get("authorization") == "Bearer " + "local-server-token")
    finally:
        mock.stop()


@test
def test_resolve_model_profile_local_reads_back_context_and_falls_back_to_default(ctx: Ctx):
    """`model.resolve_model_profile`'s own `ref.local` branch
    (`providers.huggingface_local_resolve.cached_local_context_tokens`) --
    the research doc's "read back what the server reports, never
    request it" rule, and "unknown falls back to the profile default"."""
    from halo_harness.model import ModelProfile, parse_model_ref, resolve_model_profile
    from halo_harness.providers.huggingface_local_resolve import reset_local_probe_cache
    from halo_harness.theme import set_config_value
    with _Env() as e:
        reset_local_probe_cache()  # a stale same-process cache entry must never leak in from elsewhere
        mock = MockUpstream(path_prefix="/v1").start()
        try:
            mock.models_response = {"data": [{"id": "ctx-model", "context_length": 16384}]}
            set_config_value("huggingface.local_servers", [{"name": "bench", "url": mock.base_url, "default": True}])
            ref = parse_model_ref("hf:local/ctx-model@bench")
            profile = resolve_model_profile(ref, state_dir=e.state_dir)
            ctx.check(f"context read back from the server, got {profile.context_tokens}",
                      profile.context_tokens == 16384)
        finally:
            mock.stop()
            reset_local_probe_cache()

        # Unreachable server -- falls back to the bare dataclass default,
        # never a guess.
        unreachable_ref = parse_model_ref("hf:local/ctx-model@does-not-exist")
        profile2 = resolve_model_profile(unreachable_ref, state_dir=e.state_dir)
        ctx.check(f"unknown falls back to the plain default, got {profile2}", profile2 == ModelProfile())


@test
def test_local_question_now_also_accepts_an_hf_small_role_ref(ctx: Ctx):
    """Round 5 brief item 4: "/local <question> ... may now pick an hf:
    small-role ref" -- round 3 only ever accepted `ol:`. Builds a real
    `agent.loop.Session` with `small_model_ref` set to an `hf:local/*`
    ref resolved against a manual entry, same shape tests.
    test_ollama_roles_local.py's own `test_local_cmd_answers_without_
    touching_main_transcript` already pins for `ol:`."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.commands.builtins import HeadlessFacade, _cmd_local
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.theme import set_config_value

    fh = build_fake_home()
    mock = MockUpstream(path_prefix="/v1", expected_bearer="small-role-token").start()
    try:
        _seed_config(fh, "huggingface.local_servers",
                     [{"name": "bench", "url": mock.base_url, "api_key": "small-role-token"}])
        # Left set for the WHOLE rest of this test (restored in `finally`
        # below) -- `call_small_model`'s own `_resolve_creds` call reads
        # `huggingface.local_servers` again at call time, same as
        # `test_ollama_roles_local.py`'s own `OLLAMA_HOST`-for-the-whole-
        # test pattern for the exact same reason.
        os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
        small_ref = parse_model_ref("hf:local/mock/model@bench")

        session_ctx = SessionContext(cwd=fh["proj"], model_label="or:mock/main")
        session = Session(
            cwd=fh["proj"], model_ref=parse_model_ref("or:mock/main"),
            model_profile=ModelProfile(context_tokens=10_000, max_output_tokens=1_000),
            creds=ProviderCreds(base_url="http://127.0.0.1:1", api_key=""),
            state_dir=Path(tempfile.mkdtemp(prefix="hf-local-small-role-")), model_label="or:mock/main",
            session_context=session_ctx, max_turns=10,
            permission_engine=PermissionEngine(mode="auto", cwd=fh["proj"]),
            small_model_ref=small_ref,
        )
        session.log.append_user([{"type": "text", "text": "the real conversation"}])
        before = len(session.log.nodes())

        answer = _cmd_local("say hi please", HeadlessFacade(cwd=fh["proj"], session=session))

        ctx.check(f"answer contains the scripted reply, got {answer!r}", "pong" in answer)
        after = len(session.log.nodes())
        ctx.check(f"the main transcript is UNCHANGED, before={before} after={after}", before == after)
        chats = [r for r in mock.requests if r["method"] == "POST"]
        ctx.check(f"exactly one chat call, got {len(chats)}", len(chats) == 1)
        ctx.check(f"the LOCAL server's own bearer reached the wire, got {chats[0]['headers'].get('authorization')!r}",
                  chats[0]["headers"].get("authorization") == "Bearer " + "small-role-token")
    finally:
        mock.stop()
        os.environ.pop("BRIDGE_TEST_HOME", None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
