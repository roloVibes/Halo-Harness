"""tests.test_pack_setup_state -- where a pack's Setup blocks stand (Halo 3.3.11.0 R3, packs/setup_state.py;
docs/EXTENSION_API.md "Setup blocks"):

1. `~/.halo/packs/.data/<id>/setup.json` (never the pack's own folder): untouched until marked; `done` / `skipped`
   with `at` and `by`; "" forgets; a state that is neither is refused; each change is the pack's `setup` event;
2. `unfinished`, `first_key` (the first block waiting, else the first block), `enable_lines` (one per untouched
   block), `doctor_rows` (one `info` row while one waits, none after), `door` (`halo setup <pack>`'s key and lines);
3. a file that does not read is no blocks recorded, and the real home is never touched (a scratch home).
Run: python -m tests.test_pack_setup_state
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
LINES = ["setup: setup-blocks -- Review preferences (halo setup setup-blocks)",
         "setup: setup-blocks -- Reach the review service (halo setup setup-blocks)",
         "setup: setup-blocks -- Before you start (halo setup setup-blocks)"]


@test
def test_the_file_and_its_states(ctx: Ctx):
    from halo_harness.packs import setup_state as SS
    from halo_harness.packs.discover import find
    with PacksHome() as h:
        h.install(h.source("setup-blocks"), enable=True)
        pack = find("setup-blocks", cwd=h.repo)
        path = SS.setup_path("setup-blocks")
        ctx.check(f"in the pack's data folder, not its own folder, got {path}", path == h.packs / ".data" / "setup-blocks" / "setup.json"
                  and Path(pack.root) not in path.parents)
        ctx.check("untouched: no file, nothing recorded", not path.exists() and SS.read("setup-blocks") == {}
                  and SS.state_of("setup-blocks", "prefs") == {"state": "", "at": "", "by": ""})
        rec = SS.mark("setup-blocks", "prefs", SS.DONE, by="studio")
        ctx.check(f"done, with at and by, got {rec}", rec["state"] == "done" and rec["by"] == "studio" and rec["at"].startswith("20"))
        SS.mark("setup-blocks", "about", SS.SKIPPED, by="cli")
        raw = json.loads(path.read_text(encoding="utf-8"))
        ctx.check(f"the file's shape, got {raw}", sorted(raw) == ["blocks"] and sorted(raw["blocks"]) == ["about", "prefs"]
                  and raw["blocks"]["about"]["state"] == "skipped" and sorted(raw["blocks"]["prefs"]) == ["at", "by", "state"])
        SS.mark("setup-blocks", "about", "")
        ctx.check("'' forgets: untouched again", "about" not in SS.read("setup-blocks"))
        try:
            SS.mark("setup-blocks", "prefs", "maybe")
            refused = False
        except ValueError as e:
            refused = "done, skipped" in str(e)
        ctx.check("a state that is neither is refused", refused and SS.read("setup-blocks")["prefs"]["state"] == "done")
        from halo_harness.packs.events_log import since
        changes = [e["data"] for e in since("setup-blocks:setup")]
        ctx.check(f"each change is the pack's setup event, got {changes}", [c["state"] for c in changes] == ["done", "skipped", "untouched"]
                  and changes[0] == {"block": "prefs", "state": "done", "by": "studio"})
        path.write_text("{not json", encoding="utf-8")
        ctx.check("a file that does not read: nothing recorded", SS.read("setup-blocks") == {} and len(SS.unfinished(pack)) == 3)


@test
def test_what_waits_and_the_lines_that_say_so(ctx: Ctx):
    from halo_harness.packs import setup_state as SS
    from halo_harness.packs.discover import find
    with PacksHome() as h:
        h.install(h.source("setup-blocks"), enable=True)
        pack = find("setup-blocks", cwd=h.repo)
        ctx.check(f"three untouched: one enable line each, got {SS.enable_lines(pack)}", SS.enable_lines(pack) == LINES)
        ctx.check("the first block waiting", SS.first_key(pack) == "pack:setup-blocks:prefs")
        rows = SS.doctor_rows(pack)
        ctx.check(f"one info row naming the three and the door, got {rows}", len(rows) == 1 and rows[0]["severity"] == "info"
                  and rows[0]["check"] == "setup-waiting" and rows[0]["fix"] == "halo setup setup-blocks"
                  and rows[0]["text"] == "setup-blocks: setup waiting: 3 blocks not done yet (Review preferences, "
                                         "Reach the review service, Before you start)")
        SS.mark("setup-blocks", "prefs", SS.DONE)
        SS.mark("setup-blocks", "reach", SS.SKIPPED)
        ctx.check("done and skipped are not waiting", [e["id"] for e in SS.unfinished(pack)] == ["about"]
                  and SS.enable_lines(pack) == LINES[2:] and SS.first_key(pack) == "pack:setup-blocks:about"
                  and SS.doctor_rows(pack)[0]["text"].startswith("setup-blocks: setup waiting: 1 block not done yet"))
        key, lines = SS.door("setup-blocks")
        ctx.check(f"halo setup's door: the key and a line per block, got {key} {lines}", key == "pack:setup-blocks:about" and lines == [
            "setup-blocks -- Review preferences (form): done", "setup-blocks -- Reach the review service (check): skipped",
            "setup-blocks -- Before you start (note): waiting"])
        SS.mark("setup-blocks", "about", SS.DONE)
        ctx.check("all done: no line, no row; the door opens the first block", SS.enable_lines(pack) == [] and SS.doctor_rows(pack) == []
                  and SS.first_key(pack) == "pack:setup-blocks:prefs" and SS.waiting_count(pack) == 0)
        ctx.check("a word that is no pack: None (the usage line)", SS.door("kitchen") == (None, []))
        from halo_harness.packs.grants import disable
        disable("setup-blocks")
        key, lines = SS.door("setup-blocks")
        ctx.check(f"a disabled pack: one line saying so, got {key!r} {lines}", key == "" and lines ==
                  ["setup-blocks does not run here: its Setup blocks show once it is enabled (halo pack enable setup-blocks)"])
        h.install(h.source("policy-fence"), enable=True, grants=["hooks"])
        key, lines = SS.door("policy-fence")
        ctx.check(f"a pack with no blocks: one line, got {lines}", key == "" and lines[0].startswith("policy-fence adds no Setup block"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
