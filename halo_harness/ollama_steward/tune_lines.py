"""halo_harness.ollama_steward.tune_lines -- Halo 3.3.6.0 R5: the tuning report's server-side lines and its Apply
(ollama_steward/tune_report.py builds the report).

A server-side option is the exact line for your shell on the host's OS, with the line that reverts it beside it; Halo
never runs either (code never changes a host-side Ollama setting, and nothing restarts a server):

    env_lines(key, value, os_name) -> {set, revert, restart}     OLLAMA_KV_CACHE_TYPE, OLLAMA_FLASH_ATTENTION, ...
    update_lines(os_name) -> {set, revert, restart}              an Ollama update
    os_of(host, card) -> "windows" | "linux" | "macos" | None    None: every OS's lines are shown

    apply(state_dir, host_name, option_id, *, scope="keep", session_id=None, report=None) -> {ok, lines}
        a Halo-side option's changes landed through agent_proposals.land_user, each with `scope`
"""

from __future__ import annotations

import sys
from typing import Optional

OSES = ("windows", "linux", "macos")
RESTART = {"windows": "quit Ollama from the tray (right-click, Quit Ollama), then start Ollama again",
           "linux": "sudo systemctl restart ollama",
           "macos": "quit the Ollama app from the menu bar, then open it again"}
DROPIN = "/etc/systemd/system/ollama.service.d"


def env_lines(key: str, value: str, os_name: str) -> dict:
    if os_name == "windows":
        return {"set": f'[Environment]::SetEnvironmentVariable("{key}", "{value}", "User")',
                "revert": f'[Environment]::SetEnvironmentVariable("{key}", $null, "User")', "restart": RESTART[os_name]}
    if os_name == "macos":
        return {"set": f"launchctl setenv {key} {value}", "revert": f"launchctl unsetenv {key}",
                "restart": RESTART[os_name]}
    conf = f"{DROPIN}/halo-{key.lower()}.conf"
    return {"set": (f"sudo mkdir -p {DROPIN} && printf '[Service]\\nEnvironment=\"{key}={value}\"\\n' | sudo tee {conf} "
                    "&& sudo systemctl daemon-reload"),
            "revert": f"sudo rm {conf} && sudo systemctl daemon-reload", "restart": RESTART["linux"]}


def update_lines(os_name: str) -> dict:
    return {"windows": {"set": "winget upgrade --id Ollama.Ollama", "revert": "winget install --id Ollama.Ollama --version <the version before>"},
            "macos": {"set": "brew upgrade ollama", "revert": "brew install ollama@<the version before> (or the app's download page)"},
            "linux": {"set": "curl -fsSL https://ollama.com/install.sh | sh",
                      "revert": "curl -fsSL https://ollama.com/install.sh | OLLAMA_VERSION=<the version before> sh"}}[os_name] | \
        {"restart": RESTART[os_name]}


def os_of(host, card: Optional[dict]) -> Optional[str]:
    """The host's OS when it is known: this machine's (a loopback or own address), else the card's `os`."""
    raw = str((card or {}).get("os") or "").lower()
    if not raw:
        try:
            from halo_harness.fleet.ollama_share import served_here
            raw = sys.platform if served_here(getattr(host, "url", "")) else ""
        except Exception:
            raw = ""
    if raw.startswith(("win", "nt")):
        return "windows"
    if raw.startswith(("darwin", "mac")):
        return "macos"
    return "linux" if raw.startswith("linux") else None


def server_block(kind: str, key: str, value: str, os_name: Optional[str]) -> dict:
    """{os: {set, revert, restart}} for the host's OS, or for every OS when it is not known."""
    names = [os_name] if os_name else list(OSES)
    return {o: (update_lines(o) if kind == "update" else env_lines(key, value, o)) for o in names}


def apply(state_dir, host_name: str, option_id: str, *, scope: str = "keep", session_id: Optional[str] = None,
          session_pid: Optional[int] = None, report: Optional[dict] = None) -> dict:
    from halo_harness.ollama_steward.agent_proposals import land_user
    if report is None:
        from halo_harness.ollama_steward.tune_report import report_for
        report = report_for(state_dir, host_name)
    opt = next((o for o in report.get("options") or [] if o.get("id") == option_id), None)
    if opt is None:
        return {"ok": False, "lines": [f"no option {option_id} in the tuning report of {host_name} now "
                                       "(halo local tune lists them)"]}
    if opt.get("kind") != "halo" or not opt.get("apply"):
        return {"ok": False, "lines": [f"{opt['line']}: a server-side change, run on {host_name} by you "
                                       f"({next(iter((opt.get('server') or {}).values()), {}).get('set', '')})"]}
    out, ok = [], True
    for ch in opt["apply"]:
        got = land_user(state_dir, ch, scope=scope, by="user", why=opt["line"], session_id=session_id,
                        session_pid=session_pid)
        ok = ok and got["ok"]
        out.append(got["line"])
    return {"ok": ok, "lines": out, "option": option_id}
