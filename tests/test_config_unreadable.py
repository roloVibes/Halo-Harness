"""tests.test_config_unreadable -- a config.json that does not parse (one trailing comma from a hand edit) or cannot
be read, 3.6.0.0 fix pass:
1. the map writes (`halo maps use`, Setup's Map page, Studio's map switch, the builder's "use" row) refuse it and
   leave every byte of it, instead of rewriting it as {"crew": ...} (the model, theme, mode and providers lost);
2. it is said wherever it matters: `halo config get` (not "is not set"), `halo doctor` (a WARN row, not OK),
   Setup's state (`config_error`), and once on stderr when a session or `halo -p` builds.
Scratch homes only; no model call, no network.
Run: python -m tests.test_config_unreadable
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BROKEN = '{"model": "or:x/y", "theme": "holo",\n "permission_mode": "plan", }'


class _Home:
    """A scratch home whose config.json is BROKEN (or `text`)."""

    def __init__(self, text: str = BROKEN):
        self.text = text

    def __enter__(self):
        self._saved = os.environ.get("BRIDGE_TEST_HOME")
        d = Path(tempfile.mkdtemp(prefix="cfg-unreadable-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        from halo_harness.providers.config import default_state_dir
        self.state_dir, self.cwd = Path(default_state_dir()), d / "project"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.cwd.mkdir(parents=True)
        from halo_harness.crew.changes_map import config_path
        self.path = config_path()
        self.path.write_text(self.text, encoding="utf-8")
        return self

    def __exit__(self, *exc):
        if self._saved is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = self._saved

    def untouched(self) -> bool:
        return self.path.read_text(encoding="utf-8") == self.text


def _run(fn, *a):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = fn(*a)
        except SystemExit as e:
            rc = e.code
    return rc, out.getvalue(), err.getvalue()


@test
def test_halo_maps_use_refuses_a_broken_config_and_leaves_it(ctx: Ctx):
    with _Home() as h:
        from halo_harness.maps_cli import cmd_maps
        rc, out, err = _run(cmd_maps, ["use", "starter"])
        ctx.check(f"rc 2 and the reason, got {rc} {out!r} {err!r}", rc == 2 and "not valid JSON" in err)
        ctx.check(f"config.json untouched, got {h.path.read_text(encoding='utf-8')!r}", h.untouched())


@test
def test_setup_map_page_refuses_a_broken_config_and_leaves_it(ctx: Ctx):
    with _Home() as h:
        from halo_harness.studio import setup_api
        req = SimpleNamespace(body={"map": "starter"}, cwd=h.cwd, state_dir=h.state_dir, query={}, params={})
        status, body = setup_api.post_team(req)
        ctx.check(f"422 with the reason, got {status} {body}", status == 422 and "not valid JSON" in str(body))
        ctx.check(f"config.json untouched, got {h.path.read_text(encoding='utf-8')!r}", h.untouched())


@test
def test_studio_map_switch_refuses_a_broken_config_and_leaves_it(ctx: Ctx):
    with _Home() as h:
        from halo_harness.studio import crew_map_api
        req = SimpleNamespace(body={"on": True}, cwd=h.cwd, state_dir=h.state_dir, query={}, params={"name": "starter"})
        status, body = crew_map_api.post_use(req)
        ctx.check(f"422 with the reason, got {status} {body}", status == 422 and "not valid JSON" in str(body))
        ctx.check(f"config.json untouched, got {h.path.read_text(encoding='utf-8')!r}", h.untouched())


@test
def test_config_get_says_the_file_cannot_be_read(ctx: Ctx):
    with _Home():
        from halo_harness.config_cli import cmd_config
        rc, out, err = _run(cmd_config, ["get", "model"])
        ctx.check(f"not 'is not set': rc 2 and why, got {rc} {err!r}",
                  rc == 2 and "is not set" not in err and "not valid JSON" in err)
    with _Home('{"model": "or:x/y"}'):
        from halo_harness.config_cli import cmd_config
        rc, out, err = _run(cmd_config, ["get", "permission_mode"])
        ctx.check(f"a good file still says 'is not set', got {rc} {err!r}", rc == 1 and "is not set" in err)


@test
def test_doctor_has_a_row_for_a_broken_config(ctx: Ctx):
    with _Home():
        from halo_harness.doctor import run_checks
        entries, _ok = run_checks(cwd=None)
        rows = [str(e) for e in entries]
        bad = [r for r in rows if "config.json" in r and "not valid JSON" in r]
        ctx.check(f"a WARN row names it, got {bad}", bool(bad) and "[WARN]" in bad[0])
    with _Home('{"model": "or:x/y"}'):
        from halo_harness.doctor import run_checks
        entries, _ok = run_checks(cwd=None)
        ctx.check("no such row for a good file", not [e for e in entries if "not valid JSON" in str(e)])


@test
def test_setup_state_carries_config_error(ctx: Ctx):
    with _Home() as h:
        from halo_harness.studio.setup_state import setup_state
        s = setup_state(h.cwd, h.state_dir)
        ctx.check(f"config_error says it, got {s.get('config_error')!r}", "not valid JSON" in str(s.get("config_error")))
    with _Home('{"model": "or:x/y"}') as h:
        s = setup_state(h.cwd, h.state_dir)
        ctx.check(f"and is empty for a good file, got {s.get('config_error')!r}", s.get("config_error") == "")


@test
def test_a_session_says_it_once_on_stderr(ctx: Ctx):
    with _Home():
        from halo_harness import headless, theme
        theme._PROBLEM_SAID.clear()
        src = Path(headless.__file__).read_text(encoding="utf-8")
        body = src.split("def build_session(", 1)[1].split("\ndef ", 1)[0]
        ctx.check("build_session says it (theme.warn_config_problem)", "warn_config_problem()" in body)
        err = io.StringIO()
        first = theme.warn_config_problem(err)
        second = theme.warn_config_problem(err)
        ctx.check(f"one line, once per process, got {err.getvalue()!r}",
                  first and first == second and err.getvalue().count("not valid JSON") == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
