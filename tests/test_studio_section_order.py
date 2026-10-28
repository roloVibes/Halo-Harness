"""tests.test_studio_section_order -- Halo 3.1.6.0 R6 "Session is the first tab" (the owner, 2026-10-20:
"The session tab should be the first tab in studio"): `routes/index.tsx` SECTIONS is the one order of
Studio's sections and their `Alt+N` keys (then, 12:40: "Here's the order of tabs in studio: session, team,
roles, fleet, design"; Orchestra, not in his list, keeps the last key): Session `Alt+1` ... Orchestra `Alt+6`; every `Alt+N`
that README.md, docs/ (every .md under it) and the UI's own copy and comments (ui/src) name belongs to the
section the registry gives that key, every "`Alt+1`..`Alt+6`" list runs in the registry's order, the modes
banner (tools/studio_modes_banner.py) draws its tiles in that order with those keys, and
docs/STUDIO-sections.md tells the sections in it. 3.2.0.0 R6: Packs (the Pack Manager) is appended as the
seventh section, `Alt+7`; the six keep their keys. 3.2.0.0 R7: the banner gains the Packs tile (seven). 3.3.0.0 R1:
Setup is appended as the eighth, `Alt+8`; 3.3.3.0 R2: Settings as the ninth, `Alt+9`; 3.3.5.0 R1: Local as the tenth and last,
`Alt+0` (`shell/keys.ts` reads Digit0 as the tenth slot; a pack's own section has no key). The reader is
tests/helpers/section_order.py; a reorder of SECTIONS fails here on every line it leaves behind.
Run: python -m tests.test_studio_section_order
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers import section_order as so  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
UI = REPO / "halo_harness" / "studio" / "ui" / "src"


def _docs() -> "list[Path]":
    return [REPO / "README.md"] + sorted(p for p in (REPO / "docs").rglob("*.md") if "media" not in p.parts)


@test
def test_the_registry_runs_session_first_and_orchestra_last(ctx: Ctx):
    rows = so.registry()
    ctx.check(f"ten sections (3.2.0.0 R6: Packs appended; 3.3.0.0 R1: Setup; 3.3.3.0 R2: Settings; 3.3.5.0 R1: Local), got {[r[0] for r in rows]}", len(rows) == 10)
    ctx.check(f"the keys follow the order, Alt+1 to Alt+9 then Alt+0, got {[r[2] for r in rows]}", [r[2] for r in rows] == [f"Alt+{n % 10}" for n in range(1, 11)])
    ctx.check(f"the order is Session, Team, Roles, Fleet, Design, Orchestra, Packs, Setup, Settings, Local, got {[r[1] for r in rows]}",
              [r[0] for r in rows] == ["session", "team", "roles", "fleet", "design", "orchestra", "packs", "setup", "settings", "local"])
    ctx.check("Session is Alt+1, This session, live", rows[0][1:] == ("Session", "Alt+1", "This session, live"))
    ctx.check("Orchestra is Alt+6, Runs of your agents, live", rows[5][1:] == ("Orchestra", "Alt+6", "Runs of your agents, live"))
    ctx.check("Packs is Alt+7, the Pack Manager (3.2.0.0 R6)", rows[6][1:] == ("Packs", "Alt+7", "Install, grant and enable packs"))
    ctx.check("Setup is Alt+8 (3.3.0.0 R1)", rows[7][1:] == ("Setup", "Alt+8", "Providers, models, permissions, theme and lineup"))
    ctx.check("Settings is Alt+9 (3.3.3.0 R2)", rows[8][1:] == ("Settings", "Alt+9", "Every config key, one page per group"))
    ctx.check("Local is the last, Alt+0 (3.3.5.0 R1)", rows[-1][1:] == ("Local", "Alt+0", "The machines that serve models, and the models they serve"))
    reg = (UI / "routes" / "packs" / "registry.ts").read_text(encoding="utf-8")
    ctx.check("3.3.3.0 R2: no key is left for a pack's own section (FIRST_KEY 10, past Alt+9; 3.3.5.0 R1: Alt+0 is Local)", "const FIRST_KEY = 10;" in reg and "const LAST_KEY = 9;" in reg)
    keys = (UI / "shell" / "keys.ts").read_text(encoding="utf-8")
    ctx.check("Alt+1..9 and Alt+0 take the registry's n-th section (3.2.0.0 R3: sections() is the core ones, then the packs'; "
              "3.3.5.0 R1: Digit0 is the tenth slot)", "sections()[slot - 1]" in keys and "(Number(e.code.slice(5)) || 10)" in keys
              and "/^Digit[0-9]$/" in keys)


@test
def test_every_alt_key_in_the_docs_names_the_registry_section(ctx: Ctx):
    rows = so.registry()
    docs = _docs()
    found = sum(len(so.scan(p.read_text(encoding="utf-8"), rows)[0]) for p in docs)
    ctx.check(f"the docs name the keys (README, STUDIO*, FLEET, TEAM, DESIGN, ...), got {found} lines", found >= 30)
    bad = [line for p in docs for line in so.problems(p, rows)]
    ctx.check("every Alt+N in README.md and docs/ names the section the registry gives that key:\n  " + "\n  ".join(bad), not bad)


@test
def test_the_ui_copy_and_comments_name_the_registry_key(ctx: Ctx):
    rows = so.registry()
    files = sorted(list(UI.rglob("*.ts")) + list(UI.rglob("*.tsx")))
    bad = [line for p in files for line in so.problems(p, rows)]
    ctx.check("every Alt+N in ui/src (help copy, comments) names the registry's section:\n  " + "\n  ".join(bad), not bad)
    help_src = (UI / "routes" / "sectionHelp.ts").read_text(encoding="utf-8")
    ctx.check("the section help keeps no Alt+N line of its own (the overlay puts the registry's first)",
              re.search(r'\["Alt\+[1-9]"', help_src) is None)
    overlay = (UI / "shell" / "SectionHelp.tsx").read_text(encoding="utf-8")
    ctx.check("the overlay's KEYS list starts with the section's registry key", "[[def.kbd, def.title], ...copy.keys]" in overlay)
    status = (UI / "shell" / "StatusBar.tsx").read_text(encoding="utf-8")
    ctx.check("the status bar's key hint reads the registry's first and last key",
              "SECTIONS[0].kbd" in status and "SECTIONS[SECTIONS.length - 1].kbd" in status and 'keys="Alt+1"' not in status)
    palette = (UI / "shell" / "Palette.tsx").read_text(encoding="utf-8")
    ctx.check("the palette's section groups follow the registry (3.2.0.0 R3: sections(), the packs' after)",
              "...sections().map((s) => s.title)" in palette)


@test
def test_the_modes_banner_draws_the_registry_order(ctx: Ctx):
    rows = so.registry()  # 3.2.0.0 R7: the Packs tile too (tools/capture_packs.py); 3.3.0.0 R1: Setup; 3.3.3.0 R2: Settings; 3.3.5.0 R1: Local, ten in all
    frames = so.banner_frames()
    ctx.check(f"ten tiles, got {len(frames)}", len(frames) == 10)
    ctx.check(f"the tiles run in the registry's order, got {[f[1] for f in frames]}", [f[1] for f in frames] == [r[1] for r in rows])
    ctx.check(f"each tile's key chip is its registry key, got {[f[2] for f in frames]}",
              [f[2] for f in frames] == [r[2].replace("+", " ") for r in rows])
    ctx.check(f"each tile is its section's capture, got {[f[0] for f in frames]}", [f[0] for f in frames] == [f"studio-{r[0]}.png" for r in rows])
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    alt = re.search(r'<img alt="(Halo Studio\'s ten sections[^"]*)" src="docs/media/studio-modes.png"', readme)
    pairs = re.findall(r"(\w+) \((Alt\+\d)\)", alt.group(1)) if alt else []
    ctx.check(f"the README banner's alt text names each section with its key in that order, got {pairs}",
              pairs == [(r[1], r[2]) for r in rows])


@test
def test_studio_sections_doc_tells_the_sections_in_the_registry_order(ctx: Ctx):
    rows = so.registry()
    text = (REPO / "docs" / "STUDIO-sections.md").read_text(encoding="utf-8")
    titles = {r[1] for r in rows}
    heads = [h for h in re.findall(r"^### (\w+)$", text, re.M) if h in titles]
    ctx.check(f"its section headings run in the registry's order, got {heads}", heads == [r[1] for r in rows])
    order = ", ".join(r[1] for r in rows)
    for doc in ("STUDIO-sections.md", "STUDIO.md", "README.md"):
        body = (REPO / "docs" / doc).read_text(encoding="utf-8")
        ctx.check(f"docs/{doc} names the sections in the registry's order ({order})", f"a section ({order})" in body)


@test
def test_the_reader_catches_a_stale_key(ctx: Ctx):
    """The reader itself: a key on the wrong section, a list out of order and a key with no section all
    fail; the right ones pass."""
    rows = so.registry()
    tmp = REPO / "tests" / "_section_order_probe.md"

    def probe(text: str) -> "list[str]":
        tmp.write_text(text, encoding="utf-8", newline="\n")
        try:
            return so.problems(tmp, rows)
        finally:
            tmp.unlink()

    ctx.check("Fleet (`Alt+4`) passes", probe("Fleet (`Alt+4`) shows every harness.\n") == [])
    ctx.check("Fleet (`Alt+3`) is stale", len(probe("Fleet (`Alt+3`) shows every harness.\n")) == 1)
    ctx.check("`Alt+1` Session; passes", probe("**Keys.** `Alt+1` Session; `J` hops.\n") == [])
    ctx.check("a heading names the section", probe("### Session\n\nPress `Alt+1` and it opens.\n") == [])
    ctx.check("a heading on another section flags it", len(probe("### Design\n\nPress `Alt+1` and it opens.\n")) == 1)
    ctx.check("a key with no section is flagged", len(probe("Press `Alt+2` now.\n")) == 1)
    ctx.check("3.3.5.0 R1: Local (`Alt+0`) passes", probe("Local (`Alt+0`) shows the card live.\n") == [])
    ctx.check("3.3.5.0 R1: Settings (`Alt+0`) is stale", len(probe("Settings (`Alt+0`) lists every key.\n")) == 1)
    good = "`Alt+1`..`Alt+6`: Session, Team, Roles,\nFleet, Design, Orchestra.\n"
    stale = "`Alt+1` to `Alt+6` switch between **Orchestra**, **Roles**, **Design**, **Fleet**,\n**Team** and **Session**.\n"
    ctx.check("a range over the registry order passes", probe(good) == [])
    ctx.check("a range over the old order is flagged", len(probe(stale)) == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
