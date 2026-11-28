"""tests.test_studio_prompt_words -- 3.6.0.2 P6 ("one prompt"): the Prompt panel's pure words and rules,
routes/session/promptWords.ts run under node (skipped without a node that runs .ts), against Python's:

1. `askLabel` gives the same label as `events.ask_label` for every row of THE table (permission, question, plan,
   approval, with and without typed words), and the answered lines' words are Python's (P5, P23);
2. P72: the answer removes only the text sent, and only while the record made at Enter stands: an edit after the
   sent text keeps the record, an edit, paste, cut or recall that touches its first characters drops it, and a box
   that no longer begins with the sent text is left whole;
3. P27: the header's words (`<folder> · <title, else first_words and …, else "no messages yet"> · started <HH:MM> · in a
   terminal | no terminal`, the date on another day) and the lines of P28, P29, P31, P32, word for word;
4. P31: the pick follows `follows` (pick.ts followerOf) once the old row left the list, also /clear twice and from
   P32's state; an ended pick nothing follows stays.
Run: python -m tests.test_studio_prompt_words
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
WORDS = (Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "session"
         / "promptWords.ts")

ROWS = [
    ("permission", {"action": "allow", "scope": "once"}),
    ("permission", {"action": "allow"}),
    ("permission", {"action": "allow", "scope": "session"}),
    ("permission", {"action": "allow", "scope": "always"}),
    ("permission", {"action": "deny"}),
    ("permission", {"action": "deny", "message": "  not in the repo root  "}),
    ("permission", {"action": "deny", "message": "x" * 200}),
    ("question", {"answer": "red"}),
    ("question", {"answer": ["red", "blue"]}),
    ("question", {"answer": {"q1": "red", "q2": "a typed answer"}}),
    ("question", {}),
    ("plan", {"approved": True}),
    ("plan", {"approved": False}),
    ("plan", {"approved": False, "feedback": "split step two"}),
    ("approval", {"action": "accept"}),
    ("approval", {"action": "edit"}),
    ("approval", {"action": "edit", "instruction": "use the other file"}),
    ("approval", {"action": "stop"}),
    ("approval", {"action": "compact"}),
]

JS_LABELS = """
const m = await import(%s);
console.log(JSON.stringify({ labels: %s.map(([k, f]) => m.askLabel(k, f)), words: m.ANSWERED_WORDS,
  lines: [m.answeredLine("terminal", "Allow"), m.answeredLine("studio", "Allow"), m.answeredLine("remote", "Allow"),
          m.answeredLine("", "Deny")] }));
