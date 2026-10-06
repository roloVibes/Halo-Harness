"""tests.test_ant_enumeration -- Halo 2.0.4 round 3 (deliverable 3):
`halo models --ant` (the catalog_cli.py counterpart of `--cc`/`--cx`,
listing the real ids `GET /v1/models` returns for the configured
ANTHROPIC_API_KEY, not just the nine pinned aliases) and the `/model`
picker's own `ant:` group reading that SAME `ant-models.json` cache.
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_get_endpoints import MockGetEndpoints

test, TESTS = new_registry()

_PROVIDER_ENV_VARS = ("ANTHROPIC_API_KEY", "BRIDGE_ANTHROPIC_BASE_URL", "ANTHROPIC_BASE_URL",
                      "ANTHROPIC_AUTH_TOKEN", "BRIDGE_TEST_CC_AUTH_STATUS")

_ANT_MODELS_BODY = {"data": [
    {"id": "claude-opus-5-5", "display_name": "Claude Opus 5.5"},
    {"id": "claude-sonnet-5-5", "display_name": "Claude Sonnet 5.5"},
    # Not one of the nine pinned aliases' targets -- the live-catalog-only
    # row this round adds to both `--ant` and the picker.
    {"id": "claude-haiku-3-legacy", "display_name": "Claude Haiku 3 (legacy)"},
]}


class _Env:
    """Snapshots/restores every Anthropic-shaped env var this module
    touches, plus BRIDGE_TEST_HOME/BRIDGE_STATE_DIR -- the real `~/.halo`
    is never written (same convention as test_h15_catalog_refresh.py's
    own `_Env`)."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in
                       (("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR") + _PROVIDER_ENV_VARS)}
        d = Path(tempfile.mkdtemp(prefix="ant-enum-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
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


@test
def test_cmd_models_ant_not_configured(ctx: Ctx):
    from halo_harness.catalog_cli import cmd_models
    with _Env():
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_models(["--ant"])
        ctx.check(f"exit 0 even when unconfigured, got {rc}", rc == 0)
        ctx.check(f"says not configured, got {buf.getvalue()!r}", "not configured" in buf.getvalue())


@test
def test_cmd_models_ant_refresh_populates_cache_and_lists_extra_id(ctx: Ctx):
    from halo_harness.catalog_cli import cmd_models
    from halo_harness.providers.anthropic_catalog import load_ant_models_json
    mock = MockGetEndpoints({"/v1/models": (200, _ANT_MODELS_BODY)}).start()
    try:
        with _Env() as env:
            os.environ["ANTHROPIC_API_KEY"] = "sk-ant-fake"
            os.environ["BRIDGE_ANTHROPIC_BASE_URL"] = mock.base_url
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cmd_models(["--ant", "--refresh"])
            ctx.check(f"exit 0, got {rc}", rc == 0)
            text = buf.getvalue()
            ctx.check(f"key found line printed, got {text!r}", "key found" in text)
            ctx.check(f"the nine aliases still show first, got {text!r}", "fable" in text and "opus" in text)
            ctx.check(f"the live-only extra id is listed too, got {text!r}", "claude-haiku-3-legacy" in text)
            cached = load_ant_models_json(env.state_dir)
            ctx.check(f"cache has all three live ids, got {sorted(cached)}",
                      set(cached) == {"claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-3-legacy"})
    finally:
        mock.stop()


@test
def test_cmd_models_ant_bare_never_touches_network(ctx: Ctx):
    """Same "no --refresh, no network, ever" contract `--cc`/`--cx`/bare
    `halo models` already follow -- a bare `--ant` on an unresolvable host
    must return instantly from whatever is already cached."""
    from halo_harness.catalog_cli import cmd_models
    with _Env() as env:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-fake"
        os.environ["BRIDGE_ANTHROPIC_BASE_URL"] = "https://unresolvable.invalid.example"
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_models(["--ant"])
        ctx.check(f"exit 0, no hang, got {rc}", rc == 0)
        ctx.check(f"still shows the alias table from the static fallback, got {buf.getvalue()!r}",
                  "fable" in buf.getvalue())


@test
def test_picker_ant_group_reads_the_same_live_cache(ctx: Ctx):
    """Controller.list_models()'s own `ant:` group: the nine aliases
    (existing behaviour, unchanged) PLUS any id `ant-models.json` carries
    that isn't one of those nine targets -- "the picker groups read the
    same cache" (deliverable 3)."""
    from halo_harness.providers.anthropic_catalog import write_ant_models_json
    from halo_harness.providers.enablement import enable
    with _Env() as env:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-fake"
        enable("anthropic")
        write_ant_models_json(env.state_dir, _ANT_MODELS_BODY["data"])

        from halo_harness.controller import Controller

        class _FakeModelRef:
            raw = "or:x"
            provider = "openrouter"

        class _FakeModelProfile:
            context_tokens = 128000
            max_output_tokens = 16384

        class _FakeSession:
            model_ref = _FakeModelRef()
            model_profile = _FakeModelProfile()

        ctrl = Controller(session=_FakeSession(), cwd=Path.cwd(), state_dir=env.state_dir, routes={})
        models = ctrl.list_models()
        ant_rows = {m["ref"]: m for m in models if m.get("provider") == "anthropic"}
        ctx.check(f"the nine aliases are present, got {sorted(ant_rows)}", "ant:opus" in ant_rows and "ant:fable" in ant_rows)
        ctx.check(f"the live-only extra id gets its own row, got {sorted(ant_rows)}",
                  "ant:claude-haiku-3-legacy" in ant_rows)
        ctx.check(f"it shares the SAME group label as the aliases, got {ant_rows.get('ant:claude-haiku-3-legacy')}",
                  ant_rows["ant:claude-haiku-3-legacy"]["group"] == ant_rows["ant:opus"]["group"])
        ctx.check(f"group carries the (ant:) prefix, got {ant_rows['ant:opus']['group']!r}",
                  ant_rows["ant:opus"]["group"] == "Anthropic API (key) (ant:)")
        # The alias target itself (claude-opus-5-5, claude-sonnet-5-5) must
        # NOT also appear as its own bare-id row -- it's already shown
        # under its alias name ("opus"/"sonnet-5.5"), never duplicated.
        ctx.check("no duplicate row for an alias's own resolved id",
                  "ant:claude-opus-5-5" not in ant_rows and "ant:claude-sonnet-5-5" not in ant_rows)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
