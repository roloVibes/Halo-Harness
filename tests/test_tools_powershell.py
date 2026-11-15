"""tests.test_tools_powershell -- the PowerShell tool (H2 scope A):
win32-only, both at the registry level (never registered on POSIX) and at
the tool level (skips with a clear reason on POSIX rather than failing).
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all
from halo_harness.tools.base import ToolContext

test, TESTS = new_registry()


@test
def test_powershell_only_registered_in_default_tools_on_win32(ctx: Ctx):
    from halo_harness.tools.registry import ToolRegistry
    names = ToolRegistry().names()
    if sys.platform == "win32":
        ctx.check("PowerShell present in the default registry on win32", "PowerShell" in names)
    else:
        ctx.check("PowerShell absent from the default registry off win32", "PowerShell" not in names)


@test
def test_powershell_runs_a_command(ctx: Ctx):
    if sys.platform != "win32":
        raise SkipTest("PowerShell tool is win32-only")
    from halo_harness.tools.powershell import PowerShellTool
    d = Path(tempfile.mkdtemp(prefix="ps-run-"))
    result = PowerShellTool().run({"command": "Write-Output hello-from-powershell"}, ToolContext(cwd=d))
    ctx.check("no error", result.is_error is False)
    ctx.check(f"output captured, got {result.content!r}", "hello-from-powershell" in result.content)


@test
def test_powershell_nonzero_exit_reports_marker(ctx: Ctx):
    if sys.platform != "win32":
        raise SkipTest("PowerShell tool is win32-only")
    from halo_harness.tools.powershell import PowerShellTool
    d = Path(tempfile.mkdtemp(prefix="ps-exit-"))
    result = PowerShellTool().run({"command": "exit 3"}, ToolContext(cwd=d))
    ctx.check(f"[exit code 3] marker present, got {result.content!r}", "[exit code 3]" in result.content)


TEXT = "Jörg Ünal 日本 — größe"


@test
def test_fx_powershell_hands_back_non_ascii_text_unchanged(ctx: Ctx):
    """3.6.0.0 fx windows-shell: Windows PowerShell 5.1 wrote its output in the console's OEM code page while Halo read
    it as UTF-8, so every umlaut came back as U+FFFD and CJK as '?' (in paths, file names and file contents)."""
    if sys.platform != "win32":
        raise SkipTest("PowerShell tool is win32-only")
    from halo_harness.tools.powershell import PowerShellTool
    d = Path(tempfile.mkdtemp(prefix="ps-utf8-")) / TEXT
    d.mkdir()
    (d / "f.txt").write_text(f"the text: {TEXT}\n", encoding="utf-8")
    cmd = f"(Get-Location).Path; Write-Output '{TEXT}'; Get-Content -Encoding UTF8 'f.txt'"
    result = PowerShellTool().run({"command": cmd}, ToolContext(cwd=d))
    lines = [line.strip() for line in result.content.splitlines()]
    ctx.check(f"no error, got {result.content!r}", result.is_error is False)
    ctx.check(f"the folder's path as it is, got {lines[:1]!r}", str(d) in lines)
    ctx.check(f"the written text as it is, got {lines[1:2]!r}", TEXT in lines)
    ctx.check(f"the file's text as it is, got {lines[2:3]!r}", f"the text: {TEXT}" in lines)


@test
def test_fx_powershell_hook_hands_back_non_ascii_text_unchanged(ctx: Ctx):
    """The same for a `shell: "powershell"` command hook (hooks.run_command_hook reads its output as UTF-8)."""
    if sys.platform != "win32":
        raise SkipTest("PowerShell is win32-only here")
    import os
    from halo_harness.hooks import HookDef, run_command_hook
    hook = HookDef(type="command", command=f"Write-Output '{TEXT}'", shell="powershell")
    d = Path(tempfile.mkdtemp(prefix="ps-hook-utf8-"))
    res = run_command_hook(hook, {"tool_name": "Read"}, cwd=d, env=dict(os.environ))
    ctx.check(f"exit 0 and the text as it is, got {res.exit_code} {res.stdout!r} {res.stderr[:200]!r}",
              res.exit_code == 0 and res.stdout.strip() == TEXT)


@test
def test_fx_powershell_argv_sets_utf8_output_first(ctx: Ctx):
    """Runs everywhere: the argv the tool and the hooks start sets PowerShell's output encoding to UTF-8 (no BOM)
    before the person's command, which comes last and unchanged."""
    from halo_harness.tools.powershell import powershell_argv
    argv = powershell_argv("Get-Date")
    ctx.check(f"powershell.exe -NoProfile -NonInteractive -Command, got {argv[:4]}",
              argv[:4] == ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command"])
    ctx.check(f"UTF-8 first, the command last, got {argv[4]!r}",
              argv[4].startswith("try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) }")
              and argv[4].endswith("; Get-Date"))


@test
def test_powershell_missing_command_is_error(ctx: Ctx):
    if sys.platform != "win32":
        raise SkipTest("PowerShell tool is win32-only")
    from halo_harness.tools.powershell import PowerShellTool
    result = PowerShellTool().run({}, ToolContext(cwd=Path(".")))
    ctx.check("missing command is an error", result.is_error is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
