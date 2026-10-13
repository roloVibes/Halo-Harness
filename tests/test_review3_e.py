"""tests.test_review3_e -- 3.0.2.0 review fix pass, round E (session data),
part 1: the shadow store and the private atomic writer.

  * review item 15   a failed shadow `git commit` recorded a step anyway
                     (stale HEAD, or the literal "HEAD" on an empty repo)
  * review item 87   /rewind skipped every path git C-quotes
  * review item 161  the shadow index split JSONL with str.splitlines
  * review item 86   write_private_atomic replaced a symlink with a file

Part 2 (tests/test_review3_e2.py): config/role/org/bio writers, design.json.
Part 3 (tests/test_review3_e3.py): /resume and Ctrl+P session switching.
"""
from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all

test, TESTS = new_registry()

_GIT_VARS = ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")


class _GitEnv:
    """Point git's GLOBAL config at a scratch file for one test (the real
    ~/.gitconfig is never read or written); restores both variables."""

    def __init__(self, text: str):
        self.text = text

    def __enter__(self):
        self.saved = {k: os.environ.get(k) for k in _GIT_VARS}
        cfg = Path(tempfile.mkdtemp(prefix="r3e-gitcfg-")) / "gitconfig"
        cfg.write_text(self.text, encoding="utf-8")
        os.environ["GIT_CONFIG_GLOBAL"] = str(cfg)
        os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
        return cfg.parent

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


def _store():
    from halo_harness.shadow import ShadowStore
    return ShadowStore(Path(tempfile.mkdtemp(prefix="r3e-shadow-")))


def _work_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="r3e-work-"))


# ---- item 15: a failed commit records no step -------------------------------

@test
def test_i15_global_gpgsign_and_failing_hooks_do_not_break_snapshots(ctx: Ctx):
    hooks = Path(tempfile.mkdtemp(prefix="r3e-hooks-"))
    for name in ("pre-commit", "prepare-commit-msg", "commit-msg"):
        hook = hooks / name
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8", newline="\n")
        if os.name != "nt":
            hook.chmod(0o755)
    cfg = ("[commit]\n\tgpgsign = true\n[gpg]\n\tprogram = halo-no-such-gpg-program\n"
           f"[core]\n\thooksPath = {hooks.as_posix()}\n")
    with _GitEnv(cfg):
        store = _store()
        target = _work_dir() / "a.txt"
        s1 = store.record_step({str(target): "v1\n"}, label="Write(a.txt)")
        s2 = store.record_step({str(target): "v2\n"}, label="Write(a.txt)")
    ctx.check(f"both steps were recorded, got {s1!r} / {s2!r}", bool(s1) and bool(s2))
    ctx.check("each step has its own real commit hash",
              s1.get("hash") != s2.get("hash") and all(c in "0123456789abcdef" for c in s1.get("hash", "x")))
    target.write_text("v2\n", encoding="utf-8")
    store.rewind_to(s1["id"])
    ctx.check("rewinding to step 1 restores v1", target.read_text(encoding="utf-8") == "v1\n")


@test
def test_i15_commit_failure_records_no_step(ctx: Ctx):
    store = _store()
    target = _work_dir() / "b.txt"
    first = store.record_step({str(target): "one\n"}, label="Write(b.txt)")
    real_git = store._git

    def failing_commit(*args):
        result = real_git(*args)
        if args and args[0] == "commit":
            result.returncode = 1
        return result

    store._git = failing_commit
    second = store.record_step({str(target): "two\n"}, label="Write(b.txt)")
    ctx.check(f"a failed commit returns {{}}, got {second!r}", second == {})
    ctx.check(f"only the first step is in memory, got {len(store.steps)}", len(store.steps) == 1)
    index_lines = [l for l in store._index_path.read_text(encoding="utf-8").split("\n") if l.strip()]
    ctx.check(f"only the first step is in the index, got {len(index_lines)}", len(index_lines) == 1)
    ctx.check("the first step kept its own hash", store.steps[0]["hash"] == first["hash"])


@test
def test_i15_empty_repo_never_records_the_literal_head(ctx: Ctx):
    store = _store()
    real_git = store._git

    def no_commit(*args):
        result = real_git(*args)
        if args and args[0] == "commit":
            result.returncode = 128
        return result

    store._git = no_commit
    step = store.record_step({str(_work_dir() / "c.txt"): "x\n"}, label="Write(c.txt)")
    ctx.check(f"no step on an empty repo whose commit failed, got {step!r}", step == {} and store.steps == [])


# ---- item 87: C-quoted paths are restored too --------------------------------

