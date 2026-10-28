"""tests.test_studio_setup -- the Setup section in the page (Halo 3.3.0.0 R1-R3).
Headless Chrome through the driver base (tests/helpers/studio_setup.py and
studio_setup_providers.py; skipped without one), over a seeded home (the
shipped lineups, halo-dev-cycle active), a stub catalog of two models and an
env file in that home (`HALO_ENV_FILE`); no provider request, no model call:

0. (R3) with no provider set up: Start here's first button is "Set up this
   box", its Run's 422 lands on Setup with a toast; no `?mode=` opens on
   Setup whatever was saved;
1. `?mode=setup` opens it, and Alt+8 from Roles: the eighth and last tab;
   the strip names the provider, model, lineup, mode, theme and last check;
   no block says it comes later; (3.3.1.0 R1) no panels: the rail lists the
   steps, one page each (every step opens its block's page first);
   (R2) Providers: OpenRouter's Save & test with a test key writes the env
   file, the card shows the masked tail, the strip names it; an Ollama host
   added is in the hosts table; Local models: a folder added is listed and
   counted, the runtime saved;
   (R5) Find lists two mock Ollama servers, a tick on each + Add the ticked
   puts them in the hosts table, the Models panel lists `Ollama (<name>)`
   for each, Measure (the calibration stubbed) fills the log;
2. Permissions: plan picked says "1 changed", Save writes it to
   config.json and the strip follows;
3. Terminal theme: six swatches drawn in their own colours, claude-light saved;
4. Default model: grouped by provider, the search narrows it, saved;
5. Team: balanced with its preview, Apply writes team and roles on; One
   model for everything removes team and turns roles off;
6. a config.json write from outside: the strip follows the frame;
6b. (R4) the doors: ?first=1 opens nothing (3.3.1.0 R1) and the strip says
   "set up this box"; ?block=team and a focus frame open that block's page
   and focus it;
7. (R3) Check: the five rows and their defaults, the gym's models, the card
   before the guided first run's box, a run of stub checks fills the logs,
   the summary and the strip; Linux fixes: two stubbed fixes applied.
Run: python -m tests.test_studio_setup
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}
CORE = ["Session", "Team", "Roles", "Fleet", "Design", "Orchestra", "Packs", "Setup", "Settings", "Local"]  # 3.3.3.0 R2: + Settings; 3.3.5.0 R1: + Local


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Setup checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_setup"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=400, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in info)
    return info


@test
def test_setup_opens_by_mode_and_by_alt_8(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"?mode=setup opens it, got {got.get('mode_section')!r}", str(got.get("mode_section")).startswith("Setup"))
    ctx.check(f"the nine tabs, Setup then Settings last, got {got.get('tabs')}", got.get("tabs") == CORE)
    ctx.check(f"Alt+1..9 and Alt+0 (3.3.3.0 R2: Settings on Alt+9; 3.3.5.0 R1: Local on Alt+0), got {got.get('kbds')}",
              got.get("kbds") == [f"Alt+{n % 10}" for n in range(1, 11)])
    ctx.check(f"Alt+8 from Roles opens it, got {got.get('alt8')!r}", str(got.get("alt8")).startswith("Setup"))
    ctx.check(f"3.3.1.0 R1: no panels on Setup, got {got.get('panels')}", got.get("panels") == [])
    steps = [s for s in got.get("steps") or [] if s != "linux"]  # Linux fixes: a step only on a box that needs them
    ctx.check(f"the rail lists the steps in the wizard's order, got {got.get('steps')}",
              steps == ["providers", "local", "model", "permissions", "theme", "team", "check", "summary"])
    ctx.check(f"each with its title, got {got.get('rail')}", (got.get("rail") or [""] * 3)[2] == "Default model")


@test
def test_the_strip_says_what_is_set(ctx: Ctx):
    got = _got(ctx)
    want = [["provider", "no provider set"], ["model", "not set"], ["lineup", "halo-dev-cycle"], ["permissions", "not set"],
            ["theme", "claude-dark (default)"], ["check", "not run"]]
    ctx.check(f"provider, model, lineup, permissions, theme, got {got.get('strip')}", got.get("strip") == want)
    ctx.check("the strip is there on ?mode=setup too", got.get("mode_first_strip") == want)


@test
def test_no_block_says_it_comes_later(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"R3: Linux fixes and Check are real blocks, got {got.get('later')}", got.get("later") == [])


@test
def test_no_provider_lands_on_setup(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Start here's first button, got {got.get('jump_first_button')!r} {got.get('land_first_button')!r}",
              got.get("jump_first_button") == "Set up this box" and got.get("land_first_button") == "Set up this box")
    ctx.check(f"its Run's 422 no_provider opens Setup with a toast, got {got.get('jump_section')!r} {got.get('jump_toast')!r}",
              str(got.get("jump_section")).startswith("Setup") and got.get("jump_toast") == "no provider is set up yet: Setup")
    ctx.check(f"the strip says no provider set, got {got.get('jump_strip')!r}", got.get("jump_strip") == "no provider set")
    ctx.check(f"no ?mode=, Roles saved: the page opens on Setup, got {got.get('land_section')!r} {got.get('land_boot')!r}",
              str(got.get("land_section")).startswith("Setup") and got.get("land_boot") == "1")
    ctx.check("3.3.1.0 R1: no Start here over Setup", got.get("land_overlay_on_setup") is False)
    ctx.check("3.3.2.0 R1: nor on the next section (the first section only)", got.get("land_overlay_next") is False)
    ctx.check(f"Set up this box closes the overlay on Setup, got {got.get('land_after')!r}", str(got.get("land_after")).startswith("Setup"))


@test
def test_the_check_block(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"five rows, doctor / catalog / hello ticked, got {got.get('check_rows')} {got.get('check_ticks')}",
              got.get("check_rows") == ["doctor", "catalog", "hello", "gym", "start"] and got.get("check_ticks") == [True, True, True, False, False])
    ctx.check(f"each row says what / cost / time / writes, got {got.get('check_detail')!r}",
              all(w in str(got.get("check_detail")) for w in ("Cost: ", "Time: ", "Writes: ")))
    ctx.check(f"ticking the gym lists its models, got {got.get('gym_models')}", "or:mock/beta" in (got.get("gym_models") or []))
    ctx.check(f"the guided first run's box is off until the card shows, got {got.get('check_start_locked')} {got.get('start_unlocked')}",
              got.get("check_start_locked") is True and got.get("start_unlocked") is True)
    ctx.check(f"the card under its row, got {got.get('card_first')!r}", got.get("card_first") == "The guided first run (halo start)")
    ctx.check(f"Run: the summary, got {got.get('summary')!r}", got.get("summary") == "1 failed: hello")
    ctx.check(f"each row's glyph, got {got.get('glyphs')}", got.get("glyphs") == ["ok", "ok", "!!", "ok", ""])
    logs = dict(got.get("logs") or [])
    ctx.check(f"each row's log, got {logs}", logs.get("doctor") == "doctor stub: config ok" and logs.get("hello") == "no pong (stub)")
    ctx.check(f"the strip and the rail say the last check, got {got.get('strip_check')!r} {got.get('rail_check')!r}",
              re.fullmatch(r"1 failed \d\d:\d\d", str(got.get("strip_check"))) is not None and got.get("rail_check") == got.get("strip_check"))
    ctx.check("last-check.json written", got.get("last_check_file") is True)


@test
def test_the_linux_fixes_block(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"a box missing both: the two fixes, got {got.get('linux_items')} {got.get('linux_rail')!r}"
              + (f" timeout={got.get('linux_timeout')}" if got.get("linux_timeout") else ""),
              got.get("linux_items") == ["ripgrep", "path"] and got.get("linux_rail") == "2 to apply")
    ctx.check(f"Apply ran both stubs, the lines say so, got {got.get('linux_calls')} {got.get('linux_lines')!r}",
              got.get("linux_calls") == ["rg", "rc"] and "installed rg: " in str(got.get("linux_lines")))
    ctx.check(f"then nothing to fix, got {got.get('linux_after')!r}", got.get("linux_after") == "nothing to fix on this box")


@test
def test_a_provider_key_saved_and_masked(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the eight cards in the wizard's order, got {got.get('cards')}", got.get("cards") == [
        "databricks", "openrouter", "anthropic", "ollama", "huggingface", "openai", "typesafe", "experiential"])
    ctx.check(f"not set before; a password field that says paste a key, got {got.get('or_before')!r} {got.get('or_field_type')!r}",
              got.get("or_before") == "not set" and got.get("or_field_type") == "password" and got.get("or_placeholder") == "paste a key")
    ctx.check(f"Save & test wrote the env file in the test home, got {got.get('env_has_key')}", got.get("env_has_key") is True)
    ctx.check(f"the card: the key set, its tail, typed here (3.3.5.0 R0 (g)), got {got.get('or_state')!r}",
              got.get("or_state") == "key set (****3344), typed here")
    ctx.check(f"the lines: written, then the offline test, got {got.get('or_lines')!r}",
              str(got.get("or_lines")).startswith("wrote OPENROUTER_API_KEY to ") and "reachable: not checked" in str(got.get("or_lines")))
    ctx.check(f"enabled, the field empty again, got {got.get('or_enabled')!r} {got.get('or_field_after')!r}",
              got.get("or_enabled") == "enabled" and got.get("or_field_after") == "")
    ctx.check("the key is nowhere in the page", got.get("key_in_page") is False)
    ctx.check(f"the strip names the provider, got {got.get('or_strip')!r}", got.get("or_strip") == "openrouter")


@test
def test_an_ollama_host_added(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the host is in the table as the default, got {got.get('ollama_rows')}",
              got.get("ollama_rows") == [["lan", "http://192.0.2.20:11434", "default", "-"]])
    ctx.check(f"and in config.json, got {got.get('ollama_config')}", got.get("ollama_config") == ["http://192.0.2.20:11434"])
    ctx.check(f"the card says set, got {got.get('ollama_state')!r}", str(got.get("ollama_state")).startswith("set, from config.json"))
    ctx.check(f"Find and Scan are on (3.3.0.0 R5), no placeholder line, got {got.get('ollama_finders')} {got.get('ollama_later')!r}",
              got.get("ollama_finders") == [False, False] and got.get("ollama_later") == "")


@test
def test_find_add_and_measure_ollama_servers(ctx: Ctx):
    got = _got(ctx)
    found = {r[0]: r for r in got.get("found") or []}
    ctx.check(f"Find lists both mocks, each new with a tick and its models, got {got.get('found')} ({got.get('find_by')})",
              len(found) == 2 and all(r[3] for r in found.values())
              and sorted(r[2] for r in found.values()) == ["1 model: llama3.2:3b", "2 models: qwen3:30b, gpt-oss:20b"])
    ctx.check(f"the ports line names the mock ports, got {got.get('ports_line')!r}", "ollama.discover.ports" in str(got.get("ports_line")))
    ctx.check(f"Scan in tests: the note, no new row, got {got.get('scan_line')!r} {got.get('rows_after_scan')}",
              got.get("scan_line") == "the network scan is off in tests" and got.get("rows_after_scan") == 2)
    ctx.check(f"Add the ticked (2), got {got.get('add_label')!r}", got.get("add_label") == "Add the ticked (2)")
    hosts = got.get("hosts_config") or []
    ctx.check(f"R2's host stays first and the default, the two added after, got {hosts}",
              len(hosts) == 3 and hosts[0] == ["lan", "http://192.0.2.20:11434", True] and all(h[2] is None for h in hosts[1:]))
    ctx.check(f"the hosts table shows all three, the rows say configured, got {got.get('hosts_rows')} {got.get('configured_after')}",
              [r[0] for r in got.get("hosts_rows") or []] == [h[0] for h in hosts] and got.get("configured_after") == 2)
    ctx.check(f"the add lines, got {got.get('add_lines')!r}", str(got.get("add_lines")).count("added Ollama host") == 2)
    panel = got.get("models_panel") or []
    ctx.check(f"the Models panel lists Ollama (<name>) for each new host, got {panel}",
              all(any(line.startswith(f"Ollama ({n}): ok, ") for line in panel) for n in got.get("added_names") or ["?"]))
    ctx.check(f"Measure offers every model of the added hosts, ticked, got {got.get('measure_models')}",
              len(got.get("measure_models") or []) == 3 and all(m[1] for m in got["measure_models"]))
    lines = got.get("measure_lines") or []
    ctx.check(f"one log line per model, got {lines} ({got.get('measure_by')})",
              len(lines) == 3 and all(" on " in ln and "32k fits" in ln for ln in lines))
    ctx.check(f"the summary, got {got.get('measure_summary')!r}", str(got.get("measure_summary")).startswith("3 models measured on 2 hosts in ")
              and "3 fit, 0 do not fit" in str(got.get("measure_summary")))
    ctx.check(f"the calibration ran per model (stubbed), recorded, got {got.get('measure_calls')} {got.get('fit_recorded')}",
              len(got.get("measure_calls") or []) == 3 and got.get("fit_recorded") is True)


@test
def test_a_model_folder_and_the_runtime(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the folder is listed and in config.json, got {got.get('dirs')} {got.get('dirs_config')}",
              len(got.get("dirs") or []) == 1 and got.get("dirs") == got.get("dirs_config"))
    ctx.check(f"the detection lines count its model, got {got.get('detection')!r}", "holds 1 model (gguf)" in str(got.get("detection")))
    ctx.check(f"the rail says 1 folder, got {got.get('rail_local')!r}", str(got.get("rail_local")).startswith("1 folder"))
    ctx.check(f"the runtime saved, got {got.get('runtime_config')!r}", got.get("runtime_config") == "mlx_lm")


@test
def test_permissions_save(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the four modes, got {got.get('modes')}", got.get("modes") == ["auto", "acceptEdits", "default", "plan"])
    ctx.check("a pick says 1 changed", got.get("mode_word") == "changed")
    ctx.check(f"Save writes config.json, got {got.get('mode_config')!r}", got.get("mode_config") == "plan")
    ctx.check(f"the strip follows, got {got.get('mode_strip')!r}", got.get("mode_strip") == "plan")
    ctx.check(f"the block shows what was written, got {got.get('mode_lines')!r}", str(got.get("mode_lines")).startswith("permission_mode = plan (saved to "))


@test
def test_terminal_theme_save(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"six swatches, got {got.get('swatches')}", len(got.get("swatches") or []) == 6 and "claude-light-ansi" in got["swatches"])
    ctx.check(f"a swatch is drawn in its theme's colours (claude-light's bg #eff1f5), got {got.get('swatch_bg')!r}",
              got.get("swatch_bg") == "rgb(239, 241, 245)")
    ctx.check("the block says Studio's own switch is a browser setting", "setting of this browser" in str(got.get("theme_note")))
    ctx.check(f"Save writes config.json, got {got.get('theme_config')!r}", got.get("theme_config") == "claude-light" and got.get("theme_strip") == "claude-light")


@test
def test_default_model_save(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"grouped by provider, got {got.get('groups')} {got.get('models')}",
              got.get("groups") == ["openrouter"] and got.get("models") == ["or:mock/alpha", "or:mock/beta"])
    ctx.check(f"the search narrows it by best at, got {got.get('searched')}", got.get("searched") == ["or:mock/beta"])
    ctx.check(f"Save writes config.json, got {got.get('model_config')!r}", got.get("model_config") == "or:mock/beta" and got.get("model_strip") == "or:mock/beta")


@test
def test_team_apply(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"One model first, auto, then the lineups, got {got.get('lineups')}",
              (got.get("lineups") or [])[:2] == ["one-model", "auto"] and "balanced" in got["lineups"])
    ctx.check(f"the seeded lineup is in use, got {got.get('in_use')}", got.get("in_use") == ["halo-dev-cycle"])
    ctx.check(f"the preview of the pick, got {got.get('preview')!r}", str(got.get("preview")).startswith("balanced"))
    ctx.check(f"Apply: team and roles on in config.json, the strip follows, got {got.get('team_config')} {got.get('team_strip')!r}",
              got.get("team_config") == ["balanced", True] and got.get("team_strip") == "balanced")
    ctx.check(f"One model for everything: no team, roles off, got {got.get('one_config')} {got.get('one_strip')!r}",
              got.get("one_config") == [False, False] and got.get("one_strip") == "one model for everything")


@test
def test_a_write_from_outside_shows(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"config.json written outside the page: the strip follows, got {got.get('outside_strip')!r}", got.get("outside_strip") == "acceptEdits")


@test
def test_the_doors_first_run_and_a_block(ctx: Ctx):
    """3.3.0.0 R4 (tests/helpers/studio_setup_door.py): what `halo init` and `halo setup team` open."""
    got = _got(ctx)
    ctx.check(f"?first=1: Setup and (3.3.1.0 R1) no help, no dialog, got {got.get('first_section')!r} {got.get('first_help')!r}",
              str(got.get("first_section")).startswith("Setup") and got.get("first_help") is False)
    ctx.check(f"the strip says set up this box, got {got.get('first_strip')!r}", str(got.get("first_strip")).startswith("set up this box"))
    ctx.check(f"first=1 left the address bar, the token kept, got {got.get('first_search')!r}",
              "mode=setup" in str(got.get("first_search")) and "first=" not in str(got.get("first_search")) and got.get("first_hash") is True)
    ctx.check("Start here's offer waits on the first run", got.get("first_start_open") is False)
    ctx.check(f"once: a reload opens no help and no first-run cell, got {got.get('reload_help')} {got.get('reload_strip_first')}",
              got.get("reload_help") is False and got.get("reload_strip_first") is False)
    ctx.check(f"?block=team: the Team page open, focused and in view, got {got.get('block_focus')!r} {got.get('block_visible')}",
              got.get("block_focus") == "team" and got.get("block_visible") is True and "block=" not in str(got.get("block_search")))
    ctx.check(f"a focus frame for the Check block opens its page, got {got.get('frame_focus')!r}", got.get("frame_focus") == "check")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
