"""tests.test_workflows_registry -- where squares come from and which are enabled (Halo 3.3.16.0 R3,
workflows/registry.py, workflows/spec.py): four places in precedence (yours > project > shipped for a bare
name; a pack's by `<pack>/<name>`), yours read from the state dir (a test never writes the real ~/.halo),
the library's three groups in order; the enabled set is config `workflows.enabled` (default media; 3.6.0.0 R5d:
lineups are gone); a workflow without `gives` is never a square on. No model call.

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
    from tests.helpers.trust_dir import trust
    with PacksHome() as h:
        trust(h.repo)  # 3.4.1.2 (ENGINE-1): a project's squares load only in a trusted folder
        mine = h.write(".halo/workflows/mysq.yaml", _square("Mine."))
        proj = h.write(".halo/workflows/mysq.yaml", _square("The project's."), base=h.repo)
        wf, _ = spec.find("mysq", cwd=h.repo)
        ctx.check(f"yours first, got {wf.origin if wf else None}", wf is not None and wf.origin == "yours" and wf.ref == "mysq"
                  and wf.contract.does == "Mine.")
        mine.unlink()
        wf, _ = spec.find("mysq", cwd=h.repo)
        ctx.check(f"then the project's, got {wf.origin if wf else None}", wf is not None and wf.origin == "project")
        proj.unlink()
        proj = h.write(".halo/workflows/media.yaml", _square("The project's."), base=h.repo)
        wf, _ = spec.find("media", cwd=h.repo)
        ctx.check(f"a project file never takes a shipped name, got {wf.origin if wf else None}",
                  wf is not None and wf.origin == "shipped")
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
        from halo_harness.theme import set_config_value  # 3.6.0.0 R5d: the set is config's
        set_config_value("workflows.enabled", ["doc-review/review", "media"])
        ctx.check("a workflow without gives is never a square on",
                  [w.ref for w in registry.enabled_squares(cwd=h.repo)] == ["media"])


@test
def test_the_set_is_configs(ctx: Ctx):
    from halo_harness.theme import set_config_value
    from halo_harness.workflows import registry
    with PacksHome() as h:
        ctx.check(f"default: media, got {registry.enabled_refs(cwd=h.repo)}", registry.enabled_refs(cwd=h.repo) == ["media"])
        set_config_value("workflows.enabled", ["plan"])
        ctx.check(f"config's set, got {registry.enabled_refs(cwd=h.repo)}", registry.enabled_refs(cwd=h.repo) == ["plan"])
        ctx.check("enabled_squares resolves them", [w.ref for w in registry.enabled_squares(cwd=h.repo)] == ["plan"])
        ctx.check("a name given changes nothing (lineups are gone)", registry.enabled_refs("quality", cwd=h.repo) == ["plan"])


@test
def test_config_set_writes_a_list_and_a_plain_session_offers_both(ctx: Ctx):
    """3.6.0.0 R5d (the judge's item 4): `halo config set workflows.enabled media,review` stores the list (it stored the
    string, which the reader took for the default), every list-typed key alike; the reader takes a hand-written comma
    string; `halo doctor --config` says in one line when a list-typed key holds one plain value."""
    import contextlib
    import io
    import json
    from halo_harness.config_cli import as_list, cmd_config
    from halo_harness.doctor_config import config_findings
    from halo_harness.theme import get_config_value, set_config_value
    from halo_harness.workflows.offer import squares_on
    with PacksHome() as h:
        with contextlib.redirect_stdout(io.StringIO()):
            rc = cmd_config(["set", "workflows.enabled", "media,review"])
        ctx.check(f"stored as a list, got {rc} {get_config_value('workflows.enabled')!r}",
                  rc == 0 and get_config_value("workflows.enabled") == ["media", "review"])
        got = [w.ref for w in squares_on(None, cwd=h.repo)]
        ctx.check(f"a plain session offers both squares, got {got}", got == ["media", "review"])
        for given, want in (("review", ["review"]), ('["plan","media"]', ["plan", "media"]), ("", [])):
            with contextlib.redirect_stdout(io.StringIO()):
                cmd_config(["set", "workflows.enabled", given])
            ctx.check(f"{given!r} stores {want}, got {get_config_value('workflows.enabled')!r}",
                      get_config_value("workflows.enabled") == want)
        ctx.check("every list-typed key alike (a number stays a number); other keys unchanged",
                  as_list("ollama.discover.ports", "11434,11435") == [11434, 11435]
                  and as_list("recall.sources", "~/notes") == ["~/notes"] and as_list("model", "a,b") == "a,b"
                  and as_list("ollama.hosts", {"lan": "x"}) == {"lan": "x"})
        set_config_value("workflows.enabled", "media, review")
        got = [w.ref for w in squares_on(None, cwd=h.repo)]
        ctx.check(f"the reader takes a hand-written comma string, got {got}", got == ["media", "review"])
        found = [f for f in config_findings(h.repo, state_dir=h.state) if f["key"] == "workflows.enabled"]
        ctx.check(f"doctor --config: one line for the plain value, got {found}",
                  len(found) == 1 and found[0]["severity"] == "warns"
                  and found[0]["text"].endswith('workflows.enabled is a list, not ' + json.dumps("media, review"))
                  and "halo config set workflows.enabled" in found[0]["fix"])
        set_config_value("workflows.enabled", ["media"])
        ctx.check("a list: no line", not [f for f in config_findings(h.repo, state_dir=h.state) if f["key"] == "workflows.enabled"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
