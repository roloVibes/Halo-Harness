"""tests.test_steward_profiles -- Halo 3.3.4.0 R3: the profiles and the
modes (ollama_steward/profiles.py, steward.py): `run` in auto, review and
off; `apply <id>`; `undo`; the ten-minute rule; never above a measured cap;
a change followed by worse calls rolled back on its own; the decision a call
reads (`resolve_context_decision`: the profile's window, held under the
learned cap); the session's one line for a fresh steward change; the hub
handing its profiles to a member over the fleet rig (never over the
member's own `by: "user"` entry).
Run: python -m tests.test_steward_profiles
"""
from __future__ import annotations

import contextlib
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import PC, Home, at, line  # noqa: E402

test, TESTS = new_registry()
KEY = "pc|qwen3.8:27b"


def _small_window(h) -> None:
    h.cap("qwen3.8:27b", 65536)
    h.calls(*[line(prompt_eval_count=31000, ago=3600 - i, session=None) for i in range(5)])


@contextlib.contextmanager
def _no_reads():
    """The CLI's card and catalog readers stubbed: no request to a 192.0.2.x host."""
    from halo_harness.ollama_steward import cli_steward
    saved = cli_steward._readers
    cli_steward._readers = lambda: {"card_reader": None, "catalog_reader": None}
    try:
        yield
    finally:
        cli_steward._readers = saved


def _profiles():
    from halo_harness.ollama_steward.profiles import all_profiles
    return all_profiles()


@test
def test_auto_applies_and_says_one_line(ctx: Ctx):
    from halo_harness.ollama_steward import steward
    with Home() as h:
        _small_window(h)
        said = []
        done = steward.run(h.state, mode_name="auto", say=said.append)
        prof = _profiles().get(KEY) or {}
        ctx.check(f"the window raised in the profile, by the steward, got {prof}",
                  prof.get("num_ctx") == 65536 and prof.get("by") == "steward" and prof.get("note"))
        ctx.check(f"one line said, got {said}", len(said) == 1 and "num_ctx 65536 for qwen3.8:27b on pc" in said[0])
        rows = steward.read_journal(h.state)
        ctx.check(f"one journal line: what, why, the evidence, got {rows[-1] if rows else None}",
                  len(rows) == 1 and rows[0]["kind"] == "apply" and rows[0]["from"] is None and rows[0]["to"] == 65536
                  and rows[0]["evidence"]["numbers"] and done["applied"])
        from halo_harness.providers.ollama import resolve_ollama_hosts
        other = {"id": "reply-cut-1", "rule": "reply-cut", "key": KEY, "host": "pc", "model": "qwen3.8:27b",
                 "proposal": {"field": "num_predict", "from": None, "to": 4096, "why": "a test"}}
        change, why = steward.check(h.state, other, hosts=resolve_ollama_hosts(), now=time.time())
        ctx.check(f"at most one change per model per ten minutes, got {why!r}", change is None and "ten minutes" in why)
        change, why = steward.check(h.state, other, hosts=resolve_ollama_hosts(), now=time.time() + 601)
        ctx.check(f"and after ten minutes it may, got {change}", change and change["to"] == 4096)


@test
def test_review_proposes_and_apply_by_id(ctx: Ctx):
    from halo_harness.ollama_steward import steward
    from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
    with Home() as h:
        _small_window(h)
        done = steward.run(h.state, mode_name="review", say=lambda s: None)
        ctx.check("review writes a proposal, changes nothing", done["proposed"] and KEY not in _profiles())
        fid = done["proposed"][0]["id"]
        out = io.StringIO()
        with contextlib.redirect_stdout(out), _no_reads():
            code = cmd_ollama_steward(["apply", fid])
        ctx.check(f"`apply <id>` applies it, got {code} {out.getvalue()!r}",
                  code == 0 and (_profiles().get(KEY) or {}).get("num_ctx") == 65536)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), _no_reads():
            code = cmd_ollama_steward(["apply", "window-small-nothere"])
        ctx.check(f"an unknown id: exit 1 and why, got {out.getvalue()!r}", code == 1 and "no finding" in out.getvalue())
    with Home(extra={"ollama": {"steward": {"apply": "off"}}}) as h:
        _small_window(h)
        done = steward.run(h.state, say=lambda s: None)
        ctx.check(f"off (from config): findings only, got {done['mode']}", done["mode"] == "off" and done["findings"]
                  and not steward.read_journal(h.state) and KEY not in _profiles())


