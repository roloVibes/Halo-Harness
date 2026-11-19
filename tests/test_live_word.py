"""tests.test_live_word -- Halo 3.6.0.2 R53 "'Live' names only the run": no visible string in Studio says Live except
the Live view (Agents -> 4 · Live), Session's Live drawer and links to them. Session's line-by-line panel is the Feed
(R35, `WORDS.feed`), the Map is the plan, Local's log tail follows (it is not a run). The lines that promised a live
tree, a fleet scope or a Mission panel say what is really there, and a button's title names where its click lands.
Plain Python: reads the UI source, no browser.
Run: python -m tests.test_live_word
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SRC = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"
ROUTES = SRC / "routes"
WORD = re.compile(r"\bLive\b")
# (i) where the words live and the Live view itself: a "Live" there is the run's own name
OWN = {"routes/agents/LiveView.tsx", "routes/crew/map/truth.ts", "routes/crew/map/truthWords.ts"}
# (ii) a link to the view
LINKS = ("Agents -> Live", "Agents Live", "4 · Live")
# (iv) 3.6.0.5 b (the coordinator's ruling): two ruled phrases of M1 that ARE the Live view. Each phrase is allowed, not
#      its file: a string that still says Live once the phrase is taken out is a hit.
PHRASES = (
    "Live draws each task as a named group",  # says what the Live view (Agents -> 4 · Live) draws on Auto
    "Watch it in Live",  # the button that lands on Agents -> 4 · Live
)
# (iii) files of another package left to the coordinator, with the reason (expected empty)
OTHERS: dict[str, str] = {}
STOP = set("<>{}();=")


def _read(rel: str) -> str:
    return (ROUTES / rel).read_text(encoding="utf-8")


def _segments(text: str) -> tuple[list[tuple[int, str]], str]:
    """The string literals' texts (with their line) and the code with comments and strings blanked (same length)."""
    out: list[tuple[int, str]] = []
    code = list(text)
    i, n, line = 0, len(text), 1

    def blank(a: int, b: int) -> None:
        for k in range(a, b):
            if code[k] != "\n":
                code[k] = " "

    def template(start: int) -> int:  # text[start] == "`"; returns the index after its closing back-tick
        nonlocal line
        j, buf, at = start + 1, [], line
        while j < n:
            c = text[j]
            if c == "\\":
                buf.append(text[j:j + 2])
                j += 2
                continue
            if c == "`":
                out.append((at, "".join(buf)))
                blank(start, j + 1)
                return j + 1
            if c == "$" and j + 1 < n and text[j + 1] == "{":
                out.append((at, "".join(buf)))
                blank(start, j + 2)
                buf, depth, j = [], 1, j + 2
                while j < n and depth:  # the expression: its strings count too
                    k = scan_one(j)
                    if k != j:
                        j = k
                        continue
                    depth += {"{": 1, "}": -1}.get(text[j], 0)
                    j += 1
                start, at = j, line
                continue
            if c == "\n":
                line += 1
            buf.append(c)
            j += 1
        return j

    def scan_one(j: int) -> int:
        """At j: skip a comment or a string if one starts here (recording it); return where the code goes on."""
        nonlocal line
        c = text[j]
        if text.startswith("//", j):
            e = text.find("\n", j)
            e = n if e < 0 else e
            blank(j, e)
            return e
        if text.startswith("/*", j):
            e = text.find("*/", j + 2)
            e = n if e < 0 else e + 2
            line += text.count("\n", j, e)
            blank(j, e)
            return e
        if c == "`":
            return template(j)
        if c in "\"'" and not (j > 0 and (text[j - 1].isalnum())):  # a quote after a letter is JSX text's apostrophe
            k = j + 1
            while k < n and text[k] != c and text[k] != "\n":
                k += 2 if text[k] == "\\" else 1
            out.append((line, text[j + 1:k]))
            blank(j, min(k + 1, n))
            return min(k + 1, n)
        if c == "\n":
            line += 1
        return j

    while i < n:
        j = scan_one(i)
        i = j + 1 if j == i else j
    return out, "".join(code)


def _jsx_text_hits(code: str) -> list[tuple[int, str]]:
    """A "Live" in the code that is JSX text: between a tag's `>` and the next `<`, with no code character between."""
    hits = []
    for m in WORD.finditer(code):
        a = m.start()
        while a > 0 and code[a - 1] not in STOP:
            a -= 1
        b = m.end()
        while b < len(code) and code[b] not in STOP:
            b += 1
        if a > 0 and code[a - 1] == ">" and b < len(code) and code[b] == "<" and not code[a - 2:a] == "=>":
            hits.append((code.count("\n", 0, m.start()) + 1, " ".join(code[a:b].split())))
    return hits


def _visible_live(rel: str, text: str) -> list[str]:
    strings, code = _segments(text)
    found = [(ln, s) for ln, s in strings if WORD.search(s) and not s.lstrip().startswith(("./", "../"))]
    found += _jsx_text_hits(code)
    return [f"{rel}:{ln}: {s[:140]}" for ln, s in found
            if not any(k in s for k in LINKS) and WORD.search(_unphrased(s))]


def _unphrased(s: str) -> str:
    for k in PHRASES:
        s = s.replace(k, "")
    return s


def _between(text: str, start: str, end: str) -> str:
    a = text.find(start)
    if a < 0:
        return ""
    b = text.find(end, a + len(start))
    return text[a:b if b >= 0 else len(text)]


def _attr(tag_text: str, name: str) -> str:
    m = re.search(name + r'=(?:"([^"]*)"|\{[^}]*?"([^"]*)")', tag_text)
    return (m.group(1) or m.group(2) or "") if m else ""


