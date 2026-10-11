"""tests.test_design_contrast -- design.contrast (Halo 3.0.1.0 round D5):
WCAG ratios for known pairs, hex and rgb parsing, the name heuristics, the
:root parse with the system.json fallback, and the pairs report.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_ratio_of_known_pairs(ctx: Ctx):
    from halo_harness.design.contrast import ratio
    ctx.check("black on white is 21", ratio("#000", "#fff") == 21.0 and ratio("#ffffff", "#000000") == 21.0)
    ctx.check("a colour on itself is 1", ratio("#336699", "#336699") == 1.0)
    r = ratio("#777", "#fff")
    ctx.check(f"#777 on white is 4.48 and fails AA normal text, got {r}", r == 4.48 and r < 4.5)
    ctx.check("#767676 on white just passes AA", ratio("#767676", "#fff") >= 4.5)
    ctx.check("a translucent text colour is composited over its background", ratio("rgba(0,0,0,0.5)", "#fff") < ratio("#000", "#fff"))
    try:
        ratio("nope", "#fff")
        bad = False
    except ValueError:
        bad = True
    ctx.check("a non-colour is a ValueError", bad)


@test
def test_colour_parsing(ctx: Ctx):
    from halo_harness.design.contrast import parse_color
    ctx.check("hex 3, 6 and 8 digits", parse_color("#f00")[:3] == (255, 0, 0) and parse_color("#00ff00")[:3] == (0, 255, 0)
              and round(parse_color("#0000ff80")[3], 2) == 0.5 and parse_color("#abcd")[3] == 1.0 * 0xdd / 255)
    ctx.check("rgb() with commas and with spaces", parse_color("rgb(10, 20, 30)") == (10.0, 20.0, 30.0, 1.0) and parse_color("rgb(10 20 30 / 50%)") == (10.0, 20.0, 30.0, 0.5))
    ctx.check("rgba() keeps the alpha", parse_color("rgba(255,255,255,.25)")[3] == 0.25)
    ctx.check("a length, a keyword and a bad hex are not colours", parse_color("16px") is None and parse_color("red") is None and parse_color("#12") is None and parse_color("#ggg") is None)


@test
def test_name_heuristics(ctx: Ctx):
    from halo_harness.design.contrast import role
    ctx.check("text-like names are fg", all(role(n) == "fg" for n in ("--text", "--fg", "--foreground", "--accent", "--primary", "--text-muted", "--on-surface")))
    ctx.check("background-like names are bg", all(role(n) == "bg" for n in ("--bg", "--background", "--surface", "--card", "--bg-primary", "--surface-2")))
    ctx.check("other names have no role", role("--radius") == "" and role("--space") == "" and role("--shadow") == "")


@test
def test_root_parse_system_fallback_and_pairs(ctx: Ctx):
    from halo_harness.design.contrast import check_artboard, pairs_for, root_colors, system_colors
    from halo_harness.design.store import Project
    html = "<style>:root{--text:#777;--bg:#fff;--space:16px;--accent:rgb(0,90,200);--ghost:#fff}.a{--bg:#000}</style>"
    cols = root_colors(html)
    ctx.check("only colour custom properties on :root are read", cols == {"--text": "#777", "--bg": "#fff", "--accent": "rgb(0,90,200)", "--ghost": "#fff"})
    rows = pairs_for(cols)
    ctx.check("every fg is paired with every bg (text, accent x bg)", {(p["fg"], p["bg"]) for p in rows} == {("--text", "--bg"), ("--accent", "--bg")})
    ctx.check("failing pairs come first and carry the verdicts", rows[0]["fg"] == "--text" and rows[0]["aa"] is False and rows[0]["aa_large"] is True and rows[1]["aa"] is True)
    ctx.check("the system's colour group is read, with or without the -- prefix", system_colors({"tokens": {"colors": {"accent": "#fff", "--bg": "#000"}, "spacing": {"--s": "#fff"}}}) == {"--accent": "#fff", "--bg": "#000"})
    from halo_harness.providers.config import default_state_dir
    p = Project.create("Contrast Lab", state_dir=Path(default_state_dir()))
    a = p.add_artboard("Hero")
    (p.artboard_dir(a["id"]) / "index.html").write_text("<style>:root{--text:#222}</style>", encoding="utf-8")
    p.save_system({"tokens": {"colors": {"--bg": "#fff"}}})
    out = check_artboard(p, a["id"])
    ctx.check("a page with only a text token borrows the background from system.json", len(out["pairs"]) == 1 and out["pairs"][0]["bg"] == "--bg" and out["pairs"][0]["aaa"] is True and "design system" in out["note"])
    (p.artboard_dir(a["id"]) / "index.html").write_text("<p>no tokens</p>", encoding="utf-8")
    p.save_system({})
    out = check_artboard(p, a["id"])
    ctx.check("nothing to check gives an empty list and a plain note", out["pairs"] == [] and "--text" in out["note"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="design contrast tests"))
