"""tests.test_quickstart_docs -- H12 brief Part D: README's new "Quick start
(Kali / Linux)" first section, INSTALL.md pointing to `init`, the CHANGELOG
entry, and the version bump. Pure text/metadata checks -- no subprocess, no
network.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


@test
def test_readme_first_section_is_quick_start(ctx: Ctx):
    """2.0.5 round 2d restructured the README (brief: banner, one
    paragraph, gallery, feature grid, install, themes) -- the old
    'Quick start first' pin is superseded: the gallery now leads, and the
    install one-liner + `halo init` + Windows live in ## Install."""
    text = (REPO_DIR / "README.md").read_text(encoding="utf-8")
    sections = _SECTION_RE.findall(text)
    ctx.check(f"README has at least one ## section, got {sections[:3]}", sections)
    ctx.check(f"the FIRST ## section is the gallery, got {sections[0]!r}",
              sections[0].strip().lower().startswith("what it looks like"))
    ctx.check("the banner block is above every ## section",
              text.index("_   _") < text.index("## What it looks like"))


@test
def test_readme_quick_start_mentions_init_and_windows(ctx: Ctx):
    text = (REPO_DIR / "README.md").read_text(encoding="utf-8")
    quick_start = text.split("## Install", 1)[1].split("\n## ", 1)[0]
    ctx.check("mentions `halo init`", "halo init" in quick_start)
    ctx.check("mentions an install command (uv tool install or pipx)",
              "uv tool install" in quick_start or "pipx install" in quick_start)
    ctx.check("covers Windows too, in the same leading section", "Windows" in quick_start)
    ctx.check("the Windows recipe names install-halo.ps1", "install-halo.ps1" in quick_start)


@test
def test_install_md_points_to_init_near_the_top(ctx: Ctx):
    text = (REPO_DIR / "docs" / "harness" / "INSTALL.md").read_text(encoding="utf-8")
    head = text.split("## Kali / Linux", 1)[0]
    ctx.check("INSTALL.md mentions `halo init` before the first real OS section",
              "halo init" in head)


@test
def test_rest_of_readme_unchanged_below_quick_start(ctx: Ctx):
    """Superseded shape (was: 'every pre-existing section still present,
    pushed down by Quick start') -- 2.0.5 round 2d rewrote the README
    around the gallery; this now pins the new section set and its order
    so the restructure itself is protected."""
    text = (REPO_DIR / "README.md").read_text(encoding="utf-8")
    headings = ("## What it looks like", "## Features", "## Install", "## Themes",
                "## Documentation", "## Tests", "## Licence")
    positions = []
    for heading in headings:
        ctx.check(f"{heading!r} is present", heading in text)
        positions.append(text.index(heading) if heading in text else -1)
    ctx.check(f"the sections appear in the brief's order, got {positions}",
              positions == sorted(positions) and -1 not in positions)


@test
def test_version_bumped_to_0_4_1_and_changelog_has_an_entry(ctx: Ctx):
    """H12's own pinning -- kept exact (checked against the CHANGELOG's own
    still-present [0.4.1] entry, not the CURRENT version) now that H13 has
    bumped past it; see `test_version_bumped_to_0_5_0_and_changelog_has_an_
    entry` below for H13's own version-bump pin."""
    changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    ctx.check("CHANGELOG.md still has a [0.4.1] entry", "[0.4.1]" in changelog)
    # 2.0.0 rename: CHANGELOG history keeps the name it was WRITTEN under
    # (brief: "history in CHANGELOG keeps old names for old releases") --
    # the [0.4.1] entry predates the rename, so it still says the old
    # command name verbatim; only entries at/after [2.0.0] say `halo`.
    ctx.check("the [0.4.1] entry mentions rolo-claude init",
              "rolo-claude init" in changelog.split("[0.4.1]", 1)[1].split("[0.4.0]", 1)[0])


