"""tests.test_review2_round3 -- pins for the vibes/review.md findings fixed
in R6/R7/R2 (data loss, MCP, TUI crash class; drafted by the local Ollama
model, corrected in-session -- the token-thrift offload flow):

  * f19  corrupt config.json: set_config_value refuses (CorruptConfigError),
        file untouched; valid writes still preserve siblings
  * f20  worktree removal never deletes user branches; halo-worktree-*
        branches go with the safe `git branch -d`
  * f23  the shadow repo tracks gitignored files (git add -f) so /rewind
        can restore them
  * f30  malformed MCP env/headers become a disabled placeholder, never a
        startup crash; a string `args` is shlex-split, not char-split
  * f41  ${TOKEN} in url/headers expands to the REAL credential (the
        GitHub-plugin fix)
  * f42  parallel first-use connects on a lazy server start exactly once
  * f27/f28 Option ids are indices (no DuplicateID on repeated prompts)
        and labels are rich Text (no MarkupError on `[/...]` labels)
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()

REPO = Path(__file__).resolve().parent.parent


# ---- f19: corrupt config refused ----


@test
def test_f19_corrupt_config_refused(ctx: Ctx):
    import halo_harness.theme as theme
    p = Path(tempfile.mkdtemp()) / "config.json"
    p.write_text('{"model": "keep-me" NOT-JSON', encoding="utf-8")
    original = theme._config_path
    theme._config_path = lambda: p
    try:
        raised = False
        try:
            theme.set_config_value("theme", "doom")
        except theme.CorruptConfigError:
            raised = True
        ctx.check("refused with CorruptConfigError", raised)
        ctx.check("file content untouched", "keep-me" in p.read_text(encoding="utf-8"))
        p.write_text('{"model": "keep-me"}', encoding="utf-8")
        theme.set_config_value("theme", "doom")
        data = json.loads(p.read_text(encoding="utf-8"))
        ctx.check("valid file: new key written", data.get("theme") == "doom")
        ctx.check("valid file: sibling preserved", data.get("model") == "keep-me")
    finally:
        theme._config_path = original


# ---- f20: worktree branch guards ----


def _fake_git_recorder(calls, branch):
    def fake_git(args, cwd):
        calls.append(tuple(args))
        if tuple(args) == ("rev-parse", "--abbrev-ref", "HEAD"):
            return SimpleNamespace(returncode=0, stdout=branch + "\n")
        return SimpleNamespace(returncode=0, stdout="")
    return fake_git


@test
def test_f20_user_branch_never_deleted(ctx: Ctx):
    import halo_harness.worktree as wt
    calls: list = []
    original = wt._git
    wt._git = _fake_git_recorder(calls, "feature-x")
    try:
        out = wt.remove_worktree(Path("C:/tmp/wt"), repo_root_hint=Path("C:/tmp/repo"))
        ctx.check("reports success", out[0] is True and out[1] is None)
        branch_calls = [c for c in calls if c[0] == "branch"]
        ctx.check("no branch deletion for a user branch", branch_calls == [])
    finally:
        wt._git = original


@test
def test_f20_halo_branch_uses_safe_delete(ctx: Ctx):
    import halo_harness.worktree as wt
    calls: list = []
    original = wt._git
    wt._git = _fake_git_recorder(calls, "halo-worktree-abc123")
    try:
        out = wt.remove_worktree(Path("C:/tmp/wt"), repo_root_hint=Path("C:/tmp/repo"))
        ctx.check("success", out[0] is True)
        branch_calls = [c for c in calls if c[0] == "branch"]
        ctx.check("safe -d used, not -D",
                  bool(branch_calls) and branch_calls[0] == ("branch", "-d", "halo-worktree-abc123"))
    finally:
        wt._git = original


# ---- f23: shadow snapshots ignored files ----


@test
def test_f23_shadow_snapshots_ignored_files(ctx: Ctx):
    from halo_harness.shadow import ShadowStore
    tmp = Path(tempfile.mkdtemp())
    store = ShadowStore(tmp)
    (tmp / ".gitignore").write_text("secret.txt\n", encoding="utf-8")
    step = store.record_step({"secret.txt": "payload"}, label="snap", trigger="tool")
    ctx.check("step recorded", bool(step and step.get("hash")))
    ls = store._git("ls-files")
    ctx.check("gitignored file IS tracked by the shadow repo (add -f)",
              "secret.txt" in (ls.stdout or ""))


# ---- f30: malformed MCP config ----


@test
def test_f30_malformed_env_list_is_disabled_not_crash(ctx: Ctx):
    from halo_harness.mcp.manager import parse_server
    cfg = parse_server("bad", {"type": "http", "url": "https://x/", "env": ["A=B"]}, scope="user")
    ctx.check("placeholder returned, not an exception", cfg is not None)
    ctx.check("disabled with a reason naming env",
              bool(cfg.disabled_reason) and "env" in cfg.disabled_reason)
    cfg2 = parse_server("bad2", {"type": "http", "url": "https://x/", "headers": "not-a-dict"}, scope="user")
    ctx.check("string headers disabled too", cfg2 is not None and "headers" in (cfg2.disabled_reason or ""))


@test
def test_f30_string_args_shell_split(ctx: Ctx):
    from halo_harness.mcp.manager import parse_server
    cfg = parse_server("s", {"type": "stdio", "command": "npx", "args": "--flag value"}, scope="user")
    ctx.check("string args shlex-split, not char-split", cfg.args == ["--flag", "value"])


# ---- f41: real credential expansion ----


@test
def test_f41_real_credential_expansion(ctx: Ctx):
    from halo_harness.mcp.manager import McpServerConfig, expand_config
    base = McpServerConfig(name="gh", type="http", url="https://api.example/mcp/${GITHUB_TOKEN}",
                           headers={"Authorization": "Bearer ${GITHUB_TOKEN}"})
    exp, _warns = expand_config(base, {"GITHUB_TOKEN": "ghp_realtoken123456789012345"})
    ctx.check("header carries the real credential",
              exp.headers.get("Authorization") == "Bearer ghp_realtoken123456789012345")
    ctx.check("url carries the real credential", "ghp_realtoken123456789012345" in (exp.url or ""))
    ctx.check("no ${...} left behind",
              "${" not in (exp.url or "") and "${" not in (exp.headers.get("Authorization") or ""))


# ---- f42: first-use connect locked once ----


@test
def test_f42_first_use_connect_locked_once(ctx: Ctx):
    from halo_harness.mcp.manager import McpManager

    class FakeHandle:
        def __init__(self):
            self.state = "pending"
            self.tools = []
            self.starts = 0

        def start(self, abort=None):
            time.sleep(0.05)
            self.starts += 1
            self.state = "connected"

    mgr = McpManager({}, lazy_names={"x"})
    h = FakeHandle()
    mgr.handles["x"] = h
    threads = [threading.Thread(target=mgr.ensure_started, args=("x",)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    ctx.check("all threads done", not any(t.is_alive() for t in threads))
    ctx.check("start ran exactly once (no double subprocess, no lost caller)", h.starts == 1)
    ctx.check("handle connected", h.state == "connected")


# ---- f27/f28: Option construction safe ----


@test
def test_f27_f28_option_construction_safe(ctx: Ctx):
    from rich.text import Text
    from textual.widgets.option_list import Option
    opts = [Option(Text(e), id=str(i)) for i, e in enumerate(["[/etc/hosts] fix", "continue", "continue"])]
    ctx.check("three options built with distinct ids (repeats can't DuplicateID)",
              len(opts) == 3 and len({o.id for o in opts}) == 3)
    ctx.check("markup-shaped label carried literally", "[/etc/hosts] fix" in str(opts[0].prompt))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
