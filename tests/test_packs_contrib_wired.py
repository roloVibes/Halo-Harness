"""tests.test_packs_contrib_wired -- Halo 3.4.0.0 B2: `contributes.settings` and `contributes.doctor` wired in.

1. A pack's settings rows are rows of the Settings catalog (group "From packs", `packs.settings.<id>.<key>`) only while
   the pack is enabled; `halo config get` says a row's default while it is unset, `halo config set` checks its type.
2. A pack's doctor rows are rows of `halo doctor` ("From packs, <id>: ...") only while it is enabled and granted
   `doctor`; without the grant, one row naming it; a row with a fix carries it.
3. A malformed entry is a manifest problem: `halo pack test` on the folder fails and names the entry.
Run: python -m tests.test_packs_contrib_wired
"""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
KEY = "packs.settings.contrib-rows.level"


def _config(*argv) -> "tuple[int, str, str]":
    from halo_harness.config_cli import cmd_config
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cmd_config(list(argv))
    return rc, out.getvalue(), err.getvalue()


def _pack_rows() -> "list":
    from halo_harness.settings_catalog import rows
    return [r for r in rows() if r.key.startswith("packs.settings.contrib-rows.")]


def _doctor_lines(cwd) -> "list[str]":
    from halo_harness.doctor import _check_entries
    return [line for cid, line in _check_entries(cwd) if cid.startswith("pack:contrib-rows:")]


@test
def test_settings_rows_only_while_enabled_and_config_knows_them(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source("contrib-rows"))
        ctx.check("installed, not enabled: no rows", _pack_rows() == [])
        h.cli("enable", "contrib-rows", "--grant-all")
        rows = _pack_rows()
        ctx.check(f"enabled: two rows under From packs, got {[(r.key, r.group, r.kind) for r in rows]}",
                  [(r.key, r.group, r.kind) for r in rows] == [(KEY, "from_packs", "int"),
                                                                ("packs.settings.contrib-rows.name", "from_packs", "string")]
                  and rows[0].default == 2 and "contrib-rows" in rows[0].title)
        from halo_harness.settings_catalog import groups
        ctx.check("the From packs group counts them", next(g for g in groups() if g["id"] == "from_packs")["count"] == 2)
        rc, out, _ = _config("get", KEY)
        ctx.check(f"get while unset: the pack's default, got {rc} {out!r}", rc == 0 and out.startswith("(unset: 2"))
        rc, _, err = _config("set", KEY, "loud")
        ctx.check(f"set with the wrong type: exit 2 and the line, got {rc} {err!r}", rc == 2 and "is an integer" in err)
        rc, out, _ = _config("set", KEY, "5")
        ctx.check(f"set an integer: written, got {rc} {out!r}", rc == 0 and out.strip() == f"{KEY}=5")
        ctx.check("get reads it back", _config("get", KEY)[1].strip() == "5")
        h.cli("disable", "contrib-rows")
        ctx.check("disabled: the rows are gone", _pack_rows() == [])
        rc, out, _ = _config("get", KEY)
        ctx.check(f"the value stays in config.json, read as any key, got {rc} {out!r}", rc == 0 and out.strip() == "5")


@test
def test_doctor_rows_only_while_enabled_and_granted(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source("contrib-rows"))
        ctx.check("installed, not enabled: no row", _doctor_lines(h.repo) == [])
        h.cli("enable", "contrib-rows")
        lines = _doctor_lines(h.repo)
        ctx.check(f"enabled without the grant: one row naming it, got {lines}", len(lines) == 1
                  and lines[0].startswith("[WARN] From packs, contrib-rows:") and "--grant doctor" in lines[0])
        h.cli("grant", "contrib-rows", "doctor")
        lines = _doctor_lines(h.repo)
        ctx.check(f"granted: its two rows, got {lines}", lines == [
            "[OK] From packs, contrib-rows: level 2",
            "[WARN] From packs, contrib-rows: no name set -> fix: halo config set packs.settings.contrib-rows.name x"])
        from halo_harness.doctor import run_checks
        text, _ok = run_checks(h.repo)
        ctx.check("halo doctor shows them", "[OK] From packs, contrib-rows: level 2" in text)
        h.cli("disable", "contrib-rows")
        ctx.check("disabled: gone", _doctor_lines(h.repo) == [])


@test
def test_a_malformed_entry_fails_the_pack_test(ctx: Ctx):
    from halo_harness.packs.cli_test import cmd as cmd_test
    with PacksHome() as h:
        src = h.source("contrib-rows", folder="contrib-rows")
        y = src / "pack.yaml"
        y.write_text(y.read_text(encoding="utf-8").replace("type: integer, default: 2", "type: list, default: 2"),
                     encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = cmd_test([str(src)])
        ctx.check(f"halo pack test fails naming the entry, got {rc} {out.getvalue()[-400:]!r}", rc != 0
                  and "contributes.settings[0].type: 'list' is not one of" in out.getvalue())
        shutil.rmtree(src, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="pack contributions wired tests"))
