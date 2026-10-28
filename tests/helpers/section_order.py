"""tests.helpers.section_order -- Studio's section order (Halo 3.1.6.0 R6):
`routes/index.tsx` SECTIONS parsed as (id, title, key, blurb) rows, and the
reader that finds every `Alt+N` a text file names and the section it names
it for, so tests/test_studio_section_order.py can hold every doc line, every
UI copy line and the modes banner to the registry.

How a key is matched to its section, nearest first:
  1. a section title (`Session`, `Roles`, ...) or an id hint (`?mode=<id>`,
     `--mode <id>`, `/studio <id>`, `--session`, `--fleet`, `/roles`,
     `/design`, `halo design`) on the same line, the closest one;
  2. else one on the line just above or below, in the same paragraph;
  3. else the nearest Markdown heading above that names exactly one section.
A range (`Alt+1`..`Alt+9`, `Alt+1` to `Alt+7`, `Alt+1..8`, `Alt+1..0`) names no single
section: its paragraph's run of six titles or more (`Orchestra, Roles, ...`,
`**A** | **B**`, `A, B and C`) must be the registry's order from its start
(3.2.0.0 R6: the six work sections, then Packs; 3.3.0.0 R1: then Setup; 3.3.3.0 R2: then Settings; 3.3.5.0 R1:
then Local, on Alt+0: the key `0` is the tenth slot).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INDEX = REPO / "halo_harness" / "studio" / "ui" / "src" / "routes" / "index.tsx"
BANNER = REPO / "tools" / "studio_modes_banner.py"

_ENTRY = re.compile(r'\{ id: "(\w+)", title: "(\w+)", kbd: "(Alt\+\d)", blurb: "([^"]*)"')
KEY = re.compile(r"Alt\+([0-9])(?!\d)")  # 3.2.0.0 R6: Packs is Alt+7; 3.3.0.0 R1: Setup is Alt+8; 3.3.3.0 R2: Settings is Alt+9; 3.3.5.0 R1: Local is Alt+0
RANGE = re.compile(r"`?Alt\+1`?\s*(?:\.\.\.?|to|-)\s*`?(?:Alt\+)?[67890](?!\d)`?")  # 3.3.0.0 R1: ..8; 3.3.3.0 R2: ..9; 3.3.5.0 R1: ..0
_SEP = re.compile(r"[\s*`,|/]*(?:and\s+)?[\s*`,|/]*")
HEADING = re.compile(r"^#{1,6} ")


def registry(text: "str | None" = None) -> "list[tuple[str, str, str, str]]":
    """The SECTIONS rows in order: (id, title, kbd, blurb)."""
    src = text if text is not None else INDEX.read_text(encoding="utf-8")
    body = src.split("export const SECTIONS", 1)[1].split("];", 1)[0]
    return _ENTRY.findall(body)


def banner_frames() -> "list[tuple]":
    """tools/studio_modes_banner.py's FRAMES, read with ast (the tool imports Pillow; this does not)."""
    tree = ast.parse(BANNER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "FRAMES" for t in node.targets):
            return list(ast.literal_eval(node.value))
    return []


def _patterns(rows):
    titles = "|".join(t for _, t, _, _ in rows)
    ids = "|".join(i for i, _, _, _ in rows)
    title = re.compile(rf"\b({titles})\b")
    hint = re.compile(rf"(?:\?mode=|--mode |/studio )({ids})\b|--(session|fleet)\b|(?<=[\s`(])/(roles|design)\b|halo (design)\b")
    return title, hint


def _mentions(line: str, rows) -> "list[tuple[int, int, str]]":
    """(start, end, section id) of every title and id hint on `line`."""
    title, hint = _patterns(rows)
    by_title = {t: i for i, t, _, _ in rows}
    out = [(m.start(), m.end(), by_title[m.group(1)]) for m in title.finditer(line)]
    out += [(m.start(), m.end(), next(g for g in m.groups() if g)) for m in hint.finditer(line)]
    return out