@test
def test_version_bumped_to_0_5_0_and_changelog_has_an_entry(ctx: Ctx):
    """H13's own pinning -- kept exact (checked against the CHANGELOG's own
    still-present [0.5.0] entry, not the CURRENT version) now that H14 has
    bumped past it; see `test_version_bumped_to_0_6_0_and_changelog_has_an_
    entry` below for H14's own version-bump pin."""
    changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    ctx.check("CHANGELOG.md still has a [0.5.0] entry", "[0.5.0]" in changelog)
    entry = changelog.split("[0.5.0]", 1)[1].split("\n## [", 1)[0]
    for phrase in ("lazy", "inline", "/resume"):
        ctx.check(f"the [0.5.0] entry mentions {phrase!r}", phrase in entry.lower())


@test
def test_version_bumped_to_0_6_0_and_changelog_has_an_entry(ctx: Ctx):
    """H14's own pinning -- kept exact (checked against the CHANGELOG's own
    still-present [0.6.0] entry, not the CURRENT version) now that V2a has
    bumped past it; see `test_version_bumped_to_0_7_0_and_changelog_has_an_
    entry` below for V2a's own version-bump pin."""
    changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    ctx.check("CHANGELOG.md still has a [0.6.0] entry", "[0.6.0]" in changelog)
    entry = changelog.split("[0.6.0]", 1)[1].split("\n## [", 1)[0]
    for phrase in ("databricks", "work", "team.json"):
        ctx.check(f"the [0.6.0] entry mentions {phrase!r}", phrase in entry.lower())


@test
def test_version_bumped_to_0_7_0_and_changelog_has_an_entry(ctx: Ctx):
    """H14's own pinning shape, kept exact (checked against the CHANGELOG's
    own still-present [0.7.0] entry, not the CURRENT version) now that V2b/
    V2c has bumped past it; see `test_version_bumped_to_0_8_0_and_changelog_
    has_an_entry` below for THIS milestone's own version-bump pin."""
    changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    ctx.check("CHANGELOG.md still has a [0.7.0] entry", "[0.7.0]" in changelog)
    entry = changelog.split("[0.7.0]", 1)[1].split("\n## [", 1)[0]
    for phrase in ("v2a", "reasoning replay", "route split"):
        ctx.check(f"the [0.7.0] entry mentions {phrase!r}", phrase in entry.lower())


@test
def test_version_bumped_to_0_8_0_and_changelog_has_an_entry(ctx: Ctx):
    """V2 brief (docs/harness/V2-brief.md) V2b+V2c's own pinning shape, kept
    exact (checked against the CHANGELOG's own still-present [0.8.0] entry,
    not the CURRENT version) now that the 1.0.0 docs pass has bumped past
    it; see `test_version_bumped_to_1_0_0_and_changelog_has_an_entry` below
    for THIS release's own version-bump pin."""
    changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    ctx.check("CHANGELOG.md still has a [0.8.0] entry", "[0.8.0]" in changelog)
    entry = changelog.split("[0.8.0]", 1)[1].split("\n## [", 1)[0]
    for phrase in ("work-matrix", "roles", "researcher"):
        ctx.check(f"the [0.8.0] entry mentions {phrase!r}", phrase in entry.lower())


@test
def test_version_bumped_to_1_0_0_and_changelog_has_an_entry(ctx: Ctx):
    """rolo-claude 1.0.0 (the name this release actually shipped under --
    see the [2.0.0] CHANGELOG entry for the rename itself): the stable
    general harness release -- a docs pass
    summarising the 0.7.0/0.8.0 Databricks-correctness-and-tooling line,
    NOT a rename and NOT a new console-script alias (a separate
    `databricks-claude` repository was spun off instead; see the
    CHANGELOG's own [1.0.0] entry for why the version jumped straight past
    `2.0.0`). H14's own pinning shape, kept exact (checked against the
    CHANGELOG's own still-present [1.0.0] entry, not the CURRENT version)
    now that the 1.0.1 hotfix has bumped past it; see
    `test_version_bumped_to_1_0_1_and_changelog_has_an_entry` below for
    THIS release's own version-bump pin."""
    changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    ctx.check("CHANGELOG.md has a [1.0.0] entry", "[1.0.0]" in changelog)
    entry = changelog.split("[1.0.0]", 1)[1].split("\n## [", 1)[0]
    for phrase in ("stable", "databricks-claude", "roles"):
        ctx.check(f"the [1.0.0] entry mentions {phrase!r}", phrase in entry.lower())


