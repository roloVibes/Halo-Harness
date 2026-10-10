"""tests.test_set_model_creds -- pass-B fix (review finding 2, critical):
`Controller.set_model` now refuses a ref whose credentials don't resolve
(the provider's own "not configured" sentence, before anything is ever
queued to the worker) instead of accepting it and leaving the NEXT turn
to silently send the transcript to the OLD provider's URL with the OLD
key under the NEW model id; `Session.set_model` now CLEARS creds when
given None instead of keeping the previous model's. Mirrors
tests/test_qwen_decision_only.py's own `_controller`/`_FakeSession`
pattern for the Controller half.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()

_PROVIDER_ENV_VARS = (
    "OPENROUTER_API_KEY", "DATABRICKS_HOST", "DATABRICKS_TOKEN", "ANTHROPIC_API_KEY",
    "HF_TOKEN", "OPENAI_API_KEY", "OLLAMA_HOST", "OLLAMA_API_KEY",
)


class _Env:
    """Every test scopes its own home -- BRIDGE_TEST_HOME/BRIDGE_STATE_DIR
    point at a fresh temp dir (never the real ~/.halo), and every
    provider env var this module cares about is snapshotted/restored."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in
                       ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_ENV_FILE") + _PROVIDER_ENV_VARS}
        d = Path(tempfile.mkdtemp(prefix="set-model-creds-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["BRIDGE_ENV_FILE"] = str(d / "no-env-file")
        for k in _PROVIDER_ENV_VARS:
            os.environ.pop(k, None)
        os.environ["OPENROUTER_API_KEY"] = "sk-or-scratch"  # the "scratch or: session" the brief's test names
        self.home = d
        self.state_dir = d / ".halo"
        # Halo 2.0.7 round 7b: this module is about creds-clearing/
        # refusal mechanics around set_model (its own docstring above),
        # not the subscription-routes consent gate -- pre-accept for this
        # fresh scratch home so the existing cc:/cx: cases below keep
        # resolving exactly as they did before that gate existed.
        from halo_harness.subscription_consent import record_acceptance
        record_acceptance()
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class _FakeModelRef:
    raw = "or:mock/current"
    provider = "openrouter"


class _FakeModelProfile:
    context_tokens = 128000
    max_output_tokens = 8192


class _FakeSession:
    """`Controller.set_model`'s refusal path never reads `self.session` at
    all (only `self.model_resolver`/`self.routes`/`self.state_dir`/
    `self.commands`) -- same bare stand-in tests/test_qwen_decision_only.py
    already uses for this exact method."""
    model_ref = _FakeModelRef()
    model_profile = _FakeModelProfile()


def _controller(state_dir, **kw):
    from halo_harness.controller import Controller
    return Controller(session=_FakeSession(), cwd=Path.cwd(), state_dir=state_dir, routes={}, **kw)


# ---- Controller.set_model: refuses instead of queuing a stale switch -----

@test
def test_hf_local_with_no_server_is_refused_not_queued(ctx: Ctx):
    with _Env() as env:
        ctrl = _controller(env.state_dir)
        err = ctrl.set_model("hf:local/x")
        ctx.check(f"a not-configured sentence is returned, got {err!r}", bool(err))
        ctx.check("names Hugging Face", "Hugging Face" in err)
        ctx.check("the switch was NEVER queued (model/creds stay whatever they were)", ctrl.commands.empty())


@test
def test_oai_with_no_key_is_refused_not_queued(ctx: Ctx):
    with _Env() as env:
        ctrl = _controller(env.state_dir)
        err = ctrl.set_model("oai:gpt-6-sol")
        ctx.check(f"a not-configured sentence is returned, got {err!r}", bool(err))
        ctx.check("names OPENAI_API_KEY", "OPENAI_API_KEY" in err)
        ctx.check("the switch was NEVER queued (model/creds stay whatever they were)", ctrl.commands.empty())


@test
def test_an_ordinary_configured_switch_is_unaffected(ctx: Ctx):
    """The refusal gate must not swallow a perfectly ordinary switch whose
    creds DO resolve -- `or:` is enabled via the scratch key _Env sets."""
    with _Env() as env:
        ctrl = _controller(env.state_dir)
        err = ctrl.set_model("or:mock/some-model")
        ctx.check(f"no refusal, got {err!r}", err is None)
        ctx.check("the switch WAS queued", not ctrl.commands.empty())


@test
def test_cc_and_cx_are_exempt_from_the_credentials_gate(ctx: Ctx):
    """cc:/cx: are subprocess routes that need no API key at all --
    `_resolve_creds` always returns None for them, which must never be
    read as "not configured" the way a cloud/local ref's None is."""
    with _Env() as env:
        for ref in ("cc:sonnet", "cx:astra"):
            ctrl = _controller(env.state_dir)
            err = ctrl.set_model(ref)
            ctx.check(f"{ref}: no refusal despite creds=None, got {err!r}", err is None)
            ctx.check(f"{ref}: the switch WAS queued", not ctrl.commands.empty())


@test
def test_hf_mlx_ref_does_not_crash_the_ensure_step(ctx: Ctx):
    """finding 2's other half: an hf:mlx/<repo> ref runs `_ensure_mlx_
    server_for_ref` FIRST. On this (non-Apple-Silicon) build host that's a
    safe, documented no-op (`ensure_mlx_server`'s own step 1), so this
    just pins that the new code path runs end to end without raising --
    creds still won't resolve (no registry entry exists), so the same
    refusal sentence comes back, this time naming Hugging Face."""
    with _Env() as env:
        ctrl = _controller(env.state_dir)
        err = ctrl.set_model("hf:mlx/some-repo-nobody-started")
        ctx.check(f"refused cleanly, no crash, got {err!r}", bool(err) and "Hugging Face" in err)
        ctx.check("the switch was never queued", ctrl.commands.empty())


# ---- Session.set_model: clears creds on None, never keeps stale ones -----

def _new_session(model: str, creds=None):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine

    cwd = Path(tempfile.mkdtemp(prefix="b2-session-cwd-"))
    ref = parse_model_ref(model)
    session_ctx = SessionContext(cwd=cwd, model_label=model, bare=True)
    return Session(
        cwd=cwd, model_ref=ref, model_profile=ModelProfile(), creds=creds,
        state_dir=Path(tempfile.mkdtemp(prefix="b2-session-state-")), model_label=model,
        session_context=session_ctx, permission_engine=PermissionEngine(mode="auto", cwd=cwd),
    )


@test
def test_session_set_model_clears_creds_when_given_none(ctx: Ctx):
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    with _Env():
        stale = ProviderCreds(base_url="https://openrouter.ai/api/v1", api_key="stale-or-key")
        session = _new_session("or:mock/old", creds=stale)
        ctx.check("starts with the stale creds", session.creds is stale)
        session.set_model(parse_model_ref("cx:astra"), ModelProfile(), None)
        ctx.check(f"creds cleared to None (cx: needs none), got {session.creds!r}", session.creds is None)


@test
def test_session_set_model_still_installs_real_creds_when_given(ctx: Ctx):
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    with _Env():
        old = ProviderCreds(base_url="https://openrouter.ai/api/v1", api_key="old-key")
        new = ProviderCreds(base_url="https://api.openai.com/v1", api_key="new-key")
        session = _new_session("or:mock/old", creds=old)
        session.set_model(parse_model_ref("oai:gpt-5"), ModelProfile(), new)
        ctx.check(f"the new creds are installed, got {session.creds!r}", session.creds is new)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
