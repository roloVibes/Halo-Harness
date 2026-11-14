"""tests.test_pack_doctor_info -- the doctor's `info` severity (Halo 3.3.10.0 R3, packs/doctor.py,
packs/contrib_views.py, packs/cli.py `_doctor`, packs/manager.py; docs/COMMANDS-packs.md `halo pack doctor`): an
enabled pack's Setup blocks neither done nor skipped are one `info` row (exit 0) in `halo pack doctor`, `halo doctor`
and `halo doctor --config`; the Pack Manager counts it as a note.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SETUP_NOTE = ("setup-blocks: setup waiting: 3 blocks not done yet (Review preferences, Reach the review service, "
              "Before you start)")


@test
def test_an_unfinished_pack_setup_is_a_note(ctx: Ctx):
    """3.3.11.0 R3: an enabled pack's Setup blocks neither done nor skipped are one `info` row (exit 0) in `halo pack
    doctor`, `halo doctor` and `halo doctor --config`; the Pack Manager counts it as a note and flags "setup waiting";
    nothing while the pack is disabled or once every block is done or skipped."""
    import contextlib
    import io
    from halo_harness.doctor import run_checks
    from halo_harness.doctor_config import cmd_doctor_config
    from halo_harness.packs.manager import payload
    from halo_harness.packs.setup_state import DONE, SKIPPED, mark
    with PacksHome() as h:
        h.install(h.source("setup-blocks"))
        code, out, _err = h.cli("doctor")
        row = lambda: next(p for p in payload(cwd=h.repo, state_dir=h.state)["packs"] if p["id"] == "setup-blocks")  # noqa: E731
        ctx.check(f"disabled: no row, no flag, got {out.splitlines()[-1]!r}", "setup waiting" not in out and row()["setup_waiting"] == 0)
        from halo_harness.packs.grants import enable_id
        enable_id("setup-blocks", cwd=h.repo)
        code, out, _err = h.cli("doctor")
        rows = [ln.strip() for ln in out.splitlines() if ln.startswith("  [")]
        ctx.check(f"enabled: one [INFO] row, exit 0, got {code} {rows}", code == 0 and rows == [f"[INFO] {SETUP_NOTE} -> halo setup setup-blocks"])
        code, out, _err = h.cli("doctor", "--json")
        got = [(p["severity"], p["check"], p["fix"]) for p in json.loads(out)["problems"]]
        ctx.check(f"--json: the row with its fix, got {got}", code == 0 and got == [("info", "setup-waiting", "halo setup setup-blocks")])
        r = row()
        ctx.check(f"the Pack Manager: a note and the flag, got {r['notes']} {r['setup_waiting']}", r["setup_waiting"] == 3 and r["health"] == []
                  and [(n["severity"], n["check"]) for n in r["notes"]] == [("info", "setup-waiting")])
        lines, ok = run_checks(cwd=h.repo)
        mine = [ln for ln in lines if "Pack setup" in ln]
        ctx.check(f"halo doctor: one [INFO] line naming the door, and it fails nothing, got {mine}", mine ==
                  [f"[INFO] Pack setup: {SETUP_NOTE}; halo setup setup-blocks opens them"] and not any(ln.startswith("[MISSING] Pack") for ln in lines))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_doctor_config(cwd=h.repo)
        line = next((ln for ln in buf.getvalue().splitlines() if "setup waiting" in ln), "")
        ctx.check(f"halo doctor --config tags it [INFO], got {line!r}", line.strip().startswith("[INFO] "))
        mark("setup-blocks", "prefs", DONE)
        mark("setup-blocks", "reach", SKIPPED)
        mark("setup-blocks", "about", DONE)
        code, out, _err = h.cli("doctor")
        ctx.check("every block done or skipped: no row, no flag, no halo doctor line", code == 0 and "setup waiting" not in out
                  and row()["setup_waiting"] == 0 and not [ln for ln in run_checks(cwd=h.repo)[0] if "Pack setup" in ln])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
