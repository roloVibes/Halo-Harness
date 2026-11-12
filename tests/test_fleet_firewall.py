"""tests.test_fleet_firewall -- Halo 3.4.0.1 "Found live" (defect 12): Halo says when Windows Firewall keeps other
machines off a port it listens on, and never changes a rule (peers/firewall.py reads `netsh advfirewall`).

The live check: a hub on Windows printed its URL; a member's join timed out after 10 s ("cannot reach the hub ...:
timed out"); Windows had made two inbound Block rules `python.exe` (TCP and UDP) for Halo's python when it listened.
Every netsh answer here is a fixture (the RUN seam); nothing reads this machine's rules.
Run: python -m tests.test_fleet_firewall
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.helpers import fleet_pack as _fleet_pack  # noqa: E402  (the fleet pack on, its modules by their old names)
_fleet_pack.on()

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
PY = r"C:\users\u\appdata\roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe"
ON = "Private Profile Settings:\n----------------------------------------------------------------------\nState                                 ON\nOk.\n"


def _rule(name: str, action: str, program: str = PY, protocol: str = "TCP", port: str = "Any", enabled: str = "Yes") -> str:
    return (f"Rule Name:                            {name}\n----------------------------------------------------------------------\n"
            f"Enabled:                              {enabled}\nDirection:                            In\n"
            f"Profiles:                             Private\nProtocol:                             {protocol}\n"
            f"LocalPort:                            {port}\nProgram:                              {program}\n"
            f"Action:                               {action}\n\n")


def _runner(rules: str, state: str = ON):
    def run(argv: list) -> str:
        return state if "currentprofile" in argv else rules + "Ok.\n"
    return run


def _check(rules: str, state: str = ON):
    from halo_harness.peers import firewall as F
    return F.check(7430, {F._norm(PY)}, run=_runner(rules, state))


@test
def test_the_live_checks_block_rules_are_found_and_said(ctx: Ctx):
    from halo_harness.peers import firewall as F
    got = _check(_rule("python.exe", "Block") + _rule("python.exe", "Block", protocol="UDP")
                 + _rule("Other app", "Allow", program=r"C:\other\app.exe"))
    ctx.check(f"blocked: the TCP Block rule for this python, got {got}", got["state"] == "blocked"
              and got["rules"] == ["python.exe"] and got["programs"] == [PY] and got["profiles"] == "Private")
    line = F.line(7430, got=got)
    ctx.check(f"one line: what blocks, why, the exact admin commands and what they do, got {line!r}",
              line.startswith("Windows Firewall blocks other machines from the fleet hub on port 7430")
              and "prompt was declined or not seen" in line and "a block beats an allow" in line
              and f"Get-NetFirewallApplicationFilter -Program '{PY}'" in line and "Remove-NetFirewallRule" in line
              and "New-NetFirewallRule -DisplayName 'Halo fleet hub' -Direction Inbound -Protocol TCP -LocalPort 7430 "
                  "-Action Allow -Profile Private" in line and "\n" not in line)


@test
def test_allowed_off_no_rule_and_unreadable(ctx: Ctx):
    from halo_harness.peers import firewall as F
    ctx.check("an Allow rule for the port: nothing to say", _check(_rule("Halo fleet hub", "Allow", program="Any", port="7430"))["state"] == "allowed"
              and F.line(7430, got=_check(_rule("Halo fleet hub", "Allow", program="Any", port="7430"))) == "")
    ctx.check("a port range counts", _check(_rule("lan", "Allow", program="Any", port="7000-7999"))["state"] == "allowed")
    ctx.check("an app package's Any/Any rule is not ours", _check(_rule("Store app", "Block", program="Any"))["state"] == "no-rule")
    ctx.check("a disabled Block rule does not block", _check(_rule("python.exe", "Block", enabled="No"))["state"] == "no-rule")
    off = _check(_rule("python.exe", "Block"), state=ON.replace(" ON", " OFF"))
    ctx.check(f"the firewall off: nothing in the way, got {off['state']}", off["state"] == "off")
    none = _check(_rule("Other app", "Allow", program=r"C:\other\app.exe"))
    line = F.line(7430, got=none)
    ctx.check(f"no rule: says Windows asks once and gives the allow command, got {line!r}", none["state"] == "no-rule"
              and line.startswith("No Windows Firewall rule lets other machines reach the fleet hub on port 7430")
              and "New-NetFirewallRule" in line)
    ctx.check("unreadable (another language, nothing parsed): unknown, nothing said",
              _check("Regelname: x\n")["state"] == "unknown" and F.line(7430, got={"state": "unknown", "rules": []}) == "")
    ctx.check("in a test with no seam, this machine's rules are never read", F.check(7430)["state"] in ("unknown", "not-windows"))


@test
def test_a_join_that_times_out_names_the_firewall(ctx: Ctx):
    import socket
    from halo_harness.peers.relay import unreached
    said = str(unreached("192.0.2.28", 7430, socket.timeout("timed out")))
    ctx.check(f"timeout: the hub did not answer, the firewall the usual cause, halo doctor on the hub, got {said!r}",
              said == "the hub did not answer on 192.0.2.28:7430: on Windows the firewall is the usual cause; on the hub "
                      "run `halo doctor`")
    ctx.check("refused keeps its own words", "cannot reach the hub at 192.0.2.28:7430" in str(unreached("192.0.2.28", 7430, ConnectionRefusedError("refused"))))


@test
def test_the_hub_says_it_at_start(ctx: Ctx):
    from halo_harness.fleet.hub import HubServer
    from halo_harness.peers import firewall as F
    F.RUN, F._seen = _runner(_rule("python.exe", "Block", program="Any", port="7430")), {}
    try:
        line = HubServer.firewall(SimpleNamespace(bind="0.0.0.0", port=7430))
        ctx.check(f"a hub on every interface says the line, got {line[:60]!r}", line.startswith("Windows Firewall blocks"))
        ctx.check("a hub on loopback says nothing", HubServer.firewall(SimpleNamespace(bind="127.0.0.1", port=7430)) == "")
    finally:
        F.RUN, F._seen = None, {}


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet firewall tests"))
