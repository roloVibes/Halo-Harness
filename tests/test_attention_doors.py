"""tests.test_attention_doors -- Halo 3.6.0.5 r, "Attention leaves Agents" (the owner's point 29: "What's the point of the
attention button if it just shows you the flow? Remove that from agents."): every door that opened the Agents panel opens
Session's Attention drawer, and nothing answerable is lost. Node (the pure UI modules, tests/helpers/node_ts.py) and plain
Python, on every platform; the browser half is tests/test_studio_attention_open.py.

1. a decision that belongs to no session (a conflict whose holder is in no session: its row has no harness) stays in
   Session's Attention and is counted (the coordinator's ruling on question 10); a row of another harness stays out;
2. a pack's attention row with no section of its own opens Session's Attention on O;
3. the phone's text says where to answer: "(answer it in Studio: Session, Attention)";
4. the palette's two lines are Session's: "Session: Attention" and "Session: answer next", with no A key;
5. the old panel door ("attention") opens Session's drawer, past its Start view.
Run: python -m tests.test_attention_doors
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
UI = ROOT / "halo_harness" / "studio" / "ui" / "src"


def _node(module: Path, body: str):
    from tests.helpers import node_ts
    js = f"const M = await import({json.dumps(module.resolve().as_uri())});\nconst out = {{}};\n{body}\nconsole.log(JSON.stringify(out));"
    return node_ts.run(js)


@test
def test_a_row_of_no_session_stays_in_sessions_attention(ctx: Ctx):
    got = _node(UI / "routes" / "fleet" / "attnScope.ts", """
const rows = [{ id: 'a', harness: 'h1' }, { id: 'b', harness: null }, { id: 'c', harness: 'h2' }, { id: 'd', harness: '' }];
out.in1 = rows.filter(M.rowIn({ harness: 'h1', session: 's1' })).map((r) => r.id);
out.in2 = rows.filter(M.rowIn({ harness: 'h2' })).map((r) => r.id);
out.all = rows.filter(M.rowIn({})).map((r) => r.id);
out.count = M.scopedRows(rows, 9, { harness: 'h1' });
out.unscoped = M.scopedRows(rows, 9, {}).count;
""")
    ctx.check(f"a row of no harness is in scope for any session scope, another harness's is out, got {got.get('in1')} {got.get('in2')}",
              got.get("in1") == ["a", "b", "d"] and got.get("in2") == ["b", "c", "d"])
    ctx.check(f"nothing narrows: every row, got {got.get('all')}", got.get("all") == ["a", "b", "c", "d"])
    cnt = got.get("count") or {}
    ctx.check(f"the count on Session's button counts it, got {cnt}",
              cnt.get("count") == 3 and [r.get("id") for r in cnt.get("rows") or []] == ["a", "b", "d"])
    ctx.check(f"unscoped, the watcher's live count as before, got {got.get('unscoped')}", got.get("unscoped") == 9)


@test
def test_a_pack_row_with_no_section_opens_sessions_attention(ctx: Ctx):
    from halo_harness.live import pack_attention
    got = pack_attention.open_target({"target": {}})
    ctx.check(f"no section: Session's Attention, got {got}", got == {"section": "live", "panel": "session-attention"})
    own = pack_attention.open_target({"target": {"section": "doc-review--docs"}})
    ctx.check(f"a section of its own opens it, got {own}", own == {"section": "doc-review--docs", "panel": ""})


@test
def test_the_phone_text_names_session_attention(ctx: Ctx):
    from halo_harness.live import push
    text = push.card({"harness_name": "gpu-box", "agent": "main", "kind": "cap", "what": "spend cap reached", "detail": "$5.00 today"})
    ctx.check(f"the phone's text ends where to answer, got {text[-60:]!r}",
              text.endswith("(answer it in Studio: Session, Attention)") and "Agents, Attention" not in text)


def _line(src: str, needle: str) -> str:
    return next((ln for ln in src.splitlines() if needle in ln), "")


@test
def test_the_palette_lines_open_sessions_attention(ctx: Ctx):
    src = (UI / "routes" / "fleet" / "commands.ts").read_text(encoding="utf-8")
    att = _line(src, 'id: "fleet-attention"')
    ctx.check(f"Session: Attention, in the Session group, Session's drawer, no key hint: {att.strip()[:160]!r}",
              all(w in att for w in ('group: "Session"', 'label: "Session: Attention"', "run: showAttention")) and "kbd:" not in att)
    nxt = _line(src, 'id: "fleet-answer-next"')
    ctx.check(f"Session: answer next, in the Session group, Session's drawer: {nxt.strip()[:160]!r}",
              all(w in nxt for w in ('group: "Session"', 'label: "Session: answer next"', "showAttention()")))
    left = [w for w in ("Agents: Attention", "Agents: answer next", "../agents/attention") if w in src]
    ctx.check(f"nothing of the Agents panel is left in the palette: {left}", not left)


@test
def test_the_old_panel_door_opens_sessions_drawer(ctx: Ctx):
    door = (UI / "routes" / "agents" / "fleetDoor.ts").read_text(encoding="utf-8")
    to = _line(door, 'to === "attention"')
    ctx.check(f"the door 'attention' opens Session's drawer: {to.strip()!r}", "showAttention()" in to and "./attention" not in door)
    ask = (UI / "routes" / "glance" / "openAsk.ts").read_text(encoding="utf-8")
    m = re.search(r"^export function showAttention\(\): void \{\n(.*?)^\}", ask, re.S | re.M)
    body = m.group(1) if m else ""
    ctx.check(f"showAttention: Session shown, past its Start view, the drawer open: {body.strip()!r}",
              bool(m) and all(w in body for w in ('goSection("session")', 'setSessionView("workspace")', "openAttention()")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="attention doors"))
