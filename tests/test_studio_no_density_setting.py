"""tests.test_studio_no_density_setting -- Halo 3.6.0.1: the header's three-lines button is gone (the owner, from live
use of 3.6.0.0: it "does almost nothing ... do something or remove it"). It was the density toggle of 3.3.2.0
(comfortable / compact), whose compact set only tightened the spacing and the type scale by a few pixels. It is removed
together with the setting behind it. A lint over the source, no browser:

1. the header renders no density button and imports no density store; the theme menu is still its last item;
2. lib/density.ts is gone and nothing imports it; the palette has no `density-` command;
3. tokens.css has no `:root[data-density="compact"]` block (one token set: the comfortable one);
4. Icon.tsx has no `density` / `density-compact` icon (nothing draws them now);
5. the region markers `data-density="bar|row|body"` (read by the density rules, tests/test_studio_density.py) stay.

The drawn header (no button, no gap where it was, a browser that saved `halo.studio.density = compact` opens with the
default spacing) is measured by tests/test_studio_quiet_panels.py on headless Chrome.
Run: python -m tests.test_studio_no_density_setting
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"


def _src(rel: str) -> str:
    return (UI / rel).read_text(encoding="utf-8")


@test
def test_the_header_has_no_density_button(ctx: Ctx):
    hdr = _src("shell/Header.tsx")
    ctx.check("Header.tsx renders no density-toggle", "density-toggle" not in hdr and "DensityToggle" not in hdr)
    ctx.check("Header.tsx imports no density store", "lib/density" not in hdr and "useDensity" not in hdr and "toggleDensity" not in hdr)
    ctx.check("the theme menu is still the header's last item", re.search(r"<ThemeMenu />\s*</header>", hdr) is not None)
    ctx.check("the header keeps its region marker", 'className="topbar" data-density="bar"' in hdr)


@test
def test_the_setting_behind_it_is_gone(ctx: Ctx):
    ctx.check("lib/density.ts is gone", not (UI / "lib" / "density.ts").exists())
    users = [p.relative_to(UI).as_posix() for p in list(UI.rglob("*.ts")) + list(UI.rglob("*.tsx"))
             if re.search(r"""from\s+["'][./]+(lib/)?density["']""", p.read_text(encoding="utf-8"))]
    ctx.check(f"nothing imports a density store, got {users}", not users)
    cmds = _src("shell/commands.ts")
    ctx.check("the palette has no density- command", re.search(r'id:\s*"density-', cmds) is None and "Density:" not in cmds)
    css = _src("styles/tokens.css")
    ctx.check("tokens.css has no compact density block", 'data-density="compact"' not in css)
    icon = _src("lib/ui/Icon.tsx")
    ctx.check("Icon.tsx has no density icons", re.search(r'^\s*("density-compact"|density)\s*:', icon, re.M) is None)
    users = [p.relative_to(UI).as_posix() for p in UI.rglob("*.tsx")
             if re.search(r'name=\{?[^}>]*"density(-compact)?"', p.read_text(encoding="utf-8"))]
    ctx.check(f"no component draws a density icon, got {users}", not users)


@test
def test_the_region_markers_stay(ctx: Ctx):
    marks = {rel: _src(rel) for rel in ("lib/workspace/Panel.tsx", "lib/ui/Tabs.tsx")}
    ctx.check("a panel's bar and body keep data-density bar / body",
              'data-density="bar"' in marks["lib/workspace/Panel.tsx"] and 'data-density="body"' in marks["lib/workspace/Panel.tsx"])
    ctx.check("Tabs keep data-density bar", 'data-density="bar"' in marks["lib/ui/Tabs.tsx"])
    css = _src("styles/tokens.css")
    root = re.search(r"^:root \{(.*?)^\}", css, re.S | re.M)
    body = root.group(1) if root else ""
    ctx.check("the one token set keeps the Instrument scale (--pad 12, 13 px text, a 40 px title line, a 48 px header)",
              "--pad: 12px;" in body and "--fs: 13px;" in body and "--bar-h: 40px;" in body and "--topbar-h: 48px;" in body)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
