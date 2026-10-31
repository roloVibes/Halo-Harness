"""tests.test_host_install -- Halo 3.3.7.0 R1 deliverable 5: `halo host install | uninstall` (host_install.py)
through remote/daemon_units.write_unit, over a scratch home (tests/helpers/host_rig.py):

1. the three service files for the host's argv ([python, -m, halo_harness.cli, host, serve, --foreground, ...]): a
   systemd user unit halo-host.service, a launchd agent com.halo.host (its own label), a Task Scheduler task "Halo
   Host" at logon; each with the one enable command Halo prints and never runs;
2. --port / --bind ride the argv;
3. a machine that serves no Ollama host: one line, nothing written; --anyway writes it;
4. uninstall removes the file it wrote and prints the disable command; a second says there is none;
5. no service manager is ever run (subprocess is a refusing seam for the whole module); the Signal bridge's and the
   supervisor's plists keep their own labels.
Run: python -m tests.test_host_install
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_rig import HostRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
LOCAL = {"name": "box", "url": "http://127.0.0.1:11434"}


class _NoServiceManager:
    """subprocess.run / Popen / check_output refuse while a test runs: Halo prints the enable line, never runs it."""

    def __enter__(self):
        self.saved = (subprocess.run, subprocess.Popen, subprocess.check_output)
        self.calls: list = []

        def refuse(*a, **k):
            self.calls.append(a[0] if a else k.get("args"))
            raise OSError("no service manager in a test")
        subprocess.run = subprocess.Popen = subprocess.check_output = refuse
        return self

    def __exit__(self, *exc):
        subprocess.run, subprocess.Popen, subprocess.check_output = self.saved


def _cli(*argv) -> "tuple[int, str]":
    from halo_harness.host_cli import cmd_host
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(out):
        rc = cmd_host(list(argv))
    return rc, out.getvalue()


@test
def test_the_three_service_files_for_the_hosts_argv(ctx: Ctx):
    with HostRig(host_home=None, seed=False) as rig, _NoServiceManager() as nsm:
        rig.set_peer(**{"ollama.hosts": [LOCAL]})
        rows = {}
        for os_n in ("linux", "macos", "windows"):
            rc, text = _cli("install", "--os", os_n, "--json")
            rows[os_n] = json.loads(text) if rc == 0 else {"rc": rc, "text": text}
        lin = rows["linux"]
        unit = Path(lin["unit"])
        body = unit.read_text(encoding="utf-8")
        ctx.check(f"linux: halo-host.service under <state>/host, a user unit, got {unit}", unit.name == "halo-host.service"
                  and unit.parent.name == "host" and "WantedBy=default.target" in body and "Restart=on-failure" in body)
        ctx.check(f"linux: ExecStart runs halo_harness.cli host serve --foreground, got {body!r}",
                  "-m halo_harness.cli host serve --foreground" in body and sys.executable.split("\\")[-1] in body)
        ctx.check(f"linux: the enable command links and enables, got {lin['enable']!r}",
                  lin["enable"].startswith("systemctl --user link ") and "enable --now halo-host.service" in lin["enable"])
        mac = Path(rows["macos"]["unit"])
        plist = mac.read_text(encoding="utf-8")
        ctx.check(f"macos: com.halo.host.plist with its own label and the argv, got {mac.name}", mac.name == "com.halo.host.plist"
                  and "<string>com.halo.host</string>" in plist and "<string>halo_harness.cli</string>" in plist
                  and "<string>--foreground</string>" in plist and rows["macos"]["enable"].startswith("launchctl bootstrap"))
        win = Path(rows["windows"]["unit"])
        xml = win.read_bytes().decode("utf-16")
        ctx.check(f"windows: halo-host-task.xml at logon, the argv, Task Scheduler's name, got {win.name}",
                  win.name == "halo-host-task.xml" and "<LogonTrigger>" in xml
                  and "-m halo_harness.cli host serve --foreground" in xml
                  and rows["windows"]["enable"].startswith('schtasks /Create /TN "Halo Host"'))
        ctx.check(f"no service manager ran, got {nsm.calls}", not nsm.calls)


@test
def test_port_and_bind_ride_the_argv(ctx: Ctx):
    with HostRig(host_home=None, seed=False) as rig, _NoServiceManager():
        rig.set_peer(**{"ollama.hosts": [LOCAL]})
        rc, text = _cli("install", "--os", "linux", "--port", "7555", "--bind", "192.0.2.5", "--json")
        got = json.loads(text)
        ctx.check(f"the argv carries them, got {got['argv']}", got["argv"][-4:] == ["--port", "7555", "--bind", "192.0.2.5"]
                  and "--port 7555 --bind 192.0.2.5" in Path(got["unit"]).read_text(encoding="utf-8"))
        rc, text = _cli("install", "--os", "linux")
        ctx.check(f"the words: Halo does not enable it, the one command, got {text!r}", rc == 0
                  and "Halo does not enable it" in text and "systemctl --user link" in text)


@test
def test_a_machine_that_serves_no_ollama_host(ctx: Ctx):
    from halo_harness.host.state import host_dir
    with HostRig(host_home=None, seed=False) as rig, _NoServiceManager():
        rc, text = _cli("install", "--os", "linux")
        ctx.check(f"one line, nothing written, got {rc} {text!r}", rc == 1 and len(text.strip().splitlines()) == 1
                  and "serves no Ollama host" in text and "--anyway" in text
                  and not (host_dir(rig.home) / "halo-host.service").exists())
        rc, text = _cli("install", "--os", "linux", "--anyway", "--json")
        ctx.check(f"--anyway writes it, got {rc}", rc == 0 and Path(json.loads(text)["unit"]).exists())


@test
def test_uninstall_removes_what_it_wrote(ctx: Ctx):
    with HostRig(host_home=None, seed=False) as rig, _NoServiceManager() as nsm:
        rig.set_peer(**{"ollama.hosts": [LOCAL]})
        for os_n, off in (("linux", "systemctl --user disable --now halo-host.service"),
                          ("macos", "launchctl bootout gui/$(id -u)/com.halo.host"),
                          ("windows", 'schtasks /Delete /TN "Halo Host" /F')):
            rc, text = _cli("install", "--os", os_n, "--json")
            unit = Path(json.loads(text)["unit"])
            rc, text = _cli("uninstall", "--os", os_n, "--json")
            got = json.loads(text)
            ctx.check(f"{os_n}: removed, the disable line, got {got}", rc == 0 and got["removed"] == str(unit)
                      and not unit.exists() and got["disable"] == off)
            rc, text = _cli("uninstall", "--os", os_n)
            ctx.check(f"{os_n}: a second says there is none, got {text!r}", rc == 0 and "No service file" in text
                      and off in text)
        ctx.check("no service manager ran", not nsm.calls)


@test
def test_the_other_units_keep_their_labels(ctx: Ctx):
    from halo_harness.remote import daemon_units as du
    ctx.check("the Signal bridge's plist keeps dev.halo.remote",
              "<string>dev.halo.remote</string>" in du.render_launchd(["/usr/bin/halo", "remote", "signal", "run"]))
    ctx.check("the supervisor's plist says dev.halo.supervise",
              "<string>dev.halo.supervise</string>" in du.render_launchd(["/usr/bin/halo"], {}, "dev.halo.supervise"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