@test
def test_i87_rewind_restores_non_ascii_and_quoted_paths(ctx: Ctx):
    work = _work_dir()
    names = ["plain.txt", "résumé.txt", "naïve file.txt"]
    if os.name != "nt":
        names += ['quo"te.txt', "back\\slash.txt"]
    paths = [work / n for n in names]
    store = _store()
    s1 = store.record_step({str(p): f"v1 {p.name}\n" for p in paths}, label="step 1")
    store.record_step({str(p): f"v2 {p.name}\n" for p in paths}, label="step 2")
    for p in paths:
        p.write_text(f"v2 {p.name}\n", encoding="utf-8", newline="\n")
    out = store.rewind_to(s1["id"])
    restored = {Path(f).name for f in (out or {}).get("files", [])}
    ctx.check(f"every tracked path was restored, got {sorted(restored)}", restored == set(names))
    stale = [p.name for p in paths if p.read_text(encoding="utf-8") != f"v1 {p.name}\n"]
    ctx.check(f"every file is back at step 1's content, stale: {stale}", stale == [])


# ---- item 161: the shadow index keeps a record with U+2028 in it whole --------

@test
def test_i161_index_record_with_unicode_line_separators_survives_reload(ctx: Ctx):
    from halo_harness.shadow import ShadowStore
    work = _work_dir()
    store = _store()
    odd = work / "odd name.txt"
    store.record_step({str(odd): "a\n"}, label="Write(odd name\u0085x\x0bq\x0c.txt)")
    store.record_step({str(work / "next.txt"): "b\n"}, label="Write(next.txt)")
    reloaded = ShadowStore(store.session_dir)
    ctx.check(f"both steps come back after a reload, got {len(reloaded.steps)}", len(reloaded.steps) == 2)
    ctx.check("the label is intact", reloaded.steps[0]["label"] == store.steps[0]["label"])


@test
def test_i161_dead_stream_json_line_parser_is_gone(ctx: Ctx):
    import halo_harness.cli as cli
    ctx.check("cli._parse_stream_json_lines (no callers) was removed",
              not hasattr(cli, "_parse_stream_json_lines"))


# ---- item 86: a symlinked target is written through ---------------------------

def _symlink_or_skip(target: Path, link: Path) -> None:
    try:
        os.symlink(str(target), str(link))
    except (OSError, NotImplementedError) as e:
        raise SkipTest(f"symlinks are not available here ({e})")


@test
def test_i86_write_private_atomic_writes_through_a_symlink(ctx: Ctx):
    from halo_harness.privateio import write_private_atomic
    root = Path(tempfile.mkdtemp(prefix="r3e-link-"))
    (root / "dotfiles").mkdir()
    real = root / "dotfiles" / "env"
    real.write_text("OLD=1\n", encoding="utf-8")
    link = root / ".env"
    _symlink_or_skip(real, link)
    write_private_atomic(link, "NEW=2\n")
    ctx.check("the link is still a link", link.is_symlink())
    ctx.check("the real target holds the new data", real.read_text(encoding="utf-8") == "NEW=2\n")
    ctx.check("reading through the link sees it too", link.read_text(encoding="utf-8") == "NEW=2\n")
    leftovers = [p.name for p in list(root.iterdir()) + list((root / "dotfiles").iterdir()) if p.name.endswith(".tmp")]
    ctx.check(f"no temp file left behind, got {leftovers}", leftovers == [])
    if os.name != "nt":
        ctx.check("the target is 0600", stat.S_IMODE(os.stat(real).st_mode) == 0o600)


@test
def test_i86_keep_mode_writer_and_link_chains_write_through(ctx: Ctx):
    from halo_harness.privateio import write_atomic_keep_mode
    root = Path(tempfile.mkdtemp(prefix="r3e-chain-"))
    real = root / "settings.json"
    real.write_text("{}\n", encoding="utf-8")
    if os.name != "nt":
        real.chmod(0o640)
    hop = root / "hop.json"
    _symlink_or_skip(real, hop)
    link = root / "link.json"
    _symlink_or_skip(hop, link)
    write_atomic_keep_mode(link, '{"a": 1}\n')
    ctx.check("both links survive", link.is_symlink() and hop.is_symlink())
    ctx.check("the final target got the data", real.read_text(encoding="utf-8") == '{"a": 1}\n')
    if os.name != "nt":
        ctx.check("the target kept its own mode", stat.S_IMODE(os.stat(real).st_mode) == 0o640)


@test
def test_i86_plain_path_is_unchanged(ctx: Ctx):
    from halo_harness.privateio import write_private_atomic
    p = Path(tempfile.mkdtemp(prefix="r3e-plain-")) / "sub" / "token"
    write_private_atomic(p, "t\n")
    ctx.check("a plain path is still written in place", p.read_text(encoding="utf-8") == "t\n" and not p.is_symlink())
    if os.name != "nt":
        ctx.check("0600", stat.S_IMODE(os.stat(p).st_mode) == 0o600)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
