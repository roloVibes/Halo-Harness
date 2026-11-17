"""tests.test_studio_prompt_words -- 3.6.0.2 P6 ("one prompt"): the Prompt panel's pure words and rules,
routes/session/promptWords.ts run under node (skipped without a node that runs .ts), against Python's:

1. `askLabel` gives the same label as `events.ask_label` for every row of THE table (permission, question, plan,
   approval, with and without typed words), and the answered lines' words are Python's (P5, P23);
2. P72: the answer removes only the text sent, and only while the record made at Enter stands: an edit after the
   sent text keeps the record, an edit, paste, cut or recall that touches its first characters drops it, and a box
   that no longer begins with the sent text is left whole.
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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio prompt words"))
