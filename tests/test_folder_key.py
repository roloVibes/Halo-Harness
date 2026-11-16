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
        # fix pass 2: each component is spelled as the disk spells it (an 8.3 TEMP like RUNNER~1 made long), but
        # the junction itself is never followed
        ctx.check("Windows keeps a junction's spelling, as its own cwd does",
                  folder_key(link).endswith("linked-project") and folder_key(link) != folder_key(real)
                  and os.path.samefile(folder_key(link), link))
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
        # fix pass 2: a stored key is never followed through its link (a trust record would follow the link's
        # target of today); it is found by its own spelling, as Claude Code finds it
        cj = {"projects": {str(link): {"allowedTools": ["Grep"]}}}
        ctx.check("an entry written under the link spelling is found under that spelling",
                  lookup_project(cj, str(link)).get("allowedTools") == ["Grep"])
        ctx.check("and it does not apply to the folder the link happens to point at",
                  lookup_project(cj, real) == {})
    finally:
        if saved is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved


@test
def test_a_trust_record_for_a_symlink_never_follows_where_the_link_points_today(ctx: Ctx):
    """fix pass 2 (sessions-storage): a `~/.claude.json` key `~/current` -> my-repo, trusted. Repointing the link
    at a freshly downloaded clone must not make the clone trusted (its .halo hooks and workflows would run)."""
    if os.name == "nt":
        raise SkipTest("Windows: folder_key keeps a spelling as given, no key is followed (the POSIX legs run this)")
    from halo_harness.config.claude_json import is_trusted
    root = Path(tempfile.mkdtemp(prefix="folder-key-trust-"))
    repo, clone, current = root / "my-repo", root / "downloaded-clone", root / "current"
    repo.mkdir()
    clone.mkdir()
    os.symlink(repo, current, target_is_directory=True)
    cj = {"projects": {str(current): {"hasTrustDialogAccepted": True}}}
    ctx.check("the clone is not trusted while the link points at my-repo", not is_trusted(clone, cj, {}))
    current.unlink()
    os.symlink(clone, current, target_is_directory=True)
    ctx.check("the clone is still not trusted after the link is repointed at it", not is_trusted(clone, cj, {}))
    ctx.check("a key written resolved (as halo writes it) still trusts its folder through a link",
              is_trusted(current, {"projects": {os.path.realpath(clone): {"hasTrustDialogAccepted": True}}}, {}))


@test
def test_a_lookup_resolves_the_cwd_once_and_never_a_stored_key(ctx: Ctx):
    """fix pass 2: 400 stored keys made one lookup_project 2,800 lstat calls (each key realpath'd), and a key on a
    dead network mount stalled every lookup. Only the cwd is resolved."""
    if os.name == "nt":
        raise SkipTest("Windows: folder_key never resolves, so no key is ever stat'ed there")
    from unittest import mock
    from halo_harness.config import paths
    root = Path(tempfile.mkdtemp(prefix="folder-key-many-"))
    cj = {"projects": {f"/net/gpu-box/share/proj{i}": {"allowedTools": ["Read"]} for i in range(400)}}
    cj["projects"][os.path.realpath(root)] = {"allowedTools": ["Grep"]}
    real = os.path.realpath
    calls = []

    def counting(p, *a, **kw):
        calls.append(str(p))
        return real(p, *a, **kw)
    with mock.patch.object(paths.os.path, "realpath", counting):
        found = paths.lookup_project(cj, root)
    ctx.check("the matching record is found", found.get("allowedTools") == ["Grep"])
    ctx.check(f"no stored key is resolved, got {len(calls)} realpath calls",
              len(calls) <= 2 and not any("/net/gpu-box" in c for c in calls))


