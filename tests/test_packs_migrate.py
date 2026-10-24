"""tests.test_packs_migrate -- a pack's `migrations`, shown and applied (Halo
3.2.0.0 R7, halo_harness/packs/migrate.py, packs/update.py): the entries
between two versions in order and in "<id> <from> -> <to>: <note>" words;
the manifest's lines for a bad `settings` rename; `halo pack update
--dry-run` prints the notes and the plan first and touches nothing (files,
settings, journal, no `.previous`); a real update prints the notes first,
renames `packs.settings.<id>` keys (dotted ones too; a new key you set
already wins) and journals each move; Studio's Update dry run answers the
same lines.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_studio import PackStudio  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
NOTE = "  - {from: 1.0.0, to: 1.3.0, note: settings key `lint.level` is now `lint.strictness`, settings: {lint.level: lint.strictness, style: tone}}\n"


def _bump(src: Path, version: str = "1.3.0", extra: str = NOTE) -> None:
    text = (src / "pack.yaml").read_text(encoding="utf-8").replace("version: 1.0.0", f"version: {version}")
    text = text.replace("      max_findings: {type: integer, description: The most findings one review lists}\n",
                        "      max_findings: {type: integer, description: The most findings one review lists}\n"
                        "      tone: {type: string}\n      lint: {type: object}\n")
    (src / "pack.yaml").write_text(text + extra, encoding="utf-8")


def _tree(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _settings(s) -> dict:
    return json.loads((s.state / "config.json").read_text(encoding="utf-8")).get("packs", {}).get("settings", {}).get("doc-review", {})


@test
def test_between_and_the_note_lines(ctx: Ctx):
    from halo_harness.packs import migrate as M
    m = {"migrations": [{"from": "1.2.0", "to": "1.3.0", "note": "b"}, {"from": "0.9.0", "to": "1.0.0", "note": "old"},
                        {"from": "1.0.0", "to": "1.2.0", "note": "a", "settings": {"x": "y"}}, {"from": "1.3.0", "to": "2.0.0", "note": "later"}]}
    got = M.between(m, "1.0.0", "1.3.0")
    ctx.check(f"the entries crossed, oldest first, got {[e['note'] for e in got]}", [e["note"] for e in got] == ["a", "b"])
    ctx.check("their lines", M.note_lines("doc-review", got) == ["doc-review 1.0.0 -> 1.2.0: a", "doc-review 1.2.0 -> 1.3.0: b"])
    ctx.check("the renames", M.renames(got) == [("x", "y")])
    ctx.check("a bad rename is a manifest line", M.settings_lines({"a b": "c"}, where="migrations[0].settings")[0].startswith(
        "migrations[0].settings: 'a b': 'c' is not a setting rename"))
    ctx.check("a rename to itself is a line", "renamed to itself" in M.settings_lines({"a": "a"})[0])
    ctx.check("settings must be a mapping", M.settings_lines(["a"])[0].endswith("is a mapping {old key: new key} of packs.settings.<id> names"))
    from halo_harness.packs.manifest import validate_manifest
    lines = validate_manifest({"id": "x", "name": "x", "version": "1.0.0", "halo_api": {"min": "1.0"},
                               "migrations": [{"from": "0.9.0", "to": "1.0.0", "note": "n", "settings": {"ok": 3}}]})
    ctx.check(f"validate_manifest names it, got {lines}", any(ln.startswith("migrations[0].settings: 'ok': 3") for ln in lines))


@test
def test_dry_run_prints_first_and_touches_nothing(ctx: Ctx):
    with PackStudio() as s:
        src = s.source()
        s.install(src, enable=True, grants=["hooks"])
        s.config({"packs": {"settings": {"doc-review": {"lint": {"level": "high"}, "style": "long"}}}})
        _bump(src)
        root = s.packs / "doc-review"
        before, journal = _tree(root), (s.packs / "journal.jsonl").read_bytes()
        code, out, err = s.cli("update", "doc-review", "--dry-run")
        lines = out.splitlines()
        ctx.check(f"exit 0, got {code} {err}", code == 0)
        ctx.check(f"the note first, in the brief's words, got {lines[:1]}",
                  lines[0] == "doc-review 1.0.0 -> 1.3.0: settings key `lint.level` is now `lint.strictness`")
        ctx.check(f"then what it would do, got {lines[1:]}", lines[1].startswith("would update doc-review 1.0.0 -> 1.3.0 (")
                  and "1.0.0 kept as doc-review.previous" in lines[1]
                  and "would rename packs.settings.doc-review.lint.level to lint.strictness (your value 'high')" in lines
                  and "would rename packs.settings.doc-review.style to tone (your value 'long')" in lines
                  and lines[-1] == "dry run: nothing is changed (halo pack update doc-review makes these changes)")
        ctx.check("the pack's files are as they were", _tree(root) == before)
        ctx.check("the journal is as it was", (s.packs / "journal.jsonl").read_bytes() == journal)
        ctx.check("your settings are as they were", _settings(s) == {"lint": {"level": "high"}, "style": "long"})
        ctx.check("no .previous and no staging folder", sorted(p.name for p in s.packs.iterdir()) == ["doc-review", "journal.jsonl", "state.json"])
        status, body, _ = s.call("POST", "pack/doc-review/update", {"dry_run": True})
        ctx.check(f"Studio's Update asks with the same lines, got {status}", status == 200 and body["lines"] == lines)
        ctx.check("and changes nothing either", _tree(root) == before and _settings(s)["style"] == "long")


@test
def test_update_applies_the_renames_and_journals_them(ctx: Ctx):
    with PackStudio() as s:
        src = s.source()
        s.install(src, enable=True)
        s.config({"packs": {"settings": {"doc-review": {"lint": {"level": "high"}, "style": "long", "tone": "short"}}}})
        _bump(src)
        code, out, err = s.cli("update", "doc-review")
        lines = out.splitlines()
        ctx.check(f"exit 0, the note first, got {code} {err} {lines[:2]}", code == 0
                  and lines[0] == "doc-review 1.0.0 -> 1.3.0: settings key `lint.level` is now `lint.strictness`"
                  and lines[1].startswith("updated doc-review 1.0.0 -> 1.3.0 (") and "halo pack rollback doc-review" in lines[1])
        ctx.check("the dotted key moved, its emptied mapping gone",
                  _settings(s) == {"lint": {"strictness": "high"}, "style": "long", "tone": "short"})
        ctx.check("one line per move", "renamed packs.settings.doc-review.lint.level to lint.strictness (your value 'high')" in lines)
        ctx.check("a new key you set already wins: the old one stays, one line",
                  "packs.settings.doc-review.tone is set already, so style stays as it is" in lines)
        rows = [json.loads(ln) for ln in (s.packs / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
        moves = [r for r in rows if r.get("op") == "migrate"]
        start = [r for r in rows if r.get("mark") == "start"]
        ctx.check(f"the move is journaled under the update's op_id, got {moves}",
                  len(moves) == 1 and moves[0]["setting"] == "lint.level" and moves[0]["to"] == "lint.strictness"
                  and moves[0]["value"] == "high" and start and moves[0]["op_id"] == start[0]["op_id"])
        rec = json.loads((s.packs / "state.json").read_text(encoding="utf-8"))["installed"]["doc-review"]
        ctx.check(f"the record has the new version and the one before, got {rec.get('previous')}",
                  rec["version"] == "1.3.0" and rec["previous"]["version"] == "1.0.0" and rec["previous"]["op_id"] == start[0]["op_id"])
        code, out, _err = s.cli("update", "doc-review")
        ctx.check(f"again from the same source: up to date, nothing moves, got {out.splitlines()[:1]}",
                  code == 0 and out.startswith("doc-review 1.3.0 is up to date") and (s.packs / "doc-review.previous").is_dir())


@test
def test_no_notes_and_nothing_to_rename(ctx: Ctx):
    with PackStudio() as s:
        src = s.source()
        s.install(src)
        _bump(src, "1.1.0", "  - {from: 1.0.0, to: 1.1.0, note: renamed, settings: {nothing: here}}\n")
        code, out, _err = s.cli("update", "doc-review", "--dry-run")
        ctx.check(f"a rename of a key you never set says so, got {out}", code == 0
                  and "no setting of yours to rename (nothing not set)" in out)
        _bump(src, "1.2.0", "")
        code, out, _err = s.cli("update", "doc-review")
        ctx.check(f"between 1.0.0 and 1.2.0 the 1.1.0 note still shows, got {out.splitlines()[:1]}",
                  code == 0 and out.splitlines()[0] == "doc-review 1.0.0 -> 1.1.0: renamed")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
