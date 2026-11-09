r"""tests.test_permissions_powershell -- Read / Edit deny rules gate the PowerShell tool's readers and writers the way
they gate Bash's (Halo 3.3.14.0 R2, REVIEW #13 PERMS-7; halo_harness/permissions_ps.py, permissions.py
`_decide_powershell`). With `Read(.env)` and `Edit(.env)` denied, in auto mode:

1. readers: `Get-Content .env`, `gc .env`, `cat .env`, `type .env`, `Get-Content -Path .\.env -Raw`,
   `Select-String KEY .env`, `Copy-Item .env out.txt`, `[IO.File]::ReadAllText('.env')`, `cmd /c type .env`, a script
   block, `cd sub; gc ..\.env`, `Get-Content $f` (a word that cannot be checked) are denied, as `cat .env` is in Bash;
2. writers: `Set-Content .env x`, `Add-Content -Path .env -Value x`, `Out-File .env`, `"x" > .env`, `Remove-Item .env`,
   `Move-Item a.txt .env`, `Copy-Item a.txt .env`, `[IO.File]::WriteAllText('.env', 'x')` are denied;
3. what neither rule names is allowed (`Get-Content a.txt`, `Set-Content out.txt .env`, `Copy-Item .env.example b`
   reading a file the rule does not name); a Read ASK rule asks in default mode;
4. on Windows the `\\?\` and `\\localhost\C$\` spellings of .env are denied for Get-Content and Set-Content.
Run: python -m tests.test_permissions_powershell
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


def _engine(cwd: Path, mode: str = "auto", ask: bool = False):
    from halo_harness import permissions as P
    rules = [P.parse_rule(r, source="user", base_dir=cwd, action="ask" if ask else "deny") for r in
             (("Read(.env)",) if ask else ("Read(.env)", "Edit(.env)"))]
    return P.PermissionEngine(mode=mode, cwd=cwd, **({"ask_rules": rules} if ask else {"deny_rules": rules}))


def _proj() -> Path:
    cwd = Path(tempfile.mkdtemp(prefix="ps-deny-")).resolve()
    (cwd / ".env").write_text("FAKE=1\n", encoding="utf-8")
    (cwd / "a.txt").write_text("a\n", encoding="utf-8")
    (cwd / "sub").mkdir()
    return cwd


def _ps(eng, command: str) -> str:
    return eng.decide("PowerShell", {"command": command}, None).action


@test
def test_readers_on_a_read_denied_path_are_denied(ctx: Ctx):
    cwd = _proj()
    eng = _engine(cwd)
    ctx.check("bash's cat is denied (the reference)", eng.decide("Bash", {"command": "cat .env"}, None).action == "deny")
    for cmd in ("Get-Content .env", "gc .env", "cat .env", "type .env", "Get-Content -Path .\\.env -Raw",
                "Get-Content -LiteralPath:.env", "Select-String KEY .env", "Copy-Item .env out.txt",
                "[IO.File]::ReadAllText('.env')", "[System.IO.File]::ReadAllLines(\".env\")", "cmd /c type .env",
                "& { Get-Content .env }", "cd sub; gc ..\\.env", "Get-Content $f", "Write-Output x | gc .env",
                "gc ./.env", "powershell -Command \"Get-Content .env\""):
        d = eng.decide("PowerShell", {"command": cmd}, None)
        ctx.check(f"{cmd!r}: deny, got {d.action} {d.reason!r}", d.action == "deny" and "Read-denied" in d.reason)


@test
def test_writers_on_an_edit_denied_path_are_denied(ctx: Ctx):
    cwd = _proj()
    eng = _engine(cwd)
    for cmd in ("Set-Content .env x", "Add-Content -Path .env -Value x", "Out-File .env", "'x' | Out-File -FilePath .env",
                "Write-Output x > .env", "echo x >> .env", "Remove-Item .env", "rm .env", "Move-Item a.txt .env",
                "Copy-Item a.txt -Destination .env", "[IO.File]::WriteAllText('.env', 'x')", "Clear-Content .env"):
        d = eng.decide("PowerShell", {"command": cmd}, None)
        ctx.check(f"{cmd!r}: deny, got {d.action} {d.reason!r}", d.action == "deny" and "denied" in d.reason)


@test
def test_what_the_rules_do_not_name_is_allowed_and_an_ask_rule_asks(ctx: Ctx):
    cwd = _proj()
    eng = _engine(cwd)
    for cmd in ("Get-Content a.txt", "Set-Content out.txt -Value .env", "Copy-Item a.txt b.txt", "Write-Output 2>&1",
                "Get-ChildItem", "Set-Content -Path out.txt -Value $x"):
        ctx.check(f"{cmd!r}: allowed", _ps(eng, cmd) == "allow")
    ctx.check("no path rule at all: nothing checked", _ps(_engine_none(cwd), "Get-Content .env") == "allow")
    ask = _engine(cwd, mode="default", ask=True)
    ctx.check("a Read ask rule asks", _ps(ask, "Get-Content .env") == "ask")


def _engine_none(cwd: Path):
    from halo_harness import permissions as P
    return P.PermissionEngine(mode="auto", cwd=cwd)


@test
def test_the_windows_spellings_are_denied_for_powershell(ctx: Ctx):
    if os.name != "nt":
        from tests.helpers.runner import SkipTest
        raise SkipTest("Windows paths: runs on Windows")
    cwd = _proj()
    eng = _engine(cwd)
    plain = str(cwd / ".env")
    drive, rest = plain[0], plain[3:]
    for path in ("\\\\?\\" + plain, f"\\\\localhost\\{drive}$\\{rest}"):
        for cmd in (f"Get-Content '{path}'", f"Set-Content '{path}' x"):
            ctx.check(f"{cmd!r}: deny", _ps(eng, cmd) == "deny")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
