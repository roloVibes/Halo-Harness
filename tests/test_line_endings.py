"""tests.test_line_endings -- Halo 3.1.0.0 round R2: line endings settled
once. `.gitattributes` opens with `* text=auto eol=lf` (the binaries marked
`-text`, `bin/*.cmd` kept CRLF), the index holds LF for every text file
(`git ls-files --eol` says `i/lf`), and no byte-for-byte comparison of a
text file in the package is left without folding CRLF to LF first (the way
`studio/model._is_shipped_copy` does: a copy written in text mode on
Windows comes back CRLF).

Run: python -m tests.test_line_endings
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BINARIES = ("*.png", "*.jpg", "*.gif", "*.ico", "*.woff", "*.woff2", "*.ttf", "*.pdf", "*.zip", "*.bundle", "*.pyc")
# `<bytes> == <bytes>` / `!=` on a read_bytes() call, on one line
_BYTES_COMPARE = re.compile(r"read_bytes\(\)[^#\n]*?(==|!=)|(==|!=)[^#\n]*?read_bytes\(\)")
_FOLD = 'replace(b"\\r\\n", b"\\n")'
# (path under halo_harness/) -> why its bytes comparison is not a text-mode copy that could disagree on endings
_BYTES_COMPARE_ALLOWED = {
    "flows/steps_agents.py":
        "_copy_asset compares an asset with a byte-for-byte copy (shutil.copy2) of itself; assets are mostly images, "
        "and neither side is ever written in text mode",
}


def _attr_lines() -> list:
    text = (REPO / ".gitattributes").read_text(encoding="utf-8")
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


@test
def test_gitattributes_has_the_rule_and_marks_the_binaries(ctx: Ctx):
    lines = _attr_lines()
    ctx.check(f"the first rule is `* text=auto eol=lf`, got {lines[:1]}", lines[:1] == ["* text=auto eol=lf"])
    for pattern in BINARIES:
        ctx.check(f"{pattern} is marked -text", any(ln.split()[0] == pattern and "-text" in ln.split()[1:] for ln in lines))
    ctx.check("bin/*.cmd keeps CRLF", "bin/*.cmd text eol=crlf" in lines)
    for kept in ("bin/halo text eol=lf", "scripts/*.sh text eol=lf", "docs/media/*.png binary",
                 "halo_harness/studio/static/dist/* text eol=lf", "halo_harness/studio/ui/** text eol=lf"):
        ctx.check(f"the existing rule {kept!r} stays", kept in lines)
    first = lines.index("* text=auto eol=lf")
    ctx.check("every specific rule comes after the catch-all (a later line wins in git)",
              all(lines.index(ln) > first for ln in lines if ln != "* text=auto eol=lf"))


def _git_eol() -> list:
    if shutil.which("git") is None or not (REPO / ".git").exists():
        raise SkipTest("not a git checkout (a tar copy or a source archive): the index is checked where git is")
    r = subprocess.run(["git", "ls-files", "--eol"], cwd=str(REPO), capture_output=True)
    if r.returncode != 0:
        raise SkipTest(f"git ls-files --eol failed: {r.stderr.decode('utf-8', 'replace').strip()}")
    rows = []
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        meta, _, path = line.partition("\t")
        fields = meta.split()
        if len(fields) >= 3:
            rows.append((fields[0], fields[2], path))
    return rows


@test
def test_the_index_holds_lf_for_every_text_file(ctx: Ctx):
    rows = _git_eol()
    ctx.check("git lists the tracked files", len(rows) > 100)
    text = [(i, attr, p) for i, attr, p in rows if i != "i/-text"]
    bad = [f"{p} ({i})" for i, attr, p in text if i not in ("i/lf", "i/none")]
    ctx.check(f"every text file is LF in the index, not: {bad[:20]}", not bad)
    images = [(i, p) for i, attr, p in rows if p.lower().endswith((".png", ".jpg", ".gif", ".ico"))]
    ctx.check(f"the images are binary in the index, got {[x for x in images if x[0] != 'i/-text'][:5]}",
              all(i == "i/-text" for i, _ in images))


@test
def test_no_bytes_comparison_of_a_text_file_is_left_without_the_fold(ctx: Ctx):
    pkg = REPO / "halo_harness"
    problems, seen_allowed = [], set()
    for path in sorted(pkg.rglob("*.py")):
        rel = path.relative_to(pkg).as_posix()
        for no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not _BYTES_COMPARE.search(line):
                continue
            if rel in _BYTES_COMPARE_ALLOWED:
                seen_allowed.add(rel)
                continue
            if line.count(_FOLD) < 2:
                problems.append(f"halo_harness/{rel}:{no}: {line.strip()[:120]}")
    ctx.check("every read_bytes() comparison folds CRLF to LF on both sides (or is a reasoned exception):\n  "
              + "\n  ".join(problems), not problems)
    stale = sorted(set(_BYTES_COMPARE_ALLOWED) - seen_allowed)
    ctx.check(f"every allow-listed comparison still exists (remove the entry otherwise): {stale}", not stale)


@test
def test_a_crlf_copy_of_a_shipped_lineup_is_still_the_shipped_copy(ctx: Ctx):
    from halo_harness import teams_yaml as T
    from halo_harness.studio.model import _is_shipped_copy
    shipped = T.bundled_team_templates_dir() / "standard.yaml"
    ctx.check("the shipped `standard` lineup exists", shipped.is_file())
    body = shipped.read_bytes().replace(b"\r\n", b"\n")
    d = Path(tempfile.mkdtemp(prefix="line-endings-"))
    crlf, lf, edited = d / "crlf.yaml", d / "lf.yaml", d / "edited.yaml"
    crlf.write_bytes(body.replace(b"\n", b"\r\n"))
    lf.write_bytes(body)
    edited.write_bytes(body + b"# my own line\n")
    ctx.check("a CRLF copy is the shipped copy", _is_shipped_copy("standard", {"_path": str(crlf)}))
    ctx.check("an LF copy is the shipped copy", _is_shipped_copy("standard", {"_path": str(lf)}))
    ctx.check("an edited copy is a lineup of your own", not _is_shipped_copy("standard", {"_path": str(edited)}))
    shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="line endings tests"))
