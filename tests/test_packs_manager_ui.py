"""tests.test_packs_manager_ui -- the Pack Manager in the page (Halo 3.2.0.0
R6). Headless Chrome through the driver base (tests/helpers/studio_pack_manager.py;
skipped without one), over a fresh home with no pack installed:

1. Packs is the seventh core tab on Alt+7 (the six keep their keys; Setup is the eighth), with its
   five panels; Installed is empty and Sources offers the shipped doc-review;
2. Install from a source: the row shows, disabled, with install's lines;
3. Details: the API range beside this Halo's, no dependency, the contributes
   block `halo pack inspect` prints; a Grant toggle on a disabled pack picks
   the grant for Enable (its button names the command);
4. Enable: the row runs with 1/3 granted, the pack's section tab follows Packs
   on Alt+9; a Grant toggle on the enabled pack grants at once (state.json);
4b. 3.2.0.0 R7: Update asks first with the dry run's lines, swaps the new
   version in (Details names the grant it asks for), Roll back brings 1.0.0 back;
5. Templates: Run review opens Orchestra's form, filled in with the workflow;
5b. 3.2.1.0 R2: Orchestra's own Start view, no workflow filled in: the picker
   under the goal form lists the running pack's workflows, a pick fills the form;
6. a disabled pack's row: disabled, 0/3, Enable back, its tab gone, no picker;
7. Remove with its confirm (the command, --keep-config when ticked): the
   pack's folder goes and Sources offers Install again.
Run: python -m tests.test_packs_manager_ui
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}
CORE = ["Session", "Team", "Roles", "Fleet", "Design", "Orchestra", "Packs", "Setup"]


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Pack Manager checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_pack_manager"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=400, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in info)
    return info


@test
def test_packs_is_the_seventh_section_on_alt_7(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the six, then Packs, got {got.get('tabs')}", got.get("tabs") == CORE)
    ctx.check(f"Alt+1..8, got {got.get('kbds')}", got.get("kbds") == [f"Alt{n}" for n in range(1, 9)])
    ctx.check(f"Alt+7 opens it, got {got.get('alt7')!r}", str(got.get("alt7")).startswith("Packs"))
    ctx.check(f"its five panels, got {got.get('panels')}", got.get("panels") == ["Installed", "Details", "Sources", "Settings", "Templates"])
    ctx.check("nothing installed yet; Sources offers the shipped pack", got.get("empty") is True and got.get("source_install") == "Install")


@test
def test_install_from_a_source(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the row, disabled, got {got.get('installed_state')!r}", got.get("installed_state") == "disabled")
    ctx.check(f"install's own first line, got {got.get('installed_last')!r}", str(got.get("installed_last")).startswith("installed doc-review 1.0.0 at "))
    ctx.check("Sources marks it installed; its folder is in the home", got.get("source_after") == "installed" and got.get("on_disk") is True)


@test
def test_the_details_block_and_a_grant_picked_for_enable(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the API range beside this Halo's, got {got.get('api')!r}", got.get("api") == "1.0 to 1.9; this Halo has 1.0")
    ctx.check(f"no dependency, got {got.get('requires')!r}", got.get("requires") == "no other pack")
    text = str(got.get("contributes"))
    ctx.check(f"inspect's contributes block, got {text!r}", "Studio section docs (Docs review)" in text
              and "fleet capability docs.review" in text and "workflow review: stages read, judge, write" in text)
    ctx.check(f"the permissions it requests, got {got.get('perms')}", got.get("perms") == ["mcp:lint", "hooks", "bash"])
    ctx.check(f"a toggle on a disabled pack picks it for Enable, got {got.get('enable_label')!r} {got.get('enable_title')!r}",
              got.get("picked") is True and got.get("enable_label") == "Enable (1 grant)"
              and got.get("enable_title") == "halo pack enable doc-review --grant bash")


@test
def test_enable_and_grant(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"enabled with the picked grant, got {got.get('granted')!r}", got.get("granted") == "1/3 granted")
    ctx.check(f"its section after Setup on Alt+9, got {got.get('tabs_on')} {got.get('pack_kbd')}",
              got.get("tabs_on") == CORE + ["Docs review"] and got.get("pack_kbd") == "Alt9")
    ctx.check(f"a toggle on the enabled pack grants at once, got {got.get('granted_more')!r} {got.get('state_json')}",
              got.get("granted_more") == "2/3 granted" and got.get("state_json") == [True, ["bash", "hooks"]])


@test
def test_update_asks_first_and_rollback_brings_it_back(ctx: Ctx):
    """3.2.0.0 R7: the dry run's lines in Update's confirm (the CLI's words), the swap, the grant the new version asks
    for in Details, Roll back."""
    got = _got(ctx)
    lines = got.get("update_lines") or []
    ctx.check(f"Update shows the dry run first, nothing changed yet, got {lines}", got.get("untouched") is True and lines[:1]
              == ["doc-review 1.0.0 -> 1.0.1: it also asks for network"] and lines[-1].startswith("dry run: nothing is changed"))
    ctx.check(f"the confirm names the command, got {got.get('update_cmd')!r}", got.get("update_cmd") == "halo pack update doc-review")
    last = got.get("updated_last") or []
    ctx.check(f"update's own lines, the note first, got {last[:2]}", last[:1] == ["doc-review 1.0.0 -> 1.0.1: it also asks for network"]
              and len(last) > 1 and last[1].startswith("updated doc-review 1.0.0 -> 1.0.1 (") and got.get("version_after") == "1.0.1")
    ctx.check(f"Roll back names the version kept, got {got.get('rollback_label')!r}", got.get("rollback_label") == "Roll back to 1.0.0")
    ctx.check(f"Details names the grant the new version asks for, got {got.get('compat_after')}", got.get("compat_after") ==
              ["doc-review 1.0.1 requests network, which 1.0.0 did not; it is not granted, so what needs it does not run"])
    ctx.check(f"Roll back's own first line, got {got.get('rolled_last')!r}", str(got.get("rolled_last")).startswith(
        "rolled back doc-review 1.0.1 -> 1.0.0: doc-review.previous is doc-review/ again") and got.get("previous_gone") is True)


@test
def test_run_a_workflow_fills_the_orchestra_form(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"its lineup under Templates, got {got.get('lineups')}", got.get("lineups") == ["doc-review--review"])
    ctx.check(f"Run review goes to Orchestra, got {got.get('section_after_run')!r}", str(got.get("section_after_run")).startswith("Orchestra"))
    ctx.check(f"the form names the workflow, got {got.get('wf_ref')!r} {got.get('wf_title')!r}", got.get("wf_ref") == "doc-review/review"
              and got.get("wf_title") == "Run the workflow review")
    ctx.check(f"its inputs, style at its default, got {got.get('wf_inputs')}", got.get("wf_inputs") == [["docs", ""], ["style", "short"]])


@test
def test_orchestras_start_view_picks_a_packs_workflow(ctx: Ctx):
    """3.2.1.0 R2: the picker under the goal form; a pick is the same form Run <workflow> fills."""
    got = _got(ctx)
    ctx.check(f"under the goal form, the running pack's workflow, got {got.get('pick_options')} {got.get('pick_under_goal')}",
              got.get("pick_under_goal") is True and got.get("pick_options") == ["", "doc-review/review"])
    ctx.check(f"its label, got {got.get('pick_label')!r}", str(got.get("pick_label") or "").startswith("OR RUN A PACK'S WORKFLOW"))
    ctx.check(f"a pick fills the workflow's form, got {got.get('picked_ref')!r} {got.get('picked_inputs')} {got.get('picked_title')!r}",
              got.get("picked_ref") == "doc-review/review" and got.get("picked_inputs") == [["docs", ""], ["style", "short"]]
              and got.get("picked_title") == "Run the workflow review")


@test
def test_a_disabled_packs_row(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"disabled, its grants cleared, Enable back, got {got.get('disabled_state')!r} {got.get('disabled_grants')!r}",
              got.get("disabled_state") == "disabled" and got.get("disabled_grants") == "0/3 granted" and got.get("disabled_enable") is True)
    ctx.check(f"its section tab is gone, got {got.get('tabs_off')}", got.get("tabs_off") == CORE)
    ctx.check("Templates says to enable it first", got.get("templates_off") is True)
    ctx.check("3.2.1.0 R2: no running pack with a workflow, no picker on Orchestra's Start view", got.get("picker_off") is True)


@test
def test_remove_with_its_confirm(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the confirm names the command, got {got.get('remove_cmd')!r} {got.get('remove_cmd_keep')!r}",
              got.get("remove_cmd") == "halo pack remove doc-review" and got.get("remove_cmd_keep") == "halo pack remove doc-review --keep-config")
    ctx.check(f"remove's own first line, got {got.get('removed_last')!r}", got.get("on_disk_before") is True
              and str(got.get("removed_last")).startswith("removed doc-review: ")
              and str(got.get("removed_last")).endswith("file(s) of its own deleted; its folder is gone"))
    ctx.check("its folder is gone; Sources offers Install again", got.get("on_disk_after") is False and got.get("install_again") == "Install")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
