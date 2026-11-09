"""tests.test_steward_profiles_reset -- Halo 3.3.13.1, the steward hotfix (d): a model's profile back to the
measured defaults (ollama_steward/profiles_reset.py): `halo ollama steward profiles reset [<model>]` drops the tuned
fields, says what it dropped (an absurd value by its size), keeps the other models' profiles, marks every change in
force on it reverted so no rollback or session end puts a dropped value back; `profiles` lists; Studio's
POST ollama/steward/profiles-reset does the same.
A fresh home; nothing is sent anywhere.
Run: python -m tests.test_steward_profiles_reset
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home  # noqa: E402

test, TESTS = new_registry()
KEY, OTHER = "pc|qwen3.8:27b", "pc|qwen3.5:9b"


def _seed(h) -> None:
    from halo_harness.ollama_steward import changes, steward
    from halo_harness.theme import set_config_value
    set_config_value("ollama.profiles", {KEY: {"num_predict": 2 ** 160, "num_ctx": 65536, "by": "steward"},
                                         OTHER: {"num_ctx": 16384, "by": "user"}})
    row = steward._append(h.state, {"id": "c-runaway", "kind": "apply", "key": KEY, "field": "num_predict",
                                    "from": 2 ** 159, "to": 2 ** 160, "why": "room", "finding": "cut-resent-x"})
    changes.record(h.state, by="steward", key=KEY, field="num_predict", before=2 ** 159, after=2 ** 160,
                   scope="until-restart", why="room", id=row["id"], journal_id=row["id"])


def _profiles() -> dict:
    from halo_harness.ollama_steward.profiles import all_profiles
    return all_profiles()


def _cli(*argv) -> "tuple[int, str]":
    from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = cmd_ollama_steward(list(argv))
    return rc, out.getvalue()


@test
def test_reset_drops_the_tuned_fields_and_says_what(ctx: Ctx):
    from halo_harness.ollama_steward import changes, steward
    with Home() as h:
        _seed(h)
        rc, out = _cli("profiles")
        ctx.check(f"`profiles` lists both, the absurd value by its size, got {out!r}",
                  rc == 0 and KEY in out and OTHER in out and "49 digits" in out)
        rc, out = _cli("profiles", "reset", "qwen3.8:27b")
        ctx.check(f"one line naming what it dropped, got {out!r}",
                  rc == 0 and f"reset {KEY}: dropped num_ctx 65,536, num_predict 1461... (49 digits)" in out
                  and "measured window" in out)
        ctx.check(f"that profile is gone, the other kept, got {_profiles()}",
                  KEY not in _profiles() and _profiles().get(OTHER, {}).get("num_ctx") == 16384)
        ctx.check("its change in force is marked reverted", not [r for r in changes.in_force(h.state) if r["key"] == KEY])
        ctx.check("the steward's journal has nothing in place to roll back",
                  not [r for r in steward._in_place(steward.read_journal(h.state)) if r.get("key") == KEY])
        rc, out = _cli("profiles", "reset", "qwen3.8:27b")
        ctx.check(f"again: nothing to reset, got {out!r}", "nothing to reset" in out)


@test
def test_reset_every_profile_and_the_studio_route(ctx: Ctx):
    from halo_harness.studio.ollama_steward_api import dispatch_ollama
    with Home() as h:
        _seed(h)
        req = SimpleNamespace(path="ollama/steward/profiles-reset", method="POST", body={"model": "qwen3.5:9b",
                                                                                           "host": "pc"},
                              state_dir=h.state)
        status, body = dispatch_ollama(req)
        ctx.check(f"Studio's Reset: 200 and the line, got {status} {body}",
                  status == 200 and body["reset"] == [{"key": OTHER, "dropped": {"num_ctx": "16,384"}}]
                  and "reset pc|qwen3.5:9b" in body["say"])
        ctx.check("only that model", KEY in _profiles() and OTHER not in _profiles())
        rc, out = _cli("profiles", "reset", "--json")
        ctx.check(f"no model: every profile, as JSON, got {out!r}", rc == 0 and '"key": "pc|qwen3.8:27b"' in out
                  and not _profiles())


@test
def test_a_window_or_reserve_past_2m_is_never_written(ctx: Ctx):
    from halo_harness.ollama_steward.profiles import clean, set_field
    with Home():
        ctx.check("clean drops a 2^160 reserve", "num_predict" not in clean({"num_predict": 2 ** 160}))
        ctx.check("a reserve over the window is held to it", clean({"num_ctx": 8192, "num_predict": 16384})
                  == {"num_ctx": 8192, "num_predict": 8192})
        got = set_field(KEY, "num_predict", 2 ** 22)
        ctx.check(f"set_field writes no absurd value, got {got}", "num_predict" not in got)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
