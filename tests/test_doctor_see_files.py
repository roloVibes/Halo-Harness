"""tests.test_doctor_see_files -- 3.6.0.6 W batch 2 entry 4: every file a `halo doctor` fix line names (`see="<file>
(<section>)"` in halo_harness/doctor*.py) exists in the repo, and where it names a section, the file has a heading of
that name (its `#` marks and backticks aside, any case). The chrome row's pointed at "README.md (Browser)", a section
README.md never had; it now points at docs/COMMANDS-main-io.md's `--chrome` heading. Three more named headings that
were not there (the python row's "Prerequisites: Python 3.10+", the old-install row's "Upgrading from rolo-claude
1.0.1", the permissions row's "permissions"): they name the headings that are. Plain: reads files only.
Run: python -m tests.test_doctor_see_files
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SEE = re.compile(r'see=f?"([^"]+)"')
FILE = re.compile(r"^((?:docs/|README|SECURITY|CHANGELOG)[\w./-]*\.md)(?:\s+\((.*)\))?")


def _refs() -> list:
    """(source file, line, the file named, the section named or '') for every repo file a doctor see= names."""
    out = []
    for src in sorted((ROOT / "halo_harness").glob("doctor*.py")):
        for n, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
            for ref in SEE.findall(line):
                m = FILE.match(ref)
                if m:
                    out.append((src.name, n, m.group(1), (m.group(2) or "").strip()))
    return out


def _headings(path: Path) -> set:
    return {re.sub(r"[`*]", "", ln.lstrip("#")).strip().lower()
            for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith("#")}


@test
def test_every_file_a_doctor_fix_line_names_exists_with_its_section(ctx: Ctx):
    refs = _refs()
    ctx.check(f"the doctor names repo files, got {len(refs)}", len(refs) >= 5)
    for src, n, name, section in refs:
        path = ROOT / name
        ctx.check(f"{src}:{n}: {name} exists", path.is_file())
        if path.is_file() and section:
            ctx.check(f"{src}:{n}: {name} has the heading {section!r}", section.lower() in _headings(path))


@test
def test_the_chrome_rows_fix_line_points_at_the_chrome_flags_heading(ctx: Ctx):
    refs = [r for r in _refs() if r[2] == "docs/COMMANDS-main-io.md"]
    ctx.check(f"the chrome row names docs/COMMANDS-main-io.md (--chrome, --no-chrome), got {refs}",
              any(r[3] == "--chrome, --no-chrome" for r in refs))
    text = (ROOT / "docs" / "COMMANDS-main-io.md").read_text(encoding="utf-8")
    ctx.check("that section says --chrome is the other product's and the built-in tool needs neither",
              "`--chrome` uses Claude Code's own browser extension and works only\nwhile that product does; the "
              "built-in Browser tool needs neither." in text)
    ctx.check("no fix line names README.md (Browser)", not any(r[2] == "README.md" and r[3] == "Browser" for r in _refs()))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