"""

# P72: (what was sent, the box at Enter, then each edit as the page sees it: (next box, its inputType, the selection
# start at beforeinput, the caret at input; None: no beforeinput came)), the box after the answer
CASES = {
    "nothing typed after Enter: the box empties": ("hello", "hello", [], ""),
    "typed after Enter: only that stays": ("hello", "hello", [("hello and more", "insertText", 5, 14)], "and more"),
    "a new line, then more: only the more": ("hello", "hello", [("hello\n", "insertLineBreak", 5, 6),
                                                                 ("hello\nnext", "insertText", 6, 10)], "next"),
    "leading spaces were sent with it": ("  hello", "  hello", [("  hello x", "insertText", 7, 9)], "x"),
    # P7 (the checker of P6 batch 1): an image-only send sent no text: what he typed after Enter stays exactly
    "an image-only send: two spaces and a line break typed after it stay": ("", "", [("  ", "insertText", 0, 2),
                                                                                  ("  \nnext", "insertLineBreak", 2, 3)], "  \nnext"),
    "Up recalls the line just sent: left": ("hello", "hello", [("hello", "", None, 5)], "hello"),
    "the box replaced by a longer text beginning with it: left whole": ("hello", "hello", [("hello world", "insertText", 0, 11)], "hello world"),
    "a Backspace into the sent text: left": ("hello", "hello", [("hell", "deleteContentBackward", 5, 4)], "hell"),
    "a Backspace into it, typed back: left": ("hello", "hello", [("hell", "deleteContentBackward", 5, 4),
                                                                  ("hello", "insertText", 4, 5)], "hello"),
    # the checker's walk: 'see' sent, 'e more' typed after, then a Backspace with the caret right after the sent text
    "a Backspace at the sent text's edge, the text after it beginning with its last letter: left": (
        "see", "see", [("seee more", "insertText", 3, 9), ("see more", "deleteContentBackward", 3, 2)], "see more"),
    "a word deleted back across the edge: left": ("see", "see", [("see more", "insertText", 3, 8),
                                                                  ("more", "deleteWordBackward", 4, 0)], "more"),
    "a Delete forward after the sent text: only the rest": ("hello", "hello", [("hello xy", "insertText", 5, 8),
                                                                                ("hello y", "deleteContentForward", 6, 6)], "y"),
    "a cut of the whole box, then typing: left": ("hello", "hello", [("", "deleteByCut", 0, 0), ("new", "insertText", 0, 3)], "new"),
    "an edit inside, after more was typed: left": ("hello", "hello", [("hello there", "insertText", 5, 11),
                                                                       ("hallo there", "insertText", 1, 2)], "hallo there"),
    "a paste after the sent text: only the paste": ("hello", "hello", [("hello pasted", "insertFromPaste", 5, 12)], "pasted"),
    "an undo, wherever the caret was: left": ("hello", "hello", [("hello x", "insertText", 5, 7), ("hello", "historyUndo", 7, 5)], "hello"),
    "a dropped text after it: left (a drop can start anywhere)": ("hello", "hello", [("hello x", "insertFromDrop", 7, 7)], "hello x"),
    "a composition begun inside the sent text: left": ("hello", "hello", [("helかlo", "insertCompositionText", 3, 4)], "helかlo"),
    "a slash line, more typed after": ("/effort low", "/effort low", [("/effort low next", "insertText", 11, 16)], "next"),
    "a trailing space at Enter goes with it": ("hello", "hello ", [("hello more", "insertText", 6, 10)], "more"),
}

JS_P72 = """
const m = await import(%s);
const out = {};
for (const [name, [sent, box0, edits]] of Object.entries(%s)) {
  let box = box0, stands = box0.startsWith(sent);
  for (const [next, type, before, after] of edits) {
    if (stands && !m.keepsSent(sent.length, box, next, m.editStart(type, before, after))) stands = false;
    box = next;
  }
  const after = stands ? m.afterAnswer(box, sent) : null;
  out[name] = after === null ? box : after;
}
out["a box that no longer begins with it"] = m.afterAnswer("hullo", "hello");
console.log(JSON.stringify(out));
"""


@test
def test_ask_label_table_is_one(ctx: Ctx):
    from halo_harness.events import ANSWERED_WORDS, answered_line, ask_label
    from tests.helpers import node_ts
    got = node_ts.run(JS_LABELS % (json.dumps(WORDS.resolve().as_uri()), json.dumps(ROWS))) or {}
    labels = got.get("labels") or []
    ctx.check(f"one label per row, got {len(labels)}", len(labels) == len(ROWS))
    for (kind, fields), ts_label in zip(ROWS, labels):
        py = ask_label(kind, fields)
        ctx.check(f"{kind} {json.dumps(fields)[:60]}: Python {py[:60]!r} == TS {ts_label[:60]!r}", py == ts_label)
    words = got.get("words") or {}
    ctx.check(f"the answered words for Studio and remote are Python's, got {words}",
              all(words.get(k) == v for k, v in ANSWERED_WORDS.items()))
    ctx.check(f"the four lines, got {got.get('lines')}", got.get("lines") == [
        "Answered in the terminal: Allow", answered_line("studio", "Allow"), answered_line("remote", "Allow"),
        "Answered remotely: Deny"] and answered_line("studio", "Allow") == "Answered in Studio: Allow")


@test
def test_answer_removes_only_the_sent_text(ctx: Ctx):
    from tests.helpers import node_ts
    got = node_ts.run(JS_P72 % (json.dumps(WORDS.resolve().as_uri()), json.dumps(CASES))) or {}
    for name, (_sent, _box, _edits, want) in CASES.items():
        ctx.check(f"{name}: {want!r}, got {got.get(name)!r}", got.get(name) == want)
    ctx.check(f"a box that no longer begins with it is left (null), got {got.get('a box that no longer begins with it')!r}",
              "a box that no longer begins with it" in got and got["a box that no longer begins with it"] is None)


# -- P27: the Prompt header's words; P31: the pick follows `follows` -----------------------------------------------------
PICK = WORDS.parent / "pick.ts"
JS_HEAD = """
const m = await import(%s);
const at = (y, mo, d, h, mi) => new Date(y, mo, d, h, mi).getTime();
const now = at(2026, 10, 17, 12, 0);
const row = (o) => Object.assign({session_id: "s1", cwd: "/work/halo-app", started: at(2026, 10, 17, 9, 5) / 1000, kind: "tui"}, o);
console.log(JSON.stringify({
  today: m.headLine(row({title: "Fix the parser"}), now),
  other_day: m.headLine(row({title: "Fix the parser", started: at(2026, 10, 16, 9, 10) / 1000}), now),
  windows_cwd: m.headLine(row({title: "t", cwd: "C:\\\\work\\\\halo-app\\\\"}), now),
  no_terminal: m.headLine(row({title: "Fix the parser", kind: "headless"}), now),
  untitled: m.headLine(row({title: "", first_words: "fix the parser in the"}), now),
  untitled_title_null: m.headLine(row({title: null, first_words: "add a test"}), now),
  nothing: m.headLine(row({title: "", first_words: ""}), now),
  nothing_missing: m.headLine(row({}), now),
  moved: m.movedLine(row({title: "Fix the parser"}), false), moved_short: m.movedLine(row({title: "Fix the parser"}), true),
  follow: m.followLine(row({})), ended: m.ENDED, copy: [m.COPY, m.COPIED], change: m.CHANGE_SESSION,
}));
"""


def _head(ctx: Ctx) -> dict:
    from tests.helpers import node_ts
    got = node_ts.run(JS_HEAD % json.dumps(WORDS.resolve().as_uri()))
    ctx.check("promptWords.ts runs under node with the header words", isinstance(got, dict))
    return got or {}


@test
def test_header_words_today_and_other_day(ctx: Ctx):
    got = _head(ctx)
    ctx.check(f"today: folder · title · started HH:MM · in a terminal, got {got.get('today')!r}",
              got.get("today") == "halo-app · Fix the parser · started 09:05 · in a terminal")
    ctx.check(f"another day carries the date, got {got.get('other_day')!r}",
              got.get("other_day") == "halo-app · Fix the parser · started Nov 16, 09:10 · in a terminal")
    ctx.check(f"a Windows folder (trailing separator) gives its last name, got {got.get('windows_cwd')!r}",
              got.get("windows_cwd") == "halo-app · t · started 09:05 · in a terminal")
    ctx.check(f"a session with no terminal says so, got {got.get('no_terminal')!r}",
              got.get("no_terminal") == "halo-app · Fix the parser · started 09:05 · no terminal")
    ctx.check(f"P29's lines, got {got.get('moved')!r} / {got.get('moved_short')!r}",
              got.get("moved") == "Now typing into halo-app · Fix the parser." and got.get("moved_short") == "Now typing into halo-app.")
    ctx.check(f"P31's line, got {got.get('follow')!r}", got.get("follow") == "Same terminal, new conversation: halo-app.")
    ctx.check(f"P32's and P28's words, got {got.get('ended')!r} {got.get('copy')} {got.get('change')!r}",
              got.get("ended") == "This session has ended. What you typed is still here."
              and got.get("copy") == ["Copy", "Copied."] and got.get("change") == "Change session")


@test
def test_untitled_session_shows_first_words(ctx: Ctx):
    got = _head(ctx)
    ctx.check(f"no title: the first words and …, got {got.get('untitled')!r}",
              got.get("untitled") == "halo-app · fix the parser in the… · started 09:05 · in a terminal")
    ctx.check(f"a null title too, got {got.get('untitled_title_null')!r}",
              got.get("untitled_title_null") == "halo-app · add a test… · started 09:05 · in a terminal")


@test
def test_no_prompt_says_no_messages_yet(ctx: Ctx):
    got = _head(ctx)
    for k in ("nothing", "nothing_missing"):
        ctx.check(f"{k}: 'no messages yet', never a bare id, got {got.get(k)!r}",
                  got.get(k) == "halo-app · no messages yet · started 09:05 · in a terminal" and "s1" not in str(got.get(k)))


JS_FOLLOW = """
const m = await import(%s);
const id = (r) => r ? r.session_id : null;
const out = {};
m.noteRows([{session_id: "A"}, {session_id: "B", follows: "A"}], 1);
out.both_open = id(m.followerOf([{session_id: "A"}, {session_id: "B", follows: "A"}], "A"));
m.noteRows([{session_id: "B", follows: "A"}], 2);
out.after_clear = id(m.followerOf([{session_id: "B", follows: "A"}], "A"));
out.from_A = m.followedFrom("B");
out.none = id(m.followerOf([{session_id: "C"}], "Z"));
m.noteRows([{session_id: "C", follows: "B"}], 3);
out.twice = id(m.followerOf([{session_id: "C", follows: "B"}], "A"));
m.noteRows([{session_id: "E"}], 4); m.noteRows([], 5);
out.ended_nothing = id(m.followerOf([], "E"));
out.ended_then = id(m.followerOf([{session_id: "F", follows: "E"}], "E"));
out.unseen = id(m.followerOf([{session_id: "G", follows: "H"}], "H"));
console.log(JSON.stringify(out));
"""


@test
def test_follows_moves_the_pick(ctx: Ctx):
    from tests.helpers import node_ts
    got = node_ts.run(JS_FOLLOW % json.dumps(PICK.resolve().as_uri())) or {}
    ctx.check(f"while the old row is still listed the pick stays, got {got.get('both_open')!r}", got.get("both_open") is None
              and "both_open" in got)
    ctx.check(f"the old row gone: the row that follows it, got {got.get('after_clear')!r}", got.get("after_clear") == "B")
    ctx.check(f"the move is remembered (P29's line names it), got {got.get('from_A')!r}", got.get("from_A") == "A")
    ctx.check(f"nothing follows an unknown pick, got {got.get('none')!r}", "none" in got and got["none"] is None)
    ctx.check(f"/clear twice: the newest of the line, got {got.get('twice')!r}", got.get("twice") == "C")
    ctx.check(f"an ended pick with no follower stays (P32), got {got.get('ended_nothing')!r}",
              "ended_nothing" in got and got["ended_nothing"] is None)
    ctx.check(f"from P32's state, a later follower takes the pick, got {got.get('ended_then')!r}", got.get("ended_then") == "F")
    ctx.check(f"a pick this page never saw listed is followed too, got {got.get('unseen')!r}", got.get("unseen") == "G")


JS_LIST = """
const m = await import(%s);
const out = {};
m.choseInList("B", "A"); out.list_moved = m.tookFromList("B");
m.choseInList("A", "A"); out.same_then_away = m.tookFromList("B"); out.back_by_map = m.tookFromList("A");
m.choseInList("C", "A"); out.other_change_first = m.tookFromList("D"); out.then_C = m.tookFromList("C");
console.log(JSON.stringify(out));
"""


@test
def test_choosing_the_current_session_leaves_no_mark(ctx: Ctx):
    """P28/P29 (the checker of batch 2): choosing the session already picked in `Change session` changes nothing, so
    a later move back to it by the Map or `/studio` still shows `Now typing into ...`."""
    from tests.helpers import node_ts
    got = node_ts.run(JS_LIST % json.dumps(PICK.resolve().as_uri())) or {}
    ctx.check(f"the list's own move shows no line, got {got.get('list_moved')!r}", got.get("list_moved") is True)
    ctx.check(f"a move away after choosing the current one is not the list's, got {got.get('same_then_away')!r}",
              got.get("same_then_away") is False)
    ctx.check(f"back to it by the Map: the line shows, got {got.get('back_by_map')!r}", got.get("back_by_map") is False)
    ctx.check(f"a change the list did not make uses the mark up, got {got.get('other_change_first')!r} then {got.get('then_C')!r}",
              got.get("other_change_first") is False and got.get("then_C") is False)


# -- 3.6.0.11 SS batch 2: the Feed's head says which session it shows; the words for an ended watched session; the
# prompts typed before Studio attached show as turns --
ROWS_TS = WORDS.with_name("promptRows.ts")
JS_FEED_HEAD = """
const m = await import(%s);
console.log(JSON.stringify({ others: [0, 1, 2, 5].map(m.othersLine),
  ended: m.endedLine({cwd: '/w/home', title: 'fix the tests'}), ended_win: m.endedLine({cwd: 'C:\\\\w\\\\app\\\\'}),
  none: m.endedLine(null) }));
