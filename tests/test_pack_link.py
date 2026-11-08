"""tests.test_pack_link -- `halo pack install <folder> --link` (Halo 3.3.12.0 R4, packs/link.py): a linked folder
shows in `list`, `inspect` and Studio's pack registry; an edit to its markdown panel shows on the next read with no
reinstall, and so does a new bio; `remove` (and `unlink`) take the link away and leave the folder; the journal rows
say `link` and `unlink`; `update` and `rollback` have nothing to do for a link; a project link is the repo's only.
A real Studio server on 127.0.0.1:0 over a scratch home; no model, no network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_studio import PackStudio  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _new(s, pack_id: str, *kinds) -> Path:
    from halo_harness.packs.scaffold import new
    work = s.home / "work"
    work.mkdir(exist_ok=True)
    ok, lines = new(pack_id, kinds=list(kinds), folder=work)
    assert ok, lines
    return work / pack_id


@test
def test_a_link_is_listed_inspected_and_drawn_in_place(ctx: Ctx):
    from halo_harness.packs import journal as J
    with PackStudio() as s:
        folder = _new(s, "live", "studio", "agents")
        code, out, err = s.cli("install", str(folder), "--link", "--project")
        ctx.check(f"install --link --project: one line saying it is read in place, got {out} {err}", code == 0
                  and out.startswith(f"linked live 0.1.0: {folder}") and "read in place" in out)
        ctx.check("a link file in the repo's packs folder, nothing copied", (s.repo / ".halo" / "packs" / "live.link").is_file()
                  and not (s.repo / ".halo" / "packs" / "live").exists())
        code, out, _err = s.cli("list", "--json")
        row = next(p for p in json.loads(out)["packs"] if p["id"] == "live")
        ctx.check(f"list: the pack, project scope, its folder as the source, got {row}", row["scope"] == "project"
                  and Path(row["source"]) == folder)
        code, out, _err = s.cli("inspect", "live")
        ctx.check(f"inspect by id reads the folder, got {out[-200:]}", code == 0 and "problems: none" in out)
        code, _out, err = s.cli("enable", "live", "--grant-all")
        _st, reg, _h = s.call("GET", "pack/registry")
        pack = next((p for p in reg["packs"] if p["id"] == "live"), None)
        ctx.check(f"Studio's registry lists it, got {pack and [x['id'] for x in pack['sections']]}", code == 0
                  and pack is not None and pack["sections"][0]["id"] == "live--home")
        notes = folder / "studio" / "notes.md"
        _st, raw, _h = s.raw("/api/pack/live/file/studio/notes.md")
        notes.write_text("# Live\n\nEdited in place.\n", encoding="utf-8")
        _st2, raw2, _h2 = s.raw("/api/pack/live/file/studio/notes.md")
        ctx.check(f"an edit to the markdown panel shows on the next read, no reinstall, got {raw2[:60]!r}",
                  b"Edited in place." not in raw and b"Edited in place." in raw2)
        from halo_harness import agents_yaml as A
        before = (A.resolve_agent_bio("live--lead", cwd=s.repo) or {}).get("description")
        lead = folder / "agents" / "lead.yaml"
        lead.write_text(lead.read_text(encoding="utf-8").replace("Pick me to plan", "Pick me first to plan"),
                        encoding="utf-8")
        after = (A.resolve_agent_bio("live--lead", cwd=s.repo) or {}).get("description")
        ctx.check(f"an edit to a bio in the folder shows at the next lookup, got {before!r} -> {after!r}",
                  before and after and after.startswith("Pick me first") and not before.startswith("Pick me first"))
        code, out, _err = s.cli("update", "live")
        ctx.check(f"update: nothing to do for a link, got {out}", code == 0 and "is linked to" in out)
        code, _out, err = s.cli("rollback", "live")
        ctx.check(f"rollback: the same line, exit 1, got {err}", code == 1 and "nothing to update or roll back" in err)
        code, out, _err = s.cli("unlink", "live")
        ctx.check(f"unlink: the link goes, the folder stays, got {out}", code == 0 and "stays as it is" in out
                  and not (s.repo / ".halo" / "packs" / "live.link").exists() and (folder / "pack.yaml").is_file()
                  and notes.read_text(encoding="utf-8").startswith("# Live"))
        ops = [r["op"] for r in J.rows(pack="live")]
        ctx.check(f"the journal rows say link and unlink, got {ops}", ops == ["link", "unlink"])
        code, out, _err = s.cli("list", "--json")
        ctx.check("gone from the list", "live" not in [p["id"] for p in json.loads(out)["packs"]])


@test
def test_remove_unlinks_a_user_link_and_refuses_a_second(ctx: Ctx):
    with PackStudio() as s:
        folder = _new(s, "mine", "commands")
        code, _out, _err = s.cli("install", str(folder), "--link")
        ctx.check("a user link", code == 0 and (s.packs / "mine.link").is_file())
        code, _out, err = s.cli("install", str(folder), "--link")
        ctx.check(f"a second link: one line, got {err}", code == 1 and "is already linked to" in err)
        other = s.home / "elsewhere"
        other.mkdir()
        code, out, _err = s.cli("list", "--cwd", str(other))
        ctx.check("a user link shows from any folder", "mine" in out)
        code, out, _err = s.cli("remove", "mine", "--keep-config")
        ctx.check(f"remove --keep-config: unlinked, the record kept, got {out}", code == 0 and "unlinked mine" in out
                  and "kept its record" in out and (folder / "pack.yaml").is_file())
        code, _out, err = s.cli("install", "https://example.invalid/x.git", "--link")
        ctx.check(f"--link takes a folder only, got {err}", code == 1 and "takes a pack folder on this machine" in err)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