@test
def test_live_names_only_the_run(ctx: Ctx):
    bad: list[str] = []

    def check(what: str, ok: bool) -> None:
        if not ok:
            bad.append(what)

    # 1. (P4 batch 12, rewritten to the truth: the coordinator's ruling) Setup -> Machines' five lines had no reader and a
    #    help entry was read by no panel (fleet-activity): both are gone, so no unread line can say Live
    check("MACHINES_WHAT is gone (no page read it)", "MACHINES_WHAT" not in _read("shared/StartBits.tsx"))
    check("no help entry for fleet-activity (no panel has that id)", '"fleet-activity"' not in _read("help-live.ts"))

    # 2. a button's words name where its click lands
    #    3.6.0.3 B (Z9, rewritten to the truth): the panel's Replay left; a LAST SESSIONS row's "export" saves that
    #    session's Markdown export (TraceExport's exportTrace), it goes nowhere in Studio
    hist = _read("fleet/AgentHistory.tsx")
    check("no Replay button in Session's agent panel (fleet-replay)", "fleet-replay" not in hist)
    export_link = next((ln for ln in hist.splitlines() if "fleet-history-export" in ln), "")
    check(f"a row's export link calls exportTrace, got {export_link.strip()[:160]!r}", "exportTrace(r.session_id)" in export_link)
    pip = _read("fleet/Pip.tsx")
    door = _between(_read("fleet/actions.ts"), "export function openAgentPanel", "\n}\n")
    to_live = 'goSection("agents", "live")' in door
    pip_words = re.findall(r'"(Open it[^"]*)"', pip)
    want = ("Agents -> Live", "Agents Live") if to_live else ("Agents -> Map", "Agents Map")
    check(f"the mini stream's Open names {want[0]} (openAgentPanel lands there), got {pip_words}",
              all(any(k in w for w in pip_words) for k in want))
    off = [w for w in pip_words if ("Map" if to_live else "Live") in w]
    check(f"no Open title names the other view, got {off}", not off)
    # Attention's O opens many places (a goal run's Map drawer, Workflows, Agents' Attention, an agent's Live):
    # the ruled words name the sections only, never one view of them
    o_help = next((ln for ln in _read("help-live.ts").splitlines() if "O opens where it belongs" in ln), "")
    check(f"Attention's O help reads the ruled '(Agents, Local)', got {o_help.strip()[:120]!r}",
          "O opens where it belongs (Agents, Local)." in o_help)

    # 3. the scan: no other visible string says Live
    hits: list[str] = []
    for p in sorted(SRC.rglob("*.ts*")):
        if p.suffix not in (".ts", ".tsx") or "node_modules" in p.parts:
            continue
        rel = p.relative_to(SRC).as_posix()
        if rel in OWN or rel in OTHERS:
            continue
        text = "\n".join("" if ln.lstrip().startswith(("import ", "export * from", "*")) else ln
                         for ln in p.read_text(encoding="utf-8").split("\n"))
        hits += _visible_live(rel, text)
    check("no visible string says Live for something else:\n  " + "\n  ".join(hits), not hits)
    ctx.check("R53:\n" + "\n".join(bad), not bad)


@test
def test_python_lines_name_where_replays_and_history_are(ctx: Ctx):
    """P4 batch 12: the Python side too -- a line a person reads (a string, not a docstring or a comment) that says where a
    replay or History is names Agents -> Map (R55: History is the Map's), and none uses Live for the Feed ("what only
    Live showed", "Live's group title")."""
    import ast
    root = SRC.parents[2]  # halo_harness/
    bad = []
    for p in sorted(root.rglob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        docs = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant)}
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs:
                t = n.value
                where = re.search(r"Agents (?:->|→) Live", t) and re.search(r"History|replay", t, re.I)
                if where or "only Live showed" in t or "Live's group" in t:
                    bad.append(f"{p.relative_to(root).as_posix()}:{n.lineno}: {t[:90]!r}")
    sep = "\n  "
    ctx.check("lines that send him to Live for a replay or History, or call the Feed Live:" + sep + sep.join(bad), not bad)


@test
def test_the_scanner_sees_what_a_person_reads(ctx: Ctx):
    """The scan finds a Live in a title, a template's text and JSX text, and skips comments, names and links."""
    sample = "\n".join([
        "// Live in a comment",
        "/* Live in a block */",
        'const a = <button title="Show it in Live">x</button>;',
        "const b = `the ${x} Live view`;",
        "const c = <p>",
        "  show in Live",
        "</p>;",
        "const d = <Live />; const e = isLive(f); function Live() {}",
        'const g = "Open it in Agents -> Live";',
        "const h = <p>A Live row's <i>why</i></p>;",
        "const i = () => Live < 2;",
    ])
    got = _visible_live("x.tsx", sample)
    lines = sorted(int(h.split(":")[1]) for h in got)
    ctx.check(f"a title, a template, two JSX texts found; comments, names and the link not, got {got}",
              lines == [3, 4, 6, 10])
    # the two ruled phrases are allowed as phrases, never as a file: another Live beside them is still found
    words = "\n".join([
        'export const WATCH = "Watch it in Live";',
        "const m = `Main picks, and Live draws each task as a named group. Main can hand work to: ${l}.`;",
        'const n = "Watch it in Live, or open Live";',
        'const o = "Live draws each task";',
    ])
    got = _visible_live("routes/crew/map/autoWords.ts", words)
    lines = sorted(int(h.split(":")[1]) for h in got)
    ctx.check(f"the two ruled phrases pass, a made-up Live beside or apart from them is found, got {got}", lines == [3, 4])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