@test
def test_version_bumped_to_1_0_1_and_changelog_has_an_entry(ctx: Ctx):
    """rolo-claude 1.0.1 (the name this release actually shipped under):
    the hotfix release from the owner's first real 1.0.0 run on the Kali
    work VM (DNS down, then a live `/model` screenshot from it once
    fixed) -- thirteen fixes, no behavior changes beyond them; see the
    CHANGELOG's own [1.0.1] entry for the full list. H14c's own pinning
    shape, kept exact (checked against the CHANGELOG's own still-present
    [1.0.1] entry, not the CURRENT version) now that the 2.0.0 rename has
    bumped past it; see `test_version_bumped_to_2_0_0_and_changelog_has_
    an_entry` below for THIS release's own version-bump pin."""
    changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    ctx.check("CHANGELOG.md has a [1.0.1] entry", "[1.0.1]" in changelog)
    entry = changelog.split("[1.0.1]", 1)[1].split("\n## [", 1)[0]
    for phrase in ("fail fast", "provider", "x509_strict"):
        ctx.check(f"the [1.0.1] entry mentions {phrase!r}", phrase in entry.lower())


@test
def test_version_bumped_to_2_0_0_and_changelog_has_an_entry(ctx: Ctx):
    """Halo Harness 2.0.0: the rename release -- rolo-claude 1.0.1
    continues unchanged as its own repository; this one is where every
    later feature lands. H14c's own pinning shape, kept exact (checked
    against the CHANGELOG's own still-present [2.0.0] entry, not the
    CURRENT version) now that the 2.0.1 "run from any directory" release
    has bumped past it; see `test_version_bumped_to_2_0_1_and_changelog_
    has_an_entry` below for THIS release's own version-bump pin (the
    single `__version__ == ...` exact-match check lives in the
    newest-added test only, per this file's own established convention)."""
    changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    ctx.check("CHANGELOG.md has a [2.0.0] entry", "[2.0.0]" in changelog)
    entry = changelog.split("[2.0.0]", 1)[1].split("\n## [", 1)[0]
    for phrase in ("halo", "migration", "rename", "intro"):
        ctx.check(f"the [2.0.0] entry mentions {phrase!r}", phrase in entry.lower())


@test
def test_version_bumped_to_2_0_1_and_changelog_has_an_entry(ctx: Ctx):
    """Halo Harness 2.0.1: the "run from any directory" release -- makes
    the install unmistakable and proves (by test) that no behavior
    depends on `halo` being started from inside the checkout. H14c's own
    pinning shape, kept exact (checked against the CHANGELOG's own
    still-present [2.0.1] entry, not the CURRENT version) now that 2.0.2
    has bumped past it; see `test_version_bumped_to_2_0_2_and_changelog_
    has_an_entry` below for THIS release's own version-bump pin."""
    changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    ctx.check("CHANGELOG.md has a [2.0.1] entry", "[2.0.1]" in changelog)
    # Anchor on the section HEADER: a later section may mention "[2.0.1]" in
    # passing (the 2.0.5 deprecation note does), and the bare text split
    # then sliced the wrong section (CI after round 3).
    entry = changelog.split("\n## [2.0.1]", 1)[1].split("\n## [", 1)[0]
    for phrase in ("install.md", "pythonpath fallback", "scratch", "unique sentence"):
        ctx.check(f"the [2.0.1] entry mentions {phrase!r}", phrase in entry.lower())


