"""tests.test_review3_p2 -- pins for the 3.0.2.0 review fix pass, round
P-design-paperclip (review items 44, 114-118): `paperclip pull` writes where
the lineup was loaded from; `design export --as folder` into an existing
directory; the exported index page escapes what the model wrote;
`capture_url` resolves stylesheet links properly; `scan_codebase` does not
skip a root whose own path contains a skip-dir name; WCAG verdicts use the
unrounded ratio.
"""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.fake_paperclip import FakePaperclip  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


# ---- 44 -----------------------------------------------------------------------

def _lineup_members(fake, lineup):
    fake.add_agent("boss", metadata={"halo_lineup": lineup, "halo_slot": "boss", "halo_agent": "implementer"})
    boss = next(iter(fake.agents.values()))
    fake.add_agent("worker", reportsTo=boss["id"], metadata={"halo_lineup": lineup, "halo_slot": "worker", "halo_agent": "implementer"})


@test
def test_i44_pull_writes_back_to_a_project_lineup(ctx: Ctx):
    from halo_harness.paperclip.client import Paperclip
    from halo_harness.paperclip.sync import pull_reporting_lines
    from halo_harness.teams_yaml import load_team_template_raw, save_team_template
    repo, state = Path(tempfile.mkdtemp(prefix="p44-repo-")), Path(tempfile.mkdtemp(prefix="p44-state-"))
    base = {k: v for k, v in load_team_template_raw("halo-dev-cycle").items() if not k.startswith("_")}
    ok, problems = save_team_template("team-x", base, cwd=repo, state_dir=state, project=True)
    ctx.check(f"the project lineup was written {problems}", ok)
    fake = FakePaperclip()
    try:
        _lineup_members(fake, "team-x")
        out = io.StringIO()
        pull_reporting_lines(Paperclip(fake.base_url), fake.company["id"], "team-x", cwd_halo=repo, state_dir=state, out=out)
        raw = load_team_template_raw("team-x", cwd=repo, state_dir=state)
        ctx.check("the project file now carries the positions", raw["_source"] == "project" and len((raw.get("org") or {}).get("positions") or []) == 2)
        ctx.check("no user-scope shadow copy was made", not (state / "teams" / "team-x.yaml").exists())
        ctx.check("the path written is printed", str(repo / ".halo" / "teams" / "team-x.yaml") in out.getvalue())
    finally:
        fake.close()


@test
def test_i44_pull_on_a_bundled_template_says_it_made_a_user_copy(ctx: Ctx):
    from halo_harness.paperclip.client import Paperclip
    from halo_harness.paperclip.sync import pull_reporting_lines
    repo, state = Path(tempfile.mkdtemp(prefix="p44-repo-")), Path(tempfile.mkdtemp(prefix="p44-state-"))
    fake = FakePaperclip()
    try:
        _lineup_members(fake, "halo-dev-cycle")
        out = io.StringIO()
        pull_reporting_lines(Paperclip(fake.base_url), fake.company["id"], "halo-dev-cycle", cwd_halo=repo, state_dir=state, out=out)
        dest = state / "teams" / "halo-dev-cycle.yaml"
        ctx.check("a user-scope copy was created", dest.is_file() and not (repo / ".halo").exists())
        ctx.check(f"and the output says so, got {out.getvalue()!r}", "bundled template" in out.getvalue() and str(dest) in out.getvalue())
    finally:
        fake.close()


# ---- 114, 115 ---------------------------------------------------------------------

