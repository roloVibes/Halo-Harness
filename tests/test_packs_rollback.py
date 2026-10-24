"""tests.test_packs_rollback -- an update you can take back, and an update
that never leaves a half-replaced folder (Halo 3.2.0.0 R7,
halo_harness/packs/update.py, packs/rollback.py): `halo pack rollback`
swaps `<id>.previous` back, moves the renamed settings back (from the
journal), keeps the grants, puts the journal's ownership back as it was and
keeps a file you changed since; with nothing kept it says so in one line; a
copy error while staging and a failed swap leave the old version byte for
byte; `halo pack remove` deletes the `.previous` copy, `--keep-config` keeps
it with the record and rollback installs it again; Studio's Rollback answers
the CLI's lines.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_studio import PackStudio  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _bump(src: Path, version: str = "1.1.0", settings: str = "{style: tone}") -> None:
    text = (src / "pack.yaml").read_text(encoding="utf-8").replace("version: 1.0.0", f"version: {version}")
    text = text.replace("style: {type: string, enum: [short, long]", "tone: {type: string, enum: [short, long]")
    text = text.replace("defaults: {style: short, max_findings: 20}", "defaults: {tone: short, max_findings: 20}")
    text += f"  - {{from: 1.0.0, to: {version}, note: settings key `style` is now `tone`, settings: {settings}}}\n"
    (src / "pack.yaml").write_text(text, encoding="utf-8")
    (src / "commands" / "review.md").write_text("the new review command\n", encoding="utf-8")
    (src / "studio" / "added.md").write_text("new in 1.1.0\n", encoding="utf-8")


def _tree(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _rec(s) -> dict:
    return json.loads((s.packs / "state.json").read_text(encoding="utf-8"))["installed"]["doc-review"]


def _settings(s) -> dict:
    return json.loads((s.state / "config.json").read_text(encoding="utf-8"))["packs"]["settings"]["doc-review"]


@test
def test_rollback_swaps_back_settings_grants_and_ownership(ctx: Ctx):
    from halo_harness.packs import journal as J
    with PackStudio() as s:
        src = s.source()
        s.install(src, enable=True, grants=["hooks", "bash"])
        s.config({"packs": {"settings": {"doc-review": {"style": "long"}}}})
        root = s.packs / "doc-review"
        (root / "notes.md").write_text("my notes\n", encoding="utf-8")
        first, owned_first = _tree(root), J.owned("doc-review")
        _bump(src)
        code, _out, err = s.cli("update", "doc-review")
        ctx.check(f"updated, got {code} {err}", code == 0 and _settings(s) == {"tone": "long"} and (root / "studio" / "added.md").is_file())
        ctx.check("your file came along into the new folder", (root / "notes.md").read_text(encoding="utf-8") == "my notes\n")
        (root / "notes.md").write_text("my notes, edited after the update\n", encoding="utf-8")
        code, out, err = s.cli("rollback", "doc-review")
        lines = out.splitlines()
        ctx.check(f"exit 0, what came back first, got {code} {err} {lines[:1]}", code == 0 and lines[0] ==
                  "rolled back doc-review 1.1.0 -> 1.0.0: doc-review.previous is doc-review/ again (enabled); "
                  "1.1.0 is gone (halo pack update doc-review brings it back)")
        ctx.check("the grants are kept and said", "grants kept: bash, hooks" in lines and _rec(s)["granted"] == ["bash", "hooks"])
        ctx.check("the renamed setting moved back, said", _settings(s) == {"style": "long"}
                  and "moved packs.settings.doc-review.tone back to style (value 'long')" in lines)
        ctx.check("your file changed since the update stays", "kept your copy of notes.md" in lines
                  and (root / "notes.md").read_text(encoding="utf-8") == "my notes, edited after the update\n")
        now = _tree(root)
        now.pop("notes.md")
        first.pop("notes.md")
        ctx.check("every other file is the old version's, byte for byte", now == first)
        ctx.check("no .previous, no staging folder", sorted(p.name for p in s.packs.iterdir()) == ["doc-review", "journal.jsonl", "state.json"])
        rec = _rec(s)
        ctx.check(f"the record: the old version, no previous, still enabled, got {rec}",
                  rec["version"] == "1.0.0" and "previous" not in rec and rec["enabled"] is True)
        ctx.check("the journal owns the old version's files again", J.owned("doc-review") == owned_first)
        code, _out, err = s.cli("rollback", "doc-review")
        ctx.check(f"a second rollback: one line, got {err!r}", code == 1 and err.strip() ==
                  "halo pack: doc-review has no earlier version to go back to: an update keeps the version it replaces "
                  "as doc-review.previous until the next update")
        status, body, _ = s.call("POST", "pack/doc-review/rollback")
        ctx.check(f"Studio's Rollback answers the same line, got {status} {body}", status == 422
                  and body["error"] == err.strip().removeprefix("halo pack: "))


@test
def test_studio_rollback_and_the_manager_row(ctx: Ctx):
    with PackStudio() as s:
        src = s.source()
        s.install(src, enable=True)
        _bump(src)
        status, body, _ = s.call("POST", "pack/doc-review/update", {})
        ctx.check(f"Studio's Update, got {status}", status == 200 and body["lines"][1].startswith("updated doc-review 1.0.0 -> 1.1.0"))
        _s, man, _h = s.call("GET", "pack/manager")
        row = next(p for p in man["packs"] if p["id"] == "doc-review")
        ctx.check(f"the Manager's row names the version Rollback goes back to, got {row.get('previous')!r}", row["previous"] == "1.0.0")
        status, body, _ = s.call("POST", "pack/doc-review/rollback")
        ctx.check(f"Studio's Rollback, got {status} {body.get('lines', [])[:1]}", status == 200
                  and body["lines"][0].startswith("rolled back doc-review 1.1.0 -> 1.0.0"))
        _s, man, _h = s.call("GET", "pack/manager")
        ctx.check("then nothing to roll back", next(p for p in man["packs"] if p["id"] == "doc-review")["previous"] == "")


@test
def test_a_copy_error_while_staging_leaves_the_old_version(ctx: Ctx):
    from halo_harness.packs import update as U
    with PackStudio() as s:
        src = s.source()
        s.install(src, enable=True)
        root = s.packs / "doc-review"
        before, journal = _tree(root), (s.packs / "journal.jsonl").read_text(encoding="utf-8")
        _bump(src)
        real, calls = U._copy_file, []

        def flaky(a, b):
            calls.append(a)
            if len(calls) == 4:
                raise OSError("disk full (test)")
            return real(a, b)
        U._copy_file = flaky
        try:
            code, _out, err = s.cli("update", "doc-review")
        finally:
            U._copy_file = real
        first = err.splitlines()[0] if err else ""
        ctx.check(f"exit 1, the stop line first, got {first!r}", code == 1 and first ==
                  "halo pack: update of doc-review stopped: disk full (test); 1.0.0 stays as it was (nothing was replaced)")
        ctx.check("the old version is there byte for byte", _tree(root) == before)
        ctx.check("no .previous and no staging folder left", sorted(p.name for p in s.packs.iterdir()) == ["doc-review", "journal.jsonl", "state.json"])
        rows = [json.loads(ln) for ln in (s.packs / "journal.jsonl").read_text(encoding="utf-8").splitlines()[len(journal.splitlines()):]]
        ctx.check(f"the journal owns nothing new (only the start mark), got {rows}", all("path" not in r for r in rows))
        ctx.check("the record is unchanged", _rec(s)["version"] == "1.0.0" and "previous" not in _rec(s))


@test
def test_a_failed_swap_renames_back(ctx: Ctx):
    from halo_harness.packs import update as U
    with PackStudio() as s:
        src = s.source()
        s.install(src, enable=True)
        _bump(src, "1.1.0")
        s.cli("update", "doc-review")
        prev_before, root = _tree(s.packs / "doc-review.previous"), s.packs / "doc-review"
        before = _tree(root)
        _bump(src, "1.2.0")
        real, calls = U._rename, []

        def flaky(a, b):
            calls.append((a, b))
            if len(calls) == 3:  # 1: the old .previous aside, 2: <id> -> .previous, 3: staged -> <id>
                raise OSError("in use (test)")
            return real(a, b)
        U._rename = flaky
        try:
            code, _out, err = s.cli("update", "doc-review")
        finally:
            U._rename = real
        ctx.check(f"exit 1, one stop line, got {err.splitlines()[:1]}", code == 1 and err.splitlines()[0] ==
                  "halo pack: update of doc-review stopped: in use (test); 1.1.0 stays as it was (nothing was replaced)")
        ctx.check("1.1.0 is back in place", _tree(root) == before)
        ctx.check("and the 1.0.0 kept before is still the .previous", _tree(s.packs / "doc-review.previous") == prev_before)
        ctx.check("no staging folder left", not [p for p in s.packs.iterdir() if p.name.startswith(".staging-")])


@test
def test_remove_takes_the_previous_copy_unless_keep_config(ctx: Ctx):
    with PackStudio() as s:
        src = s.source()
        s.install(src, enable=True, grants=["hooks"])
        _bump(src)
        s.cli("update", "doc-review")
        code, out, _err = s.cli("remove", "doc-review", "--keep-config")
        ctx.check(f"--keep-config keeps doc-review.previous with the record, said, got {out}", code == 0
                  and (s.packs / "doc-review.previous").is_dir() and not (s.packs / "doc-review").exists()
                  and "kept doc-review.previous with its record: halo pack rollback doc-review installs that version again" in out)
        ctx.check("a kept .previous is no pack: nothing is discovered", s.cli("list", "--json")[1].count('"id"') == 0)
        code, out, err = s.cli("rollback", "doc-review")
        ctx.check(f"rollback installs that version again, disabled, with the grants, got {code} {err} {out.splitlines()[:1]}",
                  code == 0 and "(installed again, disabled)" in out.splitlines()[0] and _rec(s)["version"] == "1.0.0"
                  and _rec(s)["granted"] == ["hooks"] and "removed" not in _rec(s) and (s.packs / "doc-review" / "pack.yaml").is_file())
        s.cli("update", "doc-review")
        code, out, _err = s.cli("remove", "doc-review")
        ctx.check(f"a plain remove deletes it, said, got {out}", code == 0 and not (s.packs / "doc-review.previous").exists()
                  and "removed doc-review.previous, the version the last update replaced" in out)
        ctx.check("nothing of the pack is left", sorted(p.name for p in s.packs.iterdir()) == ["journal.jsonl", "state.json"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
