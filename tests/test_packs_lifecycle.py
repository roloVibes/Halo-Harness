"""tests.test_packs_lifecycle -- install, enable, disable, update, remove
(Halo 3.2.0.0 R1, halo_harness/packs/install.py, grants.py, remove.py,
journal.py): an install from a fixture folder copies every file through the
journal and records the pack disabled; enable with and without grants; a
grant the pack does not request; disable clears the grants; update replaces
the pack's own files, keeps one you changed and prints the migration note;
remove deletes only the pack's own files and keeps a user bio, a lineup, a
memory folder and a setting, each listed; --keep-config keeps the grants for
the next install; a failed install rolls every file back; offline mode
answers a url with the one offline line and runs no git; a folder already
there is never overwritten; a project pack's lineup loses its permission
mode and allow rules.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _state(h) -> dict:
    return json.loads((h.packs / "state.json").read_text(encoding="utf-8"))["installed"]


def _journal(h) -> list:
    return [json.loads(ln) for ln in (h.packs / "journal.jsonl").read_text(encoding="utf-8").splitlines()]


@test
def test_install_copies_through_the_journal_and_records_it_disabled(ctx: Ctx):
    with PacksHome() as h:
        src = h.source()
        code, out, err = h.cli("install", str(src))
        ctx.check(f"install exits 0, got {code} {err}", code == 0)
        root = h.packs / "doc-review"
        ctx.check("the pack's files are in ~/.halo/packs/doc-review/", (root / "pack.yaml").is_file()
                  and (root / "skills" / "check-links" / "SKILL.md").is_file() and (root / ".mcp.json").is_file())
        rec = _state(h)["doc-review"]
        ctx.check(f"state.json: disabled, no grants, its source and folder, got {rec}",
                  rec["enabled"] is False and rec["granted"] == [] and rec["source"] == str(src)
                  and Path(rec["root"]) == root and rec["version"] == "1.0.0" and rec["scope"] == "user")
        rows = _journal(h)
        files = sorted(p for p in root.rglob("*") if p.is_file())
        ctx.check(f"one journal row per file, existed false, got {len(rows)} for {len(files)}",
                  len(rows) == len(files) and all(r["op"] == "install" and r["existed"] is False and r["before"] is None
                                                  and r["after"] for r in rows))
        ctx.check("the output says how to enable it", "halo pack enable doc-review --grant mcp:lint --grant hooks" in out)
        if os.name != "nt":
            ctx.check("state.json is private (0600)", (h.packs / "state.json").stat().st_mode & 0o777 == 0o600)
        code, _out, err = h.cli("install", str(src))
        ctx.check(f"a second install says update, got {err!r}", code == 1 and "already installed" in err and "halo pack update" in err)


@test
def test_enable_with_and_without_grants_then_disable(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source())
        code, out, _err = h.cli("enable", "doc-review")
        rec = _state(h)["doc-review"]
        ctx.check("enabled with no grants", code == 0 and rec["enabled"] is True and rec["granted"] == [])
        ctx.check(f"it lists what does not run until granted, got {out}",
                  "not running until granted: MCP server lint" in out and "--grant hooks" in out)
        code, _out, err = h.cli("enable", "doc-review", "--grant", "network")
        ctx.check(f"a grant it does not request: exit 1, one line, got {err!r}",
                  code == 1 and "does not request network" in err and _state(h)["doc-review"]["granted"] == [])
        h.cli("enable", "doc-review", "--grant", "hooks")
        h.cli("enable", "doc-review", "--grant", "mcp:lint")
        ctx.check("grants add up", _state(h)["doc-review"]["granted"] == ["hooks", "mcp:lint"])
        from halo_harness.ext import is_granted
        ctx.check("ext.is_granted reads them", is_granted("doc-review", "hooks") and not is_granted("doc-review", "bash"))
        code, out, _err = h.cli("disable", "doc-review")
        rec = _state(h)["doc-review"]
        ctx.check(f"disable: off, grants cleared and named, files kept, got {out}",
                  code == 0 and rec["enabled"] is False and rec["granted"] == [] and "grants cleared: hooks, mcp:lint" in out
                  and (h.packs / "doc-review" / "pack.yaml").is_file())
        ctx.check("a disabled pack holds no grant", not is_granted("doc-review", "hooks"))
        from halo_harness.fleet import capabilities as C
        C.save({"hash": "h", "at": 123.0}, h.state)
        code, _out, _err = h.cli("enable", "doc-review", "--grant-all")
        ctx.check("--grant-all grants every request (3.2.0.0 R2: bash, the reviewer bio's need)",
                  _state(h)["doc-review"]["granted"] == ["bash", "hooks", "mcp:lint"])
        ctx.check("enable makes Fleet's capabilities catalog gather afresh", C.load(h.state)["at"] == 0)


@test
def test_update_replaces_the_packs_files_keeps_yours_and_prints_the_migration(ctx: Ctx):
    with PacksHome() as h:
        src = h.source()
        h.install(src, enable=True, grants=["hooks"])
        root = h.packs / "doc-review"
        (root / "commands" / "review.md").write_text("my own review command\n", encoding="utf-8")
        (root / "agents" / "mine.yaml").write_text("description: mine\n", encoding="utf-8")
        text = (src / "pack.yaml").read_text(encoding="utf-8").replace("version: 1.0.0", "version: 1.1.0")
        text += "  - {from: 1.0.0, to: 1.1.0, note: the writer bio no longer extends the reviewer}\n"
        (src / "pack.yaml").write_text(text, encoding="utf-8")
        (src / "agents" / "writer.yaml").write_text("name: writer\ndescription: a new writer\n", encoding="utf-8")
        (src / "commands" / "review.md").write_text("the pack's new command\n", encoding="utf-8")
        (src / "skills" / "check-links" / "SKILL.md").unlink()
        code, out, err = h.cli("update", "doc-review")
        ctx.check(f"update exits 0, got {code} {err}", code == 0)
        ctx.check(f"the migration note between the versions is printed, got {out}",
                  "migration 1.0.0 -> 1.1.0: the writer bio no longer extends the reviewer" in out
                  and "0.9.0 -> 1.0.0" not in out)
        ctx.check("an unchanged file of the pack is replaced", "a new writer" in (root / "agents" / "writer.yaml").read_text(encoding="utf-8"))
        ctx.check("a file you changed stays, and is listed", (root / "commands" / "review.md").read_text(encoding="utf-8")
                  == "my own review command\n" and "kept your copy of commands/review.md" in out)
        ctx.check("a file the new version drops is removed", not (root / "skills" / "check-links").exists())
        ctx.check("a file you added stays", (root / "agents" / "mine.yaml").is_file())
        rec = _state(h)["doc-review"]
        ctx.check("the record has the new version, still enabled with its grants",
                  rec["version"] == "1.1.0" and rec["enabled"] and rec["granted"] == ["hooks"])


@test
def test_remove_keeps_your_work_and_lists_it(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source(), enable=True, grants=["hooks", "mcp:lint"])
        root = h.packs / "doc-review"
        h.write(".halo/agents/doc-review--writer.yaml", "description: my copy of the pack's writer\n")
        h.write(".halo/teams/mine.yaml", "agents:\n  - {agent: doc-review--reviewer, role: main}\n")
        (h.state / "teams" / "doc-review--review" / "memory").mkdir(parents=True)
        h.config({"packs": {"settings": {"doc-review": {"style": "long"}}}})
        (root / "notes.md").write_text("my notes\n", encoding="utf-8")
        code, out, err = h.cli("remove", "doc-review")
        ctx.check(f"remove exits 0, got {code} {err}", code == 0)
        ctx.check("the pack's own files are gone", not (root / "pack.yaml").exists() and not (root / "skills").exists())
        ctx.check("a file you added in its folder stays, listed", (root / "notes.md").is_file() and "kept notes.md" in out)
        ctx.check("your bio stays, listed", (h.state / "agents" / "doc-review--writer.yaml").is_file()
                  and "your bio doc-review--writer stays" in out)
        ctx.check("your lineup naming its bio stays, listed", "your lineup mine names doc-review--reviewer" in out)
        ctx.check("the memory folder stays, listed", (h.state / "teams" / "doc-review--review" / "memory").is_dir()
                  and "doc-review--review stays" in out)
        settings = json.loads((h.state / "config.json").read_text(encoding="utf-8"))
        ctx.check("your setting stays, listed", settings["packs"]["settings"]["doc-review"] == {"style": "long"}
                  and "your settings packs.settings.doc-review stay" in out)
        ctx.check("the record is gone", "doc-review" not in _state(h))


@test
def test_keep_config_keeps_the_grants_for_the_next_install(ctx: Ctx):
    with PacksHome() as h:
        src = h.source()
        h.install(src, enable=True, grants=["hooks"])
        code, out, _err = h.cli("remove", "doc-review", "--keep-config")
        rec = _state(h)["doc-review"]
        ctx.check(f"kept, disabled, removed marked, grants kept, got {rec}",
                  code == 0 and rec["enabled"] is False and rec["removed"] and rec["granted"] == ["hooks"]
                  and "kept its record (grants: hooks)" in out)
        ctx.check("the folder is gone", not (h.packs / "doc-review").exists())
        code, out, _err = h.cli("install", str(src))
        rec = _state(h)["doc-review"]
        ctx.check(f"a reinstall starts with the kept grants, disabled, got {rec}",
                  code == 0 and rec["granted"] == ["hooks"] and rec["enabled"] is False and "removed" not in rec
                  and "grants kept from before" in out)


@test
def test_a_failed_install_rolls_every_file_back(ctx: Ctx):
    from halo_harness.packs import journal as J
    with PacksHome() as h:
        real, calls = J._write_bytes, []

        def flaky(path, data, mode=None):
            calls.append(path)
            if len(calls) == 5:
                raise OSError("disk full (test)")
            return real(path, data, mode)
        J._write_bytes = flaky
        try:
            code, _out, err = h.cli("install", str(h.source()))
        finally:
            J._write_bytes = real
        ctx.check(f"exit 1 and the reason, got {err!r}", code == 1 and "disk full (test)" in err and "removed again" in err)
        ctx.check("no file of the pack is left", not (h.packs / "doc-review").exists())
        rows = _journal(h)
        ctx.check(f"four writes, four rollback rows, got {[r['op'] for r in rows]}",
                  [r["op"] for r in rows] == ["install"] * 4 + ["rollback"] * 4)
        ctx.check("no state record", not (h.packs / "state.json").exists() or "doc-review" not in _state(h))
        ctx.check("no backup folder is left", not (h.packs / ".backup").exists())


@test
def test_offline_mode_answers_a_url_with_the_one_line(ctx: Ctx):
    import subprocess
    with PacksHome() as h:
        os.environ["HALO_OFFLINE"] = "1"
        real, ran = subprocess.run, []
        subprocess.run = lambda *a, **k: ran.append(a) or real(*a, **k)
        try:
            code, _out, err = h.cli("install", "https://example.invalid/packs/doc-review.git")
        finally:
            subprocess.run = real
            os.environ.pop("HALO_OFFLINE", None)
        ctx.check(f"exit 1, the offline line, got {err!r}",
                  code == 1 and err.strip() == "halo pack: offline mode: not connecting to example.invalid")
        ctx.check("git never ran", ran == [])


@test
def test_a_folder_already_there_is_left_alone(ctx: Ctx):
    with PacksHome() as h:
        mine = h.packs / "doc-review"
        mine.mkdir(parents=True)
        (mine / "README.md").write_text("mine\n", encoding="utf-8")
        code, _out, err = h.cli("install", str(h.source()))
        ctx.check(f"exit 1, the folder named, got {err!r}", code == 1 and "Halo did not put it there" in err)
        ctx.check("nothing written into it", sorted(p.name for p in mine.iterdir()) == ["README.md"])


@test
def test_a_project_pack_is_the_untrusted_layer(ctx: Ctx):
    from halo_harness import teams_yaml as T
    with PacksHome() as h:
        h.install(h.source(), project=True, enable=True)
        ctx.check("it lands in the repo's .halo/packs/", (h.repo / ".halo" / "packs" / "doc-review" / "pack.yaml").is_file())
        lineup = T.resolve_team_template("doc-review--review", cwd=h.repo, state_dir=h.state)
        perms = lineup.get("permissions") or {}
        ctx.check(f"its lineup lost mode and allow rules, kept deny, got {perms}",
                  "mode" not in perms and "allow" not in (perms.get("rules") or {}) and perms["rules"]["deny"] == ["Bash(git push*)"])
        ctx.check("the source label is still the pack's", lineup["_source"] == "pack:doc-review" and lineup["_pack_scope"] == "project")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
