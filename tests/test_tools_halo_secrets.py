"""tests.test_tools_halo_secrets -- Halo 3.6.0.0 R0a-finish (item 5): Halo's own secret files stay out of what its tools
show (halo_harness/tools/halo_secrets.py, through tools/registry.py dispatch). A scratch home with a Studio info file
(port, token, owner salt), a provider key file, an MCP OAuth token and the host steward's key:

1. the list is the files the code that writes them names, each one there;
2. Read shows each with its secret values hidden and one line naming the setting (nothing is refused); another
   file reads as before;
3. Grep with one as its path, and a Grep over the state folder, show the lines with each secret value hidden;
4. Bash: `cat` of the Studio file prints its port, the token and the salt hidden, and one line saying so;
5. `halo config set tools.show_halo_secrets true`: Read, Grep and Bash show them again.
Run: python -m tests.test_tools_halo_secrets
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.config_seed import ConfigHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
TOKEN, SALT, KEY, OAUTH, STEWARD = "tok-0123456789abcdef", "salt-fedcba9876543210", "sk-test-not-a-real-key-42", "oauth-access-77-test", "steward-key-55aa55aa"


def _seed(h) -> dict:
    from halo_harness.config.paths import env_file_path
    from halo_harness.host.duty import _key_path
    from halo_harness.mcp.oauth import token_path
    from halo_harness.studio.server import studio_info_path
    files = {"studio": studio_info_path(h.state), "env": env_file_path(), "oauth": token_path("docs-server"), "steward": _key_path(h.state)}
    for p in files.values():
        p.parent.mkdir(parents=True, exist_ok=True)
    files["studio"].write_text(json.dumps({"pid": 4242, "port": 51234, "token": TOKEN, "salt": SALT}), encoding="utf-8")
    files["env"].write_text(f"ANTHROPIC_API_KEY={KEY}\nHALO_MODEL=a-model-name-here\n", encoding="utf-8")
    files["oauth"].write_text(json.dumps({"access_token": OAUTH, "expires_at": 1}), encoding="utf-8")
    files["steward"].write_text(STEWARD + "\n", encoding="utf-8")
    return files


def _run(name: str, args: dict, cwd: Path):
    from halo_harness.tools.base import ToolContext
    from halo_harness.tools.registry import ToolRegistry
    return ToolRegistry().dispatch(name, args, ToolContext(cwd=cwd, bash_state={"cwd": str(cwd)}))


@test
def test_the_list_and_read(ctx: Ctx):
    from halo_harness.tools.halo_secrets import SETTING, secret_files
    with ConfigHome() as h:
        files = _seed(h)
        listed = {p.resolve() for p in secret_files()}
        ctx.check(f"every file is on the list, got {sorted(map(str, listed))}", {p.resolve() for p in files.values()} <= listed)
        for what, p in files.items():
            r = _run("Read", {"file_path": str(p)}, h.repo)
            text = str(r.content)
            ctx.check(f"Read shows the {what} file, its values hidden, one line naming the setting, got {text!r}", not r.is_error
                      and "[hidden]" in text and "Halo hid" in text and SETTING in text
                      and not any(s in text for s in (TOKEN, SALT, KEY, OAUTH, STEWARD)))
        text = str(_run("Read", {"file_path": str(files["studio"])}, h.repo).content)
        ctx.check(f"the Studio file still shows its port, got {text!r}", "51234" in text)
        other = h.write("repo/notes.md", "a plain note\n")
        r = _run("Read", {"file_path": str(other)}, h.repo)
        ctx.check(f"another file reads as before, got {r.content!r}", not r.is_error and "a plain note" in str(r.content))


@test
def test_grep(ctx: Ctx):
    with ConfigHome() as h:
        files = _seed(h)
        r = _run("Grep", {"pattern": "token", "path": str(files["studio"]), "output_mode": "content"}, h.repo)
        ctx.check(f"Grep with the Studio file as its path shows the line, the token hidden, got {r.content!r}", not r.is_error
                  and "[hidden]" in str(r.content) and TOKEN not in str(r.content) and SALT not in str(r.content))
        r = _run("Grep", {"pattern": "token|steward", "path": str(h.state), "output_mode": "content", "-i": True}, h.repo)
        text = str(r.content)
        ctx.check(f"a Grep over the state folder shows the lines, each secret hidden, got {text!r}", text.count("[hidden]") >= 3
                  and not any(s in text for s in (TOKEN, SALT, OAUTH, STEWARD)) and "Halo hid" in text)


@test
def test_bash(ctx: Ctx):
    if not shutil.which("bash") and sys.platform != "win32":
        ctx.check("no bash here", True)
        return
    with ConfigHome() as h:
        files = _seed(h)
        r = _run("Bash", {"command": f"cat '{files['studio'].as_posix()}'"}, h.repo)
        text = str(r.content)
        ctx.check(f"cat prints the port, the token and the salt hidden, one line saying so, got {text!r}",
                  "51234" in text and TOKEN not in text and SALT not in text and text.count("[hidden]") == 2
                  and "Halo hid 2 secret value(s)" in text and "tools.show_halo_secrets" in text)
        r = _run("Bash", {"command": f"cat '{files['env'].as_posix()}'"}, h.repo)
        ctx.check(f"the key file: the key hidden, a model name kept, got {r.content!r}", KEY not in str(r.content)
                  and "a-model-name-here" in str(r.content))


@test
def test_the_setting_shows_them(ctx: Ctx):
    with ConfigHome() as h:
        files = _seed(h)
        h.config({"tools": {"show_halo_secrets": True}})
        r = _run("Read", {"file_path": str(files["studio"])}, h.repo)
        ctx.check(f"Read shows it, got {r.content!r}", not r.is_error and TOKEN in str(r.content))
        r = _run("Grep", {"pattern": "token", "path": str(files["studio"]), "output_mode": "content"}, h.repo)
        ctx.check(f"Grep shows it, got {r.content!r}", TOKEN in str(r.content))
        if shutil.which("bash") or sys.platform == "win32":
            r = _run("Bash", {"command": f"cat '{files['steward'].as_posix()}'"}, h.repo)
            ctx.check(f"Bash shows it, got {r.content!r}", STEWARD in str(r.content) and "[hidden]" not in str(r.content))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
