"""tests.test_studio_attention_open -- "open" on an ask that waits on you lands where the ask can be answered (Halo 3.6.0.1;
the owner's report from live use of 3.6.0.0: "when I get an attention alert and chose 'open' nothing happens"), in
headless Chrome through tests/helpers/studio_attention_open.py (skipped without Chrome); no model call.

ONE door, used by an Attention row's O, the Live ask card's O and the alert's click. Since 3.6.0.2 (P4 batch 9, the
owner's point 20) it lands on the run's drawing with the asking agent's box selected and its card open on the ask's
choices: from Agents (-> Map on the session's map or another) on Agents -> 4 · Live (this rig's session runs with no map:
since P8 4 · Live draws main's box alone under its T4 line, as Session's Live drawer does); from anywhere else (Session on
another session with the drawers open, Session showing only the Feed, Local) on Session with the row's session
selected, the Feed pointed at the asking agent (the Live column's agent pick, 3.6.0.1), its Live drawer open and Attention on
the asked row with its answers (3.6.0.1's check, restored by P8: the Live drawer takes Attention's room at 1500 px, so one
press of Attention's button shows it). The other kinds of row keep their
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


def _landed(ctx: Ctx, got: dict, case: str, what: str, where: str = "session") -> None:
    p = got.get(case) or {}
    key = _key(got)
    aid = key.split("|")[2] if key.count("|") == 2 else "?"
    boxed = bool(key) and p.get("box") == aid and (p.get("ask_keys") or 0) > 0
    if where == "agents":
        ctx.check(f"{what}: Agents -> 4 · Live, got {p.get('section')!r} {p.get('view')!r}", p.get("section") == "agents" and p.get("view") == "live")
        # P8 (the coordinator's ruling): this rig's session runs with NO map; 4 · Live draws main's box alone under its
        # T4 line (as Session's Live drawer does), so the door lands on the box with its card, never on an empty page
        ctx.check(f"{what}: the session with no map drawn under its T4 line, got {p.get('truth')!r}", p.get("truth") == "T4")
        ctx.check(f"{what}: the asking agent's box selected with its card on the ask's choices, got box {p.get('box')!r} "
                  f"{p.get('ask_keys')!r}, Feed {p.get('feed_ask')!r}, toasts {p.get('toasts')!r}", boxed)
        return
    ctx.check(f"{what}: the asking agent's box selected, its card on the ask's choices, got {p.get('box')!r} {p.get('ask_keys')!r}", boxed)
    ctx.check(f"{what}: Session, its Live drawer open, got {p.get('section')!r} {p.get('live_open')!r}",
              p.get("section") == "session" and p.get("live_open") is True)
    ctx.check(f"{what}: the asking session shown and its agent in the Feed, got {p.get('sessions')!r} {p.get('pin')!r}",
              bool(key) and p.get("pin") == key and p.get("sessions") == [key.split("|")[1]])
    # P8: restored from 3.6.0.1 (the join dropped it without saying so): the door still opens Attention and selects the
    # asked row. At this rig's 1500 px the Live drawer, opened after it, takes its room (R9: the oldest drawer closes), so
    # the driver reads what is on screen and, Attention being closed, presses its button ONCE: the asked row, selected,
    # with its answers (tests/helpers/studio_attention_open.py _attention)
    a = p.get("attn") or {}
    ctx.check(f"{what}: Attention on the asked row with its answers (open at landing: {a.get('open_at_landing')}), got "
              f"{a.get('open')!r} {a.get('row')!r} {a.get('keys')!r}",
              a.get("open") is True and bool(a.get("want")) and a.get("row") == a.get("want") and "a" in (a.get("keys") or []))


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
    _landed(ctx, got, "alert_d", "the alert from Agents -> Map on another map", "agents")


@test
def test_a_rows_o_lands_on_the_ask_from_session(ctx: Ctx):
    got = _got(ctx)
    _landed(ctx, got, "row_a", "O from Session on the other session, Attention and Agent open")
    _landed(ctx, got, "row_b", "the ask card's O from Session showing only the Feed")


@test
def test_a_rows_o_lands_on_the_ask_from_the_map(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"(c) the session's map, (d) another: {got.get('row_c_map')!r} {got.get('row_d_map')!r}",
              got.get("row_c_map") == "auto" and got.get("row_d_map") == "ship-it")
    _landed(ctx, got, "row_c", "O from Agents -> Map on the session's map", "agents")
    _landed(ctx, got, "row_d", "O from Agents -> Map on another map", "agents")


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
