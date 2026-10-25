"""tests.test_studio_roles_live_files -- Roles follows the disk (Halo 3.2.2.0
R6, "I have to refresh the page for updates that occur"): headless Chrome
through the driver base (tests/helpers/studio_roles_live_files.py; skipped
without one), the live feed on, the files watcher on a short poll:

1. a card the test writes into the open lineup's YAML shows on the canvas
   without a reload;
2. a bio form with a typed draft keeps it when the bio's file changes on
   disk, and says "<name> changed on disk" with Reload and Keep mine;
   Reload puts the file's version in the form;
3. the bio's file deleted on disk: the Bios list drops it, the form closes,
   the line says it was deleted;
4. config.json's `team` cleared from outside: the "active" chip goes.
Run: python -m tests.test_studio_roles_live_files
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


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (Roles' live-files checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_roles_live_files", "live"], capture_output=True,
                           encoding="utf-8", errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
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
def test_a_card_written_on_disk_shows_without_a_reload(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the new card shows, got {got.get('new_card')!r} after {got.get('new_card_s')!r} s",
              got.get("new_card") is True and isinstance(got.get("new_card_s"), (int, float)) and got["new_card_s"] < 15)
    ctx.check(f"one card more, got {got.get('cards_before')!r} -> {got.get('cards_after')!r}",
              isinstance(got.get("cards_before"), int) and got.get("cards_after") == got["cards_before"] + 1)
    ctx.check(f"the page was not reloaded, got {got.get('no_reload')!r}", got.get("no_reload") == "still here")


@test
def test_a_typed_bio_draft_stays_and_reload_replaces_it(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the form read the file first, got {got.get('field_before')!r}", got.get("field_before") == "first words")
    note = got.get("note") or ""
    ctx.check(f"the line says the bio changed on disk, got {note!r}", note.startswith("disk-bio changed on disk"))
    ctx.check(f"it offers Reload and Keep mine, got {got.get('note_buttons')!r}", got.get("note_buttons") == ["Reload", "Keep mine"])
    ctx.check(f"the typed draft stayed, got {got.get('draft_kept')!r}", got.get("draft_kept") == "typed in the form")
    ctx.check(f"Reload puts the file's version in, got {got.get('after_reload')!r}", got.get("after_reload") == "changed on disk by the test")
    ctx.check("the line goes after Reload", got.get("note_after_reload") is False)


@test
def test_a_bio_deleted_on_disk_leaves_the_list(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the line says it was deleted, got {got.get('gone_note')!r}",
              (got.get("gone_note") or "").startswith("disk-bio was deleted on disk. Pick another bio from the list."))
    ctx.check("the Bios list no longer has it", got.get("gone_in_list") is False)
    ctx.check("the form closed (nothing was unsaved)", got.get("form_closed") is True)


@test
def test_config_changed_outside_moves_the_active_mark(ctx: Ctx):
    got = _got(ctx)
    ctx.check("the active chip went when config.json's team was cleared", got.get("chip_gone") is True)
    ctx.check("still no reload", got.get("still_no_reload") == "still here")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
