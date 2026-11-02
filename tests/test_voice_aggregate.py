"""tests.test_voice_aggregate -- Halo 3.3.9.0 R2: the sentence aggregator (halo_harness/voice/aggregate.py), a table:
the deltas as a model streams them -> the sentences the speech server is handed, in order. A sentence ends at . ? ! before
a space (or at the reply's end), at a newline, or at 200 characters (the last space before); a fenced code block is said
once as "a code block"; tool-call lines and [...] markup are never said; a decimal point or an open [ never cuts.
Run: python -m tests.test_voice_aggregate
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
LONG = " ".join(["word"] * 60)

TABLE = [
    ("three ends", ["Hello there. How are you? Fine!"], ["Hello there.", "How are you?", "Fine!"]),
    ("split across deltas", ["Hel", "lo the", "re. Wh", "at now?"], ["Hello there.", "What now?"]),
    ("a decimal point never cuts", ["It costs 3.5 dollars", " today. Yes."], ["It costs 3.5 dollars today.", "Yes."]),
    ("a newline cuts", ["first line\nsecond line"], ["first line", "second line"]),
    ("a fence is said once", ["Look:\n``", "`py\nx = 1\ny = 2\n```\nDone."], ["Look:", "a code block", "Done."]),
    ("two fences, two mentions", ["A.\n```\na\n```\nB.\n~~~\nb\n~~~\n"], ["A.", "a code block", "B.", "a code block"]),
    ("tool-call lines are skipped", ["Checking.\n<tool_call>{\"name\": \"Read\"}</tool_call>\n", "⏺ Bash(ls)\n",
                                     "{\"name\": \"Grep\", \"arguments\": {}}\nFound it."], ["Checking.", "Found it."]),
    ("[...] markup out, a link keeps its text", ["See [1] and [the ", "docs](https://x.y/z). Then [x] go."],
     ["See and the docs.", "Then go."]),
    ("markdown marks out", ["## Title\n- **bold** item\n1. `code` step\n"], ["Title", "bold item", "code step"]),
    ("200 characters cut at a space", [LONG + LONG], None),
]


@test
def test_the_cut_rules(ctx: Ctx):
    from halo_harness.voice.aggregate import MAX_CHARS, Aggregator
    for name, deltas, want in TABLE:
        a = Aggregator()
        got: list = []
        for d in deltas:
            got += a.feed(d)
        got += a.flush()
        if want is None:
            ctx.check(f"{name}: each at most {MAX_CHARS}, cut at a space, nothing lost, got {[len(s) for s in got]}",
                      len(got) >= 3 and all(len(s) <= MAX_CHARS for s in got) and " ".join(got).split() ==
                      (LONG + LONG).split())
        else:
            ctx.check(f"{name}: got {got}", got == want)


@test
def test_a_sentence_is_handed_over_as_soon_as_it_ends(ctx: Ctx):
    from halo_harness.voice.aggregate import Aggregator
    a = Aggregator()
    ctx.check("nothing while the first sentence is open", a.feed("The first sentence") == [])
    ctx.check("it goes out at its end, before the reply ends", a.feed(" ends here. And the sec") ==
              ["The first sentence ends here."])
    ctx.check("a line that may become a fence waits for its newline", a.feed("ond.\n`") == ["And the second."]
              and a.feed("``\ncode\n") == ["a code block"])
    ctx.check("inside the fence nothing is said", a.feed("more code. Still code.\n") == [])
    ctx.check("after it the reply speaks again", a.feed("```\nBack.") == [] and a.flush() == ["Back."])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
