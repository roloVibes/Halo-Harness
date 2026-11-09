"""tests.test_remote_cards -- the plain-text cards and the reply parsers (halo_harness/remote/cards.py; Halo 2.0.9
round 3 as bridge_cards.py, 3.3.13.0 R3 renamed: the attention queue, the supervisor's asks and every transport
-- the signal pack through halo_harness.ext.remote.cards -- draw the same text). Moved here from
tests/test_remote_render.py when the rendering left with the signal pack.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from halo_harness.remote import cards  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_cards_and_replies(ctx: Ctx):
    card = cards.permission_card({"name": "Bash", "input": {"command": "rm -rf build"}, "reason": "writes files"})
    ctx.check("permission card: tool, one-line detail, reason, four choices",
              card.splitlines()[:3] == ["Permission needed: Bash", "rm -rf build", "Why: writes files"]
              and card.splitlines()[3:] == ["1 allow once", "2 allow for this session",
                                            "3 always allow (no rule was suggested, so nothing is saved)",
                                            "4 deny (4 <reason> to explain)"])
    ctx.check("a long multi-line input is shown in full, never flattened or cut",
              cards.describe_input("Bash", {"command": "a\n  b " * 100}) == ("a\n  b " * 100).strip("\n")
              and len(cards.describe_input("Bash", {"command": "a " * 500})) == 1000)
    for text, want in (("1", ("allow", "once", "")), ("2", ("allow", "session", "")), ("3", ("allow", "always", "")),
                       ("4", ("deny", "once", "")), ("4 too risky", ("deny", "once", "too risky")),
                       (" 2 ", ("allow", "session", ""))):
        got = cards.parse_permission_reply(text)
        ctx.check(f"permission reply {text!r}", got is not None and got[:3] == want)
    for text in ("5", "0", "12", "yes", "1x", "allow"):
        ctx.check(f"{text!r} is not a permission reply", cards.parse_permission_reply(text) is None)
    qs = cards.normalize_questions({"input": {"questions": [{"question": "Pick", "options": [{"label": "red"}, "blue"],
                                                             "multiSelect": True}]}})
    ctx.check("questions normalise from the list shape", qs == [{"question": "Pick", "options": ["red", "blue"], "multi": True}])
    ctx.check("and from the flat shape", cards.normalize_questions({"input": {"question": "Q", "options": ["a"]}})
              == [{"question": "Q", "options": ["a"], "multi": False}])
    q = qs[0]
    ctx.check("letters map to labels", cards.parse_question_reply(q, "b") == "blue"
              and cards.parse_question_reply(q, "a, b") == "red, blue" and cards.parse_question_reply(q, "A,B") == "red, blue")
    ctx.check("text that is not a letter list is the answer", cards.parse_question_reply(q, "c") == "c"
              and cards.parse_question_reply(q, "none of these") == "none of these")
    single = dict(q, multi=False)
    ctx.check("several letters on a single-choice question stay free text", cards.parse_question_reply(single, "a,b") == "a,b")
    ctx.check("the question card lists lettered options and a hint", cards.question_card(q).splitlines()[1:3] == ["a. red", "b. blue"]
              and "letters like a,c" in cards.question_card(q))
    st = {"cost_usd": 0.01234, "context_tokens": 5000, "context_limit": 20000}
    ctx.check("the closing line carries cost and context", cards.cost_line(st) == "Done. cost $0.0123, context 25%")
    ctx.check("without a price it shows tokens", cards.cost_line({"total_input_tokens": 10, "total_output_tokens": 3})
              == "Done. in 10 out 3 tokens")
    ctx.check("with nothing it is just Done.", cards.cost_line({}) == "Done.")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
