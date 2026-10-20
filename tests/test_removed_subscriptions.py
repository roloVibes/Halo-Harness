"""tests.test_removed_subscriptions -- Halo 3.1.5.0 round R1: the Claude Code
(`cc:`) and Codex (`cx:`) subscription routes are gone.

1. the invariants: no module under halo_harness imports cc_runtime / codex_* /
   ccbridge / subscription_* / cc_models; no builtin `/subscriptions` or
   `/settings`; no cli dispatch `subscriptions`; no enablement name
   claude_subscription / codex_subscription; no `cc:`/`cx:` prefix constant
   in model.py; the removed files are gone;
2. the guard: `--model cc:sonnet` / `cx:gpt` (and `cc:foo/bar`, which would
   otherwise parse as OpenRouter) is the one removed-route line, on
   `parse_model_ref`, headless `-p` and a config.json `model:`;
3. a config.json with `subscription_routes` / `settings` sections loads and
   `halo doctor --config` prints the two "removed in 3.1.5.0" lines;
4. `ant:sonnet` still resolves with ANTHROPIC_API_KEY and `halo models --ant`
   still lists the aliases;
5. the claude.ai connectors bridge resolves its claude auth through the moved
   module (`mcp/claude_auth.py`), against the fake claude.
No model is called. Run: python -m tests.test_removed_subscriptions
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()

from tests.helpers.config_seed import ConfigHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
PKG = REPO / "halo_harness"
GONE_MODULES = ("halo_harness.agent.cc_runtime", "halo_harness.agent.cc_control", "halo_harness.agent.cc_process",
                "halo_harness.agent.codex_runtime", "halo_harness.agent.codex_process", "halo_harness.agent.codex_turn",
                "halo_harness.providers.cc_models", "halo_harness.providers.codex_models",
                "halo_harness.providers.codex_settings", "halo_harness.providers.settings_merge",
                "halo_harness.ccbridge", "halo_harness.subscription_consent", "halo_harness.subscription_scrub",
                "halo_harness.subscriptions_cli", "halo_harness.tui.dialogs.subscription_notice")
LINE = ("(the cc: and cx: routes were removed in 3.1.5.0; use an API route, e.g. ant:sonnet with "
        "ANTHROPIC_API_KEY, or or:anthropic/<model>)")
CONFIG_LINES = ["settings: removed in 3.1.5.0, the section is ignored",
                "subscription_routes: removed in 3.1.5.0, the section is ignored"]
FAKE_CLAUDE = f'"{sys.executable}" "{REPO / "tests" / "helpers" / "fake_claude_cc.py"}"'


def _imports(path: Path) -> "list[str]":
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            out += [node.module] + [f"{node.module}.{a.name}" for a in node.names]
    return out


def _run(argv, home: Path, extra_env: "dict | None" = None):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("BRIDGE_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "ROLO_CLAUDE_", "HALO_",
                                "TYPESAFE_", "OLLAMA_", "HF_", "OPENAI_", "EXPLABS_"))}
    env.update({"BRIDGE_TEST_HOME": str(home), "PYTHONPATH": str(REPO), "BRIDGE_TEST_NO_BACKGROUND_NET": "1",
                "BRIDGE_TEST_CC_AUTH_STATUS": json.dumps({"loggedIn": False})})
    env.update(extra_env or {})
    return subprocess.run([sys.executable, "-m", "halo_harness"] + argv, env=env, cwd=str(REPO),
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)


@test
def test_no_module_imports_a_removed_one_and_the_files_are_gone(ctx: Ctx):
    bad = []
    for path in sorted(PKG.rglob("*.py")):
        for name in _imports(path):
            if any(name == g or name.startswith(g + ".") for g in GONE_MODULES):
                bad.append(f"{path.relative_to(REPO).as_posix()}: {name}")
    ctx.check(f"no import of a removed module, got {bad}", not bad)
    left = [m for m in GONE_MODULES if (REPO / (m.replace(".", "/") + ".py")).is_file()
            or [c for c in (REPO / m.replace(".", "/")).glob("*.py")]]
    ctx.check(f"the removed files are gone, left: {left}", not left)
    ctx.check("cc_tested.json is gone", not (PKG / "providers" / "cc_tested.json").exists())


@test
def test_no_command_dispatch_provider_name_or_prefix_is_left(ctx: Ctx):
    from halo_harness import model
    from halo_harness.commands.builtins import _BUILTIN_SPECS
    from halo_harness.init_providers import PROVIDERS, TAB_PROVIDERS
    from halo_harness.providers.enablement import LABELS, PREFIXES, PROVIDER_NAMES, canonical
    ctx.check("no builtin /subscriptions or /settings", not {"subscriptions", "settings"} & set(_BUILTIN_SPECS))
    cli = (PKG / "cli.py").read_text(encoding="utf-8")
    ctx.check("no cli dispatch `subscriptions`", not re.findall(r'argv\[0\] == "subscriptions"', cli))
    gone = {"claude_subscription", "codex_subscription"}
    ctx.check(f"no enablement name for a removed route, got {PROVIDER_NAMES}",
              not gone & set(PROVIDER_NAMES) and not gone & set(LABELS) and not gone & set(PREFIXES))
    ctx.check("no cc:/cx: prefix and no alias for one", not {"cc:", "cx:"} & set(PREFIXES.values())
              and all(canonical(a) == a for a in ("cc", "cx", "claude", "codex")))
    consts = [n for n in dir(model) if n.endswith("_PREFIX") and getattr(model, n) in ("cc:", "cx:")]
    ctx.check(f"model.py's prefix table names no cc:/cx: route, got {consts}", not consts)
    ctx.check(f"init offers no subscription provider or tab, got {TAB_PROVIDERS}",
              not {"claude", "codex", "settings_sources"} & (set(PROVIDERS) | set(TAB_PROVIDERS)))


@test
def test_the_guard_is_one_line_for_cc_and_cx_refs(ctx: Ctx):
    from halo_harness.model import parse_model_ref
    from halo_harness.providers.routing import InvalidModelError
    with ConfigHome():
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": True, "authMethod": "claude.ai"})
        for raw in ("cc:sonnet", "cx:gpt", "cc:foo/bar", "cx:"):
            try:
                parse_model_ref(raw)
                got = "accepted"
            except InvalidModelError as e:
                got = str(e)
            ctx.check(f"{raw}: the one line, got {got!r}", got == f"no route: {raw!r} {LINE}")
        try:
            parse_model_ref("fast", {"aliases": {"fast": "cc:opus"}})
            got = "accepted"
        except InvalidModelError as e:
            got = str(e)
        ctx.check(f"a routes.json alias onto cc: gets the line too, got {got!r}", "removed in 3.1.5.0" in got)


@test
def test_headless_and_a_config_model_print_the_one_line(ctx: Ctx):
    with ConfigHome() as h:
        r = _run(["-p", "--model", "cc:sonnet", "hi"], h.home)
        ctx.check(f"--model cc:sonnet: exit 2 with the line, got {r.returncode} {r.stderr[-300:]!r}",
                  r.returncode == 2 and f"halo: invalid --model: no route: 'cc:sonnet' {LINE}" in r.stderr)
        r = _run(["-p", "--model", "cx:gpt", "hi"], h.home)
        ctx.check(f"--model cx:gpt: the line, got {r.stderr[-300:]!r}", f"no route: 'cx:gpt' {LINE}" in r.stderr)
        h.config({"model": "cc:sonnet"})
        r = _run(["-p", "hi"], h.home)
        ctx.check(f"config.json model: cc:sonnet: the same line, got {r.returncode} {r.stderr[-300:]!r}",
                  r.returncode == 2 and f"no route: 'cc:sonnet' {LINE}" in r.stderr)
        ctx.check("one line, no traceback", "Traceback" not in r.stderr and r.stderr.strip().count("\n") == 0)


@test
def test_leftover_config_sections_load_and_doctor_names_each_once(ctx: Ctx):
    from halo_harness.doctor_config import cmd_doctor_config, config_findings
    from halo_harness.theme import get_config_value
    with ConfigHome() as h:
        h.config({"model": "or:vendor/x", "subscription_routes": {"accepted": True, "accepted_version": 1},
                  "settings": {"primary": "codex"}})
        ctx.check("config.json still loads", get_config_value("model") == "or:vendor/x")
        found = [f for f in config_findings(h.repo) if f["file"] == "~/.halo/config.json"]
        ctx.check(f"one warning per removed section, got {[f['text'] for f in found]}",
                  sorted(f["text"] for f in found) == CONFIG_LINES and {f["check"] for f in found} == {"removed-section"})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_doctor_config(cwd=h.repo)
        text = out.getvalue()
        ctx.check(f"halo doctor --config prints each line once, got {text[-500:]!r}",
                  all(text.count(line) == 1 for line in CONFIG_LINES))


@test
def test_ant_still_resolves_and_halo_models_ant_lists(ctx: Ctx):
    from halo_harness.model import parse_model_ref, resolve_model_profile
    with ConfigHome() as h:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-not-a-real-key"
        ref = parse_model_ref("ant:sonnet")
        ctx.check(f"ant:sonnet -> anthropic claude-sonnet-5-5, got {ref}",
                  ref.provider == "anthropic" and ref.model == "claude-sonnet-5-5")
        ctx.check("a bare alias goes to ant: with the key", parse_model_ref("opus").provider == "anthropic")
        ctx.check("the vendored profile backs it", resolve_model_profile(ref, h.state, {}).context_tokens == 1_000_000)
        r = _run(["models", "--ant"], h.home, {"ANTHROPIC_API_KEY": "sk-ant-not-a-real-key"})
        ctx.check(f"halo models --ant exits 0 and lists the aliases, got {r.returncode} {r.stdout[:300]!r}",
                  r.returncode == 0 and "opus" in r.stdout and "-> claude-opus-5-5 (latest Opus)" in r.stdout)
        r = _run(["models", "--cc"], h.home)
        ctx.check(f"halo models --cc is an unknown flag now, got {r.returncode}", r.returncode == 2)


@test
def test_the_connectors_bridge_resolves_claude_auth_through_the_moved_module(ctx: Ctx):
    import halo_harness.mcp.claude_auth as auth
    from halo_harness.mcp import connectors_bridge
    src = (PKG / "mcp" / "connectors_bridge.py").read_text(encoding="utf-8")
    ctx.check("connectors_bridge reads the moved module", "halo_harness.mcp.claude_auth" in src)
    with ConfigHome():
        os.environ["HALO_CLAUDE_EXE"] = FAKE_CLAUDE
        os.environ.pop("BRIDGE_TEST_CC_AUTH_STATUS", None)
        os.environ["FAKE_CLAUDE_CC_LOGGED_IN"] = "1"
        auth.reset_cached_claude_auth_status()
        try:
            ctx.check("a cold cache reads as no login yet", auth.claude_login_available() is False)
            connectors_bridge.prime_auth_cache_if_stale()
            status = auth.cached_claude_auth_status()
            ctx.check(f"the fake claude's auth status was read, got {status}",
                      status is not None and status.logged_in and status.auth_method == "claude.ai")
            ctx.check("the bridge now sees the claude.ai login", auth.claude_login_available() is True
                      and connectors_bridge._claude_ai_login_known_false() is False)
        finally:
            os.environ.pop("FAKE_CLAUDE_CC_LOGGED_IN", None)
            auth.reset_cached_claude_auth_status()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="removed subscription routes tests"))
