"""tests.test_env_file_drop -- Halo 2.0.5 round 3 (2.0.4-brief.md "5.
Deprecations", 2.0.3-brief.md G7): the legacy env file `~/.config/
vibes-hacker/env` is no longer read. `load_provider_env_files()` loads
only the new canonical `~/.config/halo/env`; the import-marker logic
(`config.paths.env_file_has_import_marker`/`ENV_IMPORT_MARKER`) is kept as
a pure, directly-testable function but is no longer CALLED from that
reader; `halo init`'s one-time copy-forward (the actual migration) is
unaffected; `halo doctor` WARNs when only the legacy file exists and says
nothing (an OK line) when the new one does. No network, no real model.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


class _Env:
    """Scopes BRIDGE_TEST_HOME (so `config.paths.home()` resolves here)
    and clears every env var that could otherwise supply a credential or
    override the env file path, so each test starts from a clean slate."""

    _CLEARED = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "HALO_ENV_FILE", "BRIDGE_ENV_FILE",
                "ROLO_CLAUDE_ENV_FILE", "OPENROUTER_API_KEY", "DATABRICKS_HOST", "DATABRICKS_TOKEN",
                "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN")

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in self._CLEARED}
        for k in self._CLEARED:
            os.environ.pop(k, None)
        self.home = Path(tempfile.mkdtemp(prefix="env-file-drop-"))
        os.environ["BRIDGE_TEST_HOME"] = str(self.home)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def write_legacy(self, content: str) -> Path:
        p = self.home / ".config" / "vibes-hacker" / "env"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def write_new(self, content: str) -> Path:
        p = self.home / ".config" / "halo" / "env"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p


@test
def test_legacy_only_is_no_longer_loaded(ctx: Ctx):
    """The core behavior change: a scratch home with ONLY the legacy file
    loads NO key at all -- before this round the fallback read would have
    found it."""
    with _Env() as env:
        env.write_legacy("DATABRICKS_TOKEN=secret-from-legacy\n")
        from halo_harness.providers.config import load_provider_env_files
        loaded = load_provider_env_files()
        ctx.check(f"nothing loaded from the legacy-only file, got {loaded}", loaded == {})
        ctx.check("not in os.environ either", "DATABRICKS_TOKEN" not in os.environ)


@test
def test_new_file_only_is_loaded_normally(ctx: Ctx):
    with _Env() as env:
        env.write_new("DATABRICKS_TOKEN=secret-from-new\n")
        from halo_harness.providers.config import load_provider_env_files
        loaded = load_provider_env_files()
        ctx.check(f"loaded from the new file, got {loaded}", loaded.get("DATABRICKS_TOKEN") == "secret-from-new")


@test
def test_both_exist_only_the_new_one_is_read(ctx: Ctx):
    """Confirms there is no blending at all any more -- a key living ONLY
    in the legacy file is invisible even when the new file also exists
    (for some other key)."""
    with _Env() as env:
        env.write_legacy("DATABRICKS_TOKEN=legacy-value\nOPENROUTER_API_KEY=legacy-or\n")
        env.write_new("DATABRICKS_TOKEN=new-value\n")
        from halo_harness.providers.config import load_provider_env_files
        loaded = load_provider_env_files()
        ctx.check(f"new file's value wins, got {loaded}", loaded.get("DATABRICKS_TOKEN") == "new-value")
        ctx.check(f"the legacy-only key never appears, got {loaded}", "OPENROUTER_API_KEY" not in loaded)


@test
def test_doctor_warns_when_only_the_legacy_file_exists(ctx: Ctx):
    with _Env() as env:
        env.write_legacy("DATABRICKS_TOKEN=secret\n")
        from halo_harness.doctor import OK, WARN, _check_env_file
        line = _check_env_file()
        ctx.check(f"a WARN line, got {line!r}", line.startswith(WARN))
        ctx.check(f"names halo init as the migration, got {line!r}", "halo init" in line)


@test
def test_doctor_says_nothing_wrong_when_the_new_file_exists(ctx: Ctx):
    with _Env() as env:
        env.write_new("DATABRICKS_TOKEN=secret\n")
        from halo_harness.doctor import OK, WARN, _check_env_file
        line = _check_env_file()
        ctx.check(f"an OK line, got {line!r}", line.startswith(OK))


@test
def test_doctor_still_warns_when_neither_file_exists(ctx: Ctx):
    with _Env():
        from halo_harness.doctor import WARN, _check_env_file
        line = _check_env_file()
        ctx.check(f"still the ordinary WARN, got {line!r}", line.startswith(WARN) and "halo init" in line)


@test
def test_import_marker_helper_still_works_directly_a_no_op_only_for_the_reader(ctx: Ctx):
    """`env_file_has_import_marker`/`ENV_IMPORT_MARKER` are kept exactly as
    they were -- `load_provider_env_files` simply no longer CALLS them
    (the no-op the brief means), they are not removed, and a test (or any
    other seam) calling them directly still gets a correct answer."""
    with _Env() as env:
        from halo_harness.config.paths import ENV_IMPORT_MARKER, env_file_has_import_marker
        marked = env.home / "marked-env"
        marked.write_text(ENV_IMPORT_MARKER + "\nDATABRICKS_TOKEN=x\n", encoding="utf-8")
        unmarked = env.home / "unmarked-env"
        unmarked.write_text("DATABRICKS_TOKEN=x\n", encoding="utf-8")
        ctx.check("detects the marker when present", env_file_has_import_marker(marked))
        ctx.check("correctly says no when absent", not env_file_has_import_marker(unmarked))


@test
def test_init_copy_forward_still_migrates_the_legacy_file(ctx: Ctx):
    """`halo init`'s one-time copy-forward (`config.paths.env_file_path_
    for_write`) IS the migration the brief says stays unaffected -- the
    first write on a box with only the legacy file still copies its
    content into the new one, marked, with the legacy file left
    untouched."""
    with _Env() as env:
        legacy_path = env.write_legacy("DATABRICKS_TOKEN=legacy-secret\n")
        legacy_before = legacy_path.read_text(encoding="utf-8")
        from halo_harness.config.paths import ENV_IMPORT_MARKER, env_file_path_for_write
        new_path = env_file_path_for_write()
        ctx.check(f"the new file now exists, got {new_path}", new_path.exists())
        content = new_path.read_text(encoding="utf-8")
        ctx.check("carries the import marker", ENV_IMPORT_MARKER in content)
        ctx.check("carries the legacy content forward", "DATABRICKS_TOKEN=legacy-secret" in content)
        ctx.check("the legacy file itself was never modified", legacy_path.read_text(encoding="utf-8") == legacy_before)
        # And the now-migrated new file is what load_provider_env_files
        # reads (the normal, unconditional case -- nothing special about
        # a copied-forward file from this function's point of view).
        from halo_harness.providers.config import load_provider_env_files
        loaded = load_provider_env_files()
        ctx.check(f"readable normally afterward, got {loaded}", loaded.get("DATABRICKS_TOKEN") == "legacy-secret")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
