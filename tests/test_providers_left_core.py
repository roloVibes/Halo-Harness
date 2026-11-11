"""tests.test_providers_left_core -- 3.4.0.0 "The core", round A: TypeSafe left the core
(halo_harness/providers/left_core.py). What is left of it in someone's setup is ignored with one line, never an
error: a `ts:` ref (a `--model`, a lineup card), `TYPESAFE_API_KEY` in the env or a settings env block, a
`providers.typesafe` row in config.json, `halo providers enable|disable|setup typesafe`, `/providers enable
typesafe`. With nothing left over, nothing is said. The `cc:`/`cx:` line (3.1.5.0) keeps its words.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

_VARS = ("OPENROUTER_API_KEY", "DATABRICKS_HOST", "DATABRICKS_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
         "TYPESAFE_API_KEY", "EXPLABS_API_KEY", "HF_TOKEN", "BRIDGE_TEST_CC_AUTH_STATUS")
WORDS = "left the core in 3.4.0.0"


class _Env:
    """A scratch home; every provider variable it touches is restored."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_ENV_FILE") + _VARS}
        d = Path(tempfile.mkdtemp(prefix="left-core-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["BRIDGE_ENV_FILE"] = str(d / "no-env-file")
        for k in _VARS:
            os.environ.pop(k, None)
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": False})
        self.home = d
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _run(fn, *args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = fn(*args)
    return rc, out.getvalue(), err.getvalue()


@test
def test_a_ts_ref_gets_one_line_and_cc_keeps_its_words(ctx: Ctx):
    from halo_harness.model import InvalidModelError, parse_model_ref
    with _Env():
        try:
            parse_model_ref("ts:jev-latest", {})
            got = ""
        except InvalidModelError as e:
            got = str(e)
        ctx.check(f"ts: is refused with the left-the-core line, got {got!r}", WORDS in got and "ts:jev-latest" in got
                  and "\n" not in got)
        try:
            parse_model_ref("cc:sonnet", {})
            cc = ""
        except InvalidModelError as e:
            cc = str(e)
        ctx.check(f"cc: keeps the 3.1.5.0 line, got {cc!r}", "removed in 3.1.5.0" in cc)


@test
def test_a_ts_card_in_a_lineup_falls_through_with_the_line(ctx: Ctx):
    from halo_harness.teams_yaml import resolve_role_table
    with _Env():
        table, notes = resolve_role_table({"name": "t", "agents": [
            {"agent": "default-model", "role": "main"},
            {"agent": "default-model", "role": "coder", "models": {"preference": "ts:jev-latest"}}]})
        ctx.check(f"the ts: card is left out of the table, got {table}", "coder" not in table)
        ctx.check(f"... with the line in its note, got {notes}", any(WORDS in n for n in notes))


@test
def test_nothing_left_over_says_nothing(ctx: Ctx):
    from halo_harness.providers.left_core import leftover_lines
    from halo_harness.providers_cli import cmd_providers
    with _Env():
        ctx.check(f"no leftovers, got {leftover_lines()}", leftover_lines() == [])
        rc, out, _err = _run(cmd_providers, [])
        ctx.check(f"halo providers: exit 0, no TypeSafe word, got {out!r}", rc == 0 and "typesafe" not in out.lower())
        from halo_harness.commands.builtins import _BUILTIN_SPECS, HeadlessFacade
        table = _BUILTIN_SPECS["providers"][3]("", HeadlessFacade(cwd=Path.cwd()))
        ctx.check(f"/providers: no TypeSafe row, got {table!r}", "typesafe" not in table.lower())


@test
def test_no_typesafe_tab_and_a_leftover_key_configures_nothing(ctx: Ctx):
    from halo_harness.init_providers import TAB_PROVIDERS, tab_credential_state
    from halo_harness.studio.setup_providers_state import KEY_FIELDS
    with _Env():
        ctx.check(f"no init tab, no Studio card, got {TAB_PROVIDERS}", "typesafe" not in TAB_PROVIDERS + tuple(KEY_FIELDS))
        os.environ["TYPESAFE_API_KEY"] = "fake-secret-value"
        gone = tab_credential_state("typesafe")
        ctx.check(f"a leftover TYPESAFE_API_KEY configures nothing, got {gone}",
                  gone["configured"] is False and gone["fields"] == [])


@test
def test_a_leftover_key_or_row_is_one_line_in_providers_and_doctor(ctx: Ctx):
    from halo_harness.doctor import _check_entries
    from halo_harness.providers.enablement import credentials_present, is_enabled
    from halo_harness.providers.left_core import leftover_lines
    from halo_harness.providers_cli import cmd_providers
    with _Env():
        os.environ["TYPESAFE_API_KEY"] = "ts-leftover"
        ctx.check("the key enables nothing", not credentials_present("typesafe") and not is_enabled("typesafe"))
        ctx.check(f"one line, got {leftover_lines()}", len(leftover_lines()) == 1 and WORDS in leftover_lines()[0])
        rc, out, _err = _run(cmd_providers, [])
        ctx.check(f"halo providers says it once and exits 0, got {rc} {out!r}", rc == 0 and out.count(WORDS) == 1)
        ctx.check("the key itself is never printed", "ts-leftover" not in out)
        rows = [line for rid, line in _check_entries() if rid == "left_core"]
        ctx.check(f"halo doctor: one [WARN] row, got {rows}", len(rows) == 1 and rows[0].startswith("[WARN]")
                  and WORDS in rows[0])
    with _Env():
        from halo_harness.theme import set_config_value
        set_config_value("providers", {"typesafe": {"enabled": True}})
        ctx.check(f"a providers.typesafe row is the same one line, got {leftover_lines()}", len(leftover_lines()) == 1)
        rc, out, _err = _run(cmd_providers, [])
        ctx.check(f"no error on the leftover row, got {rc}", rc == 0)


@test
def test_halo_providers_verbs_on_typesafe_say_the_line(ctx: Ctx):
    from halo_harness.providers_cli import cmd_providers
    with _Env():
        rc, _out, err = _run(cmd_providers, ["enable", "typesafe"])
        ctx.check(f"enable: exit 1 and the line, got {rc} {err!r}", rc == 1 and WORDS in err and "unknown" not in err)
        rc, _out, err = _run(cmd_providers, ["disable", "typesafe"])
        ctx.check(f"disable: exit 0 (it is off already) and the line, got {rc} {err!r}", rc == 0 and WORDS in err)
        rc, _out, err = _run(cmd_providers, ["setup", "typesafe"])
        ctx.check(f"setup: exit 1 and the line, got {rc} {err!r}", rc == 1 and WORDS in err)
        rc, _out, err = _run(cmd_providers, ["enable", "nosuch"])
        ctx.check(f"another name stays 'unknown provider', got {rc} {err!r}", rc == 2 and "unknown provider" in err)


@test
def test_slash_providers_enable_typesafe_says_the_line(ctx: Ctx):
    from halo_harness.commands.builtins import _BUILTIN_SPECS, HeadlessFacade
    with _Env():
        run = _BUILTIN_SPECS["providers"][3]
        got = run("enable typesafe", HeadlessFacade(cwd=Path.cwd()))
        ctx.check(f"/providers enable typesafe: the line, got {got!r}", WORDS in got)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
