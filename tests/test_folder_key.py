"""tests.test_folder_key -- 3.6.0.0 R12: a folder reached through a symlink is the same folder.

On macOS /var and /tmp are symlinks into /private, and a process's own cwd is always the resolved spelling
(getcwd). Sessions, memory, project settings and exports were stored under one spelling and looked up under the
other ("no sessions found for this directory", "MEMORY.md exists", KeyError on the typed path). One helper,
`config.paths.folder_key`, decides the key for a folder; `project_slug` and `normalize_cwd` (every per-folder
store and lookup) go through it. Here: a real symlinked project, on Linux and macOS. On Windows a process's cwd
keeps a junction's spelling, so folder_key keeps the spelling as given (checked with a real junction).
"""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all

test, TESTS = new_registry()


def _linked_project() -> "tuple[Path, Path]":
    """(real folder, a second spelling of it): a symlink on POSIX, a junction on Windows."""
    root = Path(tempfile.mkdtemp(prefix="folder-key-"))
    real = root / "real-project"
    real.mkdir()
    link = root / "linked-project"
    if os.name == "nt":
        try:
            import _winapi
            _winapi.CreateJunction(str(real), str(link))
        except (ImportError, AttributeError, OSError) as e:
            raise SkipTest(f"no junction here ({e})")
    else:
        os.symlink(real, link, target_is_directory=True)
    return real, link


@test
def test_one_key_for_a_folder_and_its_symlink(ctx: Ctx):
    from halo_harness.config.paths import folder_key, normalize_cwd, project_slug
    real, link = _linked_project()
    if os.name == "nt":
        ctx.check("Windows keeps a junction's spelling, as its own cwd does", folder_key(link) == str(link))
        return
    ctx.check("folder_key resolves the symlink", folder_key(link) == folder_key(real) == os.path.realpath(real))
    ctx.check("project_slug is one slug for both spellings", project_slug(link) == project_slug(real))
    ctx.check("normalize_cwd (the ~/.claude.json key) is one key", normalize_cwd(link) == normalize_cwd(real))
    ctx.check("a relative path is left alone", folder_key("some/relative") == "some/relative")


@test
def test_a_session_stored_through_the_link_is_found_from_the_real_folder(ctx: Ctx):
    if os.name == "nt":
        raise SkipTest("Windows: a junction keeps its spelling (its cwd is not resolved), so no second key exists")
    saved = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="folder-key-home-")
    try:
        from halo_harness.agent.sessions import resolve_continue, sessions_dir
        real, link = _linked_project()
        sid = uuid.uuid4().hex
        d = sessions_dir(link)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{sid}.jsonl").write_text("{}\n", encoding="utf-8")
        ctx.check("stored through the link, found from the real folder", resolve_continue(real) == sid)
        ctx.check("and the other way round", sessions_dir(real) == sessions_dir(link) and resolve_continue(link) == sid)
        from halo_harness.config.paths import memory_dir
        ctx.check("memory is one folder for both spellings", memory_dir(link) == memory_dir(real))
        from halo_harness.config.paths import lookup_project, normalize_cwd
        cj = {"projects": {normalize_cwd(real): {"allowedTools": ["Read"]}}}
        ctx.check("a ~/.claude.json project entry is found through the link",
                  lookup_project(cj, link).get("allowedTools") == ["Read"])
        cj = {"projects": {str(link): {"allowedTools": ["Grep"]}}}
        ctx.check("an entry written under the link spelling is found from the real folder",
                  lookup_project(cj, real).get("allowedTools") == ["Grep"])
    finally:
        if saved is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
