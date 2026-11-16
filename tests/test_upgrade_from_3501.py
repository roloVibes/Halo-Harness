"""scripts/upgrade_from_3501.py (the CI job `upgrade from 3.5.0.1 (<os>)`): its pure parts and its --dry-run.

Nothing here installs anything: every test runs with subprocess.run, Popen and call made to raise, so a dry run
that tried to run a command would fail the test instead of touching the machine's Halo.
"""
from __future__ import annotations

import io
import subprocess
import sys
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SHA = "0123456789abcdef0123456789abcdef01234567"


def _module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("upgrade_from_3501", REPO / "scripts" / "upgrade_from_3501.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses look their module up while the class is made
    spec.loader.exec_module(mod)
    return mod


def _refuse(*_a, **_k):
    raise AssertionError("upgrade_from_3501 tried to run a command in a test")


@contextmanager
def _no_processes():
    with mock.patch.object(subprocess, "run", _refuse), mock.patch.object(subprocess, "Popen", _refuse), \
            mock.patch.object(subprocess, "call", _refuse), mock.patch.object(subprocess, "check_output", _refuse):
        yield


def _dry(m, system: str) -> "tuple[int, str]":
    out = io.StringIO()
    with _no_processes(), redirect_stdout(out):
        rc = m.main(["--dry-run", "--system", system, "--sha", SHA, "--work", str(REPO / "no-such-scratch")])
    return rc, out.getvalue()


@test
def test_version_line_is_parsed_and_the_commit_matched(ctx: Ctx):
    m = _module()
    p = m.parse_version_line("some noise\nhalo 3.5.0.1 (6a66b6d, v3.5.0.1)\n")
    ctx.check(f"version, commit, ref read, got {p}", p == {"version": "3.5.0.1", "commit": "6a66b6d", "ref": "v3.5.0.1"})
    p = m.parse_version_line("halo 3.6.0.0 (0123456)")
    ctx.check(f"no ref: None, got {p}", p == {"version": "3.6.0.0", "commit": "0123456", "ref": None})
    ctx.check("a traceback is no version line", m.parse_version_line("Traceback (most recent call last):\n"
                                                                       "ModuleNotFoundError: No module named 'halo_harness'") is None)
    ctx.check("empty text: None", m.parse_version_line("") is None)
    ctx.check("a short commit that starts the sha matches", m.commit_matches("0123456", SHA))
    ctx.check("another commit does not", not m.commit_matches("6a66b6d", SHA))
    ctx.check("fewer than 7 characters never match", not m.commit_matches("0123", SHA))
    ctx.check("no commit never matches", not m.commit_matches(None, SHA))


@test
def test_commands_aim_at_the_commit(ctx: Ctx):
    m = _module()
    ctx.check("halo update is aimed with --channel main --to <sha>",
              m.update_cmd(SHA) == ["halo", "update", "--channel", "main", "--to", SHA])
    rc = m.repair_cmd(SHA)
    ctx.check(f"the repair line pins this commit's lock and installs this commit, got {rc}",
              rc[:4] == ["uv", "tool", "install", "--reinstall"]
              and rc[-2] == f"{m.RAW_URL}/{SHA}/requirements.lock" and rc[-1] == f"git+{m.REPO_URL}@{SHA}")
    w = m.installer_cmd("windows", "i.ps1", SHA, "C:/c", no_clone=True)
    ctx.check(f"the Windows installer: -Ref, -CloneDir, -NoClone, no questions, got {w}",
              w[:2] == ["powershell", "-NoProfile"] and w[w.index("-Ref") + 1] == SHA and "-Yes" in w
              and "-NoModifyPath" in w and w[-1] == "-NoClone" and w[w.index("-CloneDir") + 1] == "C:/c")
    s = m.installer_cmd("linux", "i.sh", m.OLD_TAG, "/c")
    ctx.check(f"the shell installer: --ref, --dir=, no questions, got {s}",
              s == ["bash", "i.sh", "--yes", "--no-modify-path", "--ref", m.OLD_TAG, "--dir=/c"])
    ctx.check("the tool python per system",
              m.tool_python("T", "windows").replace("\\", "/") == "T/halo-harness/Scripts/python.exe"
              and m.tool_python("T", "linux").replace("\\", "/") == "T/halo-harness/bin/python")


@test
def test_plan_per_system_names_each_way_and_what_the_docs_recommend(ctx: Ctx):
    m = _module()
    win = {w.key: w for w in m.plan("windows", SHA, new_script="n.ps1")}
    lin = {w.key: w for w in m.plan("linux", SHA, new_script="n.sh")}
    ctx.check(f"Windows ways, got {list(win)}", list(win) == ["A clone", "A git", "B studio", "C1 repair", "C2 installer", "D /update"])
    ctx.check(f"Linux ways (no B), got {list(lin)}", list(lin) == ["A clone", "A git", "C1 repair", "C2 installer", "D /update"])
    ctx.check("Windows: halo update in a shell informs only (the docs say not to)",
              not win["A clone"].recommended and not win["A git"].recommended and not win["B studio"].recommended)
    ctx.check("Windows: the repair line, the installer and /update are recommended",
              win["C1 repair"].recommended and win["C2 installer"].recommended and win["D /update"].recommended)
    ctx.check("Linux: halo update is recommended", lin["A clone"].recommended and lin["A git"].recommended)
    ctx.check("B runs a second halo", win["B studio"].background == ["halo", "studio", "--no-open"])
    ctx.check("A starts from a clone and from a --no-clone install", (win["A clone"].kind, win["A git"].kind) == ("clone", "git"))
    ctx.check("C1 stops the Studio first and that exit code is not the update's",
              win["C1 repair"].steps[0] == ["halo", "studio", "--stop"] and win["C1 repair"].tolerate == [0])
    ctx.check("D aims the /update hand-off with reinstall_cmd(to=<sha>)",
              win["D /update"].detached and win["D /update"].steps[0][-1] == SHA
              and "D.reinstall_cmd = lambda to=None: _orig(to=sys.argv[1])" in win["D /update"].steps[0][3]
              and "D.run_after_exit()" in win["D /update"].steps[0][3])


@test
def test_table_and_verdict(ctx: Ctx):
    m = _module()
    good = m.Row("C1 repair", True, 0, "halo 3.5.0.0 (0123456, 0123456)", True, True, 0, 0, 12.3)
    half = m.Row("A clone", False, 1, "", False, False, None, None, 40.0, "half install")
    ctx.check("an informing way that broke does not fail the run", m.verdict([good, half]) == 0)
    bad = m.Row("D /update", True, 0, "halo 3.5.0.1 (6a66b6d, v3.5.0.1)", False, True, 0, 0, 30.0)
    ctx.check("a recommended way that stayed on 3.5.0.1 fails the run", m.verdict([good, bad]) == 1)
    broken = m.Row("C2 installer", True, 0, "", True, False)
    ctx.check("a recommended way whose package does not import fails the run", m.verdict([good, broken]) == 1)
    t = m.markdown_table([good, half], "windows", SHA)
    ctx.check("the table has the columns asked for",
              "| way | docs | update exit | version after | at this commit | package importable |" in t)
    ctx.check("a row per way", "| C1 repair | recommended | 0 |" in t and "| A clone | informs | 1 |" in t and "| NO |" in t)


@test
def test_dry_run_prints_each_system_and_runs_nothing(ctx: Ctx):
    m = _module()
    for system in ("linux", "macos", "windows"):
        rc, out = _dry(m, system)
        ctx.check(f"{system}: exit 0", rc == 0)
        ctx.check(f"{system}: 3.5.0.1's installer from the tag", f"git show {m.OLD_TAG}:scripts/install-halo." in out)
        ctx.check(f"{system}: halo update aimed at the commit", f"halo update --channel main --to {SHA}" in out)
        ctx.check(f"{system}: the repair line", f"git+{m.REPO_URL}@{SHA}" in out)
        ctx.check(f"{system}: B only on Windows", ("B studio" in out) == (system == "windows"))
    ctx.check("nothing was created", not (REPO / "no-such-scratch").exists())


@test
def test_a_real_run_refuses_outside_ci(ctx: Ctx):
    m = _module()
    err = io.StringIO()
    with _no_processes(), mock.patch.dict("os.environ", {"GITHUB_ACTIONS": ""}), redirect_stderr(err):
        rc = m.main(["--sha", SHA])
    ctx.check(f"exit 2 and says why, got {rc}", rc == 2 and "--dry-run" in err.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
