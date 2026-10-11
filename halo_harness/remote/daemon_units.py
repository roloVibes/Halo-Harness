"""halo_harness.remote.daemon_units -- the service-manager files for
`halo remote signal run --daemon` (Halo 2.0.9 round 4).

One unit per OS, written under `<remote>/` and never enabled by Halo: the
caller prints the single command that enables it.

    linux    halo-remote.service        systemd user unit
    macos    dev.halo.remote.plist      launchd agent
    windows  halo-remote-task.xml       Task Scheduler task (at logon)

The service runs the bridge (`halo remote signal run`), which starts
signal-cli itself over stdio. `JAVA_TOOL_OPTIONS` is carried into the unit
when it is set in the environment that writes it (the proxied-VM recipe).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from halo_harness.remote.signal_config import remote_dir

OS_NAMES = ("linux", "macos", "windows")
LABEL = "dev.halo.remote"
FILES = {"linux": "halo-remote.service", "macos": LABEL + ".plist", "windows": "halo-remote-task.xml"}


def os_name(platform: Optional[str] = None) -> str:
    p = platform if platform is not None else sys.platform
    return "windows" if p.startswith("win") else ("macos" if p == "darwin" else "linux")


def run_argv() -> list:
    """How a service starts the bridge: the `halo` command when it is on
    PATH, otherwise this interpreter with `-m halo_harness`."""
    exe = shutil.which("halo")
    base = [exe] if exe else [sys.executable, "-m", "halo_harness"]
    return base + ["remote", "signal", "run"]


def _quote(word: str) -> str:
    return '"' + word.replace("\\", "\\\\").replace('"', '\\"') + '"' if any(c in word for c in ' \t"\\') else word


def render_systemd(argv: list, env: Optional[dict] = None) -> str:
    lines = ["[Unit]", "Description=Halo remote control (Signal bridge)", "After=network-online.target",
             "Wants=network-online.target", "", "[Service]", "Type=simple",
             "ExecStart=" + " ".join(_quote(w) for w in argv), "Restart=on-failure", "RestartSec=5"]
    for k, v in sorted((env or {}).items()):
        lines.append(f'Environment="{k}={v}"')
    lines += ["", "[Install]", "WantedBy=default.target", ""]
    return "\n".join(lines)


def render_launchd(argv: list, env: Optional[dict] = None) -> str:
    args = "".join(f"    <string>{escape(w)}</string>\n" for w in argv)
    envs = ""
    if env:
        envs = "  <key>EnvironmentVariables</key>\n  <dict>\n" + "".join(
            f"    <key>{escape(k)}</key>\n    <string>{escape(v)}</string>\n" for k, v in sorted(env.items())) + "  </dict>\n"
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n<dict>\n'
            f"  <key>Label</key>\n  <string>{LABEL}</string>\n"
            f"  <key>ProgramArguments</key>\n  <array>\n{args}  </array>\n{envs}"
            "  <key>RunAtLoad</key>\n  <true/>\n  <key>KeepAlive</key>\n  <true/>\n"
            "  <key>StandardOutPath</key>\n  <string>/dev/null</string>\n"
            "  <key>StandardErrorPath</key>\n  <string>/dev/null</string>\n"
            "</dict>\n</plist>\n")


def render_task_xml(argv: list) -> str:
    args = " ".join(f'"{w}"' if " " in w else w for w in argv[1:])
    return ('<?xml version="1.0" encoding="UTF-16"?>\n'
            '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
            "  <RegistrationInfo><Description>Halo remote control (Signal bridge)</Description></RegistrationInfo>\n"
            "  <Triggers><LogonTrigger><Enabled>true</Enabled></LogonTrigger></Triggers>\n"
            "  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>"
            "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>"
            "<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>"
            "<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>"
            "<RestartOnFailure><Interval>PT1M</Interval><Count>99</Count></RestartOnFailure></Settings>\n"
            f"  <Actions Context=\"Author\"><Exec><Command>{escape(argv[0])}</Command>"
            f"<Arguments>{escape(args)}</Arguments></Exec></Actions>\n</Task>\n")


def enable_command(os_n: str, path: Path) -> str:
    if os_n == "linux":
        return f"systemctl --user link {path} && systemctl --user enable --now {path.name}"
    if os_n == "macos":
        return f"launchctl bootstrap gui/$(id -u) {path}"
    return f'schtasks /Create /TN "Halo Remote" /XML "{path}"'


def write_unit(os_n: Optional[str] = None, argv: Optional[list] = None, env: Optional[dict] = None) -> tuple:
    """Write the unit for `os_n`; returns `(path, enable_command)`. Nothing is enabled."""
    os_n = os_n or os_name()
    if os_n not in OS_NAMES:
        raise ValueError(f"os must be one of {', '.join(OS_NAMES)}")
    argv = argv or run_argv()
    if env is None:
        env = {k: os.environ[k] for k in ("JAVA_TOOL_OPTIONS",) if os.environ.get(k)}
    text = (render_systemd(argv, env) if os_n == "linux" else
            render_launchd(argv, env) if os_n == "macos" else render_task_xml(argv))
    from halo_harness.privateio import write_private_atomic
    path = remote_dir() / FILES[os_n]
    if os_n == "windows":  # Task Scheduler reads the UTF-16 (BOM) form its own export writes
        path.write_bytes(text.encode("utf-16"))
    else:
        write_private_atomic(path, text)
    return path, enable_command(os_n, path)
