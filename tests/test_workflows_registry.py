"""tests.test_workflows_registry -- where squares come from and which are enabled (Halo 3.3.16.0 R3,
workflows/registry.py, workflows/spec.py): four places in precedence (yours > project > shipped for a bare
name; a pack's by `<pack>/<name>`), yours read from the state dir (a test never writes the real ~/.halo),
the library's three groups in order; the enabled sets: the auto lineup reads config `workflows.enabled`
(default media), a lineup of yours its `workflows:` list (written there), a shipped lineup says to copy it;
a workflow without `gives` is never enabled. No model call.

Run: python -m tests.test_workflows_registry
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _square(does: str) -> str:
    return (f"name: media\ndoes: {does}\ntakes: [text, pdf]\ngives: [text]\ncovers: [pdf]\nengine: session\n"
            "stages:\n  - id: look\n")


@test
def test_a_bare_name_resolves_yours_then_the_project_then_shipped(ctx: Ctx):
    from halo_harness.workflows import registry, spec
    with PacksHome() as h:
        mine = h.write(".halo/workflows/media.yaml", _square("Mine."))
        proj = h.write(".halo/workflows/media.yaml", _square("The project's."), base=h.repo)
        wf, _ = spec.find("media", cwd=h.repo)
        ctx.check(f"yours first, got {wf.origin if wf else None}", wf is not None and wf.origin == "yours" and wf.ref == "media"
                  and wf.contract.does == "Mine.")
        mine.unlink()
        wf, _ = spec.find("media", cwd=h.repo)
        ctx.check(f"then the project's, got {wf.origin if wf else None}", wf is not None and wf.origin == "project")
        proj.unlink()
        wf, _ = spec.find("media", cwd=h.repo)
        ctx.check(f"then the shipped one, got {wf.origin if wf else None}", wf is not None and wf.origin == "shipped"
                  and Path(wf.path).parent == registry.shipped_dir())
        got, why = spec.find("nothing-here", cwd=h.repo)
        ctx.check(f"an unknown name says where it looked, got {why!r}", got is None and "not yours" in why and "not shipped" in why)


@test
def test_yours_is_the_state_dir_never_the_real_home(ctx: Ctx):
    from halo_harness.workflows import registry
    with PacksHome() as h:
        origin, folder = registry.folders(cwd=h.repo)[0]
        ctx.check(f"yours under the scratch home, got {folder}", origin == "yours" and folder == h.state / "workflows")
        ctx.check("a state_dir given wins", registry.folders(cwd=h.repo, state_dir=h.home / "x")[0][1] == h.home / "x" / "workflows")


@test
def test_the_library_groups_and_a_packs_squares(ctx: Ctx):
    from halo_harness.workflows import registry
    with PacksHome() as h:
        h.install(h.source(), enable=True, grants=["bash"])
        h.write(".halo/workflows/mine.yaml", _square("Mine.").replace("name: media", "name: mine"))
        got = registry.squares(cwd=h.repo)
        groups = [registry.group_of(w) for w in got]
        ctx.check(f"yours, then packs, then shipped, got {groups}", groups == sorted(groups, key=["yours", "packs", "shipped"].index))
        refs = [w.ref for w in got]
        ctx.check(f"a pack's by <pack>/<name>, got {refs}", "doc-review/review" in refs and "mine" in refs)
        ctx.check("every shipped square listed", {"media", "plan", "code", "review", "research"} <= set(refs))
        ok, line = registry.enable("doc-review/review", cwd=h.repo)
        ctx.check(f"a workflow without gives is never enabled, got {line!r}", not ok and "not a square" in line)


@test
def test_the_auto_lineup_reads_config_and_writes_it(ctx: Ctx):
    import json
    from halo_harness.workflows import registry
    with PacksHome() as h:
        ctx.check(f"default: media, got {registry.enabled_refs(cwd=h.repo)}", registry.enabled_refs(cwd=h.repo) == ["media"])
        ok, line = registry.enable("plan", cwd=h.repo)
        ctx.check(f"one line saying what changed, got {line!r}", ok and line == "plan enabled for the auto lineup (wrote config workflows.enabled)")
        cfg = json.loads((h.state / "config.json").read_text(encoding="utf-8"))
        ctx.check(f"config holds both, got {cfg}", cfg.get("workflows", {}).get("enabled") == ["media", "plan"])
        ok, line = registry.enable("plan", cwd=h.repo)
        ctx.check(f"twice says so, got {line!r}", ok and "already on" in line)
        ok, line = registry.disable("media", cwd=h.repo)
        ctx.check(f"disable, got {registry.enabled_refs(cwd=h.repo)}", ok and registry.enabled_refs(cwd=h.repo) == ["plan"])
        ctx.check("enabled_squares resolves them", [w.ref for w in registry.enabled_squares(cwd=h.repo)] == ["plan"])


@test
def test_a_lineup_of_yours_holds_its_list_and_a_shipped_one_is_read_only(ctx: Ctx):
    from halo_harness.workflows import registry
    with PacksHome() as h:
        h.write(".halo/teams/mine.yaml", "name: mine\nagents:\n  - {agent: default-model, role: main}\nworkflows: [review]\n")
        ctx.check(f"its list, got {registry.enabled_refs('mine', cwd=h.repo)}", registry.enabled_refs("mine", cwd=h.repo) == ["review"])
        ok, line = registry.enable("media", "mine", cwd=h.repo)
        ctx.check(f"written to the lineup's file, got {line!r}", ok and "for lineup mine" in line and "mine.yaml" in line)
        text = (h.state / "teams" / "mine.yaml").read_text(encoding="utf-8")
        ctx.check(f"the file lists both, got {text!r}", "review" in text and "media" in text)
        ok, line = registry.enable("media", "quality", cwd=h.repo)
        ctx.check(f"a shipped lineup says to copy it, got {line!r}", not ok and "read-only" in line and "halo teams new" in line)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
