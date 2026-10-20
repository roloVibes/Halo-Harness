"""tests.test_studio_models_catalog -- Studio's model catalog resolves the
providers the way a session does, and Refresh says what each provider did
(Halo 3.1.4.0 R4; the owner, live on Kali: the session ran on Databricks while
the Models panel said "No provider is set up in this Halo home yet").

1. Databricks whose host and token live only in the user settings.json `env`
   block, or only in the keys step's env file (never in os.environ): GET
   models/status reports Databricks enabled and GET models lists its
   endpoints; the bare os.environ copy Studio used before does not see it;
2. Refresh over two stand-in providers, one past the time box and one that
   answers: one outcome line each, back within the box, kept with its time,
   and the late one's line replaces "still asking" when it answers;
3. with no endpoint cache, Refresh runs Databricks' endpoint discovery and
   says how many it found, or why not (HTTP 403);
4. the one-line reasons: HTTP status, timed out, unreachable, no key leaks;
5. GET models/fallback: the refs config.json, a bio and a lineup name that
   the catalog lacks (not verified, where each is named), and Halo's shipped
   OpenRouter list when OpenRouter is set up with no live list;
6. GET models/resolve: a lineup's card for a role, the role table, the default.
Run: python -m tests.test_studio_models_catalog
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
PREFIXES = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_", "OLLAMA_",
            "HF_", "EXPLABS_", "CLAUDE_CONFIG_DIR")
ENDPOINTS = [{"name": "databricks-glm-5-3", "task": "llm/v1/chat", "ready": "READY"},
             {"name": "databricks-deepseek-v4-1-flash", "task": "llm/v1/chat", "ready": "READY"}]


@contextmanager
def _home():
    """A fresh home with no provider anywhere; every provider variable snapshotted and put back."""
    saved = {k: v for k, v in os.environ.items() if k.startswith(PREFIXES)}
    for k in saved:
        os.environ.pop(k)
    home = Path(tempfile.mkdtemp(prefix="studio-catalog-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    from halo_harness.providers.config import default_state_dir
    from halo_harness.theme import set_config_value
    state = Path(default_state_dir())
    state.mkdir(parents=True, exist_ok=True)
    set_config_value("ollama.hosts", [{"name": "none", "url": "http://127.0.0.1:9"}])  # a host that answers nothing, at once
    try:
        yield home, state
    finally:
        for k in [k for k in os.environ if k.startswith(PREFIXES)]:
            os.environ.pop(k)
        os.environ.update(saved)
        shutil.rmtree(home, ignore_errors=True)


def _call(state: Path, method: str, path: str, query=None, body=None):
    from halo_harness.studio.api import Request, dispatch
    proj = state.parent / "proj"
    proj.mkdir(exist_ok=True)
    return dispatch(Request(method=method, path=path, query=query or {}, body=body or {}, cwd=proj, state_dir=state))


def _dbx_status(ctx: Ctx, state: Path, where: str) -> None:
    from halo_harness.providers.databricks import write_dbx_endpoints_json
    from halo_harness.providers.enablement import credentials_present
    write_dbx_endpoints_json(state, ENDPOINTS)
    ctx.check(f"{where}: a bare os.environ copy (Studio before) does not see it",
              where == "env file" or not credentials_present("databricks", env=dict(os.environ)))
    status, st = _call(state, "GET", "models/status")
    dbx = next((p for p in st.get("providers", []) if p["name"] == "databricks"), {})
    ctx.check(f"{where}: status reports Databricks enabled, got {dbx} {st.get('reason')!r}", status == 200 and dbx.get("enabled") is True)
    status, rows = _call(state, "GET", "models")
    refs = {r["ref"] for r in rows} if status == 200 else set()
    ctx.check(f"{where}: GET models lists its endpoints, got {sorted(refs)[:6]}",
              {"dbx:databricks-glm-5-3", "dbx:databricks-deepseek-v4-1-flash"} <= refs)


@test
def test_databricks_only_in_settings_json_is_a_set_up_provider(ctx: Ctx):
    with _home() as (home, state):
        (home / ".claude").mkdir()
        (home / ".claude" / "settings.json").write_text(json.dumps({"env": {
            "DATABRICKS_HOST": "https://your-workspace.cloud.databricks.com", "DATABRICKS_TOKEN": "dapi-test-not-real"}}), encoding="utf-8")
        _dbx_status(ctx, state, "settings.json env")


@test
def test_databricks_only_in_the_keys_step_env_file_is_a_set_up_provider(ctx: Ctx):
    with _home() as (home, state):
        env_file = home / ".config" / "halo" / "env"
        env_file.parent.mkdir(parents=True)
        env_file.write_text("DATABRICKS_HOST=https://your-workspace.cloud.databricks.com\nDATABRICKS_TOKEN=dapi-test-not-real\n", encoding="utf-8")
        _dbx_status(ctx, state, "env file")


@test
def test_refresh_lines_one_per_provider_within_the_box(ctx: Ctx):
    from halo_harness.studio import models_refresh as MR

    def answers(state_dir, env):
        (Path(state_dir) / "models.json").write_text(json.dumps({"fakeco/alpha-1": {"context_length": 1000}}), encoding="utf-8")
        return True, 1, ""

    def slow(state_dir, env):
        time.sleep(2.5)
        return True, 7, ""
    keep, box = MR.jobs_for, MR.BOX_S
    MR.jobs_for = lambda state_dir, env, local=True: [("Fast", "openrouter", answers), ("Slow", "slowpoke", slow),
                                                      ("Off", "anthropic", "a key is here but the provider is off: halo providers enable anthropic")]
    try:
        with _home() as (_home_dir, state):
            MR.BOX_S = 1
            t0 = time.monotonic()
            MR.refresh(state, {})
            took = time.monotonic() - t0
            ctx.check(f"back within the box (1 s), took {took:.1f}s", took < 1.8)
            time.sleep(2.0)  # that run's straggler answers before the route's run below
            status, r = _call(state, "POST", "models/refresh")
            ctx.check(f"one line each, got {r.get('attempts')}", r.get("attempts") == [
                "Fast: ok, 1 model", "Slow: timed out after 1 s (still asking: its list lands when it answers)",
                "Off: a key is here but the provider is off: halo providers enable anthropic"])
            ctx.check("kept with its time", isinstance(MR.last(state).get("at"), float) and r.get("refreshed_at") == MR.last(state)["at"])
            time.sleep(2.2)
            late = next((o for o in MR.last(state)["outcomes"] if o["name"] == "Slow"), {})
            ctx.check(f"the late answer replaces its line, got {late}", late.get("ok") is True and late.get("line") == "ok, 7 models")
            status, st = _call(state, "GET", "models/status")
            ctx.check("status carries the outcomes and when", st.get("refreshed_at") and len(st.get("outcomes") or []) == 3)
    finally:
        MR.jobs_for, MR.BOX_S = keep, box


@test
def test_refresh_runs_databricks_discovery_without_a_cache(ctx: Ctx):
    from halo_harness.providers import databricks as D
    from halo_harness.studio import models_refresh as MR
    keep = D.probe_databricks_endpoints_full
    try:
        with _home() as (home, state):
            os.environ.update(DATABRICKS_HOST="https://your-workspace.cloud.databricks.com", DATABRICKS_TOKEN="dapi-test-not-real")
            D.probe_databricks_endpoints_full = lambda host, token: (200, ENDPOINTS)
            got = {o["name"]: o for o in MR.refresh(state, dict(os.environ), local=False)["outcomes"]}
            ctx.check(f"discovery ran and says what it found, got {got.get('Databricks')}",
                      got.get("Databricks", {}).get("line") == "ok, 2 models" and len(D.load_dbx_endpoints_json(state)) == 2)
            D.probe_databricks_endpoints_full = lambda host, token: (403, [])
            got = {o["name"]: o for o in MR.refresh(state, dict(os.environ), local=False)["outcomes"]}
            ctx.check(f"a refusal says why, got {got.get('Databricks')}", "HTTP 403" in got.get("Databricks", {}).get("line", ""))
    finally:
        D.probe_databricks_endpoints_full = keep


@test
def test_the_one_line_reasons(ctx: Ctx):
    import socket
    from halo_harness.providers.http import UpstreamConnectError
    from halo_harness.studio.models_refresh import clean, explain
    ctx.check("an HTTP status says what it means", explain(RuntimeError("OpenRouter /models returned 401")) == "HTTP 401 (the key was refused)")
    ctx.check("a timeout says so", explain(socket.timeout("timed out")).startswith("timed out"))
    ctx.check("a connect failure is unreachable", explain(UpstreamConnectError("cannot reach openrouter.ai")).startswith("unreachable: "))
    fake = "sk" + "-or-v1-" + "0123456789abcdef"  # built here: no key-shaped literal in the source
    ctx.check("no key reaches a line", fake not in clean(f"Bearer {fake} failed") and fake not in clean(f"key {fake}") and "<redacted>" in clean(f"key {fake}"))


@test
def test_fallback_offers_the_refs_in_use_and_the_shipped_list(ctx: Ctx):
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.theme import set_config_value
    with _home() as (_home_dir, state):
        set_config_value("roles.worker", "ol:qwen3-coder:30b@lan")
        save_agent_bio("pinned", {"description": "x", "kind": "subagent", "models": {"preference": "dbx:databricks-glm-5-3"}}, state_dir=state)
        (state / "teams").mkdir(exist_ok=True)
        lines = ["name: mine", "agents:", "  - {agent: pinned, role: main, models: {preference: 'or:vendor/card-pick'}}", ""]
        (state / "teams" / "mine.yaml").write_text(chr(10).join(lines), encoding="utf-8")
        status, fb = _call(state, "GET", "models/fallback")
        rows = {r["ref"]: r for r in fb.get("rows", [])}
        ctx.check(f"config.json's and a bio's refs, not verified, with where, got {sorted(rows)[:5]}",
                  rows.get("ol:qwen3-coder:30b@lan", {}).get("verified") is False and "roles.worker" in rows["ol:qwen3-coder:30b@lan"]["detail"]
                  and "bio pinned" in rows.get("dbx:databricks-glm-5-3", {}).get("detail", ""))
        ctx.check(f"a lineup card's own model too, got {rows.get('or:vendor/card-pick')}", "lineup mine (main)" in rows.get("or:vendor/card-pick", {}).get("detail", ""))
        ctx.check("OpenRouter not set up: no shipped list", not fb.get("shipped"))
        set_config_value("providers.openrouter.enabled", True)
        status, fb = _call(state, "GET", "models/fallback")
        ctx.check(f"OpenRouter on with no live list: Halo's shipped list, got {fb.get('shipped')}",
                  fb.get("shipped") is True and any(r["source"] == "shipped" and r["ref"].startswith("or:") for r in fb["rows"]))


@test
def test_resolve_names_what_a_role_runs_on(ctx: Ctx):
    from halo_harness.teams_yaml import ensure_builtin_team_templates
    from halo_harness.theme import set_config_value
    with _home() as (_home_dir, state):
        ensure_builtin_team_templates(state_dir=state)
        status, r = _call(state, "GET", "models/resolve", {"role": "main", "lineup": "standard"})
        ctx.check(f"a lineup's card for the role, got {r}", status == 200 and r["source"] == "lineup" and r["card"] and r["ref"])
        set_config_value("roles.main", "or:fakeco/beta-2")
        set_config_value("team", "standard")
        status, r = _call(state, "GET", "models/resolve", {"role": "main"})
        ctx.check(f"the role table, and the active lineup's card for a link, got {r}",
                  r["source"] == "roles" and r["ref"] == "or:fakeco/beta-2" and r["lineup"] == "standard" and r["card"])
        set_config_value("model", "or:fakeco/alpha-1")
        status, r = _call(state, "GET", "models/resolve")
        ctx.check(f"no role: the default model, got {r}", r["source"] == "default" and r["ref"] == "or:fakeco/alpha-1")
        ctx.check("an unknown lineup is a 404", _call(state, "GET", "models/resolve", {"role": "main", "lineup": "nope"})[0] == 404)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
