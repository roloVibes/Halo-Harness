"""tests.test_remote_render -- Halo 2.0.9 round 3: outbound rendering
(`halo_harness/remote/render.py`, `bridge_cards.py`): Markdown flattened to
plain text, chunking at 1800 UTF-8 bytes, the text-attachment fallback past
four chunks, MONOSPACE style ranges in UTF-16 units, and the card texts.
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from halo_harness.remote import bridge_cards as cards
from halo_harness.remote import render
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def nb(s: str) -> int:
    return len(s.encode("utf-8"))


@test
def test_markdown_flattening(ctx: Ctx):
    md = ("# Title\n\n## Sub head\n\nSome **bold**, *italic*, __strong__, `inline` and snake_case_name.\n\n"
          "- one\n* two\n+ three\n  - nested\n\n1. first\n2. second\n\n> quoted\n\n"
          "A [link](http://example.invalid/x) and ![img](http://example.invalid/i.png).\n\n---\n\nend")
    out = render.render_markdown(md)
    text = out.messages[0].text
    lines = text.split("\n")
    ctx.check("one message, no attachment", len(out.messages) == 1 and out.attachment is None)
    ctx.check("headings become upper-case lines", "TITLE" in lines and "SUB HEAD" in lines)
    ctx.check("emphasis and inline-code markers are dropped", "Some bold, italic, strong, inline and snake_case_name." in lines)
    ctx.check("lists use '-' and keep their indent", "- one" in lines and "- two" in lines and "- three" in lines and "  - nested" in lines)
    ctx.check("numbered lists are kept", "1. first" in lines and "2. second" in lines)
    ctx.check("quote markers are dropped", "quoted" in lines)
    ctx.check("links become 'text (url)'", "A link (http://example.invalid/x) and img (http://example.invalid/i.png)." in lines)
    ctx.check("rules vanish and blank runs collapse", "---" not in lines and "\n\n\n" not in text)
    ctx.check("no styles without code", out.messages[0].styles == [])


@test
def test_code_fences_and_monospace_ranges(ctx: Ctx):
    md = "Before\n\n```python\nx = 1\n  y = 'two'\n```\nAfter\n\n~~~\nlast = True\n~~~"
    out = render.render_markdown(md)
    text = out.messages[0].text
    ctx.check("fence lines are dropped, code lines kept verbatim (indent included)",
              text == "Before\n\nx = 1\n  y = 'two'\nAfter\n\nlast = True")
    u16 = text.encode("utf-16-le")

    def span(sty):
        a, n, kind = sty.split(":")
        return u16[int(a) * 2:(int(a) + int(n)) * 2].decode("utf-16-le"), kind

    got = [span(s) for s in out.messages[0].styles]
    ctx.check("each code run is one MONOSPACE range covering exactly its lines",
              got == [("x = 1\n  y = 'two'", "MONOSPACE"), ("last = True", "MONOSPACE")])
    em = render.render_markdown("café \U0001f600 ok\n```\ncode \U0001f600\n```")
    t2 = em.messages[0].text.encode("utf-16-le")
    a, n, _ = em.messages[0].styles[0].split(":")
    ctx.check("ranges count UTF-16 code units (an emoji is two)",
              t2[int(a) * 2:(int(a) + int(n)) * 2].decode("utf-16-le") == "code \U0001f600" and int(n) == 7)
    st = {}
    first = render.render_markdown("intro\n```\nline one", st)
    second = render.render_markdown("line two\n```\nback to text", st)
    ctx.check("a fence spanning two streamed pieces keeps its meaning",
              first.messages[0].styles and second.messages[0].styles and "back to text" in second.messages[0].text
              and second.messages[0].styles[0].startswith("0:8:"))


@test
def test_chunking_at_the_byte_limit(ctx: Ctx):
    words = " ".join(f"word{i:04d}" for i in range(700))
    out = render.render_plain(words)
    sizes = [nb(m.text) for m in out.messages]
    ctx.check("a long text is several messages", 2 <= len(out.messages) <= 4 and out.attachment is None)
    ctx.check("every message is at most 1800 UTF-8 bytes", max(sizes) <= render.CHUNK_BYTES)
    ctx.check("no word is cut: rejoining the chunks gives the original words",
              " ".join(m.text.replace("\n", " ") for m in out.messages).split() == words.split())
    multi = ("éèê " * 400).strip()
    sizes = [nb(m.text) for m in render.render_plain(multi).messages]
    ctx.check("multibyte text is counted in bytes, not characters", len(multi) < 1800 < nb(multi) and len(sizes) >= 2
              and max(sizes) <= 1800)
    token = "x" * 4000
    toks = render.render_plain(token).messages
    ctx.check("a single huge token is split on the byte boundary",
              len(toks) == 3 and all(nb(m.text) <= 1800 for m in toks) and "".join(m.text for m in toks) == token)
    emo = "\U0001f600" * 700  # 4 bytes each
    ctx.check("a character is never cut in half", all(nb(m.text) <= 1800 and m.text.encode("utf-8").decode("utf-8")
                                                   for m in render.render_plain(emo).messages))
    paras = "\n\n".join(f"paragraph {i} " + "word " * 60 for i in range(12))
    out = render.render_plain(paras)
    whole = {ln for ln in paras.splitlines() if ln}
    seen = {ln for m in out.messages for ln in m.text.splitlines() if ln}
    ctx.check("lines that fit are never split across messages", whole <= seen and len(out.messages) >= 2
              and all(nb(m.text) <= 1800 for m in out.messages))
    ctx.check("exactly 1800 bytes fits in one message", len(render.render_plain("a" * 1800).messages) == 1
              and len(render.render_plain("a" * 1801).messages) == 2)


@test
def test_attachment_fallback_past_four_chunks(ctx: Ctx):
    four = "word " * 1400   # 7000 bytes -> 4 chunks
    ctx.check("4 chunks stay as 4 messages", len(render.render_plain(four).messages) == 4
              and render.render_plain(four).attachment is None)
    big = "line of text number\n" * 600   # 12000 bytes
    out = render.render_plain(big)
    ctx.check("more than 4 chunks becomes ONE message plus a text attachment",
              len(out.messages) == 1 and out.attachment is not None)
    ctx.check("the message is a short head and says where the rest is",
              nb(out.messages[0].text) < 1500 and "attached as reply.txt" in out.messages[0].text)
    head = "data:text/plain;filename=reply.txt;base64,"
    ctx.check("the attachment is a data: URI with the reply file name", out.attachment.startswith(head))
    ctx.check("it decodes to the whole text", base64.b64decode(out.attachment[len(head):]).decode("utf-8").strip() == big.strip())


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
