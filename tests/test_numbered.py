"""tests.test_numbered -- 3.6.0.1 setup-words: a number a person types is ASCII 0-9 only.

`str.isdigit()` is True for '²' (int() then raises: a traceback at the terminal setup's numbered picks, `halo stop`,
`/intro`, Studio's live-agents API) and for '２' / '٢' (int() quietly reads them as 2: the second row is picked though
the person typed no ASCII number). One helper (halo_harness/numbered.py) and every site that reads a typed number.
Pure calls: no process, no network, no real home.
Run: python -m tests.test_numbered
"""

from __future__ import annotations

import os
import sys
import tempfile
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
ODD = ["²", "２", "٢", "۲", "+1", "-1", "2.", "", "   "]


def _scratch_home() -> None:
    home = tempfile.mkdtemp(prefix="numbered-")
    os.environ["BRIDGE_TEST_HOME"] = home
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"
    os.environ["HALO_NO_UPDATER"] = "1"


def _calls(fn, *a, **kw):
    try:
        return fn(*a, **kw), None
    except Exception as e:  # noqa: BLE001 -- the fault under test is an exception
        return None, f"{type(e).__name__}: {e}"


@test
def test_whole_number_takes_ascii_digits_only(ctx: Ctx):
    from halo_harness.numbered import pick, whole_number
    for s in ODD + ["１２"]:
        ctx.check(f"whole_number({s!r}) is None", whole_number(s) is None)
    for s, want in ((" 2 ", 2), ("2", 2), ("02", 2), ("10", 10)):
        ctx.check(f"whole_number({s!r}) == {want}", whole_number(s) == want)
    ctx.check("signed: '-1' -> -1", whole_number("-1", signed=True) == -1)
    for s in ("--5", "+5", "-²", "-", "- 1"):
        ctx.check(f"signed: {s!r} -> None", whole_number(s, signed=True) is None)
    ctx.check("not a string -> None", whole_number(None) is None and whole_number(3) is None)
    for s, want in (("0", None), ("4", None), ("3", 3), ("²", None), ("２", None)):
        ctx.check(f"pick({s!r}, 3) == {want}", pick(s, 3) == want)


@test
def test_the_terminal_setup_picks_never_raise_and_ask_again(ctx: Ctx):
    _scratch_home()
    from rich.console import Console
    from halo_harness import init_cli
    real = init_cli._prompt_plain
    try:
        feed = ["²", "２", "٢", "2"]
        init_cli._prompt_plain = lambda _label: feed.pop(0)
        buf = StringIO()
        got, err = _calls(init_cli._ask_number, "x", 3, 1, Console(file=buf, width=200))
        ctx.check(f"_ask_number: no exception, got {err}", err is None)
        ctx.check(f"_ask_number: the fourth answer (2), got {got!r}", got == 2)
        ctx.check("_ask_number: asked again three times", buf.getvalue().count("type a number from 1 to 3") == 3)
        feed[:] = ["²", "２", "٢", "2"]
        entries = [{"ref": "or:a"}, {"ref": "or:b"}, {"ref": "or:c"}]
        buf = StringIO()
        got, err = _calls(init_cli._numbered_model_pick, entries, Console(file=buf, width=200))
        ctx.check(f"_numbered_model_pick: no exception, got {err}", err is None)
        ctx.check(f"_numbered_model_pick: the second entry, got {got!r}", got == "or:b")
    finally:
        init_cli._prompt_plain = real
    from halo_harness import init_ollama
    buf = StringIO()
    got, err = _calls(init_ollama._pick_host, Console(file=buf, width=200), lambda _l: "²")
    ctx.check(f"_pick_host('²'): no exception, got {err}", err is None)
    ctx.check(f"_pick_host('²'): no server, got {got!r}", got is None and "no server picked" in buf.getvalue())
    buf = StringIO()
    got, err = _calls(init_ollama._pick_host, Console(file=buf, width=200), lambda _l: "١")
    ctx.check(f"_pick_host('١'): not row 1, got {got!r} {err}", err is None and got is None)


@test
def test_halo_stop_and_intro_never_raise(ctx: Ctx):
    from halo_harness import ps_cli
    from halo_harness.tui.intro_lines import parse_intro_index
    table = [{"pid": 2, "kind": "studio", "kept": False, "owner": "x"}]
    for s in ODD + [" 2 ", "2"]:
        got, err = _calls(ps_cli.pick, table, [s])
        ctx.check(f"ps_cli.pick({s!r}): no exception, got {err}", err is None)
        if err is None:
            hit = bool(got[0])
            # argv words carry no blanks: only the word '2' is pid 2 ('２' and '٢' are unknown words now)
            ctx.check(f"ps_cli.pick({s!r}): pid 2 only for an ASCII 2, got {hit}", hit == (s == "2"))
        got, err = _calls(parse_intro_index, s)
        ctx.check(f"parse_intro_index({s!r}): no exception, got {err}", err is None)
        ctx.check(f"parse_intro_index({s!r}) is 1 only for 2, got {got!r}", got == (1 if s.strip() == "2" else None))


