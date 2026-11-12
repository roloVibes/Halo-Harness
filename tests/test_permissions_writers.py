r"""tests.test_permissions_writers -- Halo 3.4.1.2 (ENGINE-4): the Read / Edit deny rules missed common writers and
readers in both shells. With `Read(.env)` and `Edit(.env)` denied, in auto mode:

1. Bash: `tee .env < x`, `cp x .env`, `mv x .env`,
   `rm .env`, `truncate -s0 .env`, `ln .env y`, `ln -s x .env`, `mv .env y`, `dd if=.env of=y`, `dd if=x of=.env`,
   `sudo tee -a .env`, `install x .env`, `cp -t . x` (x named .env) are denied (permissions_bash_io.py);
2. PowerShell: `Format-Hex .env`, `Get-Item .env | Get-Content`, `Write-Output ${C:\..\.env}`,
   `[IO.StreamReader]::new('.env')`, `New-Object IO.StreamReader '.env'`, `'x' | Tee-Object -FilePath .env`,
   `Rename-Item x .env`, `Import-Clixml .env`, `${C:\..\.env} = 'x'`, `[IO.StreamWriter]::new('.env')` are denied;
3. what neither rule names is still allowed (`cp a.txt b.txt`, `mv a.txt b.txt`, `rm b.txt`, `tee out.txt`,
   `Tee-Object -Variable v`, `Rename-Item a.txt b.txt`, `Format-Hex a.txt`, `Get-Item .env`).
Run: python -m tests.test_permissions_writers
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _engine(cwd: Path):
    from halo_harness import permissions as P
    rules = [P.parse_rule(r, source="user", base_dir=cwd, action="deny") for r in ("Read(.env)", "Edit(.env)")]
    return P.PermissionEngine(mode="auto", cwd=cwd, deny_rules=rules)


def _proj() -> Path:
    cwd = Path(tempfile.mkdtemp(prefix="writers-deny-")).resolve()
    (cwd / ".env").write_text("FAKE=1\n", encoding="utf-8")
    (cwd / "a.txt").write_text("a\n", encoding="utf-8")
    (cwd / "x").write_text("x\n", encoding="utf-8")
    (cwd / "sub").mkdir()
    return cwd


@test
def test_engine4_bash_writers_and_readers_are_denied(ctx: Ctx):
    cwd = _proj()
    eng = _engine(cwd)
    for cmd in ("tee .env < x", "echo x | tee -a .env", "sudo tee .env", "cp x .env", "cp -f x .env", "mv x .env",
                "rm .env", "rm -f .env", "unlink .env", "shred -u .env", "truncate -s0 .env", "truncate -s 0 .env",
                "ln .env y", "ln -s x .env", "ln -sf x .env", "mv .env y", "mv .env sub/", "dd if=.env of=y",
                "dd if=x of=.env", "install x .env", "cd sub && cp ../x ../.env", "cp -t . sub/.env",
                "truncate -r .env y", "curl -o .env https://x", "curl -s --output .env https://x", "wget -O .env x",
                "wget --output-document=.env x", "rsync -a x .env"):
        d = eng.decide("Bash", {"command": cmd}, None)
        ctx.check(f"{cmd!r}: deny, got {d.action} {d.reason!r}", d.action == "deny")
    for cmd in ("cp a.txt b.txt", "mv a.txt b.txt", "rm b.txt", "tee out.txt", "ln -s a.txt b", "dd if=a.txt of=b",
                "truncate -s0 a.txt", "cp a.txt sub", "curl -o out.html https://x", "wget -O - https://x",
                "rsync -a a.txt host:.env"):
        d = eng.decide("Bash", {"command": cmd}, None)
        ctx.check(f"{cmd!r}: still allowed, got {d.action} {d.reason!r}", d.action == "allow")


@test
def test_engine4_powershell_writers_and_readers_are_denied(ctx: Ctx):
    cwd = _proj()
    eng = _engine(cwd)
    drive = str(cwd / ".env")
    # `${C:\path}` names a file through a drive letter: a Windows spelling (PowerShell on Linux has no `C:`)
    by_drive = ["Write-Output ${" + drive + "}", "${" + drive + "} = 'x'"] if os.name == "nt" else []
    for cmd in ["Format-Hex .env", "fhx .env", "Get-Item .env | Get-Content", "gi .env | gc",
                "[IO.StreamReader]::new('.env')", "[System.IO.StreamReader]::new(\"" + drive + "\")",
                "New-Object IO.StreamReader '.env'", "'x' | Tee-Object -FilePath .env", "'x' | tee .env",
                "Rename-Item x .env", "ren x .env", "Import-Clixml .env", "[IO.StreamWriter]::new('.env')",
                "Get-ChildItem .env | Select-String KEY", "Export-Clixml -Path .env -InputObject 1"] + by_drive:
        d = eng.decide("PowerShell", {"command": cmd}, None)
        ctx.check(f"{cmd!r}: deny, got {d.action} {d.reason!r}", d.action == "deny")
    for cmd in ("'x' | Tee-Object -Variable v", "Rename-Item a.txt b.txt", "Format-Hex a.txt", "Get-Item .env",
                "[IO.StreamReader]::new('a.txt')", "Write-Output ${" + str(cwd / "a.txt") + "}"):
        d = eng.decide("PowerShell", {"command": cmd}, None)
        ctx.check(f"{cmd!r}: still allowed, got {d.action} {d.reason!r}", d.action == "allow")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
