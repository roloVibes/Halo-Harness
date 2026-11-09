r"""tests.test_permissions_win_paths -- Halo 3.3.13.1 (plans/REVIEW-2026-11.md #2, PERMS-2): with `Read(.env)` and
`Edit(.env)` denied, the long-path (`\\?\C:\<proj>\.env`, `\\?\UNC\localhost\C$\...`) and admin-share
(`\\localhost\C$\<proj>\.env`) spellings of the file are denied for Read, Edit, Write and Grep; any other
`\\`-rooted path for a path tool is asked while such a rule exists (halo_harness/permissions_paths.py).
The pure-function test runs everywhere; the engine test runs on Windows only (the spellings are Windows paths).
Run: python -m tests.test_permissions_win_paths
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_plain_drive_takes_the_prefixes_off(ctx: Ctx):
    import socket
    from halo_harness.permissions_paths import plain_drive
    me = socket.gethostname()
    cases = {"//?/C:/proj/.env": "C:/proj/.env", "//./c:/proj/.env": "c:/proj/.env",
             "//?/UNC/localhost/C$/proj/.env": "C:/proj/.env", "//localhost/C$/proj/.env": "C:/proj/.env",
             "//127.0.0.1/d$/x": "D:/x", f"//{me}/C$/proj/.env": "C:/proj/.env", "//LOCALHOST/C$": "C:/",
             "//192.0.2.40/C$/proj/.env": "//192.0.2.40/C$/proj/.env", "//localhost/share/x": "//localhost/share/x",
             "C:/proj/.env": "C:/proj/.env"}
    got = {k: plain_drive(k, True) for k in cases}
    ctx.check(f"each spelling to its drive path, got {got}", got == cases)
    ctx.check("off Windows nothing changes", plain_drive("//localhost/C$/x", False) == "//localhost/C$/x")


@test
def test_an_unmapped_network_path_is_asked_while_a_path_rule_exists(ctx: Ctx):
    from halo_harness import permissions as P
    from halo_harness.permissions_paths import unc_ask
    cwd = Path(tempfile.mkdtemp(prefix="winpath-pure-"))
    deny = [P.parse_rule("Read(.env)", source="user", base_dir=cwd, action="deny")]
    eng = SimpleNamespace(deny_rules=deny, ask_rules=[])
    hit = unc_ask(eng, "Read", {"file_path": r"\\192.0.2.40\share\proj\.env"}, None, windows=True)
    ctx.check(f"a network path with a Read deny rule: asked, got {hit}", hit is not None and "network path" in hit.raw)
    ctx.check("a drive path: no ask", unc_ask(eng, "Read", {"file_path": r"C:\proj\x"}, None, windows=True) is None)
    ctx.check("no path rule: no ask", unc_ask(SimpleNamespace(deny_rules=[], ask_rules=[]), "Read",
                                              {"file_path": r"\\192.0.2.40\share\x"}, None, windows=True) is None)
    ctx.check("not a path tool: no ask", unc_ask(eng, "Bash", {"command": "x"}, None, windows=True) is None)


def _engine(cwd: Path, mode: str = "auto"):
    from halo_harness import permissions as P
    return P.PermissionEngine(mode=mode, cwd=cwd, deny_rules=[
        P.parse_rule("Read(.env)", source="user", base_dir=cwd, action="deny"),
        P.parse_rule("Edit(.env)", source="user", base_dir=cwd, action="deny")])


@test
def test_the_windows_spellings_are_denied(ctx: Ctx):
    if os.name != "nt":
        from tests.helpers.runner import SkipTest
        raise SkipTest("Windows paths: runs on Windows")
    from halo_harness.tools.edit import EditTool
    from halo_harness.tools.grep_tool import GrepTool
    from halo_harness.tools.read import ReadTool
    from halo_harness.tools.write import WriteTool
    cwd = Path(tempfile.mkdtemp(prefix="winpath-")).resolve()
    (cwd / ".env").write_text("FAKE=1\n", encoding="utf-8")
    plain = str(cwd / ".env")
    drive, rest = plain[0], plain[3:]
    spellings = {"extended": "\\\\?\\" + plain, "unc-admin": f"\\\\localhost\\{drive}$\\{rest}",
                 "unc-extended": f"\\\\?\\UNC\\localhost\\{drive}$\\{rest}"}
    eng = _engine(cwd)
    tools = {"Read": ReadTool(), "Edit": EditTool(), "Write": WriteTool()}
    for label, path in spellings.items():
        for name, tool in tools.items():
            d = eng.decide(name, {"file_path": path, "content": "x", "old_string": "a", "new_string": "b"}, tool=tool)
            ctx.check(f"{label} {name}: deny, got {d.action} ({d.reason})", d.action == "deny")
        g = eng.decide("Grep", {"pattern": "FAKE", "path": path}, tool=GrepTool())
        ctx.check(f"{label} Grep: deny, got {g.action}", g.action == "deny")
    d = eng.decide("Read", {"file_path": r"\\192.0.2.40\share\proj\.env"}, tool=tools["Read"])
    ctx.check(f"another machine's share: asked, got {d.action} ({d.reason})", d.action == "ask")
    ctx.check("a plain file next to it is still allowed",
              eng.decide("Read", {"file_path": str(cwd / "notes.txt")}, tool=tools["Read"]).action == "allow")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
