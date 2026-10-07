"""tests.test_roles_doctor_round -- Halo 2.0.6 round 7: `halo doctor
--roles` (the v2.0.4 review's item 6, roles hygiene headless).

The lineup editor's warning set as a standalone command: no 'main', a
judge in the same model family as the coder (self-preference bias), an
unreachable gateway endpoint. Fast by construction -- no model calls,
at most one reachability probe per distinct gateway host.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

REPO_DIR = Path(__file__).resolve().parent.parent


def _scoped(home: Path, roles: dict):
    """A fake home whose config.json carries the given roles table, with
    the env scoped for both in-process and CLI-child use."""
    cfg = home / ".halo"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "config.json").write_text(json.dumps({"roles": roles}), encoding="utf-8")


def _env_for(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_ENV_FILE", "HALO_GOVERNOR")}
    env.update({"BRIDGE_TEST_HOME": str(home), "PYTHONPATH": str(REPO_DIR),
                "BRIDGE_TEST_NO_BACKGROUND_NET": "1"})
    return env


@test
def test_model_family_buckets(ctx: Ctx):
    from halo_harness.agents_doctor import _model_family
    cases = {
        "or:z-ai/glm-5.3": "glm", "or:z-ai/glm-5.3-flash": "glm",
        "ol:qwen3-coder:30b@lan": "qwen", "or:qwen/qwen3.8-flash": "qwen",
        "or:deepseek/deepseek-v4-pro-0813": "deepseek", "or:deepseek/deepseek-v4-flash": "deepseek",
        "cc:sonnet": "sonnet", "cc:opus": "opus",
        "or:mock/model": "model", "dbx:databricks-claude-4-5": "databricks-claude",
    }
    for ref, want in cases.items():
        ctx.check(f"{ref} -> {want}", _model_family(ref) == want)
    ctx.check("an empty ref has no family", _model_family("") is None)


@test
def test_hygiene_flags_the_three_problems(ctx: Ctx):
    import contextlib

    @contextlib.contextmanager
    def _env(home):
        saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        os.environ["BRIDGE_TEST_HOME"] = str(home)
        os.environ.pop("BRIDGE_STATE_DIR", None)
        try:
            yield
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    from halo_harness.agents_doctor import check_roles_hygiene
    home = Path(tempfile.mkdtemp(prefix="rolesdoc-"))

    # 1. same-family judge/coder: both qwen -> bias warning
    _scoped(home, {"main": "or:mock/glm-5", "coder": "ol:qwen3-coder:30b@lan",
                   "judge": "or:qwen/qwen3.8-flash"})
    with _env(home):
        problems = check_roles_hygiene()
    bias = [p for p in problems if "judge and coder" in p]
    ctx.check(f"the same-family judge/coder warns, got {problems}",
              len(bias) == 1 and "qwen" in bias[0])

    # 2. no main at all (neither roles.main nor a top-level model)
    _scoped(home, {"coder": "ol:qwen3-coder:30b@lan", "judge": "or:deepseek/deepseek-v4-flash"})
    with _env(home):
        problems = check_roles_hygiene()
    ctx.check(f"a missing main warns, got {problems}", any("no main model" in p for p in problems))

    # 2b. a top-level `model` key alone is a VALID main (the VM's own
    # config spells it that way) -- no warning
    cfg = home / ".halo" / "config.json"
    cfg.write_text(json.dumps({"model": "ol:qwen3.8:27b@lan",
                               "roles": {"coder": "ol:qwen3-coder:30b@lan",
                                         "judge": "or:deepseek/deepseek-v4-flash"}}),
                   encoding="utf-8")
    with _env(home):
        problems = check_roles_hygiene()
    ctx.check(f"a top-level model is a valid main, got {problems}",
              not any("no main model" in p for p in problems))

    # 3. a clean table: different families, main set, mock gateways only
    # (the local-model `ol:` route needs no probe; nothing remote configured)
    _scoped(home, {"main": "ol:qwen3.8:27b@lan", "coder": "ol:qwen3-coder:30b@lan",
                   "judge": "or:deepseek/deepseek-v4-flash"})
    with _env(home):
        problems = check_roles_hygiene()
    ctx.check(f"a local-first clean lineup stays clean, got {problems}",
              not [p for p in problems if "'main'" in p or "judge and coder" in p])


@test
def test_cli_exit_codes_and_json(ctx: Ctx):
    home = Path(tempfile.mkdtemp(prefix="rolescli-"))
    # clean lineup (all-local ol: models, no remote probe)
    _scoped(home, {"main": "ol:qwen3.8:27b@lan", "coder": "ol:qwen3-coder:30b@lan",
                   "judge": "ol:bugtrace:latest"})
    r = subprocess.run([sys.executable, "-m", "halo_harness", "doctor", "--roles"],
                       env=_env_for(home), cwd=str(REPO_DIR), capture_output=True, text=True,
                       timeout=120)
    ctx.check(f"a clean lineup exits 0, got {r.returncode} stderr={r.stderr[-200:]!r}",
              r.returncode == 0)
    ctx.check("the clean result line prints", "looks healthy" in r.stdout)

    # dirty: no main
    _scoped(home, {"coder": "ol:qwen3-coder:30b@lan"})
    r2 = subprocess.run([sys.executable, "-m", "halo_harness", "doctor", "--roles", "--json"],
                        env=_env_for(home), cwd=str(REPO_DIR), capture_output=True, text=True,
                        timeout=120)
    ctx.check(f"a dirty lineup exits 1, got {r2.returncode}", r2.returncode == 1)
    try:
        # the header lines print before the JSON (the same convention
        # --agents/--teams use); the payload starts at the first brace
        payload = json.loads(r2.stdout[r2.stdout.index("{"):])
        ctx.check("the json payload carries the problems list",
                  isinstance(payload.get("problems"), list) and any("main" in p for p in payload["problems"]))
    except ValueError:
        ctx.check("the json output parses", False)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
