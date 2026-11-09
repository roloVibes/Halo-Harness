"""tests.test_pack_run -- a pack command that runs a program needs the `bash` grant and knows its pack's id (Halo
3.3.14.0 R1, the November review's #9; commands/pack_run.py, packs/manifest.py `needed`), over the service-pack fixture
(its entry command `run:`s service/ticker.py --say, which prints the words and HALO_PACK_ID):

1. the pack needs `bash` for "command service-pack (run:)"; enable lists it while it is not granted;
2. enabled without the grant: the command keeps its prompt form (no program runs) and `halo pack doctor` says what is
   missing; granted: it is a core command that runs the program;
3. a pack linked from a folder of another name: HALO_PACK_ID is the pack's id, not the folder's name.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome, fixture  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
NEED = ("bash", "command service-pack (run:)")


def _command(h, root: Path, name: str):
    from halo_harness.commands.registry import Registry
    from halo_harness.packs import registry
    registry.invalidate()
    return Registry.discover(h.repo, home=h.home, plugin_roots=[root]).resolve(name)


def _facade(h):
    return type("F", (), {"cwd": h.repo, "session": None})()


@test
def test_a_run_command_needs_bash(ctx: Ctx):
    from halo_harness.packs.discover import find
    from halo_harness.packs.doctor import problems
    from halo_harness.packs.grants import enable, needs
    with PacksHome() as h:
        h.install(h.source("service-pack"))
        pack = find("service-pack", cwd=h.repo)
        ctx.check(f"needed names the command, got {needs(pack)}", NEED in needs(pack))
        ok, lines = enable(pack, grant=["services"])
        ctx.check(f"enable lists it as not granted, got {lines}", ok and any(
            "not running until granted: command service-pack (run:) (halo pack enable service-pack --grant bash)" == ln
            for ln in lines))
        root = h.packs / "service-pack"
        cmd = _command(h, root, "/service-pack")
        ctx.check(f"without bash: the prompt form, got {cmd and cmd.kind}", cmd is not None and cmd.kind == "prompt")
        rows = [r for r in problems(cwd=h.repo) if r["check"] == "not-granted" and "(run:)" in r["text"]]
        ctx.check(f"the doctor says what is missing, got {rows}", rows and "bash is not granted" in rows[0]["text"]
                  and rows[0]["fix"] == "halo pack enable service-pack --grant bash")
        enable(pack, grant=["bash"])
        cmd = _command(h, root, "/service-pack")
        ctx.check("granted bash: a core command (no model call)", cmd is not None and cmd.kind == "core")
        out = cmd.run("one two", _facade(h))
        ctx.check(f"it runs the program with the words and the id, got {out!r}",
                  "the pack's own program says: one two" in out and "HALO_PACK_ID=service-pack" in out)


@test
def test_a_linked_pack_in_another_folder_sees_its_id(ctx: Ctx):
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import enable
    from halo_harness.packs.link import link
    with PacksHome() as h:
        folder = h.home / "work" / "svc-folder"
        shutil.copytree(fixture("service-pack"), folder, ignore=shutil.ignore_patterns("__pycache__"))
        ok, lines = link(str(folder), cwd=h.repo)
        ctx.check(f"linked, got {lines[:1]}", ok)
        from halo_harness.packs import registry
        registry.invalidate()
        ok, lines = enable(find("service-pack", cwd=h.repo), grant=["services", "bash"])
        ctx.check(f"enabled with bash, got {lines[:1]}", ok)
        from halo_harness.commands.registry import Registry
        reg = Registry.discover(h.repo, home=h.home, plugin_roots=[folder.resolve()])
        cmds = [c for c in reg.all() if str(c.name).endswith("service-pack")] if hasattr(reg, "all") else []
        cmd = cmds[0] if cmds else reg.resolve("/svc-folder:service-pack") or reg.resolve("/service-pack")
        ctx.check(f"the command is there and runs a program, got {cmd and (cmd.name, cmd.kind)}", cmd is not None and cmd.kind == "core")
        out = cmd.run("hi", _facade(h)) if cmd is not None else ""
        ctx.check(f"HALO_PACK_ID is the pack's id, not svc-folder, got {out!r}", "HALO_PACK_ID=service-pack" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