def _board(p, title, aid, html="<p>hi</p>"):
    d = p.artboard_dir(aid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(html, encoding="utf-8")
    meta = p.meta()
    meta.setdefault("artboards", []).append({"id": aid, "title": title, "kind": "prototype", "app": "", "created": "x"})
    p.save_meta(meta)


@test
def test_i114_folder_export_twice_into_the_same_out(ctx: Ctx):
    from halo_harness.design.export import export_project
    from halo_harness.design.store import Project
    p = Project.create("Twice")
    _board(p, "Hero", "hero")
    out = Path(tempfile.mkdtemp(prefix="r3p-out-"))
    first = export_project(p, "folder", out)
    (p.artboard_dir("hero") / "index.html").write_text("<p>second</p>", encoding="utf-8")
    second = export_project(p, "folder", out)
    ctx.check(f"the second export did not raise: {second}", second and "folder:" in second[-1])
    ctx.check("it says what it overwrote", any("overwrote" in line and "hero" in line for line in second))
    ctx.check("the files are the new ones", (out / "hero" / "index.html").read_text(encoding="utf-8") == "<p>second</p>")
    ctx.check("the first run reported no overwrite", not any("overwrote" in line for line in first))


@test
def test_i115_index_page_escapes_titles_ids_and_the_project_name(ctx: Ctx):
    from halo_harness.design.export import export_project
    from halo_harness.design.store import Project
    p = Project.create("Evil</title><script>alert(1)</script>")
    _board(p, "<img src=x onerror=alert(1)>", "poster")
    _board(p, "Quote", "a'b&c")
    out = Path(tempfile.mkdtemp(prefix="r3p-out-"))
    export_project(p, "folder", out)
    page = (out / "index.html").read_text(encoding="utf-8")
    ctx.check("no raw tag from the title", "<img src=x" not in page and "&lt;img src=x onerror" in page)
    ctx.check("no raw script from the project name", "<script>alert(1)" not in page and "&lt;/title&gt;" in page)
    ctx.check("quote and ampersand in an id are encoded in the href", "a%27b%26c" in page and "a'b&c/" not in page)


# ---- 116, 117 ---------------------------------------------------------------------

@test
def test_i116_capture_url_resolves_stylesheet_links_against_the_page(ctx: Ctx):
    from halo_harness.design.sync import capture_url
    page = ('<link rel="stylesheet" href="/static/site.css"><link rel="stylesheet" href="../theme.css">'
            '<link rel="stylesheet" href="//cdn.example/x.css?a=1&amp;b=2"><link rel="stylesheet" href="local.css">')
    asked = []

    def fetch(u):
        asked.append(u)
        return page if u.endswith("page.html") else ":root{--brand:#336699}"
    capture_url("https://site.example/docs/page.html", fetch=fetch)
    ctx.check(f"each form resolved, got {asked[1:]}", asked[1:] == [
        "https://site.example/static/site.css", "https://site.example/theme.css",
        "https://cdn.example/x.css?a=1&b=2", "https://site.example/docs/local.css"])
    asked.clear()
    capture_url("https://site.example/a/b.html", fetch=lambda u: asked.append(u) or
                ('<base href="https://static.example/assets/"><link rel="stylesheet" href="app.css">' if len(asked) == 1 else ""))
    ctx.check(f"a <base href> is honoured, got {asked}", asked[1:] == ["https://static.example/assets/app.css"])


@test
def test_i117_scan_codebase_under_a_root_named_build(ctx: Ctx):
    from halo_harness.design.sync import components_in, scan_codebase
    root = Path(tempfile.mkdtemp(prefix="r3p-")) / "build" / "dist" / "myapp"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.css").write_text(":root{--brand:#336699;--space:8px}", encoding="utf-8")
    (root / "node_modules" / "lib").mkdir(parents=True)
    (root / "node_modules" / "lib" / "x.css").write_text(":root{--junk:#000}", encoding="utf-8")
    (root / "components" / "node_modules").mkdir(parents=True)
    (root / "components" / "Button.tsx").write_text("export {}", encoding="utf-8")
    (root / "components" / "node_modules" / "Junk.tsx").write_text("export {}", encoding="utf-8")
    found = scan_codebase(root)
    flat = {k: v for group in found["tokens"].values() for k, v in group.items()}
    ctx.check(f"tokens found under a build/dist path, got {flat}", "--brand" in flat and "--space" in flat)
    ctx.check("a skip-dir below the root is still skipped", "--junk" not in flat)
    ctx.check("components skip it too", [c["name"] for c in components_in(root)] == ["Button"])


# ---- 118 --------------------------------------------------------------------------

@test
def test_i118_verdicts_use_the_unrounded_ratio(ctx: Ctx):
    from halo_harness.design.contrast import pairs_for, raw_ratio, ratio
    raw = raw_ratio("#4e6af2", "#ffffff")
    ctx.check(f"the true ratio is below 4.5 but rounds to it, got {raw}", raw < 4.5 and ratio("#4e6af2", "#ffffff") == 4.5)
    row = pairs_for({"--text": "#4e6af2", "--bg": "#ffffff"})[0]
    ctx.check("the pair fails AA", row["aa"] is False)
    ctx.check(f"and is not displayed as passing, got {row['ratio']}", row["ratio"] < 4.5)
    ok = pairs_for({"--text": "#767676", "--bg": "#ffffff"})[0]
    ctx.check("a pair above 4.5 still passes", ok["aa"] is True and ok["ratio"] >= 4.5)
    ctx.check("black on white shows 21.0", pairs_for({"--text": "#000", "--bg": "#fff"})[0]["ratio"] == 21.0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="review3 p2 tests"))
