"""halo_harness.tools.halo_secrets -- Halo's own secret files kept out of what its tools show (Halo 3.6.0.0 R0a-finish,
item 5: the owner's own agent once printed the Studio token file in a session).

The files, each named by the code that writes it with the private-file helper:
    studio.json        studio/server.py studio_info_path: the running Studio's port, token and owner salt
    the provider keys  config/paths.py env_file_path (and its legacy path): API keys and refresh tokens
    MCP OAuth tokens   mcp/oauth.py oauth_dir: one <server>.json each
    steward.key        host/duty.py: the host steward's signing key

    secret_files() -> [Path]                  the files above that exist now (an MCP OAuth folder: each file in it)
    guarded(tool, name, input, ctx) -> ToolResult
        every tool call goes through it (tools/registry.py dispatch): the output of Read, Grep, Bash, BashOutput and
        PowerShell has each secret value those files hold replaced by [hidden], with one line saying so and naming
        the setting that shows them: `halo config set tools.show_halo_secrets true`. Nothing is refused: a file
        still reads (its names, its port, its shape), only the secret values are hidden.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SETTING = "tools.show_halo_secrets"
HOW = f"to look anyway: halo config set {SETTING} true"
MASKED = ("Read", "Grep", "Bash", "BashOutput", "PowerShell")
HIDDEN = "[hidden]"


def secret_files() -> "list[Path]":
    from halo_harness.config.paths import bridge_home, env_file_path, legacy_env_file_path
    from halo_harness.host.duty import _key_path
    from halo_harness.mcp.oauth import oauth_dir
    from halo_harness.studio.server import studio_info_path
    state = bridge_home()
    out = [studio_info_path(state), env_file_path(), legacy_env_file_path(), _key_path(state)]
    try:
        out += sorted(oauth_dir().glob("*.json"))
    except OSError:
        pass
    return [p for p in out if p.is_file()]


KEYISH = re.compile(r"(token|salt|secret|key|password|auth|cred)", re.I)


def _values(path: Path) -> "list[str]":
    """The secret values in one file: a JSON file's strings under a token / salt / secret / key name, an env file's
    values under such a name, a key file's text (a port, a path or a model name is not a secret and stays)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    try:
        stack, out = [(json.loads(text), False)], []
        while stack:
            d, named = stack.pop()
            if isinstance(d, dict):
                stack += [(v, named or bool(KEYISH.search(str(k)))) for k, v in d.items()]
            elif isinstance(d, list):
                stack += [(v, named) for v in d]
            elif isinstance(d, str) and named:
                out.append(d)
        return out
    except ValueError:
        pass
    pairs = re.findall(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", text, re.M)
    return [v.strip().strip("'\"") for k, v in pairs if KEYISH.search(k)] if pairs else [text.strip()]


def mask(text: str) -> "tuple[str, int]":
    """`text` with every secret value (8 characters or more) of Halo's files replaced; the count replaced."""
    vals = sorted({v for f in secret_files() for v in _values(f) if len(v) >= 8}, key=len, reverse=True)
    n = 0
    for v in vals:
        if v in text:
            n += text.count(v)
            text = text.replace(v, HIDDEN)
    return text, n


def _shown() -> bool:
    from halo_harness.theme import get_config_value
    try:
        return get_config_value(SETTING, default=False) is True
    except Exception:
        return False


def guarded(tool, name: str, input: dict, ctx):
    """`tool.run(input, ctx)` with the values of Halo's secret files hidden (above); a check that cannot run leaves
    the result as it is."""
    result = tool.run(input, ctx)
    try:
        if name in MASKED and isinstance(result.content, str) and result.content and not _shown():
            text, n = mask(result.content)
            if n:
                result.content = text + f"\n(Halo hid {n} secret value(s) of its own files in this output; {HOW})"
    except Exception:  # noqa: BLE001 -- the guard never breaks a tool
        pass
    return result
