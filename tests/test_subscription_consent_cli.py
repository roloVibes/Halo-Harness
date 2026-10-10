"""tests.test_subscription_consent_cli -- Halo 2.0.7 fix pass round 7b:
`halo subscriptions`, `halo doctor`/`/providers`'s status line, and a
lineup naming a cc:/cx: model falling back to the default model with a
one-line note. Companion to test_subscription_consent.py (the gate
itself + model.parse_model_ref). No network, no real binary.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_ENV_FILE", "BRIDGE_TEST_CC_AUTH_STATUS",
          "BRIDGE_TEST_CODEX_LOGIN_STATUS", "ANTHROPIC_API_KEY")


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _VARS}
        d = Path(tempfile.mkdtemp(prefix="subs-consent-cli-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["BRIDGE_ENV_FILE"] = str(d / "no-env-file")
        os.environ.pop("ANTHROPIC_API_KEY", None)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# halo subscriptions (CLI).
# ---------------------------------------------------------------------------

@test
def test_cli_status_reports_off(ctx: Ctx):
    from halo_harness.subscriptions_cli import cmd_subscriptions
    with _Env():
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_subscriptions(["status"])
        ctx.check(f"exit 0, got {rc}", rc == 0)
        ctx.check(f"reports off, got {buf.getvalue()!r}", "off (not accepted)" in buf.getvalue())


def _patch_read_typed_acceptance(reply_or_eof):
    """Patches the exact name `subscriptions_cli.cmd_subscriptions` calls
    (`from halo_harness.subscription_consent import ... read_typed_
    acceptance ...`) -- NOT `builtins.input`, which `read_typed_
    acceptance(prompt=input)`'s own default argument already bound to the
    real builtin at function-definition time, long before any test could
    patch it. `reply_or_eof is EOFError` (the class, not an instance)
    simulates the real function's OWN already-caught "nothing to read"
    outcome -- a plain False, exactly what `read_typed_acceptance` itself
    returns for a non-interactive stdin, never a raised exception
    `cmd_subscriptions` would have to catch."""
    import halo_harness.subscriptions_cli as cli_mod
    real = cli_mod.read_typed_acceptance
    if reply_or_eof is EOFError:
        def _fake(prompt=None):
            return False
    else:
        def _fake(prompt=None):
            return (reply_or_eof or "").strip() == "I accept"
    cli_mod.read_typed_acceptance = _fake
    return real


@test
def test_cli_accept_with_noninteractive_stdin_stays_off(ctx: Ctx):
    from halo_harness.subscription_consent import is_accepted
    from halo_harness.subscriptions_cli import cmd_subscriptions
    import halo_harness.subscriptions_cli as cli_mod
    with _Env():
        real = _patch_read_typed_acceptance(EOFError)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cmd_subscriptions(["accept"])
        finally:
            cli_mod.read_typed_acceptance = real
        ctx.check(f"exit 1 (declined), got {rc}", rc == 1)
        ctx.check("still not accepted", is_accepted() is False)


@test
def test_cli_accept_with_the_exact_phrase_accepts(ctx: Ctx):
    from halo_harness.subscription_consent import is_accepted
    from halo_harness.subscriptions_cli import cmd_subscriptions
    import halo_harness.subscriptions_cli as cli_mod
    with _Env():
        real = _patch_read_typed_acceptance("I accept")
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cmd_subscriptions(["accept"])
        finally:
            cli_mod.read_typed_acceptance = real
        ctx.check(f"exit 0, got {rc}", rc == 0)
        ctx.check("now accepted", is_accepted() is True)


@test
def test_cli_accept_with_the_wrong_text_stays_off(ctx: Ctx):
    from halo_harness.subscription_consent import is_accepted
    from halo_harness.subscriptions_cli import cmd_subscriptions
    import halo_harness.subscriptions_cli as cli_mod
    with _Env():
        real = _patch_read_typed_acceptance("sure, why not")
        try:
            with redirect_stdout(io.StringIO()):
                rc = cmd_subscriptions(["accept"])
        finally:
            cli_mod.read_typed_acceptance = real
        ctx.check(f"exit 1, got {rc}", rc == 1)
        ctx.check("stays off", is_accepted() is False)


@test
def test_cli_revoke(ctx: Ctx):
    from halo_harness.subscription_consent import is_accepted, record_acceptance
    from halo_harness.subscriptions_cli import cmd_subscriptions
    with _Env():
        record_acceptance()
        with redirect_stdout(io.StringIO()):
            rc = cmd_subscriptions(["revoke"])
        ctx.check(f"exit 0, got {rc}", rc == 0)
        ctx.check("off again", is_accepted() is False)


# ---------------------------------------------------------------------------
# doctor / /providers.
# ---------------------------------------------------------------------------

@test
def test_doctor_check_reports_off_then_on(ctx: Ctx):
    from halo_harness import doctor
    from halo_harness.subscription_consent import record_acceptance
    with _Env():
        line = doctor._check_subscription_consent()
        ctx.check(f"OK + off, got {line!r}", line.startswith(doctor.OK) and "off (not accepted)" in line)
        record_acceptance()
        line2 = doctor._check_subscription_consent()
        ctx.check(f"OK + on, got {line2!r}", "on (accepted" in line2)


@test
def test_providers_table_includes_the_status_line(ctx: Ctx):
    from halo_harness.providers_cli import cmd_providers
    with _Env():
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_providers(["list"])
        ctx.check(f"status line present, got {buf.getvalue()!r}", "subscription routes:" in buf.getvalue())


# ---------------------------------------------------------------------------
# A lineup naming cc:/cx: with routes off -> default model, one-line note.
# ---------------------------------------------------------------------------

@test
def test_lineup_naming_cc_falls_back_with_a_note(ctx: Ctx):
    from halo_harness import teams_yaml
    with _Env():
        template = {"agents": [{"agent": "worker", "role": "subagent", "as": "worker"}]}
        bios = {"worker": {"models": {"preference": "cc:opus"}}}

        def _fake_resolve_agent_bio(name, *, cwd=None, state_dir=None):
            return bios.get(name)

        import halo_harness.agents_yaml as agents_yaml_mod
        real_resolve_bio = agents_yaml_mod.resolve_agent_bio
        agents_yaml_mod.resolve_agent_bio = _fake_resolve_agent_bio
        try:
            role_table, notes = teams_yaml.resolve_role_table(template)
        finally:
            agents_yaml_mod.resolve_agent_bio = real_resolve_bio
        ctx.check(f"cc: role left out of the table, got {role_table}", "worker" not in role_table)
        ctx.check(f"a one-line note names acceptance, got {notes}",
                  any("available after acceptance" in n for n in notes))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
