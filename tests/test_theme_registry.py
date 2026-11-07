"""tests.test_theme_registry -- the palette registry (Halo 3.3.12.0 R1, halo_harness/themes): ten palettes, two
postures, the `-daltonized` / `-ansi` modifiers, the WCAG contrast pins, `resolve_theme` unchanged for the two
classic names, a removed game theme's notice unchanged, and the words `/theme` and `halo config set theme` say.
Run: python -m tests.test_theme_registry
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

TEN = ("claude-dark", "claude-light", "holo", "paper", "midnight", "ember", "forest", "slate", "dusk", "dawn")
DARK = {"claude-dark", "holo", "midnight", "ember", "forest", "dusk"}
HEX = re.compile(r"^#[0-9a-f]{6}$")


@test
def test_ten_palettes_two_postures_one_vocabulary(ctx: Ctx):
    from halo_harness.themes import registry as R
    from halo_harness.themes.palettes import TOKEN_NAMES
    ctx.check(f"the ten, in order, got {R.ids()}", R.ids() == TEN)
    ctx.check("the postures: six dark, four light", {p for p in TEN if R.posture(p) == "dark"} == DARK
              and all(R.posture(p) == "light" for p in set(TEN) - DARK))
    for pid in TEN:
        p = R.palette(pid)
        ctx.check(f"{pid}: a label and every token a #rrggbb", bool(p["label"]) and tuple(p["tokens"]) == TOKEN_NAMES
                  and all(HEX.match(v) for v in p["tokens"].values()))
    ctx.check("follow the system: holo dark, paper light", R.follow("dark") == "holo" and R.follow("light") == "paper")


@test
def test_every_modifier_is_a_valid_name(ctx: Ctx):
    from halo_harness import theme as T
    from halo_harness.themes import registry as R
    want = {f"{pid}{suf}" for pid in TEN for suf in ("", "-daltonized", "-ansi")}
    ctx.check(f"VALID_THEMES = the ten x the modifiers, got {len(T.VALID_THEMES)} names", set(T.VALID_THEMES) == want)
    for name in sorted(want):
        ctx.check(f"{name} valid and drawn in a full token set", T.is_valid_theme(name) and len(R.tokens(name)) == 17)
    for bad in ("holo-daltonized-ansi", "ansi", "-ansi", "solarized", "holo-", None, 7):
        ctx.check(f"{bad!r} is not a theme", not T.is_valid_theme(bad) and R.tokens(bad) is None)
    ctx.check("split", R.split("ember-daltonized") == ("ember", "daltonized") and R.split("claude-light-ansi") == ("claude-light", "ansi"))
    ctx.check("the ansi set follows the posture", R.tokens("paper-ansi")["bg"] == "#ffffff" and R.tokens("ember-ansi")["bg"] == "#000000")


@test
def test_daltonized_differs_in_the_accent_pair_and_never_red_against_green(ctx: Ctx):
    import colorsys
    from halo_harness.themes import registry as R

    def hue(h: str) -> float:
        r, g, b = R.rgb(h)
        return colorsys.rgb_to_hls(r / 255, g / 255, b / 255)[0] * 360

    for pid in TEN:
        base, dal = R.tokens(pid), R.tokens(f"{pid}-daltonized")
        ctx.check(f"{pid}: the accent pair differs", (base["accent"], base["accent2"]) != (dal["accent"], dal["accent2"]))
        ctx.check(f"{pid}: ok is blue ({dal['ok']}), bad orange ({dal['bad']})",
                  180 <= hue(dal["ok"]) <= 230 and 15 <= hue(dal["bad"]) <= 45)
        ctx.check(f"{pid}: the accent pair blue and orange", 180 <= hue(dal["accent"]) <= 230 and 25 <= hue(dal["accent2"]) <= 50)
        ctx.check(f"{pid}: the rest unchanged", all(dal[k] == base[k] for k in ("bg", "bg2", "surface", "text", "muted", "warn")))


@test
def test_every_name_meets_wcag_aa_from_its_tokens(ctx: Ctx):
    from halo_harness.themes import registry as R
    ctx.check("the contrast formula (white on black is 21:1)", round(R.contrast("#ffffff", "#000000"), 2) == 21.0)
    for name in R.names():
        rows = R.contrast_rows(name)
        low = [r for r in rows if r[2] < r[3]]
        ctx.check(f"{name}: {len(rows)} pairs at 4.5:1 body / 3:1 large, under: {low}", len(rows) == len(R.PAIRS) and not low)


@test
def test_resolve_theme_unchanged_for_the_classic_names_and_the_removed_notice(ctx: Ctx):
    from halo_harness import theme as T
    tc = {"COLORTERM": "truecolor"}
    ctx.check("the default is still claude-dark", T.DEFAULT_THEME == "claude-dark" and T.resolve_theme(env=tc) == "claude-dark")
    ctx.check("claude-light wins as before", T.resolve_theme(env=tc, persisted_theme="claude-light") == "claude-light")
    ctx.check("no truecolor: claude-dark-ansi", T.resolve_theme(env={"TERM": "xterm"}) == "claude-dark-ansi")
    ctx.check("a new palette resolves like any name", T.resolve_theme(env=tc, persisted_theme="ember") == "ember")
    ctx.check("the removed notice, verbatim", T.removed_theme_notice("claude-dark", persisted="doom")
              == "theme: doom was a game theme, removed in 3.1.5.0; using claude-dark")
    from halo_harness.tui.theme import variables_for
    v = variables_for("claude-dark")
    ctx.check("claude-dark draws as before", (v["bridge-bg"], v["bridge-accent"], v["bridge-tool"], v["bridge-thinking"])
              == ("#1e1e2e", "#89b4fa", "#fab387", "#585b70"))
    ctx.check("an unknown name falls back to claude-dark", variables_for("nope") == v)
    ctx.check("-daltonized now draws differently", variables_for("claude-dark-daltonized")["bridge-success"] != v["bridge-success"])


@test
def test_the_words_of_theme_and_config_set(ctx: Ctx):
    from halo_harness.themes import cli
    text = cli.listing("ember-daltonized")
    lines = text.splitlines()
    ctx.check(f"the current line, then the ten, got {lines[:2]}", lines[0] == "Current theme: ember-daltonized"
              and [ln.split()[1] if ln.startswith(" *") else ln.split()[0] for ln in lines[1:11]] == list(TEN))
    ctx.check("ember marked, with its posture and label", any(ln.startswith(" * ember") and " dark " in ln and "Red and orange" in ln
                                                              for ln in lines))
    ctx.check("the modifiers said, the one on now named", "-daltonized" in lines[11] and "on now: -daltonized" in lines[11])
    line = cli.refusal("solarized")
    ctx.check(f"a refusal names the ten in one line, got {line!r}", "\n" not in line and all(p in line for p in TEN)
              and line.startswith("not a valid theme name: 'solarized'"))
    ctx.check("a game theme keeps its note", cli.refusal("doom").endswith("doom was a game theme, removed in 3.1.5.0"))


@test
def test_halo_config_set_theme_and_the_doctor(ctx: Ctx):
    import contextlib
    import io
    from halo_harness import theme as T
    from halo_harness.config_cli import _cmd_set
    from tests.helpers.config_seed import ConfigHome
    with ConfigHome() as h:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            ok = _cmd_set(["theme", "ember-daltonized"])
            bad = _cmd_set(["theme", "solarized"])
        ctx.check(f"a palette with a modifier saves, got {ok} {T.load_persisted_theme()!r}", ok == 0 and T.load_persisted_theme() == "ember-daltonized")
        lines = err.getvalue().strip().splitlines()
        ctx.check(f"an unknown name: exit 2, one line naming the ten, got {bad} {lines}", bad == 2 and len(lines) == 1
                  and all(p in lines[0] for p in TEN) and T.load_persisted_theme() == "ember-daltonized")
        T.set_config_value("theme", "solarized")
        from halo_harness.doctor_config import config_findings
        found = [f for f in config_findings(h.repo) if f.get("key") == "theme"]
        ctx.check(f"doctor --config names the unknown theme, got {[f['text'][:80] for f in found]}",
                  len(found) == 1 and found[0]["text"].startswith("theme is one of claude-dark") and "dawn-ansi" in found[0]["text"])


@test
def test_schema_and_catalog_read_the_registry(ctx: Ctx):
    from halo_harness.schemas.config_json import schema
    from halo_harness.settings_catalog import rows
    from halo_harness.themes.registry import names
    ctx.check("the config schema's enum is the registry's names", schema()["properties"]["theme"]["enum"] == list(names()))
    row = next(r for r in rows() if r.key == "theme")
    ctx.check("the Settings row's choices are the registry's names", tuple(row.choices) == names())
    src = "\n".join((Path(__file__).resolve().parent.parent / "halo_harness" / f).read_text(encoding="utf-8")
                    for f in ("schemas/config_json.py", "settings_catalog_rows_a.py"))
    ctx.check("no literal palette list in either", '"claude-light"' not in src and '"holo"' not in src)


if __name__ == "__main__":
    os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
