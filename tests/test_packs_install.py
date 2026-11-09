"""tests.test_packs_install -- Halo 3.3.13.1 (plans/REVIEW-2026-11.md #3, PACKS-1): `halo pack install` and `halo
pack update` copy a pack's own files only. A source with a file that is a symbolic link to a file outside the folder
(on Windows without the link privilege: a directory junction pointing outside) is not installed: one line names the
entry and nothing is written; an update to such a source leaves the pack as it was; `update` copies with
`follow_symlinks=False`; `halo pack install --link` (the owner's own folder, read in place) is unchanged.
A scratch home, the shipped doc-review pack copied as the source, a fake env file outside it.
Run: python -m tests.test_packs_install
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SECRET = "FAKE-OWNER-FILE-for-the-test\n"


def _plant(h, src: Path) -> "tuple[str, Path]":
    """A link inside `src` to a file of the owner's outside it (the finding's case was the env file; a fake file
    here): (the entry's relative path, the outside file)."""
    outside = h.home / "owner-files"
    outside.mkdir(parents=True, exist_ok=True)
    (outside / "notes.txt").write_text(SECRET, encoding="utf-8")
    target = src / "skills" / "check-links" / "SKILL.md"
    target.unlink()
    try:
        os.symlink(outside / "notes.txt", target)
        return "skills/check-links/SKILL.md", outside / "notes.txt"
    except (OSError, NotImplementedError):  # Windows without the symlink privilege: a junction needs none
        import _winapi
        _winapi.CreateJunction(str(outside), str(src / "skills" / "linked"))
        return "skills/linked", outside / "notes.txt"


def _anywhere(root: Path) -> bool:
    return any(SECRET in p.read_text(encoding="utf-8", errors="replace") for p in root.rglob("*")
               if p.is_file() and not p.is_symlink()) if root.exists() else False


@test
def test_a_link_out_of_the_pack_is_not_installed(ctx: Ctx):
    with PacksHome() as h:
        src = h.source()
        rel, _outside = _plant(h, src)
        code, _out, err = h.cli("install", str(src))
        ctx.check(f"install exits 1 with one line naming {rel}, got {code} {err!r}",
                  code == 1 and rel in err and "nothing is written" in err and len(err.strip().splitlines()) == 1)
        ctx.check("nothing was written", not (h.packs / "doc-review").exists())
        ctx.check("the outside file's text is nowhere under the packs folder", not _anywhere(h.packs))


@test
def test_an_update_to_a_linked_source_leaves_the_pack(ctx: Ctx):
    with PacksHome() as h:
        src = h.source()
        h.install(src)
        root = h.packs / "doc-review"
        before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
        text = (src / "pack.yaml").read_text(encoding="utf-8").replace("version: 1.0.0", "version: 1.1.0")
        (src / "pack.yaml").write_text(text, encoding="utf-8")
        rel, _outside = _plant(h, src)
        code, _out, err = h.cli("update", "doc-review")
        ctx.check(f"update exits 1 naming {rel}, got {code} {err!r}", code == 1 and rel in err
                  and "stays as it is" in err)
        ctx.check("the pack is as it was", sorted(p.relative_to(root).as_posix() for p in root.rglob("*")) == before
                  and not _anywhere(h.packs))


@test
def test_update_copies_a_link_as_a_link(ctx: Ctx):
    import inspect
    from halo_harness.packs import update
    ctx.check("update's copy never reads through a link",
              "follow_symlinks=False" in inspect.getsource(update._copy_file))


@test
def test_install_link_is_unchanged(ctx: Ctx):
    with PacksHome() as h:
        src = h.source()
        _plant(h, src)
        code, out, err = h.cli("install", "--link", str(src))
        ctx.check(f"--link: the owner's own folder, used in place as before, got {code} {out!r} {err!r}", code == 0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
