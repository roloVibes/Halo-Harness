"""tests.test_review3_f2 -- 3.0.2.0 review fix pass, round F: review items 83
(the proxy launch's settings.json restore), 84 (a corrupt config.json is one
line, not a traceback) and 85 (preflight canaries the lane a session uses).
Every file lives under a temp dir; the real ~/.claude is never touched.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_ENV_KEYS = ("BRIDGE_STATE_DIR", "BRIDGE_TEST_HOME", "HALO_MODEL", "BRIDGE_MODEL", "ROLO_CLAUDE_MODEL")


@contextlib.contextmanager
def _home():
    """A fresh state dir for one test (BRIDGE_STATE_DIR) with the model
    variables cleared, everything restored afterwards."""
    saved = {k: os.environ.get(k) for k in _ENV_KEYS}
    home = Path(tempfile.mkdtemp(prefix="r3f2-home-"))
    for k in _ENV_KEYS:
        os.environ.pop(k, None)
    os.environ["BRIDGE_STATE_DIR"] = str(home)
    try:
        yield home
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---- item 83 ------------------------------------------------------------------

_SETTINGS = '{\n    "model": "opus",\n    "env": {"ANTHROPIC_AUTH_TOKEN": "tok-x"},\n    "statusLine": {"command": "echo ✓"}\n}'


def _write(path: Path, text: str, mode: int = 0o600) -> None:
    path.write_text(text, encoding="utf-8", newline="")
    if os.name != "nt":
        os.chmod(path, mode)


@test
def test_item83_unchanged_content_is_left_byte_for_byte(ctx: Ctx):
    from halo_harness.settings_restore import restore_model
    d = Path(tempfile.mkdtemp(prefix="r3f2-claude-"))
    p = d / "settings.json"
    _write(p, _SETTINGS)
    before = (p.read_bytes(), os.stat(p).st_mtime_ns)
    wrote = restore_model(p, "opus")
    ctx.check("nothing was written", wrote is False)
    ctx.check("bytes and mtime unchanged (4-space indent, non-ASCII, no trailing newline)",
              (p.read_bytes(), os.stat(p).st_mtime_ns) == before)
    p2 = d / "nomodel.json"
    _write(p2, '{"env": {}}\n')
    ctx.check("no model remembered and none present: untouched", restore_model(p2, None) is False)


@test
def test_item83_a_real_change_keeps_mode_indent_and_text(ctx: Ctx):
    from halo_harness.settings_restore import restore_model
    d = Path(tempfile.mkdtemp(prefix="r3f2-claude-"))
    p = d / "settings.json"
    _write(p, _SETTINGS.replace('"opus"', '"hijacked"'))
    ctx.check("rewritten because the model differs", restore_model(p, "opus") is True)
    text = p.read_text(encoding="utf-8")
    ctx.check("model restored, the rest intact", json.loads(text)["model"] == "opus"
              and json.loads(text)["statusLine"]["command"] == "echo ✓")
    ctx.check("4-space indent kept, non-ASCII not escaped, no trailing newline added",
              text.startswith('{\n    "model"') and "✓" in text and not text.endswith("\n"))
    if os.name != "nt":
        ctx.check("mode stays 0600", (os.stat(p).st_mode & 0o777) == 0o600)
    p3 = d / "drop.json"
    _write(p3, '{\n  "model": "x",\n  "a": 1\n}\n')
    restore_model(p3, None)
    ctx.check("a model that was never set is removed again", json.loads(p3.read_text(encoding="utf-8")) == {"a": 1})


@test
def test_item83_a_symlinked_settings_file_stays_a_symlink(ctx: Ctx):
    from halo_harness.settings_restore import restore_model
    d = Path(tempfile.mkdtemp(prefix="r3f2-claude-"))
    target = d / "dotfiles-settings.json"
    _write(target, '{\n  "model": "other"\n}\n')
    link = d / "settings.json"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        raise SkipTest("symlinks are not available here")
    restore_model(link, "opus")
    ctx.check("the link is still a link", link.is_symlink())
    ctx.check("the real target got the change", json.loads(target.read_text(encoding="utf-8"))["model"] == "opus")


@test
def test_item83_bridge_uses_the_restore_helper(ctx: Ctx):
    src = (REPO / "bridge.py").read_text(encoding="utf-8")
    ctx.check("bridge.py restores through settings_restore.restore_model", "restore_model(claude_settings_path" in src)
    ctx.check("and no longer opens settings.json for writing itself", 'open(tmp_path, "w"' not in src)


# ---- item 84 ------------------------------------------------------------------

def _main(argv):
    from halo_harness import cli
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


@test
def test_item84_corrupt_config_is_one_line_and_exit_2(ctx: Ctx):
    with _home() as home:
        (home / "config.json").write_text('{"theme": "halo", "model": "or:x/y",', encoding="utf-8")
        for argv in (["update", "--check", "--channel", "stable"], ["providers", "enable", "openrouter"]):
            code, _out, err = _main(argv)
            ctx.check(f"{argv[:2]}: exit 2, got {code}", code == 2)
            ctx.check(f"{argv[:2]}: one halo: line naming the file, got {err!r}",
                      err.startswith("halo: ") and "config.json" in err and "Traceback" not in err)
        ctx.check("the corrupt file was not rewritten",
                  (home / "config.json").read_text(encoding="utf-8").endswith('"or:x/y",'))


@test
def test_item84_library_callers_still_get_the_exception(ctx: Ctx):
    from halo_harness.theme import CorruptConfigError, set_config_value
    with _home() as home:
        (home / "config.json").write_text("{not json", encoding="utf-8")
        try:
            set_config_value("model", "or:a/b")
        except CorruptConfigError:
            ctx.check("set_config_value still raises", True)
        else:
            ctx.check("set_config_value still raises", False)


@test
def test_item84_the_wizard_step_shows_a_notice_instead_of_crashing(ctx: Ctx):
    from halo_harness.theme import CorruptConfigError
    from halo_harness.tui.dialogs.init_wizard import StepScreen

    class _App:
        notes: list = []

        def notify(self, msg, **kw):
            self.notes.append(msg)

    class _Step:
        app = _App()

        def commit(self):
            raise CorruptConfigError("config.json is not valid JSON")
    ok = StepScreen._commit_or_notify(_Step())
    ctx.check("commit failure is reported, not raised", ok is False and _Step.app.notes == ["config.json is not valid JSON"])


# ---- item 85 ------------------------------------------------------------------

@test
def test_item85_preflight_lane_follows_the_session_chain(ctx: Ctx):
    from halo_harness import launch_state
    from halo_harness.preflight import _default_lane
    with _home() as home:
        ctx.check("nothing pinned anywhere: no lane (never a guess)", _default_lane(home) is None)
        (home / "routes.json").write_text('{"default": "or:routes/model"}', encoding="utf-8")
        ctx.check("routes.json `default` identifies the lane", _default_lane(home) == "or:routes/model")
        (home / "config.json").write_text('{"model": "or:cfg/model"}', encoding="utf-8")
        ctx.check("routes.json beats config.json, like a session", _default_lane(home) == "or:routes/model")
        (home / "routes.json").unlink()
        ctx.check("config.json model identifies the lane", _default_lane(home) == "or:cfg/model")
        os.environ["HALO_MODEL"] = "or:env/model"
        ctx.check("HALO_MODEL beats config.json", _default_lane(home) == "or:env/model")
        launch_state.record_last_model("or:last/model", cwd=Path.cwd())
        ctx.check("the last-used model (/model) beats all of them", _default_lane(home) == "or:last/model")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