@test
def test_version_bumped_to_2_0_2_and_changelog_has_an_entry(ctx: Ctx):
    """Halo Harness 2.0.2 (W7 round 1): terminal tab title re-assertion
    and roles v2 (per-role effort, custom role names, tab/shell
    completion, role templates). H14c's own pinning shape, kept exact
    (checked against the CHANGELOG's own still-present [2.0.2] entry, not
    the CURRENT version) now that 2.0.3 has bumped past it; see
    `test_version_bumped_to_2_0_3_and_changelog_has_an_entry` below for
    THIS release's own version-bump pin."""
    changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    ctx.check("CHANGELOG.md has a [2.0.2] entry", "[2.0.2]" in changelog)
    entry = changelog.split("\n## [2.0.2]", 1)[1].split("\n## [", 1)[0]
    for phrase in ("terminal", "role"):
        ctx.check(f"the [2.0.2] entry mentions {phrase!r}", phrase in entry.lower())


@test
def test_version_bumped_to_2_0_3_and_changelog_has_an_entry(ctx: Ctx):
    """Halo Harness 2.0.3 round 2 (`plans/2.0.3-ollama-round2-brief.md`):
    the `ol:` provider on Ollama's native `/api/chat` API. H14c's own
    pinning shape, kept exact (checked against the CHANGELOG's own
    still-present [2.0.3] entry, not the CURRENT version) now that
    2.0.3.1 has bumped past it; see `test_version_bumped_to_2_0_3_1_and_
    changelog_has_an_entry` below for THIS release's own version-bump pin."""
    changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    ctx.check("CHANGELOG.md has a [2.0.3] entry", "[2.0.3]" in changelog)
    entry = changelog.split("[2.0.3]", 1)[1].split("\n## [", 1)[0]
    for phrase in ("ollama", "num_ctx"):
        ctx.check(f"the [2.0.3] entry mentions {phrase!r}", phrase in entry.lower())


@test
def test_version_matches_the_newest_dated_changelog_section(ctx: Ctx):
    """The version pin, release-proof. The 2.0.3.1 form of this test pinned
    the literal "2.0.3.1", so it could only break AFTER `scripts/release.py`
    bumped the version -- which happens after every suite has run -- and
    it did, on the first CI run after the v2.0.4 tag. The rule now: the
    package version equals the newest DATED `## [x.y.z] - YYYY-MM-DD`
    section of the CHANGELOG (an `unreleased` section above it is the next
    version in progress and is skipped). True during development, true the
    moment the release script dates a section, no literal to forget."""
    import re
    from halo_harness import __version__
    changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    dated = re.findall(r"^## \[(\d+(?:\.\d+)+)\] - \d{4}-\d{2}-\d{2}\s*$", changelog, flags=re.M)
    ctx.check("CHANGELOG.md has at least one dated section", bool(dated))
    newest = dated[0] if dated else None
    ctx.check(f"__version__ equals the newest dated CHANGELOG section {newest!r}, got {__version__!r}",
              __version__ == newest)
    ctx.check("CHANGELOG.md has a [2.0.3.1] entry", "[2.0.3.1]" in changelog)
    entry = changelog.split("[2.0.3.1]", 1)[1].split("\n## [", 1)[0]
    for phrase in ("clipboard", "image"):
        ctx.check(f"the [2.0.3.1] entry mentions {phrase!r}", phrase in entry.lower())


@test
def test_readme_badge_matches_version(ctx: Ctx):
    """2.0.5 round 2b (brief item 6, packaging): the README's own version
    badge -- both the alt text and the shields.io badge URL -- tracks
    `__version__` exactly, the SAME derived-never-literal rule `test_
    version_matches_the_newest_dated_changelog_section` above already
    applies one level up (CHANGELOG -> __version__ -> here, never a
    literal in either test). Owner's own report, from a review of v2.0.4:
    "the README badge embedded in METADATA still says version 2.0.1" --
    three releases stale; `scripts/release.py` now rewrites this file's
    own badge on every release (`tests/test_release_script.py` pins that
    rewrite itself)."""
    from halo_harness import __version__
    readme = (REPO_DIR / "README.md").read_text(encoding="utf-8")
    ctx.check(f'README.md badge alt text says "version {__version__}", got '
              f'the stale-badge check in the surrounding text',
              f'alt="version {__version__}"' in readme)
    ctx.check(f"README.md badge URL encodes {__version__!r}",
              f"badge/version-{__version__}-" in readme)