class _Req:
    def __init__(self, query):
        self.query, self.params, self.state_dir = query, {"sid": "s", "aid": "a"}, tempfile.mkdtemp(prefix="numq-")


@test
def test_studio_number_queries_answer_422_not_500(ctx: Ctx):
    from halo_harness.studio import live_agents_api as L
    seen = []
    real = L.forward
    try:
        L.forward = lambda sid, verb, fields: seen.append(fields) or (200, {})
        for s in ["²", "２", "٢", "+1", "2.", "x"]:
            for fn, q in ((L.get_tail, {"n": s}), (L.get_history, {"n": s, "role": "r"})):
                got, err = _calls(fn, _Req(q))
                ctx.check(f"{fn.__name__}(n={s!r}): no exception, got {err}", err is None)
                ctx.check(f"{fn.__name__}(n={s!r}): 422, got {got!r}"[:200], got is not None and got[0] == 422)
        got, err = _calls(L.get_tail, _Req({"n": " 2 "}))
        ctx.check(f"get_tail(n=' 2 ') reaches forward with n=2, got {got} {err} {seen}",
                  err is None and seen and seen[-1].get("n") == 2)
    finally:
        L.forward = real


@test
def test_a_typed_cron_step_never_raises(ctx: Ctx):
    from halo_harness.agents_yaml import valid_cron_field
    for s, want in (("2", True), ("²", False), ("２", False), ("٢", False), ("0", False)):
        got, err = _calls(valid_cron_field, "*/" + s)
        ctx.check(f"valid_cron_field('*/{s}'): no exception, got {err}", err is None)
        ctx.check(f"valid_cron_field('*/{s}') == {want}, got {got!r}", got is want)
    for f in ("２", "1-２", "٢"):
        got, err = _calls(valid_cron_field, f)
        ctx.check(f"valid_cron_field({f!r}) is False, got {got!r} {err}", err is None and got is False)


@test
def test_the_signal_packs_phone_pick_never_raises(ctx: Ctx):
    sys.path.insert(0, str(REPO / "halo_harness" / "templates" / "packs" / "signal"))
    try:
        from halo_signal import ctl
    except Exception as e:  # noqa: BLE001
        ctx.check(f"halo_signal.ctl imports, got {type(e).__name__}: {e}", False)
        return

    class _P:
        def peers(self):
            return {"aci-a": {"paired_at": 1}, "aci-b": {"paired_at": 2}, "aci-c": {"paired_at": 3}}
    for s in ["²", "２", "٢", "2"]:
        got, err = _calls(ctl._pick, _P(), s)
        ctx.check(f"ctl._pick({s!r}): no exception, got {err}", err is None)
        if err is None:
            ctx.check(f"ctl._pick({s!r}): the second phone only for 2, got {got!r}",
                      (got[0] == "aci-b") == (s == "2"))


@test
def test_every_other_typed_number_site_gives_its_own_answer(ctx: Ctx):
    from halo_harness.local_pool.members import parse_target
    got, err = _calls(parse_target, "gpu-box:²")
    ctx.check(f"parse_target('gpu-box:²'): the bad-port answer, got {got!r} {err}", err is None and got == ("gpu-box", -1))
    got, err = _calls(parse_target, "[::1]:²")
    ctx.check(f"parse_target('[::1]:²'): the bad-port answer, got {got!r} {err}", err is None and got == ("::1", -1))
    from halo_harness.remote.client import parse_endpoint
    got, err = _calls(parse_endpoint, "tcp:gpu-box:²")
    ctx.check(f"parse_endpoint('tcp:gpu-box:²'): its own refusal, got {err}", err and "unrecognised control endpoint" in err)
    from halo_harness.peers.relay import parse_url
    got, err = _calls(parse_url, "http://gpu-box:²")
    ctx.check(f"parse_url(':²'): its own refusal, got {err}", err and "bad port" in err)
    from halo_harness.whatsnew_cli import _vkey
    got, err = _calls(_vkey, "3.².0")
    ctx.check(f"_vkey('3.².0') never raises, got {got!r} {err}", err is None and got == (3, 0, 0))
    from halo_harness.studio import pool_act_api
    for s, want in (("²", None), ("２", None), (" 7 ", 7)):
        got, err = _calls(pool_act_api._int, s)
        ctx.check(f"pool_act_api._int({s!r}) == {want}, got {got!r} {err}", err is None and got == want)
    from halo_harness.studio.settings_values import coerce
    for s in ("²", "-²", "--5", "２"):
        got, err = _calls(coerce, "int", None, s, "k")
        ctx.check(f"settings coerce int {s!r}: 'not a whole number', got {got!r} {err}",
                  err is None and got[0] is None and "not a whole number" in " ".join(got[1]))
    got, err = _calls(coerce, "int", None, " -5 ", "k")
    ctx.check(f"settings coerce int ' -5 ' -> -5, got {got!r} {err}", err is None and got == (-5, []))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="numbered tests"))
