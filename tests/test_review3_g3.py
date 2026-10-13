"""tests.test_review3_g3 -- pins for the 3.0.2.0 review fix pass, round
G3-mcp-commands (part 1): completion scripts, MCP config parsing, project
.mcp.json writes, command-body placeholders, and the doctor deep prompt.

  * item 10   the PowerShell completion script drops/escapes unsafe words
  * item 142  the completion word filter no longer admits a backslash
  * item 69   a string `args` with an unbalanced quote is a disabled entry
  * item 71   $ARGUMENTS after an apostrophe in prose is still substituted
  * item 140  project .mcp.json: atomic write, non-object mcpServers is a
              clean error instead of a traceback
  * item 143  doctor --mcp deep never sends literal secrets to the model
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()

POISON = "or:x'; Write-Host PWNED; '"


# ---- items 10 + 142: completion scripts ------------------------------------

@test
def test_item10_powershell_completion_drops_and_escapes_unsafe_words(ctx: Ctx):
    from halo_harness.completion_cli import _powershell_script
    script = _powershell_script(["mcp", "dev"], ["architect"], ["or:ok/model-1", POISON, "or:a`b", "or:$(x)"])
    ctx.check("the poisoned id never reaches the script", "PWNED" not in script)
    ctx.check("backtick / $() ids are dropped too", "`b" not in script and "$(x)" not in script)
    ctx.check("a clean ref is still offered", "'or:ok/model-1'" in script)
    ctx.check("the array literal is intact", "$allWords = @('mcp', 'dev', 'architect', 'or:ok/model-1')" in script)


@test
def test_item10_powershell_array_doubles_a_single_quote(ctx: Ctx):
    # belt and braces: even a word that got past the filter could not close
    # the quote. Drive _ps_array through a filter-bypassing call.
    import halo_harness.completion_cli as cc
    orig = cc._completion_safe_words
    cc._completion_safe_words = lambda words: list(words)
    try:
        script = cc._powershell_script(["it's"], [], [])
    finally:
        cc._completion_safe_words = orig
    ctx.check("single quote doubled inside the PowerShell string", "'it''s'" in script)


@test
def test_item142_completion_filter_rejects_a_backslash(ctx: Ctx):
    from halo_harness.completion_cli import _bash_script, _completion_safe_words, _zsh_script
    words = _completion_safe_words(["a\\b", "or:zzz\\", "ok:ref/x-1", "plain+1@2"])
    ctx.check(f"backslash words dropped, others kept, got {words}", words == ["ok:ref/x-1", "plain+1@2"])
    bash = _bash_script(["mcp"], [], ["or:zzz\\", "or:fine"])
    zsh = _zsh_script(["mcp"], [], ["or:zzz\\", "or:fine"])
    ctx.check("bash script has no stray backslash word", "zzz" not in bash and "or:fine" in bash)
    ctx.check("zsh script has no stray backslash word", "zzz" not in zsh)


# ---- item 69: unbalanced quote in string args ------------------------------

@test
def test_item69_unbalanced_quote_in_string_args_is_a_disabled_entry(ctx: Ctx):
    from halo_harness.mcp.manager import parse_server
    cfg = parse_server("srv", {"type": "stdio", "command": "npx", "args": "\"unterminated"}, scope="project")
    ctx.check(f"entry becomes type=invalid, got {cfg.type!r}", cfg.type == "invalid")
    ctx.check("the reason names the args", "args" in (cfg.disabled_reason or "") and "shell-split" in cfg.disabled_reason)
    ok = parse_server("srv", {"type": "stdio", "command": "npx", "args": "-y 'a b'"}, scope="project")
    ctx.check("a balanced string still splits", ok.args == ["-y", "a b"])


# ---- item 71: placeholders after an apostrophe ------------------------------

@test
def test_item71_arguments_after_an_apostrophe_in_prose(ctx: Ctx):
    from halo_harness.commands.registry import substitute_arguments as sub
    out = sub("Review the user's request carefully: $ARGUMENTS", "fix the login bug")
    ctx.check(f"placeholder substituted, no trailer, got {out!r}",
              out == "Review the user's request carefully: fix the login bug")
    out2 = sub("Don't guess. First $0 then $1 (it's fine)", "a b")
    ctx.check(f"$N after Don't substituted, got {out2!r}", out2 == "Don't guess. First a then b (it's fine)")
    out3 = sub("awk '{print $1}' $0", "f.txt")
    ctx.check("a real shell single-quoted span stays literal", out3 == "awk '{print $1}' f.txt")
    out4 = sub("run x='$1' and $0", "z")
    ctx.check(f"a quote after = still opens a span, got {out4!r}", out4 == "run x='$1' and z")
    out5 = sub("lone ' quote then $0", "z")
    ctx.check(f"an unclosed span on the line does not swallow the body, got {out5!r}",
              out5 == "lone ' quote then z")


# ---- item 140: project .mcp.json -------------------------------------------

@test
def test_item140_non_object_mcpservers_is_a_clean_error_and_nothing_is_rewritten(ctx: Ctx):
    from halo_harness import mcp_cli
    with tempfile.TemporaryDirectory() as d:
        cwd = Path(d)
        path = cwd / ".mcp.json"
        path.write_text('{"mcpServers": []}', encoding="utf-8")
        for argv in (["add", "-s", "project", "--cwd", d, "srv", "--", "npx", "x"],
                     ["add-json", "-s", "project", "--cwd", d, "srv", '{"command": "npx"}'],
                     ["remove", "-s", "project", "--cwd", d, "srv"]):
            err = io.StringIO()
            try:
                with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                    rc = mcp_cli.cmd_mcp(argv)
                raised = None
            except Exception as e:  # noqa: BLE001
                rc, raised = None, e
            ctx.check(f"{argv[0]}: no traceback ({raised!r})", raised is None)
            ctx.check(f"{argv[0]}: non-zero exit and the message names mcpServers",
                      rc not in (0, None) and "mcpServers must be an object" in err.getvalue())
        ctx.check("the file was left untouched", path.read_text(encoding="utf-8") == '{"mcpServers": []}')
        ctx.check("the form-side reader returns {} instead of raising",
                  mcp_cli._raw_entry_for(scope="project", name="srv", cwd=cwd) == {})


@test
def test_item140_project_write_goes_through_a_temp_file_and_replace(ctx: Ctx):
    from halo_harness import mcp_cli
    calls = []
    real_replace = os.replace

    def spy(src, dst):
        calls.append((Path(src).name, Path(dst).name))
        return real_replace(src, dst)

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / ".mcp.json"
        os.replace = spy
        try:
            mcp_cli._write_dot_mcp_json(path, {"mcpServers": {"a": {"command": "c"}}})
        finally:
            os.replace = real_replace
        ctx.check(f"os.replace(tmp, .mcp.json) was used, got {calls}",
                  len(calls) == 1 and calls[0][1] == ".mcp.json" and calls[0][0] != ".mcp.json")
        ctx.check("content is right", json.loads(path.read_text(encoding="utf-8"))["mcpServers"]["a"]["command"] == "c")
        ctx.check("no temp file left behind", [p.name for p in Path(d).iterdir()] == [".mcp.json"])


# ---- item 143: doctor deep config masking ----------------------------------

def _stdio_cfg():
    from halo_harness.mcp.manager import McpServerConfig
    return McpServerConfig(
        name="leaky", type="stdio", command="npx", scope="user",
        args=["-y", "some-mcp", "--api-key", "sk-live-9f8e7d6c5b4a39281706f5e4d3c2b1a0", "--db",
              "postgres://u:p4ssw0rd@db.example/x", "--token=plainvalue1", "DB_PASSWORD=hunter22", "--keyfile", "/etc/k.pem"],
        env={"GH_PAT": "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2", "NODE_ENV": "production", "MY_TOKEN": "t0k3n"})


@test
def test_item143_config_entry_for_prompt_masks_args_and_env_values(ctx: Ctx):
    from halo_harness.mcp.doctor_deep import config_entry_for_prompt
    blob = json.dumps(config_entry_for_prompt(_stdio_cfg()))
    for secret in ("sk-live-9f8e", "p4ssw0rd", "plainvalue1", "hunter22", "ghp_a1B2", "t0k3n"):
        ctx.check(f"{secret!r} is not in the prompt config", secret not in blob)
    ctx.check("non-secret args and env survive", all(x in blob for x in ("some-mcp", "--keyfile", "/etc/k.pem", "production", "db.example")))


@test
def test_item143_propose_fix_never_hands_literal_secrets_to_the_model(ctx: Ctx):
    from halo_harness.mcp import doctor_deep
    seen = []
    cfg = _stdio_cfg()
    doctor_deep.propose_fix("evidence", doctor_deep.config_entry_for_prompt(cfg), cwd=Path("."),
                            model_call=lambda system, user: seen.append(user) or "kind: other")
    # a raw, unmasked corpus entry goes through the backstop pass
    raw = {"command": "npx", "args": ["--api-key", "sk-live-9f8e7d6c5b4a39281706f5e4d3c2b1a0"],
           "env": {"GH_PAT": "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2", "DB": "postgres://u:p4ssw0rd@db/x"}}
    doctor_deep.propose_fix("evidence", raw, cwd=Path("."), model_call=lambda s, u: seen.append(u) or "kind: other")
    for i, user in enumerate(seen):
        for secret in ("sk-live-9f8e", "p4ssw0rd", "ghp_a1B2", "hunter22"):
            ctx.check(f"prompt {i} has no {secret!r}", secret not in user)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
