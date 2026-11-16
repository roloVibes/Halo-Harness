"""tests.test_studio_attention_open -- "open" on an ask that waits on you lands where the ask can be answered (Halo 3.6.0.1;
the owner's report from live use of 3.6.0.0: "when I get an attention alert and chose 'open' nothing happens"), in
headless Chrome through tests/helpers/studio_attention_open.py (skipped without Chrome); no model call.

ONE door, used by an Attention row's O, the Live ask card's O and the alert's click: Session, the row's session
selected, the Feed pointed at the asking agent (the Live column's agent pick), the Attention drawer open with that row
selected and its answers there -- from Session on another session with the drawers open, from Session showing only the
Feed, from Agents -> Map on the session's map and on another map, and from Local. The other kinds of row keep their
homes (the steward's note opens Local); a row whose session has ended says so in one toast line, never silently.
Run: python -m tests.test_studio_attention_open
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_attention_open", why="the doors need headless Chrome", cache=_RUN, timeout=600)


def _key(got: dict) -> str:
    """The asking agent's key, as the driver names it: `<harness>|<the asking session>|main`."""
    return str(got.get("key") or "")


def _landed(ctx: Ctx, got: dict, case: str, what: str) -> None:
    p = got.get(case) or {}
    row = got.get("row") or ""
    key = _key(got)
    ctx.check(f"{what}: Session, got {p.get('section')!r}", p.get("section") == "session")
    ctx.check(f"{what}: the asking session shown and its agent in the Feed, got {p.get('sessions')!r} {p.get('pin')!r}",
              bool(key) and p.get("pin") == key and p.get("sessions") == [key.split("|")[1]])
    ctx.check(f"{what}: Attention open on that row with its answers, got {p.get('attn_open')!r} {p.get('row')!r} {p.get('keys')!r}",
              p.get("attn_open") is True and bool(row) and p.get("row") == row and "a" in (p.get("keys") or []))


@test
def test_the_alert_click_lands_on_the_ask_from_anywhere(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the ask made one notification: {got.get('row')!r}", bool(got.get("row")))
    before = got.get("alert_b_before") or {}
    ctx.check(f"(b) started on the other session, every agent, Attention closed: {before}",
              before.get("sessions") == ["attnopenother000000000000000002"] and before.get("pin") == "" and before.get("attn_open") is False)
    _landed(ctx, got, "alert_b", "the alert from Session showing only the other session's Feed")
    _landed(ctx, got, "alert_e", "the alert from Local")
    ctx.check(f"(d) the open map was another one: {got.get('alert_d_map')!r}", got.get("alert_d_map") == "ship-it")
    _landed(ctx, got, "alert_d", "the alert from Agents -> Map on another map")


@test
def test_a_rows_o_lands_on_the_ask_from_session(ctx: Ctx):
    got = _got(ctx)
    _landed(ctx, got, "row_a", "O from Session on the other session, Attention and Agent open")
    _landed(ctx, got, "row_b", "the ask card's O from Session showing only the Feed")


@test
def test_a_rows_o_lands_on_the_ask_from_the_map(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"(c) the session's map, (d) another: {got.get('row_c_map')!r} {got.get('row_d_map')!r}",
              got.get("row_c_map") == "starter" and got.get("row_d_map") == "ship-it")
    _landed(ctx, got, "row_c", "O from Agents -> Map on the session's map")
    _landed(ctx, got, "row_d", "O from Agents -> Map on another map")


@test
def test_other_rows_keep_their_homes_and_a_gone_session_is_said(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the steward's note still opens Local: {got.get('home_steward')}", (got.get("home_steward") or {}).get("section") == "local")
    ended = got.get("home_ended") or {}
    ctx.check(f"a row whose session ended: one toast line says so, nothing moves: {ended}",
              any("ended" in t for t in ended.get("toasts") or []) and ended.get("section") == "agents")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio attention open"))
