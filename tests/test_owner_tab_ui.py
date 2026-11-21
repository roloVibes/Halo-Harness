"""tests.test_owner_tab_ui -- why a Studio tab can only look, in the three cases there are (Halo 3.6.0.6 PF, the owner's
point 31: "Owners page issues keeps happening when I try to run packs."). ONE answer says whether this tab can change
things NOW (`viewOnly` in lib/owner.ts: a proof for the key in use, not merely a salt served), and its sentence comes
from `ownerLine` in lib/ownerTab.ts; the notice row, the status bar's VIEW ONLY cell, the glance's note and the shell's
`data-owner` all read it through `useViewOnly` (lib/ui/OwnerTab.tsx), re-read when the key changes. The button
"Make this tab yours" reloads bypassing the cache (`location.reload(true)`): Firefox's plain reload looks to Studio
exactly like a link (tests/test_studio_owner_tab_firefox.py drives a real Firefox). Run in node through
tests/helpers/node_ts.py (no browser, no wall clock).
Run: python -m tests.test_owner_tab_ui
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
LIB = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "lib"
SRC = LIB.parent
LINK = "This tab can look but not change things, because a link or a script opened it."
RELOAD = "This tab can look but not change things: Studio could not tell this reload from a link."
AGAIN = "This tab can look but not change things, because Studio was started again since it was opened."


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


@test
def test_the_three_sentences_and_none(ctx: Ctx):
    from tests.helpers import node_ts
    words = json.dumps((LIB / "ownerTab.ts").resolve().as_uri())
    got = node_ts.run(f"const M = await import({words});\nconst f = M.ownerLine || (() => 'no ownerLine');\n"
                      "console.log(JSON.stringify({link: f(false, true, 'navigate'), back: f(false, true, 'back_forward'),"
                      " reload: f(false, true, 'reload'), none: f(false, true, ''), again: f(true, false, 'navigate'),"
                      " again_reload: f(true, false, 'reload'), his: f(true, true, 'navigate'), his_reload: f(true, true, 'reload')}));")
    ctx.check(f"no salt, the entry is not a reload: the link sentence, got {got}",
              got.get("link") == LINK and got.get("back") == LINK and got.get("none") == LINK)
    ctx.check(f"no salt, the entry IS a reload: the reload sentence, got {got.get('reload')!r}", got.get("reload") == RELOAD)
    ctx.check(f"a salt, a key the proof was not made for: Studio was started again, got {got.get('again')!r} {got.get('again_reload')!r}",
              got.get("again") == AGAIN and got.get("again_reload") == AGAIN)
    ctx.check(f"a salt and the proof's key: nothing said, got {got.get('his')!r} {got.get('his_reload')!r}",
              got.get("his") == "" and got.get("his_reload") == "")


@test
def test_one_answer_read_everywhere_and_re_read_on_a_new_key(ctx: Ctx):
    owner = _read(LIB / "owner.ts")
    ctx.check("lib/owner.ts answers from the navigation entry's type", "getEntriesByType(\"navigation\")" in owner
              and "export function viewOnly(" in owner)
    ctx.check("lib/owner.ts no longer has ownerPage (a salt served is not the answer)", "ownerPage" not in owner)
    tab = _read(LIB / "ui" / "OwnerTab.tsx")
    ctx.check("lib/ui/OwnerTab.tsx re-reads the answer when the key changes (onTokenChange)",
              "export function useViewOnly(" in tab and "onTokenChange" in tab)
    for rel in ("App.tsx", "shell/StatusBar.tsx"):
        src = _read(SRC / rel)
        ctx.check(f"{rel} reads useViewOnly and not ownerPage", "useViewOnly" in src and "ownerPage" not in src)
    ctx.check("the notice row reads it", "if (!useViewOnly()) return null;" in tab)
    glance = _read(SRC / "routes" / "glance" / "Glance.tsx")
    ctx.check("the glance's note is the same component, the notice row (its old sentence is gone)",
              "<OwnerTabRow" in glance and "Paste the glance's address" not in glance and "ownerPage" not in glance)


@test
def test_the_button_reloads_bypassing_the_cache(ctx: Ctx):
    """Firefox honours reload(true) and sends `Cache-Control: no-cache`, which the server's reload rule takes; the
    other browsers ignore the argument. Only for a trusted press."""
    tab = _read(LIB / "ui" / "OwnerTab.tsx")
    m = re.search(r"function yours\([^)]*\)[^{]*\{(.*?)\n\}", tab, re.S)
    body = m.group(1) if m else ""
    ctx.check(f"the handler reloads with true, only for isTrusted, got {body.strip()!r}",
              "isTrusted" in body and re.search(r"reload\)?\.call\(location, true\)|reload\(true\)", body) is not None)
    ctx.check("one comment names the Firefox test", "test_studio_owner_tab_firefox" in tab)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
