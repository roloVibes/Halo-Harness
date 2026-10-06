"""tests.test_mcp_doctor_deep -- halo_harness/mcp/{doctor_probe,doctor_deep}.py,
providers/learned_rules.py's new `mcp_fix` rows, and halo_harness/doctor.py's
`--mcp deep` subcommand (Halo 2.0.4 round 6, "MCP connectivity deep dive").
Every handshake/port-TLS check here runs against a REAL stdio subprocess
(tests/helpers/fake_mcp_server.py) or a REAL loopback socket -- never a mock
-- so the evidence a real deep dive would print is exercised for real; the
model is always an injected mock (`model_call=...`), never a real provider,
and no test ever reads/writes the real `~/.claude.json`/`~/.halo`.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
FAKE_SERVER_ARGS = ["-m", "tests.helpers.fake_mcp_server"]

test, TESTS = new_registry()


def _fake_cfg(name="fake", *, mode=None, extra_env=None, scope="user"):
    from halo_harness.mcp.manager import McpServerConfig
    env = dict(extra_env or {})
    if mode:
        env["FAKE_MCP_MODE"] = mode
    return McpServerConfig(name=name, type="stdio", command=sys.executable, args=list(FAKE_SERVER_ARGS),
                            env=env, cwd=str(REPO_DIR), scope=scope)


def _fresh_claude_json(entries: dict) -> Path:
    """Overwrites THIS process's scoped `~/.claude.json` with exactly
    `{"mcpServers": entries}` -- same "write exactly what this test needs,
    right before using it" convention `test_tui.py`'s own McpStatus tests
    already follow, so reusing a name across two tests in this file is
    never a collision (each overwrites before it runs)."""
    from halo_harness.config.paths import claude_json_path
    path = claude_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"mcpServers": entries}), encoding="utf-8")
    return path


# ---- doctor_probe: resolve_command_step / resolve_url_step -----------------

@test
def test_resolve_command_step_command_not_found(ctx: Ctx):
    from halo_harness.mcp import doctor_probe as P
    from halo_harness.mcp.manager import McpServerConfig
    cfg = McpServerConfig(name="x", type="stdio", command="definitely-not-a-real-cmd-xyz")
    step = P.resolve_command_step(cfg)
    ctx.check(f"fails with a command-not-found reason, got {step.detail!r}",
              step.ok is False and "not found on PATH" in step.detail)


@test
def test_resolve_command_step_shim_points_at_a_missing_interpreter(ctx: Ctx):
    from halo_harness.mcp import doctor_probe as P
    from halo_harness.mcp.manager import McpServerConfig
    d = Path(tempfile.mkdtemp(prefix="halo-shim-test-"))
    shim = d / "fake.cmd"
    shim.write_text('@"C:\\nonexistent\\python.exe" %*\n', encoding="utf-8")
    cfg = McpServerConfig(name="x", type="stdio", command=str(shim))
    step = P.resolve_command_step(cfg)
    ctx.check(f"resolves the shim but flags its missing interpreter, got {step.detail!r}",
              step.ok is True and "MISSING" in step.detail)


@test
def test_resolve_command_step_shim_points_at_a_real_interpreter(ctx: Ctx):
    from halo_harness.mcp import doctor_probe as P
    from halo_harness.mcp.manager import McpServerConfig
    d = Path(tempfile.mkdtemp(prefix="halo-shim-test-"))
    shim = d / "fake.cmd"
    shim.write_text(f'@"{sys.executable}" %*\n', encoding="utf-8")
    cfg = McpServerConfig(name="x", type="stdio", command=str(shim))
    step = P.resolve_command_step(cfg)
    ctx.check(f"resolves and confirms the real interpreter exists, got {step.detail!r}",
              step.ok is True and "(exists)" in step.detail and "MISSING" not in step.detail)


@test
def test_resolve_url_step_shape_check(ctx: Ctx):
    from halo_harness.mcp import doctor_probe as P
    from halo_harness.mcp.manager import McpServerConfig
    ok_cfg = McpServerConfig(name="x", type="http", url="https://example.com:9999/mcp")
    bad_cfg = McpServerConfig(name="y", type="http", url="not a url at all")
    ctx.check("a well-formed url parses", P.resolve_url_step(ok_cfg).ok is True)
    ctx.check("a malformed url fails", P.resolve_url_step(bad_cfg).ok is False)


# ---- doctor_probe: the real stdio handshake, every scripted failure mode --

@test
def test_handshake_steps_normal_mode_connects(ctx: Ctx):
    from halo_harness.mcp import doctor_probe as P
    steps = P.handshake_steps("normalmode", _fake_cfg("normalmode"), tool_env=dict(os.environ), cwd=REPO_DIR)
    ctx.check(f"one OK handshake step, got {[(s.name, s.ok) for s in steps]}",
              len(steps) == 1 and steps[0].ok and steps[0].name == "handshake")


@test
def test_handshake_steps_crash_mode_is_an_initialize_failure_with_stderr_captured(ctx: Ctx):
    """"initialize error" + "immediate exit with stderr" -- crash mode
    exits(1) (with a stderr line) before the handshake completes; the
    command itself resolves fine (sys.executable is real), so this is
    classified "handshake", never "spawn"."""
    from halo_harness.mcp import doctor_probe as P
    steps = P.handshake_steps("crashmode", _fake_cfg("crashmode", mode="crash"), tool_env=dict(os.environ),
                              cwd=REPO_DIR)
    ctx.check(f"one FAIL handshake step, got {[(s.name, s.ok) for s in steps]}",
              len(steps) == 1 and not steps[0].ok and steps[0].name == "handshake")
    ctx.check(f"the captured stderr line is in the evidence, got {steps[0].detail!r}",
              "crash mode -- exiting immediately" in steps[0].detail)


@test
def test_handshake_steps_slow_mode_times_out(ctx: Ctx):
    """"handshake timeout" -- a short MCP_CONNECT_TIMEOUT_MS/MCP_TIMEOUT
    against a server that sleeps well past both."""
    old_connect = os.environ.pop("MCP_CONNECT_TIMEOUT_MS", None)
    old_overall = os.environ.pop("MCP_TIMEOUT", None)
    try:
        os.environ["MCP_CONNECT_TIMEOUT_MS"] = "300"
        os.environ["MCP_TIMEOUT"] = "500"
        from halo_harness.mcp import doctor_probe as P
        cfg = _fake_cfg("slowmode", mode="slow", extra_env={"FAKE_MCP_SLEEP_S": "3"})
        steps = P.handshake_steps("slowmode", cfg, tool_env=dict(os.environ), cwd=REPO_DIR)
        ctx.check(f"handshake fails (timed out), got {[(s.name, s.ok, s.detail) for s in steps]}",
                  len(steps) == 1 and not steps[0].ok)
    finally:
        for name, old in (("MCP_CONNECT_TIMEOUT_MS", old_connect), ("MCP_TIMEOUT", old_overall)):
            if old is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old


@test
def test_handshake_steps_tools_list_error_is_distinct_from_handshake(ctx: Ctx):
    """"tools/list error" -- initialize succeeds (a real session); the
    listing itself always raises -- two steps, `handshake` OK and
    `tools_list` FAIL, never collapsed into one hard failure."""
    from halo_harness.mcp import doctor_probe as P
    steps = P.handshake_steps("toolslisterr", _fake_cfg("toolslisterr", mode="tools-list-error"),
                              tool_env=dict(os.environ), cwd=REPO_DIR)
    ctx.check(f"exactly 2 steps, got {[(s.name, s.ok) for s in steps]}", len(steps) == 2)
    ctx.check("handshake (initialize) is OK", steps[0].name == "handshake" and steps[0].ok is True)
    ctx.check(f"tools_list is FAIL with the real exception text, got {steps[1].detail!r}",
              steps[1].name == "tools_list" and steps[1].ok is False
              and "intentionally broken" in steps[1].detail)


@test
def test_handshake_steps_wrong_env_var_names_the_var_in_evidence(ctx: Ctx):
    """"wrong env var" -- the server refuses to start unless a specific
    var is set to the expected value; the captured stderr line names it,
    so the evidence (and later the model prompt) can point at it."""
    from halo_harness.mcp import doctor_probe as P
    steps = P.handshake_steps("needsenv", _fake_cfg("needsenv", mode="needs-env"), tool_env=dict(os.environ),
                              cwd=REPO_DIR)
    ctx.check(f"fails, naming the missing var, got {steps[0].detail!r}",
              steps[0].ok is False and "FAKE_MCP_REQUIRED_VAR" in steps[0].detail)
    # ... and setting it (via the config's own env block) connects fine.
    cfg_fixed = _fake_cfg("needsenv2", mode="needs-env", extra_env={"FAKE_MCP_REQUIRED_VAR": "expected-value"})
    steps2 = P.handshake_steps("needsenv2", cfg_fixed, tool_env=dict(os.environ), cwd=REPO_DIR)
    ctx.check(f"connects once the var is set, got {[(s.name, s.ok) for s in steps2]}", steps2[0].ok is True)


# ---- doctor_probe: port_and_tls_step (http/sse) ----------------------------

@test
def test_port_and_tls_step_closed_port(ctx: Ctx):
    import socket
    from halo_harness.mcp import doctor_probe as P
    from halo_harness.mcp.manager import McpServerConfig
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()  # bound then released -- nothing is listening there now
    cfg = McpServerConfig(name="y", type="http", url=f"http://127.0.0.1:{port}/mcp")
    step = P.port_and_tls_step(cfg, timeout_s=1.5)
    ctx.check(f"fails against a closed port, got {step.detail!r}", step.ok is False)


@test
def test_port_and_tls_step_bad_tls_answer(ctx: Ctx):
    from halo_harness.mcp import doctor_probe as P
    from halo_harness.mcp.manager import McpServerConfig
    from tests.helpers.fake_mcp_server import serve_plain_tcp_no_tls
    with serve_plain_tcp_no_tls() as port:
        cfg = McpServerConfig(name="tls", type="http", url=f"https://127.0.0.1:{port}/mcp")
        step = P.port_and_tls_step(cfg, timeout_s=2.0)
        ctx.check(f"a plain-TCP server answering https:// fails the TLS handshake, got {step.detail!r}",
                  step.ok is False)


# ---- doctor_probe: the whole assembled probe -------------------------------

@test
def test_probe_server_end_to_end_healthy_and_failed(ctx: Ctx):
    from halo_harness.mcp import doctor_probe as P
    healthy = P.probe_server("e2eok", _fake_cfg("e2eok"), tool_env=dict(os.environ), cwd=REPO_DIR)
    ctx.check(f"every step ok -> verdict healthy, got {healthy.verdict}", healthy.verdict == "healthy")
    ctx.check("resolve_command/env_diff/config_shape all ran",
              {s.name for s in healthy.steps} >= {"resolve_command", "handshake", "env_diff", "config_shape"})

    failed = P.probe_server("e2efail", _fake_cfg("e2efail", mode="crash"), tool_env=dict(os.environ), cwd=REPO_DIR)
    ctx.check(f"a failing handshake -> verdict failed, got {failed.verdict}", failed.verdict == "failed")
    ctx.check(f"failing_step names the handshake, got {failed.failing_step}", failed.failing_step == "handshake")
    evidence = failed.evidence_text()
    ctx.check("evidence_text renders every step with OK/FAIL tags",
              "[FAIL] handshake" in evidence and "[OK] env_diff" in evidence)


@test
def test_probe_server_disabled_and_pending_approval_never_connect(ctx: Ctx):
    from halo_harness.mcp import doctor_probe as P
    from halo_harness.mcp.manager import McpServerConfig
    disabled_cfg = McpServerConfig(name="d", type="invalid", disabled_reason="unknown transport 'carrier-pigeon'")
    pending_cfg = McpServerConfig(name="p", type="stdio", command="node", pending_approval=True)
    r1 = P.probe_server("d", disabled_cfg, tool_env=dict(os.environ), cwd=REPO_DIR)
    r2 = P.probe_server("p", pending_cfg, tool_env=dict(os.environ), cwd=REPO_DIR)
    ctx.check(f"disabled -> one step, never spawns, got {r1.steps}",
              len(r1.steps) == 1 and "carrier-pigeon" in r1.steps[0].detail)
    ctx.check(f"pending approval -> one step, never spawns, got {r2.steps}",
              len(r2.steps) == 1 and "pending" in r2.steps[0].detail.lower())


# ---- doctor_deep: the fixed-prompt proposal parser -------------------------

@test
def test_parse_fix_proposal_every_kind(ctx: Ctx):
    from halo_harness.mcp import doctor_deep as D
    cases = {
        "CONFIG_EDIT: env.FOO=bar": ("config_edit", True),
        "INSTALL: pip install uv": ("install", False),
        "PATH: C:\\real\\node.exe": ("path", True),
        "URL: https://example.com:9999/mcp": ("url", True),
        "ENV: SOME_VAR": ("env", False),
        "ENV: UNKNOWN": ("env", False),
        "just some free text, no tag": ("other", False),
        "": None,
        "   ": None,
    }
    for reply, want in cases.items():
        p = D.parse_fix_proposal(reply)
        if want is None:
            ctx.check(f"blank reply {reply!r} -> None", p is None)
            continue
        want_kind, want_mech = want
        ctx.check(f"{reply!r} -> kind={want_kind!r}, got {p and p.kind!r}", p is not None and p.kind == want_kind)
        ctx.check(f"{reply!r} -> mechanically_appliable={want_mech}, got {p and p.mechanically_appliable}",
                  p.mechanically_appliable == want_mech)


@test
def test_propose_fix_sends_evidence_and_config_to_the_injected_model(ctx: Ctx):
    from halo_harness.mcp import doctor_deep as D
    calls = []

    def mock_call(system_text, user_text):
        calls.append((system_text, user_text))
        return "CONFIG_EDIT: env.FOO=bar"

    proposal = D.propose_fix("=== some evidence ===", {"type": "stdio", "command": "node"},
                              cwd=REPO_DIR, model_call=mock_call)
    ctx.check("exactly one model call", len(calls) == 1)
    ctx.check("the fixed system prompt was sent", calls[0][0] == D.FIX_SYSTEM_PROMPT)
    ctx.check("the user text carries the evidence and the config", "some evidence" in calls[0][1]
              and "\"command\": \"node\"" in calls[0][1])
    ctx.check(f"parsed correctly, got {proposal}", proposal.kind == "config_edit")


@test
def test_propose_fix_never_raises_when_the_model_call_fails(ctx: Ctx):
    from halo_harness.mcp import doctor_deep as D

    def boom(system_text, user_text):
        raise RuntimeError("no route to model")

    proposal = D.propose_fix("evidence", {}, cwd=REPO_DIR, model_call=boom)
    ctx.check(f"a failed call -> a non-mechanical 'other' proposal, never a raise, got {proposal}",
              proposal is not None and not proposal.mechanically_appliable)


@test
def test_failure_signature_stable_across_changing_digits_but_distinct_per_message(ctx: Ctx):
    from halo_harness.mcp import doctor_deep as D
    sig1 = D.failure_signature(command="node.exe", error_text="X missing (pid 1234)")
    sig2 = D.failure_signature(command="node.exe", error_text="X missing (pid 9999)")
    sig3 = D.failure_signature(command="node.exe", error_text="Y is completely different")
    ctx.check(f"stable across a changing digit, got {sig1} vs {sig2}", sig1 == sig2)
    ctx.check(f"distinct for a different message, got {sig1} vs {sig3}", sig1 != sig3)
    ctx.check("the command basename is part of the signature", sig1.startswith("node:"))


# ---- doctor_deep: applying a proposal (config_edit/path/url only) ---------

@test
def test_apply_fix_advisory_kinds_write_nothing(ctx: Ctx):
    from halo_harness.mcp import doctor_deep as D
    _fresh_claude_json({"advisory-srv": {"type": "stdio", "command": sys.executable, "args": FAKE_SERVER_ARGS}})
    cfg = _fake_cfg("advisory-srv")
    for proposal in (D.FixProposal(kind="install", detail="pip install x", raw_text="INSTALL: pip install x"),
                     D.FixProposal(kind="env", detail="SOME_VAR", raw_text="ENV: SOME_VAR"),
                     D.FixProposal(kind="other", detail="unparseable", raw_text="unparseable")):
        changed, msg = D.apply_fix(proposal, name="advisory-srv", cfg=cfg, cwd=REPO_DIR)
        ctx.check(f"{proposal.kind} is never auto-applied, got changed={changed} msg={msg!r}", changed is False)


@test
def test_apply_fix_config_edit_path_url_round_trip_to_disk(ctx: Ctx):
    from halo_harness.mcp import doctor_deep as D
    from halo_harness.config.claude_json import load_claude_json
    _fresh_claude_json({"mech-srv": {"type": "stdio", "command": sys.executable, "args": FAKE_SERVER_ARGS,
                                       "env": {}}})
    cfg = _fake_cfg("mech-srv")

    changed, msg = D.apply_fix(D.FixProposal(kind="config_edit", detail="env.FOO=bar", raw_text="x"),
                                 name="mech-srv", cfg=cfg, cwd=REPO_DIR)
    ctx.check(f"config_edit applied, got {msg!r}", changed is True)
    data = load_claude_json()
    ctx.check(f"env.FOO written, got {data['mcpServers']['mech-srv']}",
              data["mcpServers"]["mech-srv"]["env"]["FOO"] == "bar")

    changed2, _msg2 = D.apply_fix(D.FixProposal(kind="path", detail="C:\\real\\node.exe", raw_text="x"),
                                    name="mech-srv", cfg=cfg, cwd=REPO_DIR)
    ctx.check("path applied", changed2 is True)
    data2 = load_claude_json()
    ctx.check(f"command replaced, got {data2['mcpServers']['mech-srv']['command']}",
              data2["mcpServers"]["mech-srv"]["command"] == "C:\\real\\node.exe")

    from halo_harness.mcp.manager import McpServerConfig
    data_before = load_claude_json()
    data_before["mcpServers"]["mech-srv-url"] = {"type": "http", "url": "http://old:1/mcp"}
    from halo_harness.config.paths import claude_json_path
    claude_json_path().write_text(json.dumps(data_before), encoding="utf-8")
    url_cfg = McpServerConfig(name="mech-srv-url", type="http", url="http://old:1/mcp", scope="user")
    changed3, _msg3 = D.apply_fix(D.FixProposal(kind="url", detail="http://new:2/mcp", raw_text="x"),
                                    name="mech-srv-url", cfg=url_cfg, cwd=REPO_DIR)
    ctx.check("url applied", changed3 is True)
    data3 = load_claude_json()
    ctx.check(f"url replaced, got {data3['mcpServers']['mech-srv-url']['url']}",
              data3["mcpServers"]["mech-srv-url"]["url"] == "http://new:2/mcp")


# ---- doctor_deep.diagnose(): the whole probe -> propose -> apply -> retest
# -> learn pipeline, against a REAL fake server and a REAL scratch
# ~/.claude.json -- deliverable 3's "--apply round trips the config edit
# and the re-test" and "the learned-rule replay fixes the same signature
# without the model".

@test
def test_diagnose_apply_round_trips_the_config_edit_and_retests(ctx: Ctx):
    from halo_harness.mcp import doctor_deep as D
    _fresh_claude_json({"deepfix1": {"type": "stdio", "command": sys.executable, "args": FAKE_SERVER_ARGS,
                                        "env": {"FAKE_MCP_MODE": "needs-env"}}})
    cfg = _fake_cfg("deepfix1", mode="needs-env")
    state_dir = Path(tempfile.mkdtemp(prefix="halo-deep-state-"))

    def mock_call(system_text, user_text):
        return "CONFIG_EDIT: env.FAKE_MCP_REQUIRED_VAR=expected-value"

    result = D.diagnose("deepfix1", cfg, cwd=REPO_DIR, tool_env=dict(os.environ), state_dir=state_dir,
                          apply=True, model_call=mock_call)
    ctx.check(f"the first probe genuinely failed, got {result.verdict}", result.verdict == "failed")
    ctx.check(f"the proposal came from the model, got via_model={result.via_model}", result.via_model is True)
    ctx.check(f"the fix was applied AND verified healthy on retest, got applied={result.applied}",
              result.applied is True)

    from halo_harness.config.claude_json import load_claude_json
    on_disk = load_claude_json()
    ctx.check(f"the env var is now on disk, got {on_disk['mcpServers']['deepfix1']}",
              on_disk["mcpServers"]["deepfix1"]["env"]["FAKE_MCP_REQUIRED_VAR"] == "expected-value")

    line = D.last_diagnosis_line(state_dir, "deepfix1")
    ctx.check(f"a last-diagnosis record was persisted, got {line!r}", line and "applied" in line)


@test
def test_diagnose_without_apply_proposes_but_never_touches_disk(ctx: Ctx):
    from halo_harness.mcp import doctor_deep as D
    _fresh_claude_json({"noapplysrv": {"type": "stdio", "command": sys.executable, "args": FAKE_SERVER_ARGS,
                                          "env": {"FAKE_MCP_MODE": "needs-env"}}})
    cfg = _fake_cfg("noapplysrv", mode="needs-env")
    state_dir = Path(tempfile.mkdtemp(prefix="halo-deep-state-"))

    def mock_call(system_text, user_text):
        return "CONFIG_EDIT: env.FAKE_MCP_REQUIRED_VAR=expected-value"

    result = D.diagnose("noapplysrv", cfg, cwd=REPO_DIR, tool_env=dict(os.environ), state_dir=state_dir,
                          apply=False, model_call=mock_call)
    ctx.check(f"a fresh proposal with apply=False is shown but never applied, got applied={result.applied}",
              result.applied is False)
    from halo_harness.config.claude_json import load_claude_json
    on_disk = load_claude_json()
    ctx.check("nothing was written to disk", "FAKE_MCP_REQUIRED_VAR" not in on_disk["mcpServers"]["noapplysrv"].get(
        "env", {}))


@test
def test_diagnose_learned_rule_replay_skips_the_model_entirely(ctx: Ctx):
    """Deliverable 3: a fix that worked once is "fixed automatically next
    time" -- a SECOND, differently-named server hitting the identical
    underlying failure (same command, same stderr) is fixed with NO model
    call at all, and with no explicit `apply=True` either (the replay
    itself is the "yes" -- it already earned that the first time)."""
    from halo_harness.mcp import doctor_deep as D
    state_dir = Path(tempfile.mkdtemp(prefix="halo-deep-state-"))
    _fresh_claude_json({
        "learnsrc": {"type": "stdio", "command": sys.executable, "args": FAKE_SERVER_ARGS,
                     "env": {"FAKE_MCP_MODE": "needs-env"}},
        "learnreplay": {"type": "stdio", "command": sys.executable, "args": FAKE_SERVER_ARGS,
                        "env": {"FAKE_MCP_MODE": "needs-env"}},
    })

    def mock_call(system_text, user_text):
        return "CONFIG_EDIT: env.FAKE_MCP_REQUIRED_VAR=expected-value"

    first = D.diagnose("learnsrc", _fake_cfg("learnsrc", mode="needs-env"), cwd=REPO_DIR,
                         tool_env=dict(os.environ), state_dir=state_dir, apply=True, model_call=mock_call)
    ctx.check(f"the teaching run applied and verified, got {first.applied}", first.applied is True)

    def must_not_be_called(system_text, user_text):
        raise AssertionError("the model must never be called on a learned-rule replay")

    second = D.diagnose("learnreplay", _fake_cfg("learnreplay", mode="needs-env"), cwd=REPO_DIR,
                          tool_env=dict(os.environ), state_dir=state_dir, apply=False,
                          model_call=must_not_be_called)
    ctx.check(f"replayed, no model call, got via_model={second.via_model}", second.via_model is False)
    ctx.check(f"applied automatically with no explicit yes needed, got applied={second.applied}",
              second.applied is True)
    from halo_harness.config.claude_json import load_claude_json
    on_disk = load_claude_json()
    ctx.check("the second server's own entry was fixed too",
              on_disk["mcpServers"]["learnreplay"]["env"]["FAKE_MCP_REQUIRED_VAR"] == "expected-value")


# ---- deliverable 5: the corpus reader --------------------------------------

@test
def test_corpus_reader_on_a_fixture_directory(ctx: Ctx):
    from halo_harness.mcp import doctor_deep as D
    corpus = Path(tempfile.mkdtemp(prefix="halo-corpus-fixture-"))
    (corpus / "broken-server.log").write_text(
        "[2026-10-01 10:00:00] connect failed (failed): FileNotFoundError: [Errno 2] "
        "No such file or directory: 'ghost-cmd'\n", encoding="utf-8")
    (corpus / "broken-server.test.txt").write_text(
        "halo mcp test: broken-server: failed after 12ms -- FileNotFoundError: [Errno 2] "
        "No such file or directory: 'ghost-cmd'\n", encoding="utf-8")
    (corpus / "broken-server.config.json").write_text(
        json.dumps({"type": "stdio", "command": "ghost-cmd"}), encoding="utf-8")
    (corpus / "healthy-server.test.txt").write_text(
        "halo mcp test: healthy-server: ok in 45ms -- 3 tool(s).\n", encoding="utf-8")
    (corpus / "bugreport.txt").write_text(
        "MCP servers:\n  broken-server: failed -- FileNotFoundError\n  other-server: connected\n",
        encoding="utf-8")

    names = D.discover_corpus_servers(corpus)
    ctx.check(f"every name discovered across log/test-output/bugreport, got {names}",
              set(names) == {"broken-server", "healthy-server", "other-server"})

    def mock_call(system_text, user_text):
        ctx.check("ghost-cmd made it into the model prompt", "ghost-cmd" in user_text)
        return "INSTALL: npm install -g ghost-cmd-replacement"

    results = D.diagnose_from_corpus(corpus, model_call=mock_call)
    by_name = {r.server: r for r in results}
    ctx.check(f"broken-server diagnosed as failed, got {by_name['broken-server'].verdict}",
              by_name["broken-server"].verdict == "failed")
    ctx.check(f"a fix was proposed from the corpus evidence, got {by_name['broken-server'].proposal}",
              by_name["broken-server"].proposal is not None and by_name["broken-server"].proposal.kind == "install")
    ctx.check("nothing is ever applied from a corpus (no live server)", by_name["broken-server"].applied is False)
    ctx.check(f"healthy-server read as healthy, got {by_name['healthy-server'].verdict}",
              by_name["healthy-server"].verdict == "healthy")
    ctx.check(f"other-server (bugreport-only) read as healthy, got {by_name['other-server'].verdict}",
              by_name["other-server"].verdict == "healthy")


# ---- the CLI surface: `halo doctor --mcp deep [name] [--apply] [--from]` -

@test
def test_cli_mcp_deep_apply_round_trip(ctx: Ctx):
    """In-process (never a subprocess, so the injected mock model takes
    effect): `halo doctor --mcp deep <name> --apply` end to end."""
    from halo_harness import doctor as doctor_mod
    from halo_harness.mcp import doctor_deep as D
    _fresh_claude_json({"cliapply": {"type": "stdio", "command": sys.executable, "args": FAKE_SERVER_ARGS,
                                        "env": {"FAKE_MCP_MODE": "needs-env"}}})
    old = D._default_model_call
    D._default_model_call = lambda cwd: (
        lambda system_text, user_text: "CONFIG_EDIT: env.FAKE_MCP_REQUIRED_VAR=expected-value")
    try:
        rc = doctor_mod.cmd_doctor(["--mcp", "deep", "cliapply", "--apply", "--cwd", str(REPO_DIR)])
    finally:
        D._default_model_call = old
    ctx.check(f"exit 0 once the fix verifies, got {rc}", rc == 0)
    from halo_harness.config.claude_json import load_claude_json
    on_disk = load_claude_json()
    ctx.check("the on-disk entry carries the fix",
              on_disk["mcpServers"]["cliapply"]["env"]["FAKE_MCP_REQUIRED_VAR"] == "expected-value")


@test
def test_cli_mcp_deep_from_corpus_never_applies(ctx: Ctx):
    from halo_harness import doctor as doctor_mod
    corpus = Path(tempfile.mkdtemp(prefix="halo-cli-corpus-"))
    (corpus / "ghost.test.txt").write_text(
        "halo mcp test: ghost: failed after 5ms -- FileNotFoundError: ghost-cmd\n", encoding="utf-8")
    rc = doctor_mod.cmd_doctor(["--mcp", "deep", "--from", str(corpus), "--apply"])
    ctx.check(f"a corpus-only failing server exits nonzero, got {rc}", rc == 1)


@test
def test_cli_mcp_deep_unknown_name_reports_cleanly(ctx: Ctx):
    from halo_harness import doctor as doctor_mod
    _fresh_claude_json({})
    rc = doctor_mod.cmd_doctor(["--mcp", "deep", "no-such-server-xyz", "--cwd", str(REPO_DIR)])
    ctx.check(f"an unknown name fails cleanly (never a crash), got {rc}", rc == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