@test
def test_changelog_2_0_0_mentions_the_fixpass_additions(ctx: Ctx):
    """2.0.0 fixpass finding 3: the state-dir migration (and the deliberate
    choice to leave no link behind -- item B), the env-file copy-forward,
    the team.json fallback, the kept-recognizing-old markers, and the
    stream-json version alias must all be mentioned somewhere in the
    [2.0.0] entry -- not just fixed in code with no record of why."""
    changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = changelog.split("## [2.0.0]", 1)[1].split("\n## [", 1)[0].lower()
    for phrase in ("no link is created", "content forward", "team.json", "provenance marker",
                   "rolo_claude_version"):
        ctx.check(f"the [2.0.0] entry mentions {phrase!r}", phrase in entry)


@test
def test_upgrading_section_exists_in_readme_and_install_md(ctx: Ctx):
    """2.0.0 fixpass finding 3 (superseded by 2.0.1, see CHANGELOG): 2.0.0
    briefly had an upgrader's install command break outright against an
    already-installed rolo-claude 1.0.1 console script (uv aborted, pipx
    silently refused, pip silently overwrote) -- as of 2.0.1, `halo`'s own
    distribution ships exactly one console script and never conflicts with
    it at all, so there is no `--force` escape hatch left to document; both
    README.md and INSTALL.md must still say plainly that uninstalling the
    old tool first is recommended (not required), with the exact uninstall
    command for each of the three installers."""
    readme = (REPO_DIR / "README.md").read_text(encoding="utf-8")
    install = (REPO_DIR / "docs" / "harness" / "INSTALL.md").read_text(encoding="utf-8")
    # The front page no longer talks about the previous name at all (2026-10-02
    # README redo; 2.0.5 round 2d took it off every front page, and the
    # upgrade section itself now says "pre-2.0" instead of the name); the
    # upgrade path lives in docs/INSTALL.md, which the README links to.
    ctx.check("README.md links to docs/INSTALL.md for the upgrade path", "docs/INSTALL.md" in readme)
    ctx.check("docs/INSTALL.md names the upgrade path", "upgrading from" in install.lower()
              and "pre-2.0 install" in install.lower())
    ctx.check("INSTALL.md has a real '## Upgrading from a pre-2.0 install (1.0.1)' section",
              "## Upgrading from a pre-2.0 install (1.0.1)" in install)
    install_section = install.split("## Upgrading from a pre-2.0 install (1.0.1)", 1)[1].split("\n## ", 1)[0]
    for cmd in ("uv tool uninstall <old-name>", "pipx uninstall <old-name>", "pip uninstall <old-name>"):
        ctx.check(f"INSTALL.md's upgrade section names the exact command form {cmd!r}", cmd in install_section)
    ctx.check("INSTALL.md's upgrade section says plainly that uninstalling is recommended, not required",
              "recommended" in install_section.lower())
    ctx.check("INSTALL.md's upgrade section says plainly that no link is left at the old location",
              "no link is created" in install_section.lower())
    ctx.check("...and that the separate 1.0.1 install must not be used again",
              "1.0.1" in install_section and "must not" in install_section.lower())
    ctx.check("INSTALL.md points an upgrader at the section before the install commands run",
              install.index("## Upgrading from a pre-2.0 install (1.0.1)") < install.index("## Kali / Linux"))