@test
def test_memory_and_sessions_use_one_slug_through_a_link(ctx: Ctx):
    """fix pass 2: on Windows memory_dir resolve()d a junction or subst drive while sessions kept the spelling,
    so one folder had its sessions under one project slug and its memory under another."""
    saved = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="folder-key-home-")
    try:
        from halo_harness.agent.sessions import sessions_dir
        from halo_harness.config.paths import memory_dir, project_slug
        real, link = _linked_project()
        for spelling in (link, real):
            ctx.check(f"memory sits under the sessions' slug ({spelling.name})",
                      memory_dir(spelling).parent.name == project_slug(spelling) == sessions_dir(spelling).name)
    finally:
        if saved is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved


@test
def test_a_claude_md_exclude_written_through_a_link_matches(ctx: Ctx):
    """fix pass 2: on Windows a claudeMdExcludes pattern spelled through a junction (or subst / mapped drive)
    matched nothing, because the file is resolve()d and the pattern's folder was not."""
    from halo_harness.config.claude_md import _excluded
    real, link = _linked_project()
    (real / "sub").mkdir()
    md = real / "sub" / "CLAUDE.md"
    md.write_text("x", encoding="utf-8")
    via_link = str(link).replace("\\", "/") + "/sub/*"
    via_real = str(real).replace("\\", "/") + "/sub/*"
    ctx.check("a pattern through the link excludes the file reached through the link",
              _excluded(link / "sub" / "CLAUDE.md", [via_link]))
    ctx.check("and the file reached directly", _excluded(md, [via_link]))
    ctx.check("a pattern on the real folder still works", _excluded(link / "sub" / "CLAUDE.md", [via_real]))
    ctx.check("an unrelated pattern does not", not _excluded(md, [str(real.parent).replace("\\", "/") + "/other/*"]))


@test
def test_windows_one_key_for_a_folder_typed_in_another_case(ctx: Ctx):
    """fix pass 2 batch 2 (sessions-storage): PowerShell keeps the typed case in the cwd (`cd c:\\users\\me\\proj`
    gives `C:\\users\\me\\proj`), so the same folder had two session/memory slugs and its ~/.claude.json and
    trust.json records were not found. Windows folders are case-insensitive: one key whatever the case typed."""
    if os.name != "nt":
        raise SkipTest("Windows only: POSIX folders are case-sensitive (two cases are two folders)")
    saved = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="folder-key-home-")
    try:
        from halo_harness.agent.sessions import resolve_continue, sessions_dir
        from halo_harness.config.claude_json import is_trusted
        from halo_harness.config.paths import folder_key, lookup_project, memory_dir, normalize_cwd, project_slug
        root = Path(tempfile.mkdtemp(prefix="folder-key-case-"))
        real = root / "CaseProject"
        real.mkdir()
        real = Path(folder_key(real))
        typed = Path(str(real).lower())
        ctx.check("the typed case and the folder's own case give one slug", project_slug(typed) == project_slug(real))
        ctx.check("one memory folder", memory_dir(typed) == memory_dir(real))
        ctx.check("one ~/.claude.json key", normalize_cwd(typed) == normalize_cwd(real))
        ctx.check("folder_key spells the folder as the disk does", folder_key(typed) == str(real))
        sid = uuid.uuid4().hex
        d = sessions_dir(real)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{sid}.jsonl").write_text('{"type":"user"}\n', encoding="utf-8")
        ctx.check("a session made from the real case is continued from the typed case", resolve_continue(typed) == sid)
        cj = {"projects": {normalize_cwd(real, resolve=False).lower(): {"allowedTools": ["Read"]}}}
        ctx.check("a project record stored in another case is found",
                  lookup_project(cj, real).get("allowedTools") == ["Read"])
        trust = {normalize_cwd(real, resolve=False).lower(): True}
        ctx.check("a trust.json record stored in another case is found", is_trusted(real, {}, trust))
        ctx.check("a path that does not exist is left as typed",
                  folder_key(str(root / "no-such" / "MiXeD")) == str(root / "no-such" / "MiXeD"))
    finally:
        if saved is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