"""
JS_ROWS = """
const r = await import(%s);
const key = 'h|S|main';
const lines = [{key, kind: 'asked', text: 'old question', ts: 10, n: 1}, {key, kind: 'text', text: 'old answer', ts: 11, n: 2},
  {key: 'h|S|w1', kind: 'asked', text: 'helper task', ts: 12, n: 3}, {key, kind: 'asked', text: 'heard live', ts: 20, n: 4},
  {key: 'h|T|main', kind: 'asked', text: 'other session', ts: 21, n: 6}, {key, kind: 'asked', text: 'heard live', ts: 30, n: 7}];
const turns = [{n: 5, sid: 'S', ts: 20, text: 'heard live', via: 'terminal', receipt: '', turn: 2}];
const said = (x) => x.turn ? 'you:' + x.turn.text : x.line ? x.line.kind + ':' + x.line.text : 'out';
console.log(JSON.stringify({ rows: r.feedRows(turns, lines, [], 'S', key, 240).map(said) }));
"""


@test
def test_feed_head_words_for_other_sessions_and_an_ended_one(ctx: Ctx):
    from tests.helpers import node_ts
    got = node_ts.run(JS_FEED_HEAD % json.dumps(WORDS.resolve().as_uri())) or {}
    ctx.check(f"the chip: nothing for 0, then '1 other session running' / 'n other sessions running', got {got.get('others')}",
              got.get("others") == ["", "1 other session running", "2 other sessions running", "5 other sessions running"])
    ctx.check(f"the watched session ended: the open one's folder, word for word, got {got.get('ended')!r} {got.get('ended_win')!r}",
              got.get("ended") == "The session you watched ended; home is running."
              and got.get("ended_win") == "The session you watched ended; app is running.")
    ctx.check(f"nothing open: no such line, got {got.get('none')!r}", got.get("none") == "")


@test
def test_prompts_typed_before_studio_attached_show_as_turns(ctx: Ctx):
    # Reader E (e): the backlog's prompts are `asked` lines, which the Prompt panel did not show: answers without their
    # questions. Main's `asked` lines are turns; one heard live as a turn (the same text, about the same time) is not drawn twice.
    from tests.helpers import node_ts
    ctx.check(f"routes/session/promptRows.ts exists, got {ROWS_TS.exists()}", ROWS_TS.exists())
    if not ROWS_TS.exists():
        return
    got = node_ts.run(JS_ROWS % json.dumps(ROWS_TS.resolve().as_uri())) or {}
    ctx.check(f"the prompt, its answer, the live turn once, a repeat later as its own turn; no helper's or other session's, got {got.get('rows')}",
              got.get("rows") == ["you:old question", "text:old answer", "you:heard live", "you:heard live"])


KEYS = WORDS.parent / "promptKeys.ts"
# (key, text, selection start, end, a recalled entry stands untouched with the caret at its end) -> what the key does
ARROWS = [
    ("ArrowUp", "a long prompt", 13, 13, False, "start"),         # first line, caret not at 0: to the start, no recall
    ("ArrowUp", "a long prompt", 0, 0, False, "older"),           # at 0: history, older
    ("ArrowUp", "", 0, 0, False, "older"),                         # an empty box is at 0
    ("ArrowUp", "one\ntwo", 6, 6, False, "native"),               # not on the first line: the browser's own move
    ("ArrowUp", "one\ntwo", 2, 2, False, "start"),
    ("ArrowUp", "recalled", 8, 8, True, "older"),                  # a recalled entry untouched: older at once
    ("ArrowUp", "re\ncalled", 9, 9, True, "native"),              # ...but a multi-line one moves up first, as the terminal
    ("ArrowDown", "a long prompt", 3, 3, False, "end"),           # the mirror: to the very end
    ("ArrowDown", "a long prompt", 13, 13, False, "newer"),
    ("ArrowDown", "one\ntwo", 1, 1, False, "native"),
    ("ArrowDown", "one\ntwo", 5, 5, False, "end"),
    ("ArrowDown", "", 0, 0, False, "newer"),
    ("ArrowDown", "recalled", 8, 8, True, "newer"),
]


@test
def test_up_goes_to_the_start_of_the_prompt_before_it_walks_history(ctx: Ctx):
    """3.6.0.11 (the owner: "The up button should bring you to the start of your prompt. If it's long I'm over holding
    done the left button"): Studio's box walked history on any Up on the first line. Now the terminal's rule, 1:1."""
    from tests.helpers import node_ts
    js = (f"const k = await import({KEYS.resolve().as_uri()!r}); const cs = {json.dumps(ARROWS)};"
          " console.log(JSON.stringify(cs.map(([key, t, s, e, w]) => k.arrowMove(key, t, s, e, w))))")
    got = node_ts.run(js)
    for case, move in zip(ARROWS, got):
        ctx.check(f"{case[:5]} -> {case[5]!r}, got {move!r}", move == case[5])


# -- 3.6.0.12 BS batch 2: a one-line `!command` from the Prompt box runs in the session, as in the terminal --
BANG_ROUTES = [  # (text, an image rides along) -> the door
    ("!echo hi", False, "slash"),
    ("!ls -la", False, "slash"),
    ("/cost", False, "slash"),
    ("!echo hi", True, "slash"),          # an image chip beside it waits for the next prompt, as in the terminal
    ("/cost", True, "slash"),             # 3.6.0.17 P1: so does a `/` line's (tui/app.py keeps the chip for the next prompt)
    (" !echo hi", False, "slash"),        # 3.6.0.17 P1: the terminal judges the stripped line: a space before it
    (" /cost", False, "slash"),
    ("\n!echo hi", False, "slash"),       # ...or a blank line before it
    ("!echo hi\nand more", False, "submit"),  # a second line: a prompt
    ("echo hi", False, "submit"),
    ("say !this", False, "submit"),
]
JS_BANG = """
const m = await import(%s);
console.log(JSON.stringify({ routes: %s.map(([t, img]) => m.routeOf(t, img)),
  ran: m.bangLines({state: 'ran', output: 'BANG-ONE\\nsecond'}), ran_lines: m.bangLines({state: 'ran', lines: ['x', '']}),
  ran_empty: m.bangLines({state: 'ran', output: ''}), asked: m.bangLines({state: 'asked', id: 'inline-1'}),
  denied: m.bangLines({state: 'denied', reason: 'a deny rule matches Bash(rm:*)'}),
  running: m.bangLines({state: 'running', id: 'inline_2'}),
  stop: [m.isBang('inline_2'), m.isBang('toolu_2'), m.isBang(undefined), m.BANG_STOP] }));
"""
HELP_TS = WORDS.parent.parent / "help-session.ts"
BANG_HELP = ("A line that starts with ! runs that command in the session at once, as in the terminal: no model turn; "
             "its output shows here and in the Feed.")


@test
def test_a_bang_line_goes_through_the_slash_door_and_its_answer_words(ctx: Ctx):
    """The owner: "can I run commands in the terminal like Claude code using the "!" ? If not that is a must have".
    Studio's box sent a `!` line as a prompt (a model turn). The door does not depend on a running turn: `routeOf`
    takes no busy state, and `send` asks nothing else before it (a `!` is never a steer and never queued)."""
    from tests.helpers import node_ts
    got = node_ts.run(JS_BANG % (json.dumps(WORDS.resolve().as_uri()), json.dumps([[t, i] for t, i, _ in BANG_ROUTES]))) or {}
    ctx.check(f"the doors, got {got.get('routes')}", got.get("routes") == [d for _, _, d in BANG_ROUTES])
    ctx.check(f"ran: `ran`, then the output's lines, got {got.get('ran')} {got.get('ran_lines')} {got.get('ran_empty')}",
              got.get("ran") == ["ran", "BANG-ONE", "second"] and got.get("ran_lines") == ["ran", "x"]
              and got.get("ran_empty") == ["ran"])
    ctx.check(f"asked, word for word, got {got.get('asked')}", got.get("asked") == ["asks first: answer below"])
    ctx.check(f"denied, word for word, got {got.get('denied')}", got.get("denied") == ["denied: a deny rule matches Bash(rm:*)"])
    ctx.check(f"still running, word for word, got {got.get('running')}",
              got.get("running") == ["still running: Stop is on its row; its output shows in the Feed"])
    ctx.check(f"Stop belongs on a ! command's own row only, got {got.get('stop')}", got.get("stop") == [True, False, False, "Stop"])


JS_DENIED = """
const r = await import(%s);
const key = 'h|S|main', t = 1000;
const err = (ts, type, sid) => ({key: 'h|' + sid + '|main', kind: 'error', text: 'refused, in any words', ts, n: ts, errType: type});
const out = (ts, sid) => ({n: ts, sid, ts, line: '!rm x', lines: ['denied: blocked']});
const said = (x) => x.out ? 'out:' + x.out.line : x.line.kind + ':' + (x.line.errType || '');
const rows = (lines, outs) => r.feedRows([], lines, outs, 'S', key, 240).map(said);
console.log(JSON.stringify({
  studio: rows([err(t + 1, 'inline_shell_denied', 'S')], [out(t, 'S')]),
  terminal: rows([err(t + 1, 'inline_shell_denied', 'S')], []),
  two_one_out: rows([err(t + 1, 'inline_shell_denied', 'S'), err(t + 5, 'inline_shell_denied', 'S')], [out(t, 'S')]),
  other_error: rows([err(t + 1, 'api_error', 'S')], [out(t, 'S')]),
  far: rows([err(t + 500, 'inline_shell_denied', 'S')], [out(t, 'S')]),
}));
"""


@test
def test_a_refused_bang_shows_once(ctx: Ctx):
    """3.6.0.17 P2: a `!` refused from Studio drew two rows in the Prompt panel (the panel's own `denied:` answer and the
    session's error line); the terminal draws one. Told apart by the error's TYPE (the Controller's
    `inline_shell_denied`), never by its words: a refusal in the terminal still shows the session's line."""
    from tests.helpers import node_ts
    got = node_ts.run(JS_DENIED % json.dumps(ROWS_TS.resolve().as_uri())) or {}
    ctx.check(f"refused from Studio: the panel's own row once, got {got.get('studio')}", got.get("studio") == ["out:!rm x"])
    ctx.check(f"refused in the terminal: the session's line, got {got.get('terminal')}",
              got.get("terminal") == ["error:inline_shell_denied"])
    ctx.check(f"one answer row takes out one error line, got {got.get('two_one_out')}",
              got.get("two_one_out") == ["out:!rm x", "error:inline_shell_denied"])
    ctx.check(f"another error is never taken out, got {got.get('other_error')}", got.get("other_error") == ["out:!rm x", "error:api_error"])
    ctx.check(f"a refusal minutes away is another one, got {got.get('far')}", got.get("far") == ["out:!rm x", "error:inline_shell_denied"])


@test
def test_the_feeds_error_entry_carries_its_type(ctx: Ctx):
    """3.6.0.17 P2: the feed's error entry carries the error's own type (live and from the transcript file, which holds
    it already: agent/log.py), so Studio tells the rows apart without reading words."""
    from halo_harness import events
    from halo_harness.agent.agent_transcript import entries_from_nodes, entry_from_event
    live = entry_from_event(events.error("!rm x -- denied: blocked", err_type="inline_shell_denied")) or {}
    ctx.check(f"live: the type rides on the entry, got {live}", live.get("kind") == "error" and live.get("err_type") == "inline_shell_denied")
    kept = entries_from_nodes([{"type": "error", "message": "boom", "err_type": "inline_shell_denied", "ts": 1}])
    ctx.check(f"from the transcript file: the same, got {kept}", [e.get("err_type") for e in kept] == ["inline_shell_denied"])
    plain = entry_from_event(events.error("boom")) or {}
    ctx.check(f"an error with no own type is as before, got {plain}", "err_type" not in plain)
    src = (WORDS.parent.parent / "shared" / "liveFeed.ts").read_text(encoding="utf-8")
    ctx.check("the feed's error line keeps the entry's type (liveFeed.ts fromEntry)", "errType" in src.split('e.kind === "error"', 1)[-1].split("\n", 1)[0])


AFTER_NATIVE = [  # (key, caret before, caret after the browser's own move, length) -> where the caret ends (None: kept)
    ("ArrowUp", 400, 320, 400, None),   # up a screen line of a wrapped prompt: kept
    ("ArrowUp", 50, 50, 400, 0),        # on its first screen line the browser did nothing: to the start
    ("ArrowUp", 50, 0, 400, 0),         # ...or went to 0 itself: the same end
    ("ArrowDown", 0, 80, 400, None),    # down a screen line: kept
    ("ArrowDown", 350, 350, 400, 400),  # on the last screen line: to the end
    ("ArrowDown", 350, 400, 400, 400),
]


@test
def test_up_and_down_on_a_wrapped_line_move_a_screen_line_first(ctx: Ctx):
    """3.6.0.17 P3: Up on one long wrapped prompt jumped to its start; the terminal moves one screen line first
    (tui/widgets/input.py action_cursor_up). The browser makes the move; `afterNative` judges where it landed."""
    from tests.helpers import node_ts
    js = (f"const k = await import({KEYS.resolve().as_uri()!r}); const cs = {json.dumps([c[:4] for c in AFTER_NATIVE])};"
          " console.log(JSON.stringify(cs.map(([key, b, a, n]) => typeof k.afterNative === 'function' ? k.afterNative(key, b, a, n) : 'missing')))")
    got = node_ts.run(js) or []
    for case, to in zip(AFTER_NATIVE, got):
        ctx.check(f"{case[:4]} -> {case[4]!r}, got {to!r}", to == case[4])
    ctx.check(f"every case answered, got {len(got)}", len(got) == len(AFTER_NATIVE))


@test
def test_the_prompt_panels_help_says_what_a_bang_line_does(ctx: Ctx):
    src = HELP_TS.read_text(encoding="utf-8")
    block = src.split('"session-prompt"', 1)[-1].split('"session-conversations"', 1)[0]
    ctx.check("the Prompt panel's help holds the sentence, word for word", BANG_HELP in block)



JS_GUEST = """
const w = await import(%s);
const p = await import(%s);
const now = new Date(2026, 10, 27, 15, 0).getTime();
const g = { session_id: "guest-1", kind: "guest", title: "Claude Code", cwd: "/w/shop", started: now / 1000 - 60 };
const t = { session_id: "t-1", kind: "tui", title: "fix", cwd: "/w/shop", started: now / 1000 - 30 };
console.log(JSON.stringify({ head: w.headLine(g, now), tuiHead: w.headLine(t, now), isGuest: [w.isGuest(g), w.isGuest(t), w.isGuest(null)],
  talked: [p.talkedTo(g), p.talkedTo(t)], line: w.GUEST_LINE, auto: p.autoPick([t, g], "", false, false) }));
"""


@test
def test_a_claude_code_session_reads_watch_only_and_is_never_talked_to(ctx: Ctx):
    """3.6.0.25 G: a guest row's header says `<folder> · Claude Code · started <HH:MM> · watch only`; Session never
    moves to it by itself (`talkedTo`); a terminal session's header is as it was."""
    from tests.helpers import node_ts
    got = node_ts.run(JS_GUEST % (json.dumps(WORDS.resolve().as_uri()), json.dumps(PICK.resolve().as_uri()))) or {}
    ctx.check(f"the guest's header, got {got.get('head')!r}", got.get("head") == "shop · Claude Code · started 14:59 · watch only")
    ctx.check(f"a terminal's header unchanged, got {got.get('tuiHead')!r}", got.get("tuiHead") == "shop · fix · started 14:59 · in a terminal")
    ctx.check("isGuest", got.get("isGuest") == [True, False, False])
    ctx.check("nothing is typed into a guest: talkedTo is false for it", got.get("talked") == [False, True])
    ctx.check(f"the pick follows the terminal session, never the guest, got {got.get('auto')!r}", got.get("auto") == "t-1")
    ctx.check("the line", got.get("line") == "Claude Code · watch only: Studio shows this session; nothing is typed into it or steered from here.")


@test
def test_the_session_pages_draw_no_prompt_box_steer_or_cost_for_a_guest(ctx: Ctx):
    """3.6.0.25 G, read in the source (the browser half is tests/test_studio_session.py): the Prompt panel's foot is the
    watch-only line, the Steer box is that line, Steer and Screenshot are disabled, the cost is "not known"."""
    src = {n: (WORDS.parent / n).read_text(encoding="utf-8") for n in ("Prompt.tsx", "LiveSteer.tsx", "LiveHead.tsx", "Cost.tsx")}
    ctx.check("Prompt: the line instead of the composer", "isGuest(ss) ? <div" in src["Prompt.tsx"] and "prompt-watch-only" in src["Prompt.tsx"])
    ctx.check("LiveSteer: the line instead of the box", "if (isGuest(ss))" in src["LiveSteer.tsx"] and "session-live-watch-only" in src["LiveSteer.tsx"])
    ctx.check("LiveHead: Steer and Screenshot disabled", src["LiveHead.tsx"].count("isGuest(") == 3 and "disabled={!t.key || watch}" in src["LiveHead.tsx"])
    ctx.check("Cost: not known, twice", src["Cost.tsx"].count("if (isGuest(ss))") == 2 and "NOT_KNOWN" in src["Cost.tsx"])


JS_GUEST_COST = """
const n = await import(%s);
const w = await import(%s);
const node = (id, parent, extra) => ({ id, key: `h|g-1|${id}`, parent, name: id, role: "", model: "claude-x", state: "running",
  pick: "", activity: "", glow: "", card: "", cardLabel: "", task: "", current: "Read", cost: null, started: null, ended: null, ...extra });
const waits = (ns) => new Map(ns.map((x) => [x.id, { kind: "tool", what: "Read a file", since: null, who: x.key, tool: "Read" }]));
const path = { leaf: null, wait: null };
const guest = [node("main", null, { guest: true }), node("a1", "main", { guest: true })];
const plain = [node("main", null, {}), node("a1", "main", {})];
const g = n.narrate(guest, waits(guest), path, () => "");
const p = n.narrate(plain, waits(plain), path, () => "");
const gs = { kind: "guest" }, ts = { kind: "tui" };
console.log(JSON.stringify({ guest: g.text, guestRows: g.rows, plain: p.text,
  cost: [w.agentCost(gs, 0), w.agentCost(gs, null), w.agentCost(ts, 0), w.agentCost(ts, 0.5)],
  why: [w.watchWhy(gs), w.watchWhy(ts) === undefined] }));
"""


@test
def test_a_claude_code_sessions_cost_reads_not_known_on_live_and_on_every_card(ctx: Ctx):
    """The check: outside Session's Cost panel a guest's spend read $0 (Live's narration: spendWords; the cards:
    cost(a.cost_usd)). A guest's agents are marked (liveModel `guest`), the narration says "cost not known", and the
    cards' cost (fleet/watchOnly.agentCost, used by the inspector, its glance, the pinned stream and the Map's drawer)
    says "not known"; a terminal session's figures are as they were."""
    from tests.helpers import node_ts
    routes = WORDS.parent.parent
    got = node_ts.run(JS_GUEST_COST % (json.dumps((routes / "crew" / "live" / "narrate.ts").resolve().as_uri()),
                                       json.dumps((routes / "fleet" / "watchOnly.ts").resolve().as_uri()))) or {}
    ctx.check(f"Live's sentence: cost not known, no $ figure; got {got.get('guest')!r}",
              str(got.get("guest") or "").endswith("· cost not known") and "$" not in str(got.get("guest")))
    ctx.check(f"its per-place rows too, got {got.get('guestRows')}", all("cost not known" in r[1] and "$" not in r[1] for r in got.get("guestRows") or [[0, "$"]]))
    ctx.check(f"a terminal session's sentence keeps its figure, got {got.get('plain')!r}", str(got.get("plain") or "").endswith("· $0.000"))
    ctx.check(f"the cards: not known for a guest, the figure otherwise; got {got.get('cost')}",
              (got.get("cost") or [None] * 4)[:2] == ["not known", "not known"]
              and all(str(c).startswith("$") for c in (got.get("cost") or [""] * 4)[2:]))
    ctx.check("the controls' title is the watch-only line", (got.get("why") or [None])[0] == "Claude Code · watch only: Studio shows this session; nothing is typed into it or steered from here."
              and (got.get("why") or [None, None])[1] is True)
    fleet = routes / "fleet"
    src = {p: (routes / p).read_text(encoding="utf-8") for p in ("fleet/Agent.tsx", "fleet/Pip.tsx", "crew/map/BoxHead.tsx",
                                                                  "crew/live/liveModel.ts", "fleet/store.ts")}
    ctx.check("no card prints cost(a.cost_usd) any more", not any("{cost(" in s or "money(" in s for s in src.values()))
    ctx.check("liveModel marks a guest record's agents (3.6.0.26 H: but a hand-out worker's, whose cost is Halo's)",
              'rec.kind === "guest" && a.row.kind !== "halo-worker" ? { guest: true }' in src["crew/live/liveModel.ts"])
    ctx.check("a guest session's name carries 'watch only' on every view (sessionTitle)",
              "isGuest(s) ? `${title} · ${WATCH_ONLY}`" in src["fleet/store.ts"])
    ctx.check("the inspector's controls are off with the line for a guest", "watchWhy(r.s, a)" in src["fleet/Agent.tsx"]
              and '|| !!watchOnly' in src["fleet/Agent.tsx"] and fleet.is_dir())


@test
def test_a_hand_out_workers_card_shows_its_numbers_and_its_stop_works_every_other_guest_card_stays_watch_only(ctx: Ctx):
    """3.6.0.26 H: a hand-out worker's row (agent kind `halo-worker`) in a Claude Code session is Halo's: its cost
    shows and its Stop is on (it stops that job); its Pause and Steer stay off with a line that says why; every other
    agent of the guest stays watch only, and a terminal session is as it was."""
    from tests.helpers import node_ts
    routes = WORDS.parent.parent
    js = """const w = await import(%s);
const g = { kind: "guest" }, t = { kind: "tui" }, worker = { kind: "halo-worker" }, sub = { kind: "subagent" };
console.log(JSON.stringify({ cost: [w.agentCost(g, 0, worker), w.agentCost(g, 0, sub), w.agentCost(g, 0), w.agentCost(t, 0, sub)],
  stop: [w.stopWhy(g, worker) ?? null, w.stopWhy(g, sub) ?? null, w.stopWhy(g) ?? null, w.stopWhy(t, sub) ?? null],
  watch: [w.watchWhy(g, worker) ?? null, w.watchWhy(g, sub) ?? null, w.watchWhy(t, worker) ?? null],
  pip: w.pipMeta(g, "running", 0, "claude-code", worker) }));""" % json.dumps((routes / "fleet" / "watchOnly.ts").resolve().as_uri())
    got = node_ts.run(js)
    if got is None:
        return
    ctx.check(f"the worker's cost is its figure, every other guest agent's not known; got {got['cost']}",
              got["cost"][0].startswith("$") and got["cost"][1:3] == ["not known", "not known"] and got["cost"][3].startswith("$"))
    ctx.check(f"the worker's Stop is on; a guest's other agents' and the session's off; got {got['stop']}",
              got["stop"][0] is None and str(got["stop"][1]).startswith("Claude Code · watch only")
              and str(got["stop"][2]).startswith("Claude Code · watch only") and got["stop"][3] is None)
    ctx.check(f"its other controls: off with their own line; got {got['watch']}",
              got["watch"][0] == "a hand-out takes Stop only: Halo runs it for this Claude Code session"
              and str(got["watch"][1]).startswith("Claude Code · watch only") and got["watch"][2] is None)
    ctx.check(f"the pinned stream shows the worker's figure, got {got['pip']!r}", "not known" not in got["pip"])
    src = {p: (routes / p).read_text(encoding="utf-8") for p in ("fleet/Agent.tsx", "crew/map/Feed.tsx")}
    ctx.check("the inspector's and the Map feed's Stop read stopWhy", "stopWhy(r.s, a)" in src["fleet/Agent.tsx"]
              and "disabled={!!stopNo}" in src["crew/map/Feed.tsx"])


@test
def test_the_pinned_streams_meta_line_keeps_its_spaces(ctx: Ctx):
    """The review of 3.6.0.25 G: the cost change lost the space before the harness name ("idle · $0.0000 ·halo") for
    every session. The line is watchOnly.pipMeta now, the one the pinned stream (fleet/Pip.tsx) prints."""
    from tests.helpers import node_ts
    fleet = WORDS.parent.parent / "fleet"
    js = """const w = await import(%s);
console.log(JSON.stringify([w.pipMeta({ kind: "tui" }, "idle", 0, "halo"), w.pipMeta({ kind: "guest" }, "running", null, "claude-code"),
  w.pipMeta(null, "done", 0.5, "a-very-long-harness-name")]));""" % json.dumps((fleet / "watchOnly.ts").resolve().as_uri())
    got = node_ts.run(js)
    if got is None:
        return
    ctx.check(f"state · cost · name, a space on each side of every dot; got {got}",
              got == ["idle · $0.0000 · halo", "running · not known · claude-code", "done · $0.5000 · a-very-long-har…"])
    pip = (fleet / "Pip.tsx").read_text(encoding="utf-8")
    ctx.check("the pinned stream prints that line (3.6.0.26 H: with its agent, a worker shows its figure)", "{pipMeta(ref.s, a.state, a.cost_usd, ref.h.name, a)}" in pip)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio prompt words"))
