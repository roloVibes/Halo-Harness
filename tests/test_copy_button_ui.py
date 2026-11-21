"""tests.test_copy_button_ui -- Studio's Copy button on a reply and on a code block (Halo 3.6.0.6 C, the owner's point
33 of 2026-11-20: "Copying from the session barely works!"), the page's pure half: lib/copyText.ts run under node
(skipped without a node that runs .ts), and its wiring in Session's Live column and the Prompt panel's feed. The whole
path in Chrome (a real hover, a real press, the clipboard read back) is tests/test_studio_copy.py.

1. a reply is split into prose and code blocks without losing a character; a code block's Copy gives the code only,
   its indentation and line breaks kept, no fence lines; a reply's Copy gives the text as the agent wrote it;
2. the button's words are "Copy", "Copied" (two seconds) and "Select and copy it yourself";
3. ONE component, CopyButton, on every reply row and every code block of Live and of the Prompt feed;
4. a Live row's clock, kind, tag, Why control, after-text and the steer dock are not selectable, and a drag that
   selected text is not a click on the row.
Run: python -m tests.test_copy_button_ui
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SRC = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"
SESSION = SRC / "routes" / "session"

CODE = "def total(items):\n    return sum(\n        i.price for i in items\n    )\n\n\tprint('tab kept')"
REPLY = f"Here is the fix:\n```python\n{CODE}\n```\nThen run it.\n~~~\nhalo --version\n~~~\n"
CASES = {
    "prose and two blocks": REPLY,
    "no code at all": "Just words, two lines.\nThe second.",
    "a streaming reply, the fence not closed yet": "Start:\n```js\nconst a = 1;\n  const b = 2;",
    "an empty block": "Empty:\n```\n```\nafter",
    "windows line ends": "Lines:\r\n```\r\nx = 1\r\n  y = 2\r\n```\r\ndone",
    "a fence as the first line": "```sh\nls -la\n```",
}
WANT_CODE = {
    "prose and two blocks": [CODE, "halo --version"],
    "no code at all": [],
    "a streaming reply, the fence not closed yet": ["const a = 1;\n  const b = 2;"],
    "an empty block": [""],
    "windows line ends": ["x = 1\r\n  y = 2"],
    "a fence as the first line": ["ls -la"],
}

JS = """
const m = await import(%s);
const out = {words: [m.COPY, m.COPIED, m.COPY_REFUSED, m.COPIED_MS], cases: {}};
for (const [name, src] of Object.entries(%s)) {
  const segs = m.segments(src);
  out.cases[name] = {joined: m.joined(segs) === src, code: m.codeBlocks(src), source: m.replySource({text: src}),
                     opens: segs.filter((s) => s.code).map((s) => s.open)};
}
console.log(JSON.stringify(out));
"""


def _run() -> dict:
    from tests.helpers import node_ts
    js = JS % (json.dumps((SRC / "lib" / "copyText.ts").resolve().as_uri()), json.dumps(CASES))
    return node_ts.run(js) or {}


@test
def test_a_code_blocks_copy_is_the_code_only_and_nothing_is_lost(ctx: Ctx):
    got = _run().get("cases") or {}
    for name, src in CASES.items():
        g = got.get(name) or {}
        ctx.check(f"{name}: the segments joined are the reply again, got {g.get('joined')!r}", g.get("joined") is True)
        ctx.check(f"{name}: each block's code, indentation and line breaks kept, got {g.get('code')!r}", g.get("code") == WANT_CODE[name])
        ctx.check(f"{name}: the reply's Copy is its source, got {g.get('source')!r}", g.get("source") == src)
    ctx.check(f"the fence lines are not code, got {(got.get('prose and two blocks') or {}).get('opens')!r}",
              (got.get("prose and two blocks") or {}).get("opens") == ["```python", "~~~"])


@test
def test_the_buttons_words(ctx: Ctx):
    ctx.check("Copy, Copied for two seconds, and the refused clipboard's words",
              _run().get("words") == ["Copy", "Copied", "Select and copy it yourself", 2000])


@test
def test_one_copy_button_on_every_reply_and_code_block(ctx: Ctx):
    btn = SRC / "lib" / "ui" / "CopyButton.tsx"
    ctx.check("lib/ui/CopyButton.tsx is the one component", btn.is_file())
    b = btn.read_text(encoding="utf-8") if btn.is_file() else ""
    ctx.check("it says the words of lib/copyText.ts and writes with the page's clipboard",
              all(w in b for w in ("COPY", "COPIED", "COPY_REFUSED", "COPIED_MS", "navigator.clipboard")))
    ctx.check("it is a tab stop (no tabIndex of -1)", "tabIndex={-1}" not in b)
    ctx.check("a refused clipboard selects the text for him", "addRange" in b)
    reply = SESSION / "ReplyText.tsx"
    r = reply.read_text(encoding="utf-8") if reply.is_file() else ""
    ctx.check("ReplyText draws a reply's code blocks, each with its CopyButton", "segments(" in r and "<CopyButton" in r)
    rows = (SESSION / "LiveRows.tsx").read_text(encoding="utf-8")
    feed = (SESSION / "PromptFeed.tsx").read_text(encoding="utf-8")
    for name, s in (("Live", rows), ("the Prompt feed", feed)):
        ctx.check(f"{name}: a reply draws through ReplyText and carries a CopyButton of its source",
                  "<ReplyText" in s and "<CopyButton" in s and "replySource(" in s)
    for f in SRC.rglob("*.tsx"):
        if f.name != "CopyButton.tsx":
            ctx.check(f"{f.name}: no second Copy button of a reply", "function CopyButton" not in f.read_text(encoding="utf-8"))


@test
def test_a_live_rows_chrome_is_not_selectable_and_a_drag_is_not_a_click(ctx: Ctx):
    css = (SRC / "styles" / "session-live.css").read_text(encoding="utf-8")
    m = re.search(r"([^{}]*)\{[^{}]*user-select:\s*none", css)
    sel = m.group(1) if m else ""
    for cls in (".fac-ts", ".fac-kind", ".slv-who", ".slv-why", ".slv-after", ".slv-foot", ".copy-btn"):
        ctx.check(f"{cls} is not selectable, got {sel.strip()!r}", cls in sel)
    ctx.check("the Steer box's own text stays selectable", re.search(r"\.slv-foot\s*:is\(textarea, input\)\s*\{\s*user-select:\s*text", css) is not None)
    rows = (SESSION / "LiveRows.tsx").read_text(encoding="utf-8")
    ctx.check("the row's pick returns early on a selection inside the row", "dragged(" in rows and "const pick" in rows
              and re.search(r"const pick = .*dragged\(", rows) is not None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="copy button ui"))
