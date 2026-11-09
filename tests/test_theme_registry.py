"""tests.test_theme_registry -- the palette registry (Halo 3.3.12.0 R1, halo_harness/themes): eleven palettes (3.3.15.0: + instrument), two
postures, the `-daltonized` / `-ansi` modifiers, the WCAG contrast pins, `resolve_theme` unchanged for the two
classic names, a removed game theme's notice unchanged, and the words `/theme` and `halo config set theme` say.
R2: the registry is live -- a pack's palette (`<pack-id>/<id>`) is valid only while its pack is enabled, its
modifiers derived like the eleven's, `is_valid_theme`, the schema, the Settings row and `/theme` read it at call time,
register / unregister, and the eleven unchanged.
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

ELEVEN = ("claude-dark", "claude-light", "holo", "instrument", "paper", "midnight", "ember", "forest", "slate", "dusk", "dawn")
DARK = {"claude-dark", "holo", "instrument", "midnight", "ember", "forest", "dusk"}
HEX = re.compile(r"^#[0-9a-f]{6}$")


@test
def test_eleven_palettes_two_postures_one_vocabulary(ctx: Ctx):
    from halo_harness.themes import registry as R
    from halo_harness.themes.palettes import TOKEN_NAMES
    ctx.check(f"the eleven, in order, got {R.ids()}", R.ids() == ELEVEN)
    ctx.check("the postures: seven dark, four light (3.3.15.0: + instrument)", {p for p in ELEVEN if R.posture(p) == "dark"} == DARK
              and all(R.posture(p) == "light" for p in set(ELEVEN) - DARK))
    for pid in ELEVEN:
        p = R.palette(pid)
        ctx.check(f"{pid}: a label and every token a #rrggbb", bool(p["label"]) and tuple(p["tokens"]) == TOKEN_NAMES
                  and all(HEX.match(v) for v in p["tokens"].values()))
    ctx.check("follow the system: instrument dark (3.3.15.0), paper light", R.follow("dark") == "instrument" and R.follow("light") == "paper")


@test
def test_every_modifier_is_a_valid_name(ctx: Ctx):
    from halo_harness import theme as T
    from halo_harness.themes import registry as R
    want = {f"{pid}{suf}" for pid in ELEVEN for suf in ("", "-daltonized", "-ansi")}
    ctx.check(f"VALID_THEMES = the eleven x the modifiers, got {len(T.VALID_THEMES)} names", set(T.VALID_THEMES) == want)
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

    for pid in ELEVEN:
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
    # 3.3.15.0 R4: unset is instrument in the terminal too (claude-dark before); `auto` draws the default there
    ctx.check("the default is instrument", T.DEFAULT_THEME == "instrument" and T.resolve_theme(env=tc) == "instrument")
    ctx.check("claude-light wins as before", T.resolve_theme(env=tc, persisted_theme="claude-light") == "claude-light")
    ctx.check("no truecolor: instrument-ansi", T.resolve_theme(env={"TERM": "xterm"}) == "instrument-ansi")
    ctx.check("a saved auto draws the default, truecolor-aware", T.resolve_theme(env=tc, persisted_theme="auto") == "instrument"
              and T.resolve_theme(env={"TERM": "xterm"}, persisted_theme="auto") == "instrument-ansi"
              and T.is_theme_value("auto") and not T.is_valid_theme("auto"))
    ctx.check("a new palette resolves like any name", T.resolve_theme(env=tc, persisted_theme="ember") == "ember")
    ctx.check("the removed notice, verbatim", T.removed_theme_notice("instrument", persisted="doom")
              == "theme: doom was a game theme, removed in 3.1.5.0; using instrument")
    from halo_harness.tui.theme import variables_for
    v = variables_for("claude-dark")
    ctx.check("claude-dark draws as before", (v["bridge-bg"], v["bridge-accent"], v["bridge-tool"], v["bridge-thinking"])
              == ("#1e1e2e", "#89b4fa", "#fab387", "#585b70"))
    ctx.check("an unknown name falls back to instrument", variables_for("nope") == variables_for("instrument")
              and variables_for("nope")["bridge-bg"] == "#07090c")
    ctx.check("-daltonized now draws differently", variables_for("claude-dark-daltonized")["bridge-success"] != v["bridge-success"])


@test
def test_the_words_of_theme_and_config_set(ctx: Ctx):
    from halo_harness.themes import cli
    text = cli.listing("ember-daltonized")
    lines = text.splitlines()
    ctx.check(f"the current line, then the eleven, got {lines[:2]}", lines[0] == "Current theme: ember-daltonized"
              and [ln.split()[1] if ln.startswith(" *") else ln.split()[0] for ln in lines[1:12]] == list(ELEVEN))
    ctx.check("ember marked, with its posture and label", any(ln.startswith(" * ember") and " dark " in ln and "Red and orange" in ln
                                                              for ln in lines))
    ctx.check("the modifiers said, the one on now named", "-daltonized" in lines[12] and "on now: -daltonized" in lines[12])
    line = cli.refusal("solarized")
    ctx.check(f"a refusal names the eleven in one line, got {line!r}", "\n" not in line and all(p in line for p in ELEVEN)
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
        ctx.check(f"an unknown name: exit 2, one line naming the eleven, got {bad} {lines}", bad == 2 and len(lines) == 1
                  and all(p in lines[0] for p in ELEVEN) and T.load_persisted_theme() == "ember-daltonized")
        T.set_config_value("theme", "solarized")
        from halo_harness.doctor_config import config_findings
        found = [f for f in config_findings(h.repo) if f.get("key") == "theme"]
        ctx.check(f"doctor --config names the unknown theme, got {[f['text'][:80] for f in found]}",
                  len(found) == 1 and found[0]["text"].startswith("theme is one of auto, claude-dark") and "dawn-ansi" in found[0]["text"])
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            follow = _cmd_set(["theme", "auto"])  # 3.3.15.0 R4: follow the system is a value the key takes
        ctx.check(f"auto saves, got {follow} {T.load_persisted_theme()!r}", follow == 0 and T.load_persisted_theme() == "auto")
        from halo_harness.config_cli import _cmd_get
        T.unset_config_value("theme")
        got = io.StringIO()
        with contextlib.redirect_stdout(got):
            rc = _cmd_get(["theme"])
        ctx.check(f"config get theme unset: (unset: instrument), got {rc} {got.getvalue()!r}",
                  rc == 0 and got.getvalue().strip() == "(unset: instrument)")


@test
def test_schema_and_catalog_read_the_registry(ctx: Ctx):
    from halo_harness.schemas.config_json import schema
    from halo_harness.settings_catalog import rows
    from halo_harness.themes.registry import names
    # 3.3.15.0 R4: "auto" (follow the system) leads both: a value the key takes, no longer only the unset key
    ctx.check("the config schema's enum is auto then the registry's names", schema()["properties"]["theme"]["enum"] == ["auto"] + list(names()))
    row = next(r for r in rows() if r.key == "theme")
    ctx.check("the Settings row's choices are auto then the registry's names", tuple(row.choices) == ("auto",) + names())
    src = "\n".join((Path(__file__).resolve().parent.parent / "halo_harness" / f).read_text(encoding="utf-8")
                    for f in ("schemas/config_json.py", "settings_catalog_rows_a.py"))
    ctx.check("no literal palette list in either", '"claude-light"' not in src and '"holo"' not in src)


@test
def test_a_pack_palette_is_valid_only_while_its_pack_is_enabled(ctx: Ctx):
    from halo_harness import theme as T
    from halo_harness.packs.grants import disable, enable_id
    from halo_harness.schemas.config_json import schema
    from halo_harness.settings_catalog import rows
    from halo_harness.themes import registry as R
    from halo_harness.themes.cli import listing
    from tests.helpers.packs_home import PacksHome
    with PacksHome() as h:
        h.install(h.source("pack-theme"))
        ctx.check("installed and disabled: not a theme", not T.is_valid_theme("pack-theme/nightshade") and R.pack_ids() == ()
                  and len(T.VALID_THEMES) == 33)
        enable_id("pack-theme", cwd=h.repo)
        names = {"pack-theme/nightshade", "pack-theme/linen"}
        ctx.check(f"enabled: both valid at once, got {R.pack_ids()}", set(R.pack_ids()) == names and all(T.is_valid_theme(n) for n in names)
                  and len(T.VALID_THEMES) == 39 and "pack-theme/linen-ansi" in T.VALID_THEMES)
        ctx.check("the eleven unchanged, first", R.ids() == ELEVEN and R.all_ids()[:11] == ELEVEN and R.names()[:33] == tuple(
            f"{p}{m}" for p in ELEVEN for m in ("", "-daltonized", "-ansi")))
        ctx.check("the schema and the Settings row see it now", "pack-theme/linen" in schema()["properties"]["theme"]["enum"]
                  and "pack-theme/nightshade-daltonized" in next(r for r in rows() if r.key == "theme").choices)
        base = R.palette("pack-theme/nightshade")
        dal = R.tokens("pack-theme/nightshade-daltonized")
        ctx.check("-daltonized is the same derivation as the eleven's", dal == R.daltonize(base["tokens"], "dark") and dal != base["tokens"]
                  and {dal["accent"], dal["ok"]} == {dal["accent"]} and R.split("pack-theme/nightshade-daltonized") == ("pack-theme/nightshade", "daltonized"))
        ctx.check("-ansi is the posture's 16 colours", R.tokens("pack-theme/linen-ansi") == R.tokens("paper-ansi"))
        ctx.check("posture and label", R.posture("pack-theme/linen") == "light" and R.label("pack-theme/linen-daltonized").startswith("Warm linen"))
        rows_low = [r for name in ("pack-theme/nightshade", "pack-theme/linen") for suf in ("", "-daltonized", "-ansi")
                    for r in R.contrast_rows(name + suf) if r[2] < r[3]]
        ctx.check(f"every pin over its six names, got {rows_low}", rows_low == [])
        ctx.check("resolve_theme honours it", T.resolve_theme(env={}, persisted_theme="pack-theme/linen") == "pack-theme/linen")
        from halo_harness.tui.theme import variables_for
        ctx.check("the terminal draws it at once", variables_for("pack-theme/nightshade")["bridge-accent"] == base["tokens"]["accent"])
        text = listing("pack-theme/linen")
        ctx.check("/theme lists it under the pack's name, marked", "From the pack pack-theme (Pack themes):" in text
                  and " * pack-theme/linen" in text and text.index("dawn") < text.index("From the pack"))
        disable("pack-theme")
        ctx.check("disabled: gone at once", not T.is_valid_theme("pack-theme/nightshade") and len(T.VALID_THEMES) == 33
                  and T.resolve_theme(env={"COLORTERM": "truecolor"}, persisted_theme="pack-theme/linen") == "instrument")
        ctx.check("a core name never reads the packs", R.split("holo-ansi") == ("holo", "ansi") and R.split("x/y") == ("", ""))


@test
def test_register_and_unregister(ctx: Ctx):
    from halo_harness import theme as T
    from halo_harness.themes import registry as R
    from halo_harness.themes.palettes import PALETTES
    holo = next(p for p in PALETTES if p["id"] == "holo")
    try:
        got = R.register("hand", {"id": "glow", "label": "By hand", "posture": "dark", "tokens": dict(holo["tokens"])})
        ctx.check(f"registered as hand/glow, got {got}", got == ["hand/glow"] and T.is_valid_theme("hand/glow-daltonized")
                  and R.palette("hand/glow")["pack"] == "hand")
        rows_ = [r for r in R.as_json()["palettes"] if r.get("pack") == "hand"]
        ctx.check("the API's rows carry pack and the Studio variables", len(rows_) == 1 and rows_[0]["vars"]["--accent"] == holo["tokens"]["accent"])
    finally:
        ctx.check("unregister takes it out", R.unregister("hand") and not T.is_valid_theme("hand/glow") and not R.unregister("hand"))
    ctx.check("as_json without packs: the eleven exactly as R1 sent them", [p["id"] for p in R.as_json()["palettes"]] == list(ELEVEN)
              and all("pack" not in p and "vars" not in p for p in R.as_json()["palettes"]))


if __name__ == "__main__":
    os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
