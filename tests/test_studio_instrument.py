"""tests.test_studio_instrument -- Halo 3.3.15.0 L1 "Instrument, the look" (docs/design/studio-instrument/PROPOSAL.md;
the owner 2026-11-08: "I downloaded a new gui look for halo"). Unit pins, then headless Chrome through
tests/helpers/studio_instrument.py (skipped without one) over capture_studio's seeded home and the Studio fleet rig;
no provider request, no model call:

1. the palette: `instrument` is PROPOSAL section 1's seventeen tokens, dark, every text token >= 4.5:1 on bg, surface
   and surface-2 (the lowest, faint on surface-2, 4.9), accent_ink on accent >= 10; it is the dark default;
2. the derived block: the static names of section 2 (radii, spacing, type, motion 160 / 240 / 600 ms, the dot grid,
   the soft tints, the 1 px glows) and no colour literal in the files the look rewrote; each under the 250-line cap;
3. the prefix strip (lib/modelName.ts, run under node when there is one);
4. Chrome: a fresh dark-system page is `data-theme="instrument"` (3.3.15.0 R4; `auto` before), drawn in instrument; the rail is 52 px, 176 px on its
   chevron, kept across a reload; a panel and the palette carry their four corner ticks (the selected panel's in the
   text colour); nothing animates on any core section's load or switch;
5. Chrome, the rig: the Session Map's and Roles Live's nodes show the model without its provider prefix, the
   Inspector's Live tab the full id; Roles' Apply asks with the three mono lines DOES / COSTS / WRITES; the working
   agents animate, and with prefers-reduced-motion nothing runs after a state change.
Run: python -m tests.test_studio_instrument
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
_RUN: dict = {}
PROPOSAL = ("#07090C", "#0B0E12", "#0F1318", "#151A21", "#232A33", "#1A2028", "#E6EDF3", "#9AA6B2", "#7D8995",
            "#22D3EE", "#F5A524", "#031317", "#3DD68C", "#F5A524", "#FF5C6A", "#A78BFA", "#67E8F9")
REWRITTEN = ["styles/base.css", "styles/shell.css", "styles/motion.css", "styles/nodes.css", "styles/instrument.css", "styles/holo.css",
             "styles/workspace.css", "lib/ui/Dialog.tsx", "lib/ui/DialogCost.tsx", "lib/ui/Surface.tsx", "lib/ui/Toast.tsx",
             "lib/ui/Field.tsx", "lib/ui/FitMeter.tsx", "lib/modelName.ts", "lib/motion/born.ts"]
SHORT = {"or:qwen/qwen3-coder": "qwen3-coder", "ol:qwen3:30b@gpu-box": "qwen3:30b", "hf:local/Qwen2.5-7B@box": "Qwen2.5-7B",
         "hf:mlx/mlx-community/Qwen2.5-7B-4bit": "Qwen2.5-7B-4bit", "ant:claude-opus-5.5": "claude-opus-5.5", "gemma:7b": "gemma:7b",
         "dbx:databricks-gpt-5-mini": "databricks-gpt-5-mini", "qwen3-lead": "qwen3-lead", "": ""}


def _got(ctx: Ctx, which: str) -> dict:
    return driver_got(ctx, "tests.helpers.studio_instrument", why="the Instrument look's checks need headless Chrome",
                      cache=_RUN, key=which, args=(which,), timeout=420, tail=600, what=f"the {which} driver")


@test
def test_the_palette_is_the_proposal_and_the_dark_default(ctx: Ctx):
    from halo_harness.themes import registry as R
    from halo_harness.themes.palettes import FOLLOW_DARK, TOKEN_NAMES
    p = R.palette("instrument")
    ctx.check("instrument is in the registry, dark", bool(p) and p["posture"] == "dark")
    ctx.check("its seventeen tokens are PROPOSAL section 1's", tuple(p["tokens"][k].upper() for k in TOKEN_NAMES) == PROPOSAL)
    low = [(f, b, round(R.contrast(p["tokens"][f], p["tokens"][b]), 2)) for f in ("text", "muted", "faint")
           for b in ("bg", "bg2", "surface", "surface2") if R.contrast(p["tokens"][f], p["tokens"][b]) < 4.5]
    ctx.check(f"every text token over 4.5:1 on every face, under: {low}", not low)
    ctx.check("faint on surface-2 is the lowest, 4.9", round(R.contrast(p["tokens"]["faint"], p["tokens"]["surface2"]), 1) == 4.9)
    ctx.check("accent_ink on accent over 10:1", R.contrast(p["tokens"]["accent_ink"], p["tokens"]["accent"]) >= 10)
    ctx.check("every pinned pair of instrument and its modifiers passes", all(r[2] >= r[3] for n in ("instrument", "instrument-daltonized",
              "instrument-ansi") for r in R.contrast_rows(n)))
    ctx.check("follow the system: instrument dark, holo still a palette", FOLLOW_DARK == "instrument" and R.follow("dark") == "instrument"
              and R.palette("holo") is not None and R.follow("light") == "paper")
    from halo_harness.theme import DEFAULT_THEME
    ctx.check("3.3.15.0 R4: instrument is the default everywhere", R.DEFAULT == "instrument" and DEFAULT_THEME == "instrument")


@test
def test_the_derived_block_and_no_colour_literal(ctx: Ctx):
    css = (UI / "styles" / "tokens.css").read_text(encoding="utf-8")
    static = css.split("/* themes:begin")[0]
    for name in ("--r-panel: 6px", "--r-card: 4px", "--r-chip: 3px", "--s-1: 4px", "--s-6: 28px", "--dur-fast: 160ms", "--dur-base: 240ms",
                 "--dur-slow: 600ms", "--t-data: 400 12px/18px", "--t-body: 400 13px/20px", "--glass: var(--surface)", "--grid-size: 16px",
                 "--glow-accent: 0 0 0 1px color-mix(in srgb, var(--accent) 55%", "--soft-accent: var(--accent-soft)", "--rail-w: 52px"):
        ctx.check(f"tokens.css declares {name}", name in static)
    ctx.check("the reduced-motion rule zeroes the durations", "--dur-slow: 0ms" in css)
    for rel in REWRITTEN:
        text = (UI / rel).read_text(encoding="utf-8")
        body = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        raw = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", body)
        n = len(text.splitlines())
        ctx.check(f"{rel}: no colour literal ({raw}), {n} lines <= 250", not raw and n <= 250)


@test
def test_the_prefix_strip(ctx: Ctx):
    src = (UI / "lib" / "modelName.ts").read_text(encoding="utf-8")
    ctx.check("one rule, Halo's route words", "/^(or|ol|dbx|db|ant|oai|hf|xp):/" in src)
    # 3.3.16.0 R2: the Fleet map's and Tree's nodes went; Agents -> Live draws every agent with LiveNode on either scope
    users = {f: (UI / f).read_text(encoding="utf-8") for f in ("routes/roles/LiveNode.tsx", "routes/session/Live.tsx")}
    ctx.check(f"the nodes and Live's tags use it, got {[f for f, t in users.items() if 'shortModel(' not in t]}",
              all("shortModel(" in t for t in users.values()))
    from tests.helpers import node_ts  # 3.4.1.1: a node without TypeScript (Debian's) transpiles with the UI's tsc
    url = (UI / "lib" / "modelName.ts").resolve().as_uri()
    keys = list(SHORT)
    got = node_ts.run(f"const m = await import({url!r}); console.log(JSON.stringify({keys!r}.map(m.shortModel)))")
    ctx.check(f"each id loses its prefix, its host and its vendor path, got {got}", got == [SHORT[k] for k in keys])


@test
def test_the_page_is_instrument_on_a_dark_system(ctx: Ctx):
    got = _got(ctx, "fresh")
    ctx.check(f"data-theme instrument (3.3.15.0 R4: the default), instrument's colours, got {got.get('theme')} {got.get('bg')} "
              f"{got.get('accent')} {got.get('body_bg')}", got.get("theme") == "instrument" and got.get("bg") == "#07090c" and got.get("surface") == "#0f1318"
              and got.get("accent") == "#22d3ee" and got.get("body_bg") == "rgb(7, 9, 12)")


@test
def test_the_rail_collapses_and_remembers(ctx: Ctx):
    got = _got(ctx, "fresh")
    ctx.check(f"52 px, 176 px on its chevron, got {got.get('rail_w')} {got.get('rail_open_w')}",
              got.get("rail_w") == 52 and got.get("rail_open_w") == 176)
    ctx.check(f"kept across a reload, got {got.get('rail_reload')}", got.get("rail_reload") == ["open", 176, "open"])
    ctx.check(f"and back to 52, got {got.get('rail_back')}", got.get("rail_back") == 52)


@test
def test_a_surface_carries_its_corner_ticks(ctx: Ctx):
    got = _got(ctx, "fresh")
    want = [4, "10px 1px, 1px 10px, 10px 1px, 1px 10px"]
    ctx.check(f"a panel's four ticks, got {got.get('panel_ticks')}", got.get("panel_ticks") == want)
    ctx.check(f"the selected panel's ticks in the text colour, got {got.get('selected_ticks')}", got.get("selected_ticks") == 4)
    ctx.check(f"the palette's too, and the one shadow level, got {got.get('palette_ticks')} {got.get('palette_shadow')!r}",
              got.get("palette_ticks") == want and "40px" in str(got.get("palette_shadow")))


@test
def test_nothing_animates_on_a_section_load(ctx: Ctx):
    got = _got(ctx, "fresh")
    loads, keys = got.get("load_anims") or {}, got.get("key_anims") or {}
    ctx.check(f"each core section loaded: no animation started, got {loads}", len(loads) == 6 and all(v == [] for v in loads.values()))  # 3.3.16.0 R2: six
    ctx.check(f"each reached by Alt+1..6: none either, got {keys}", len(keys) == 6 and all(v == [] for v in keys.values()))
    ctx.check(f"the listener sees one that does start, got {got.get('listener_control')}", got.get("listener_control") == ["m-blink"])


@test
def test_a_node_shows_the_model_without_its_prefix(ctx: Ctx):
    got = _got(ctx, "rig")
    want = ["cheap-coder", "cheap-fast", "glm-5-coder"]
    ctx.check(f"the Session Map's nodes, got {got.get('map_labels')}", got.get("map_labels") == want)
    ctx.check(f"their tooltip keeps the full id, got {got.get('map_titles')}",
              all(f"or:mock/{w}" in str(t) for w, t in zip(want, got.get("map_titles") or [])))  # 3.3.16.0 R2: the line's title is the full id
    ctx.check(f"Roles Live's nodes, got {got.get('live_labels')}",
              [str(x).split(" ·")[0] for x in got.get("live_labels") or []] == want)
    ctx.check(f"the Inspector's Live tab has the full id, got {got.get('inspector_meta')!r}", "or:mock/cheap-fast" in str(got.get("inspector_meta")))


@test
def test_a_confirmation_shows_does_costs_writes(ctx: Ctx):
    got = _got(ctx, "rig")
    ctx.check(f"three keys, got {got.get('cost_keys')}", got.get("cost_keys") == ["DOES", "COSTS", "WRITES"])
    lines = got.get("cost_lines") or []
    ctx.check(f"three lines, each said, got {lines}", len(lines) == 3 and all(str(x).strip() for x in lines)
              and "config.json" in str(lines[2]))
    ctx.check(f"in mono, got {got.get('cost_font')!r}", "Mono" in str(got.get("cost_font")) or "monospace" in str(got.get("cost_font")))
    ctx.check(f"the dialog wears its ticks, got {got.get('dialog_ticks')}", (got.get("dialog_ticks") or [0])[0] == 4)


@test
def test_reduced_motion_is_an_instant_state_swap(ctx: Ctx):
    got = _got(ctx, "rig")
    ctx.check(f"the working agents animate with motion allowed, got {got.get('motion_running')}", (got.get("motion_running") or 0) > 0)
    ctx.check(f"with prefers-reduced-motion nothing runs after a state change, got {got.get('reduced_running')}",
              got.get("reduced_running") == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
