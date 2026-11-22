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
    ("!echo hi", True, "submit"),         # with an image it stays a prompt, as in the terminal
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


@test
def test_the_prompt_panels_help_says_what_a_bang_line_does(ctx: Ctx):
    src = HELP_TS.read_text(encoding="utf-8")
    block = src.split('"session-prompt"', 1)[-1].split('"session-conversations"', 1)[0]
    ctx.check("the Prompt panel's help holds the sentence, word for word", BANG_HELP in block)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio prompt words"))
