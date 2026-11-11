"""tests.test_whatsnew -- what a version changed, without the repo (Halo 3.3.16.2, "from a session's own review":
a `uv tool install` carries no CHANGELOG.md):

1. the package ships halo_harness/data/changelog.md, whose newest entry is CHANGELOG.md's newest dated one (a
   release refreshes it: scripts/release.py's set_changelog_date writes it), at most twelve, all dated;
2. `halo whatsnew`: the installed version's summary and each `###` heading with its first line; `<version>`,
   `--full`, `--since`, `--summary`; a version not shipped exits 1 and says which are;
3. `/whatsnew` is a slash command with the same text;
4. after `halo update` installs a newer version, its last lines are the new summary and "halo whatsnew for the
   rest" (nothing extra when the version did not move; a failed install exits 1).
No model call, no network. Run: python -m tests.test_whatsnew
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
SAMPLE = """# Changelog

## [9.1.0] - unreleased

**Not out yet.** Nothing here ships.

## [9.0.1] - 2026-02-02

**The small fix.** One thing was wrong. Now it is right. A third sentence.

### Fixed

- **The thing** now works on every box,
  even the slow one.

### Docs

- One page.

## [9.0.0] - 2026-01-01

**The big one.** Everything changed.
"""


@test
def test_the_packaged_copy_is_the_newest_dated_entries(ctx: Ctx):
    from halo_harness import whatsnew as W
    shipped = W.load()
    dated = [e for e in W.entries((REPO / "CHANGELOG.md").read_text(encoding="utf-8")) if e.dated]
    ctx.check(f"it ships, got {len(shipped)} entries", 0 < len(shipped) <= W.KEEP and all(e.dated for e in shipped))
    ctx.check(f"its newest entry is CHANGELOG.md's newest dated one, got {shipped[0].version if shipped else None} vs "
              f"{dated[0].version}", shipped and shipped[0].version == dated[0].version
              and shipped[0].body.strip() == dated[0].body.strip())
    text = W.packaged(SAMPLE)
    ctx.check("an unreleased entry never ships", "9.1.0" not in text and "## [9.0.1] - 2026-02-02" in text)


@test
def test_the_command_says_what_changed(ctx: Ctx):
    from halo_harness import whatsnew as W
    from halo_harness.whatsnew_cli import MORE, text_for
    rows = W.entries(W.packaged(SAMPLE))
    code, text = text_for(rows=rows, installed="9.0.1")
    ctx.check(f"the installed version: two sentences, the headings and their first line, got {text!r}",
              code == 0 and "The small fix. One thing was wrong." in text and "A third" not in text
              and "Fixed:\n  The thing now works on every box," in text and "Docs:\n  One page." in text
              and text.rstrip().endswith(f"{MORE} (--full)"))
    code, text = text_for("9.0.1", full=True, rows=rows)
    ctx.check("--full: the whole entry", code == 0 and "even the slow one." in text)
    code, text = text_for(since="9.0.0", rows=rows)
    ctx.check(f"--since: every entry after it, got {text[:40]!r}", code == 0 and "9.0.1" in text and "The big one" not in text)
    code, text = text_for(only_summary=True, rows=rows, installed="9.0.0")
    ctx.check(f"--summary, got {text!r}", code == 0 and text == "The big one. Everything changed.")
    code, text = text_for("8.0.0", rows=rows)
    ctx.check(f"a version not shipped: exit 1 and which are, got {text!r}", code == 1 and "9.0.1, 9.0.0" in text)
    code, text = text_for(rows=rows, installed="9.1.0")
    ctx.check("an unreleased install: the newest shipped entry, said so", code == 0 and "no dated entry for 9.1.0" in text)
    code, text = text_for(rows=[])
    ctx.check("no data file: one line saying so", code == 1 and "no changelog ships with this install" in text)
    from halo_harness.whatsnew_cli import cmd_whatsnew
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = cmd_whatsnew(["--summary"])
    ctx.check(f"halo whatsnew --summary on the real data, got {rc} {out.getvalue()[:80]!r}", rc == 0 and out.getvalue().strip())


@test
def test_the_slash_command(ctx: Ctx):
    from halo_harness.commands.registry import Registry
    reg = Registry.discover(Path(os.environ.get("BRIDGE_TEST_HOME") or tempfile.mkdtemp()))
    cmd = reg.resolve("whatsnew")
    ctx.check("/whatsnew is registered", cmd is not None)
    from halo_harness.whatsnew_cli import slash_text
    ctx.check("its text is the command's", slash_text("--summary") and "halo whatsnew" in slash_text("--bogus"))


@test
def test_after_update_the_last_lines_are_the_new_summary(ctx: Ctx):
    from halo_harness.whatsnew_cli import after_update
    calls = []

    def run_fn(cmd, **kw):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="The small fix. One thing was wrong.\n")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = after_update(0, {"version": "9.0.0"}, "halo 9.0.1 (abc1234, master)", run_fn=run_fn)
    lines = out.getvalue().strip().splitlines()
    ctx.check(f"the new install's summary, then where the rest is, got {lines}", rc == 0 and calls == [
        ["halo", "whatsnew", "--summary"]] and lines == ["halo update: what is new -- The small fix. One thing was wrong.",
                                                          "halo update: halo whatsnew for the rest"])
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = after_update(0, {"version": "9.0.1"}, "halo 9.0.1 (def5678, master)", run_fn=run_fn)
    ctx.check("the same version: nothing more", rc == 0 and out.getvalue() == "")
    ctx.check("a failed install exits 1", after_update(2, {"version": "9.0.0"}, "", run_fn=run_fn) == 1)


@test
def test_a_release_refreshes_the_packaged_copy(ctx: Ctx):
    spec = importlib.util.spec_from_file_location("halo_release_for_whatsnew", REPO / "scripts" / "release.py")
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    repo = Path(tempfile.mkdtemp(prefix="whatsnew-release-", dir=os.environ.get("BRIDGE_TEST_HOME") or None))
    (repo / "CHANGELOG.md").write_text(SAMPLE, encoding="utf-8")
    release.set_changelog_date("9.1.0", "2026-03-03", repo)
    data = (repo / "halo_harness" / "data" / "changelog.md").read_text(encoding="utf-8")
    ctx.check(f"dating the release writes the data file, its newest entry the new one, got {data[:160]!r}",
              "## [9.1.0] - 2026-03-03" in data and data.index("9.1.0") < data.index("9.0.1"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
