"""tests.test_packs_cli -- `halo pack ...` (Halo 3.2.0.0 R1,
halo_harness/packs/cli.py): every verb in text and with `--json`, its
`--help`, the usage and exit codes (0 done, 1 could not, 2 usage), the
`halo pack` branch of the top-level CLI, the completion word, an install
by id through config `packs.sources`, and the packs group of `halo config
where` and `halo doctor --config`.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_usage_help_and_exit_codes(ctx: Ctx):
    from halo_harness.packs.cli import VERBS, cmd_pack
    ctx.check("the verbs", VERBS == ("list", "inspect", "install", "enable", "disable", "update", "remove", "doctor"))
    for argv, code in (([], 2), (["--help"], 0), (["frobnicate"], 2)):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cmd_pack(argv)
        ctx.check(f"halo pack {' '.join(argv)}: exit {code}, got {rc}", rc == code)
        if argv != ["frobnicate"]:
            ctx.check("the usage names every verb", all(f"halo pack {v}" in out.getvalue() for v in VERBS))
    for verb in VERBS:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = cmd_pack([verb, "--help"])
        ctx.check(f"halo pack {verb} --help exits 0", rc == 0 and f"usage: halo pack {verb}" in out.getvalue())
    with PacksHome() as h:
        from halo_harness.cli import main
        so = io.StringIO()
        with contextlib.redirect_stdout(so):
            rc = main(["pack", "list", "--cwd", str(h.repo)])
        ctx.check(f"`halo pack` is a verb of the CLI, got {rc}", rc == 0 and so.getvalue().startswith("No packs here."))
    from halo_harness.completion_cli import SUBCOMMANDS
    ctx.check("completion offers pack", "pack" in SUBCOMMANDS)


@test
def test_every_verb_in_text_and_json(ctx: Ctx):
    with PacksHome() as h:
        code, out, _ = h.cli("list", "--json")
        ctx.check("an empty list as JSON", code == 0 and json.loads(out) == {"packs": []})
        src = h.source()
        code, out, _ = h.cli("install", str(src), "--json")
        data = json.loads(out)
        ctx.check(f"install --json: ok and lines, got {data}", code == 0 and data["ok"] and data["lines"][0].startswith("installed doc-review 1.0.0"))
        code, out, _ = h.cli("list", "--json")
        row = json.loads(out)["packs"][0]
        ctx.check(f"list --json: the row, got {row}", row["id"] == "doc-review" and row["state"] == "disabled"
                  and row["offers"]["bios"] == ["doc-review--reviewer", "doc-review--writer"] and row["source"] == str(src))
        code, out, _ = h.cli("list")
        ctx.check(f"list: one line per pack, got {out!r}", out.count("\n") == 1 and "doc-review" in out and "2 bios" in out)
        code, out, _ = h.cli("enable", "doc-review", "--grant", "hooks", "--json")
        ctx.check("enable --json", code == 0 and json.loads(out)["ok"])
        code, out, _ = h.cli("inspect", "doc-review", "--json")
        d = json.loads(out)
        perms = {p["name"]: p["granted"] for p in d["permissions"]}
        ctx.check(f"inspect --json: permissions and which are granted, got {perms}", perms == {"mcp:lint": False, "hooks": True})
        ctx.check("inspect --json: the settings with their defaults", d["settings"] == {"style": "short", "max_findings": 20})
        ctx.check("inspect --json: no problems", d["problems"] == [] and d["state"] == "enabled")
        code, out, _ = h.cli("inspect", "doc-review")
        ctx.check("inspect: the text", code == 0 and "mcp:lint (MCP server lint): not granted" in out and "lineups: doc-review--review" in out)
        code, out, _ = h.cli("inspect", str(src))
        ctx.check(f"inspect a folder (a source), got {out[:80]!r}", code == 0 and "(a source folder)" in out)
        code, _out, err = h.cli("inspect", "nope")
        ctx.check("inspect an unknown id: exit 1", code == 1 and "neither an installed pack" in err)
        code, out, _ = h.cli("doctor", "--json")
        found = json.loads(out)["problems"]
        ctx.check(f"doctor --json: the ungranted server, exit 1, got {found}",
                  code == 1 and [p["check"] for p in found] == ["not-granted"] and "mcp:lint" in found[0]["text"])
        h.cli("enable", "doc-review", "--grant", "mcp:lint")
        code, out, _ = h.cli("doctor")
        ctx.check(f"doctor clean: exit 0, got {out}", code == 0 and "RESULT: 0 problem(s)" in out)
        code, out, _ = h.cli("update", "doc-review", "--json")
        data = json.loads(out)
        ctx.check(f"update --json from an unchanged source, got {data}", code == 0 and "(0 file(s) changed)" in data["lines"][0]
                  and "no migration notes" in data["lines"])
        code, out, _ = h.cli("disable", "doc-review", "--json")
        ctx.check("disable --json", code == 0 and json.loads(out)["ok"])
        code, out, _ = h.cli("remove", "doc-review", "--json")
        ctx.check("remove --json", code == 0 and json.loads(out)["ok"] and not (h.packs / "doc-review").exists())
        code, out, err = h.cli("remove", "doc-review", "--json")
        ctx.check("remove again: ok false, exit 1", code == 1 and json.loads(out)["ok"] is False)


@test
def test_install_by_id_through_packs_sources(ctx: Ctx):
    with PacksHome() as h:
        src = h.source()
        code, _out, err = h.cli("install", "doc-review")
        ctx.check(f"a bare id with no sources: one line, got {err!r}", code == 1 and "no pack doc-review in config packs.sources" in err)
        h.config({"packs": {"sources": [str(src.parent), str(h.home / "gone")]}})
        code, out, err = h.cli("install", "doc-review")
        ctx.check(f"found in a source folder, got {code} {err}", code == 0 and (h.packs / "doc-review" / "pack.yaml").is_file())
        from halo_harness.packs.state import entry
        ctx.check("the record names the folder it came from", entry("doc-review")["source"] == str(src))
        code, out, _err = h.cli("doctor")
        ctx.check(f"doctor names the source folder that is gone, got {out}", "packs.sources:" in out and "gone is not a folder" in out)


@test
def test_config_where_and_doctor_config_have_the_packs_group(ctx: Ctx):
    from halo_harness.config_where import GROUPS, where_rows
    from halo_harness.doctor_config import config_findings
    ctx.check("a packs group", ("packs", "Packs") in GROUPS)
    with PacksHome() as h:
        ctx.check("a clean home: no pack findings", [f for f in config_findings(h.repo) if f["kind"] == "packs"] == [])
        h.install(h.source(), enable=True)
        rows = [r for r in where_rows(h.repo) if r["kind"] == "packs"]
        ctx.check(f"the repo folder, the home folder, state.json; got {[r['file'] for r in rows]}",
                  [r["file"] for r in rows] == ["./.halo/packs", "~/.halo/packs", "~/.halo/packs/state.json"])
        ctx.check("the home row lists the pack, running", rows[1]["sets"] == ["doc-review"] and "1 running" in rows[1]["note"])
        bios = [r for r in where_rows(h.repo) if r["kind"] == "bios" and r["scope"] == "pack"]
        ctx.check(f"the pack's bio folder is a read-only bios row, got {[(r['sets'], r['note']) for r in bios]}",
                  len(bios) == 1 and bios[0]["sets"] == ["doc-review--reviewer", "doc-review--writer"]
                  and "read-only" in bios[0]["note"])
        found = [f for f in config_findings(h.repo) if f["kind"] == "packs"]
        ctx.check(f"doctor --config lists the ungranted needs, got {[f['text'] for f in found]}",
                  len(found) == 2 and all(f["check"] == "pack-not-granted" and f["severity"] == "warns" for f in found))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
