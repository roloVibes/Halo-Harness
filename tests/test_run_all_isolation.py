"""tests.test_run_all_isolation -- Halo 3.1.0.0 round R1: tests/run_all.py
gives every module its own fresh home and reads the tier without importing.

1. Two tiny modules run through run_all's own loop (`main()` over a faked
   discovery): the first writes a `models.json` into its state dir, the
   second asserts it does not see it, and that its home is a different
   directory under the same scratch root; the first module's home is gone
   after the run, and the env is back to what it was.
2. `ensure_scoped_state_dir_once` re-scopes once per run_all module and stays
   "once" for a module run alone.
3. The state-dir caches are reset between modules.
4. The tier: `TIER = "full"` in the file head, read by regex; `--fast`,
   `--tier full`, nothing = all; a bad flag exits 2.
Run: python -m tests.test_run_all_isolation
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

_WRITER = '''
import json, os
from pathlib import Path
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import new_registry
ensure_scoped_state_dir_once()
test, TESTS = new_registry()
SEEN = {}

@test
def test_writes_a_catalog(ctx):
    from halo_harness.providers.config import default_state_dir
    state = Path(default_state_dir())
    state.mkdir(parents=True, exist_ok=True)
    (state / "models.json").write_text(json.dumps({"vendor/only-in-a": {}}), encoding="utf-8")
    SEEN.update(home=os.environ.get("BRIDGE_TEST_HOME"), state=str(state))
    ctx.check("the catalog is there", (state / "models.json").is_file())
'''

_READER = '''
import os
from pathlib import Path
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import new_registry
ensure_scoped_state_dir_once()
test, TESTS = new_registry()
SEEN = {}

@test
def test_does_not_see_the_catalog(ctx):
    from halo_harness.providers.config import default_state_dir
    state = Path(default_state_dir())
    SEEN.update(home=os.environ.get("BRIDGE_TEST_HOME"), state=str(state), saw=(state / "models.json").exists())
    ctx.check(f"no models.json from the first module under {state}", not (state / "models.json").exists())
'''


def _package(*sources: str) -> "tuple[str, list[str]]":
    """A throwaway package on sys.path holding one module per source; returns (package, module names)."""
    root = Path(tempfile.mkdtemp(prefix="run-all-iso-"))
    pkg = f"_run_all_iso_{uuid.uuid4().hex[:8]}"
    (root / pkg).mkdir()
    (root / pkg / "__init__.py").write_text("", encoding="utf-8")
    names = []
    for i, src in enumerate(sources):
        (root / pkg / f"test_iso_{i}.py").write_text(src, encoding="utf-8")
        names.append(f"{pkg}.test_iso_{i}")
    sys.path.insert(0, str(root))
    return pkg, names


def _run_main(names: list, argv=None) -> "tuple[int, str]":
    import tests.run_all as R
    real_discover, real_sessions = R.discover_test_modules, R._real_sessions_snapshot
    R.discover_test_modules = lambda: list(names)
    R._real_sessions_snapshot = lambda: set()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = R.main(argv)
    finally:
        R.discover_test_modules, R._real_sessions_snapshot = real_discover, real_sessions
    return rc, buf.getvalue()


@test
def test_second_module_does_not_see_the_first_modules_catalog(ctx: Ctx):
    import tests.run_all as R
    pkg, names = _package(_WRITER, _READER)
    env_before = R._snapshot_guarded_env()
    rc, out = _run_main(names)
    a, b = sys.modules[names[0]].SEEN, sys.modules[names[1]].SEEN
    ctx.check(f"both modules passed, got rc={rc}:\n{out[-1500:]}", rc == 0 and out.count("[PASS]") == 2)
    ctx.check(f"each module had its own home, got {a.get('home')} / {b.get('home')}",
              a.get("home") and b.get("home") and a["home"] != b["home"])
    ctx.check("the homes sit side by side under one scratch root, named after the module",
              Path(a["home"]).parent == Path(b["home"]).parent and Path(a["home"]).name == "test_iso_0"
              and Path(b["home"]).name == "test_iso_1")
    ctx.check(f"the second module never saw the first one's models.json, got {b}", b.get("saw") is False)
    ctx.check("the first module's home was removed after it", not Path(a["home"]).exists())
    after = R._snapshot_guarded_env()
    survivors = {"BRIDGE_TEST_NO_BACKGROUND_NET", "BRIDGE_TEST_CC_AUTH_STATUS"}  # main()'s own whole-run seams
    changed = {k for k in set(env_before) | set(after)
               if env_before.get(k) != after.get(k) and not k.startswith("HALO_")} - survivors  # main() clears HALO_* once
    ctx.check(f"the guarded env is back to what it was (BRIDGE_TEST_HOME included), got {changed}", not changed)
    ctx.check(f"the run names its tier, got {out[:200]!r}", "[tier] all (fast + full): 2 module(s)" in out)


@test
def test_ensure_scoped_state_dir_once_rescopes_per_module(ctx: Ctx):
    from tests.helpers import provider_env_defaults as P
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    root = Path(tempfile.mkdtemp(prefix="run-all-iso-scope-"))
    try:
        os.environ.pop("BRIDGE_STATE_DIR", None)
        os.environ["BRIDGE_TEST_HOME"] = str(root / "test_a")
        P.begin_module("tests.test_a", root / "test_a")
        P.ensure_scoped_state_dir_once()
        P.end_module()
        os.environ["BRIDGE_TEST_HOME"] = str(root / "test_a")  # module a's home left behind
        P.begin_module("tests.test_b", root / "test_b")
        P.ensure_scoped_state_dir_once()
        ctx.check("the first call in module b points at b's home",
                  os.environ["BRIDGE_TEST_HOME"] == str(root / "test_b"))
        os.environ["BRIDGE_TEST_HOME"] = str(root / "elsewhere" / "chosen-by-a-test")
        P.ensure_scoped_state_dir_once()
        ctx.check("a later call in the same module is the plain once no-op",
                  os.environ["BRIDGE_TEST_HOME"] == str(root / "elsewhere" / "chosen-by-a-test"))
        P.end_module()
        own = str(Path(tempfile.gettempdir()) / "a-home-module-c-chose-itself")
        os.environ["BRIDGE_TEST_HOME"] = own
        P.begin_module("tests.test_c", root / "test_c")
        P.ensure_scoped_state_dir_once()
        ctx.check("a home the module chose itself is kept", os.environ["BRIDGE_TEST_HOME"] == own)
        P.end_module()
        os.environ.pop("BRIDGE_TEST_HOME", None)
        P.ensure_scoped_state_dir_once()
        ctx.check("alone (no run_all module): a fresh scratch home, once",
                  "halo-scratch-" in os.environ.get("BRIDGE_TEST_HOME", ""))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@test
def test_state_caches_are_reset_between_modules(ctx: Ctx):
    from tests.helpers import run_all_support as S
    import halo_harness.config.paths as paths
    import halo_harness.providers.databricks as dbx
    paths._state_dir_memo["/scratch/earlier-module-home"] = Path("/scratch/earlier-module-home/.halo")
    dbx._DBX_ROUTE_CACHE["databricks-some-model"] = {"idx": 1}
    done = S.reset_state_caches()
    ctx.check(f"the memo and the route cache are empty, got {done}",
              not paths._state_dir_memo and not dbx._DBX_ROUTE_CACHE)
    ctx.check("it names what it reset", {"halo_harness.config.paths._state_dir_memo",
                                         "halo_harness.providers.databricks._DBX_ROUTE_CACHE"} <= set(done))


@test
def test_tier_is_read_from_the_file_head_without_importing(ctx: Ctx):
    from tests.helpers import run_all_support as S
    d = Path(tempfile.mkdtemp(prefix="run-all-iso-tier-"))
    full = d / "test_full_one.py"
    full.write_text('"""doc"""\nfrom __future__ import annotations\n\nTIER = "full"  # Chrome\nraise SystemExit(9)\n', encoding="utf-8")
    fast = d / "test_fast_one.py"
    fast.write_text('"""doc"""\nraise SystemExit(9)\n', encoding="utf-8")
    late = d / "test_late.py"
    late.write_text("x = 1\n" * 4000 + 'TIER = "full"\n', encoding="utf-8")
    ctx.check("TIER = \"full\" -> full", S.module_tier(full) == "full")
    ctx.check("no TIER line -> fast", S.module_tier(fast) == "fast")
    ctx.check("a TIER line past the head is not read", S.module_tier(late) == "fast")
    ctx.check("select: full only", S.select_tier([full, fast], "full") == [full])
    ctx.check("select: fast only", S.select_tier([full, fast], "fast") == [fast])
    ctx.check("select: everything", S.select_tier([full, fast], None) == [full, fast])
    ctx.check("--fast", S.parse_tier_args(["--fast"]) == "fast")
    ctx.check("--tier full", S.parse_tier_args(["--tier", "full"]) == "full" and S.parse_tier_args(["--tier=fast"]) == "fast")
    ctx.check("no flag = all", S.parse_tier_args([]) is None)
    try:
        S.parse_tier_args(["--tier", "slow"])
        ctx.check("a bad tier raises", False)
    except ValueError:
        pass


@test
def test_the_repo_marks_its_chrome_and_pilot_modules_full(ctx: Ctx):
    from tests.helpers import run_all_support as S
    tests_dir = Path(__file__).resolve().parent
    for name in ("test_studio_ui", "test_studio_modes", "test_wizard_lineup", "test_tui_inplace"):  # 3.1.5.0: test_scene went with the game themes
        ctx.check(f"{name} is in the full tier", S.module_tier(tests_dir / f"{name}.py") == "full")
    for name in ("test_run_all_isolation", "test_orchestra_plan_review", "test_release_script"):
        ctx.check(f"{name} is in the fast tier", S.module_tier(tests_dir / f"{name}.py") == "fast")


@test
def test_main_runs_only_the_asked_tier_and_refuses_a_bad_flag(ctx: Ctx):
    pkg, names = _package('TIER = "full"\nfrom tests.helpers.runner import new_registry\ntest, TESTS = new_registry()\n')
    rc, out = _run_main(names, ["--tier", "nope"])
    ctx.check(f"a bad tier exits 2, got {rc}", rc == 2)
    rc, out = _run_main(names, ["--fast"])
    ctx.check(f"--fast names the tier and the count, got {out[:300]!r}", rc == 0 and "[tier] fast (no Chrome, no TUI pilots)" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