@test
def test_install_md_top_level_exists_is_linked_from_readme_and_leads_with_one_liners(ctx: Ctx):
    """2.0.1 "run from any directory" release: a NEW top-level docs/
    INSTALL.md (distinct from the existing docs/harness/INSTALL.md, which
    keeps its own exhaustive walkthrough and its own "Upgrading from
    rolo-claude 1.0.1" section pinned above) leads with one install line
    per platform and is linked from the README, not just sitting there
    unreferenced."""
    readme = (REPO_DIR / "README.md").read_text(encoding="utf-8")
    install_path = REPO_DIR / "docs" / "INSTALL.md"
    ctx.check("docs/INSTALL.md exists", install_path.is_file())
    install = install_path.read_text(encoding="utf-8")
    ctx.check("README links to docs/INSTALL.md", "[docs/INSTALL.md](docs/INSTALL.md)" in readme)
    ctx.check("docs/INSTALL.md names the --reinstall form (the one command for first install AND "
              "every post-`git pull` reinstall)", "uv tool install --reinstall ." in install)
    ctx.check("docs/INSTALL.md names the pipx alternative", "pipx install --force -e ." in install)
    ctx.check("docs/INSTALL.md mentions the PEP 668 externally-managed-environment note",
              "externally-managed-environment" in install)
    ctx.check("docs/INSTALL.md names the direct-from-GitHub install",
              "uv tool install git+https://github.com/roloVibes/Halo-Harness" in install)
    ctx.check("docs/INSTALL.md says to cd anywhere and type halo",
              "cd anywhere" in install.lower() and "type `halo`" in install.lower())
    ctx.check("docs/INSTALL.md says the clone is for git pull only",
              "git pull` only" in install.lower() or "git pull only" in install.lower())
    ctx.check("docs/INSTALL.md keeps its own pre-2.0 upgrade section (2.0.5 round 2d naming)",
              "## Upgrading from a pre-2.0 install (1.0.1)" in install)
    ctx.check("docs/INSTALL.md links onward to the exhaustive docs/harness/INSTALL.md",
              "harness/INSTALL.md" in install)


@test
def test_round6_update_docs_are_in_place(ctx: Ctx):
    """Halo 2.0.2 round 6: clear install/update steps -- README's Install
    (three one-liners) and new Update section, docs/INSTALL.md's Windows
    PowerShell/Uninstall/Update sections, HANDBOOK/COMMANDS naming `halo
    update`/`/update`, and the CHANGELOG [2.0.2] entry."""
    readme = (REPO_DIR / "README.md").read_text(encoding="utf-8")
    # 2.0.5 round 2d: the README's update guidance lives INSIDE ## Install
    # ("Updates: `halo update`, or `/update` inside the TUI") instead of
    # its own ## Update section.
    ctx.check("README names halo update and /update",
              "halo update" in readme and "/update" in readme)
    ctx.check("README's Install section names all three one-liners",
              "install-halo.sh" in readme and "uv tool install git+" in readme and "pipx install git+" in readme)

    install = (REPO_DIR / "docs" / "INSTALL.md").read_text(encoding="utf-8")
    ctx.check("docs/INSTALL.md has a Windows PowerShell one-liner naming install-halo.ps1",
              "install-halo.ps1" in install and "### Windows" in install)
    ctx.check("docs/INSTALL.md has its own ## Update section", "## Update" in install)
    ctx.check("docs/INSTALL.md has an ## Uninstall section", "## Uninstall" in install)
    ctx.check("docs/INSTALL.md's Update section names halo --force and the Windows order",
              "--force" in install.split("## Update", 1)[1].split("## ", 1)[0])

    handbook = (REPO_DIR / "docs" / "HANDBOOK.md").read_text(encoding="utf-8")
    ctx.check("HANDBOOK.md documents halo update and /update",
              "halo update" in handbook and "/update" in handbook)

    commands = (REPO_DIR / "docs" / "COMMANDS.md").read_text(encoding="utf-8")
    ctx.check("COMMANDS.md has a ## `halo update` heading", "## `halo update`" in commands)

    slash = (REPO_DIR / "docs" / "SLASH-COMMANDS.md").read_text(encoding="utf-8")
    ctx.check("SLASH-COMMANDS.md has a ### `/update` heading", "### `/update`" in slash)

    changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = changelog.split("## [2.0.2]", 1)[1].split("\n## [", 1)[0]
    ctx.check("the [2.0.2] entry mentions halo update and /update", "halo update" in entry and "/update" in entry)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