def _closest(line: str, a: int, b: int, rows) -> "str | None":
    best = None
    for s, e, sid in _mentions(line, rows):
        d = a - e if e <= a else (s - b if s >= b else 0)
        if best is None or d < best[0]:
            best = (d, sid)
    return best[1] if best else None


def _heading_section(lines: "list[str]", i: int, rows) -> "str | None":
    for j in range(i, -1, -1):
        if HEADING.match(lines[j]):
            found = {sid for _, _, sid in _mentions(lines[j], rows)}
            return found.pop() if len(found) == 1 else None
    return None


def _paragraph(lines: "list[str]", i: int) -> "tuple[int, int]":
    lo = i
    while lo > 0 and lines[lo - 1].strip():
        lo -= 1
    hi = i
    while hi + 1 < len(lines) and lines[hi + 1].strip():
        hi += 1
    return lo, hi


def title_runs(text: str, rows) -> "list[list[str]]":
    """Every run of section titles separated only by list punctuation (three titles or more)."""
    title, _ = _patterns(rows)
    runs, cur, last_end = [], [], None
    for m in title.finditer(text):
        if cur and _SEP.fullmatch(text[last_end:m.start()]):
            cur.append(m.group(1))
        else:
            if len(cur) >= 3:
                runs.append(cur)
            cur = [m.group(1)]
        last_end = m.end()
    if len(cur) >= 3:
        runs.append(cur)
    return runs


def scan(text: str, rows) -> "tuple[list, list]":
    """(pairs, ranges): pairs are (line no, key n, section id or None, line); ranges are (line no, the
    paragraph's title runs, line)."""
    lines = text.split("\n")
    pairs, ranges = [], []
    for i, line in enumerate(lines):
        spans = [m.span() for m in RANGE.finditer(line)]
        if spans:
            lo, hi = _paragraph(lines, i)
            ranges.append((i + 1, title_runs("\n".join(lines[lo:hi + 1]), rows), line.strip()))
        for m in KEY.finditer(line):
            if any(a <= m.start() < b for a, b in spans):
                continue
            sid = _closest(line, m.start(), m.end(), rows)
            if sid is None:
                lo, hi = _paragraph(lines, i)
                near = [(abs(j - i), _closest(lines[j], len(lines[j]) if j < i else 0, len(lines[j]) if j < i else 0, rows))
                        for j in (i - 1, i + 1) if lo <= j <= hi]
                near = [n for n in sorted(near, key=lambda n: n[0]) if n[1]]
                sid = near[0][1] if near else _heading_section(lines, i, rows)
            pairs.append((i + 1, int(m.group(1)) or 10, sid, line.strip()))  # Alt+0 is the tenth slot
    return pairs, ranges


def problems(path: Path, rows) -> "list[str]":
    """Every line of `path` whose Alt+N names another section than the registry's, or whose range lists
    the six sections out of order."""
    want = {n: sid for n, (sid, _, _, _) in enumerate(rows, 1)}
    order = [t for _, t, _, _ in rows]
    rel = path.relative_to(REPO).as_posix()
    out = []
    pairs, ranges = scan(path.read_text(encoding="utf-8"), rows)
    for no, n, sid, line in pairs:
        if sid is None:
            out.append(f"{rel}:{no}: Alt+{n % 10} names no section the reader can find: {line[:120]}")
        elif sid != want[n]:
            out.append(f"{rel}:{no}: Alt+{n % 10} is {want.get(n)}, the line names {sid}: {line[:120]}")
    for no, runs, line in ranges:
        for run in runs:
            if len(set(run)) >= 6 and run != order[:len(run)]:  # 3.2.0.0 R6: the six, or the six then Packs (3.3.0.0 R1: then Setup; 3.3.3.0 R2: then Settings; 3.3.5.0 R1: then Local)
                out.append(f"{rel}:{no}: the sections run {', '.join(run)}, the registry {', '.join(order)}: {line[:120]}")
    return out