@test
def test_the_run_and_undo_commands(ctx: Ctx):
    from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
    with Home() as h:
        _small_window(h)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), _no_reads():
            code = cmd_ollama_steward(["run", "--once"])
        text = out.getvalue()
        ctx.check(f"run --once: the change said, then the summary, got {text!r}",
                  code == 0 and "steward: num_ctx 65536" in text and "1 applied" in text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_ollama_steward(["undo"])
            cmd_ollama_steward(["undo"])
        ctx.check(f"undo says what went back, then that nothing is left, got {out.getvalue()!r}",
                  "steward undo: num_ctx back to None" in out.getvalue() and "nothing to undo" in out.getvalue())


@test
def test_undo_reverts_the_newest_change(ctx: Ctx):
    from halo_harness.ollama_steward import steward
    with Home() as h:
        from halo_harness.ollama_steward.profiles import set_field
        set_field(KEY, "num_predict", 4096, by="user")
        _small_window(h)
        steward.run(h.state, mode_name="auto", say=lambda s: None)
        row = steward.undo_last(h.state)
        prof = _profiles().get(KEY) or {}
        ctx.check(f"the window back to unset, the user's field kept, got {prof}",
                  "num_ctx" not in prof and prof.get("num_predict") == 4096 and row["kind"] == "undo")
        ctx.check("nothing more to undo", steward.undo_last(h.state) is None)


@test
def test_never_above_a_measured_cap(ctx: Ctx):
    from halo_harness.ollama_steward import steward
    with Home(hosts=[{**PC, "max_ctx": 49152}]) as h:
        _small_window(h)
        f = {"id": "x-1", "rule": "window-small", "key": KEY, "host": "pc", "model": "qwen3.8:27b",
             "proposal": {"field": "num_ctx", "from": None, "to": 131072, "why": "a test"}}
        from halo_harness.providers.ollama import resolve_ollama_hosts
        change, _why = steward.check(h.state, f, hosts=resolve_ollama_hosts(), now=time.time())
        ctx.check(f"held under max_ctx 49,152 (the learned cap is 65,536), got {change}", change["to"] == 49152)


@test
def test_a_change_followed_by_worse_calls_rolls_back(ctx: Ctx):
    from halo_harness.ollama_steward import steward
    with Home() as h:
        h.calls(*[line(prompt_eval_count=9000, ago=7200 - i, session=None) for i in range(10)])
        _small_window(h)
        steward.run(h.state, mode_name="auto", say=lambda s: None)
        h.calls(*[line(prompt_eval_count=9000, status=500 if i < 3 else 200, ago=-5 - i, session=None)
                  for i in range(10)])
        said = []
        done = steward.run(h.state, mode_name="auto", say=said.append, now=time.time() + 700)
        ctx.check(f"rolled back and said so, got {said}", done["rolled_back"] and "rollback" in said[0]
                  and "3 bad calls of the next 10" in said[0])
        ctx.check(f"the window is back, got {_profiles().get(KEY)}", "num_ctx" not in (_profiles().get(KEY) or {}))


@test
def test_the_decision_a_call_reads(ctx: Ctx):
    """What `resolve_context_decision` reads (`ollama_hw._apply_profile`): the
    profile's window wins over the estimate, never over the learned cap (the
    wire is pinned by tests/test_ollama_window_steward.py)."""
    from halo_harness.ollama_steward.profiles import set_field
    from halo_harness.providers import ollama_hw
    with Home(hosts=[{**PC, "url": "http://192.0.2.10:11434"}]) as h:
        h.cap("qwen3.8:27b", 32768)
        set_field(KEY, "num_ctx", 65536, by="user")
        prof, fit = ollama_hw._apply_profile(type("H", (), {"name": "pc", "url": PC["url"]})(), "qwen3.8:27b", None,
                                             learned_cap=32768, host_max_ctx=None, trained=262144)
        ctx.check(f"held under the learned cap, got {fit} {prof}", fit == 32768 and prof["num_ctx"] == 32768)
        set_field(KEY, "num_ctx", 16384, by="user")
        prof, fit = ollama_hw._apply_profile(type("H", (), {"name": "pc", "url": PC["url"]})(), "qwen3.8:27b", 49152,
                                             learned_cap=32768, host_max_ctx=None, trained=262144)
        ctx.check(f"under the cap it wins over the estimate (49,152), got {fit}", fit == 16384)


@test
def test_a_fresh_steward_change_is_said_once_in_the_session(ctx: Ctx):
    from halo_harness.agent.ollama_window_steward import note_prepared
    from halo_harness.ollama_steward.ledger import now_iso

    class S:
        _pending_ollama_notices: list = []
    s = S()
    s._pending_ollama_notices = []
    prof = {"by": "steward", "at": now_iso(), "note": "steward: num_ctx 65536 for qwen3.8:27b on pc (3 trims)"}
    st = {"last": {"profile": prof}}
    note_prepared(st, 1000, 100, s)
    note_prepared(st, 1000, 100, s)
    ctx.check(f"said once, got {s._pending_ollama_notices}", s._pending_ollama_notices == [prof["note"]])
    st2 = {"last": {"profile": {**prof, "at": at(7200)}}}
    note_prepared(st2, 1000, 100, s)
    ctx.check("an old change is not said again", len(s._pending_ollama_notices) == 1)


@test
def test_the_hub_hands_its_profiles_to_a_member(ctx: Ctx):
    """The hub (A) keys its profile by its own host; the member (B) calls the
    same server by another name ("lan"); B keeps it as `lan|...` with by
    "hub", and its own "user" entry stays."""
    import json
    from halo_harness.fleet import ollama_share
    from tests.helpers.fleet_hub_rig import HubRig, wait_for
    saved = (ollama_share.FLUSH_S, ollama_share.CHECK_S, dict(ollama_share._OWN))
    ollama_share.FLUSH_S, ollama_share.CHECK_S = 0.2, 0.05
    try:
        with HubRig() as rig:
            cfg = json.loads((rig.home_a / "config.json").read_text(encoding="utf-8"))
            cfg["ollama"] = {"hosts": [{"name": "pc", "url": "http://127.0.0.1:11434"}],
                             "profiles": {KEY: {"num_ctx": 65536, "num_predict": 4096, "by": "steward", "at": at()},
                                          "pc|qwen3-coder:30b": {"num_ctx": 32768, "by": "steward", "at": at()}}}
            (rig.home_a / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
            rig.set_b(**{"fleet.ollama.share": "all", "ollama.profiles": {
                "lan|qwen3-coder:30b": {"num_ctx": 16384, "by": "user"}}})
            own = set(ollama_share.own_addresses()) | {"192.0.2.10"}
            ollama_share._OWN.update(at=time.monotonic() + 3600, set=own)
            rig.join()
            from halo_harness.config.paths import bridge_home
            from halo_harness.ollama_steward import ledger
            ledger.record_call(bridge_home(), {"host": {"name": "lan", "url": "http://192.0.2.10:11434"},
                                               "model": "qwen3.8:27b", "status": 200})
            ledger.record_call(bridge_home(), {"host": {"name": "lan", "url": "http://192.0.2.10:11434"},
                                               "model": "qwen3-coder:30b", "status": 200})
            _controller, act = rig.session()
            wait_for(lambda: rig.member_session(act.session_id))
            got = wait_for(lambda: (_profiles().get("lan|qwen3.8:27b") or None), timeout=20)
            ctx.check(f"B keeps the hub's profile under its own host name, by hub, got {got}",
                      got and got.get("num_ctx") == 65536 and got.get("by") == "hub")
            mine = _profiles().get("lan|qwen3-coder:30b") or {}
            ctx.check(f"B's own user entry stays, got {mine}", mine.get("num_ctx") == 16384 and mine.get("by") == "user")
    finally:
        ollama_share.FLUSH_S, ollama_share.CHECK_S = saved[0], saved[1]
        ollama_share._OWN.clear()
        ollama_share._OWN.update(saved[2])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
