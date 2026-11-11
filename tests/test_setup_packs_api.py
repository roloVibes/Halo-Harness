"""tests.test_setup_packs_api -- a pack's own Setup blocks through Studio's routes (Halo 3.3.11.0 R3,
studio/setup_packs_api.py, checks/pack.py, packs/setup_state.py) over a scratch home (tests/helpers/
setup_home.py) with the fixture pack setup-blocks; no model call, no request anywhere:

1. the blocks appear only while the pack is enabled (`GET setup/packs`, `GET setup/state`'s `packs`), in the
   manifest's order, a form with its two schema fields and values, a check with its four lines, a note with its text;
   with no pack contributing setup the state's `packs` is [] and the checks are the core ones (3.3.15.0 R5: five on the Auto lineup);
2. a form save writes the pack's settings and marks the block done; a bad value is 422 with the schema's line and a
   key the block does not show 422 too, nothing written;
3. the note is dismissed (done), any block can be skipped, the state file says so;
4. the check runs through the checks job as `pack:<id>:<block>`, green (its two lines, the block done) and red
   (HALO_SETUP_TEST_FAIL=1: its lines and the exit, the block not done); `POST setup/check` takes the key too;
5. nothing private: no environment value, provider key or other pack's setting in any answer or frame.
Run: python -m tests.test_setup_packs_api
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import fixture  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.setup_home import SetupHome  # noqa: E402

test, TESTS = new_registry()
KEY = "pack:setup-blocks:reach"
FAKE_KEY = "fake-provider-value-setupblocks-91c2"  # not key-shaped: the privacy scan reads the tests too
OTHER = "other-pack-setting-value-7f3a"


class _Env(SetupHome):
    """A Setup home with the fixture installed (enabled unless told), the packs registry fresh both ways."""

    def __init__(self, enable: bool = True):
        self.enable = enable

    def __enter__(self):
        super().__enter__()
        from halo_harness.packs import registry
        from halo_harness.packs.discover import find
        from halo_harness.packs.grants import enable
        from halo_harness.packs.install import install
        registry.invalidate()
        ok, lines = install(str(fixture("setup-blocks")), cwd=self.cwd)
        assert ok, lines
        if self.enable:
            assert enable(find("setup-blocks", cwd=self.cwd))[0]
        return self

    def __exit__(self, *exc):
        from halo_harness.packs import registry
        registry.invalidate()
        _forget_job()
        return super().__exit__(*exc)


class _Server:
    def __init__(self):
        self.events, self.events_lock, self.frames = None, threading.Lock(), []
        self.event_taps = [lambda f: self.frames.append(f) if f.get("event") == "setup" else None]


def _call(e, method, path, body=None, server=None):
    from halo_harness.studio.api import Request, dispatch
    return dispatch(Request(method=method, path=path, query={}, body=body or {}, cwd=e.cwd, state_dir=e.state_dir, server=server))


def _wait_summary(server, limit: float = 60.0) -> list:
    """Wait on the job's frames (the summary frame), never on a sleep; the `setup` frames' data."""
    from halo_harness.studio import setup_check_job
    end = time.monotonic() + limit
    while time.monotonic() < end and not any(f["data"].get("key") == "summary" for f in list(server.frames)):
        time.sleep(0.05)
    while setup_check_job.running() and time.monotonic() < end:
        time.sleep(0.05)
    return [f["data"] for f in server.frames]


def _forget_job() -> None:
    from halo_harness.studio import setup_check_job
    end = time.monotonic() + 60
    while setup_check_job.running() and time.monotonic() < end:
        time.sleep(0.05)
    with setup_check_job._lock:
        setup_check_job._state["job"] = None


def _states(e) -> dict:
    from halo_harness.packs.setup_state import read
    return {k: v["state"] for k, v in read("setup-blocks", e.state_dir).items()}


@test
def test_the_blocks_show_only_while_the_pack_is_enabled(ctx: Ctx):
    with _Env(enable=False) as e:
        status, body = _call(e, "GET", "setup/packs")
        _s, state = _call(e, "GET", "setup/state")
        ctx.check(f"disabled: no blocks anywhere, got {status} {body}", status == 200 and body == {"packs": []} and state["packs"] == [])
        ctx.check("the checks are the core ones (3.3.15.0 R5: this home runs Auto, so no guided first run)",
                  [c["key"] for c in state["checks"]] == ["doctor", "catalog", "hello", "steward", "gym"])
        ctx.check("a block of a disabled pack is 404", _call(e, "GET", "setup/packs/setup-blocks/prefs")[0] == 404)
        from halo_harness.packs.discover import find
        from halo_harness.packs.grants import enable
        enable(find("setup-blocks", cwd=e.cwd))
        _s, body = _call(e, "GET", "setup/packs")
        _s, state = _call(e, "GET", "setup/state")
        packs = body["packs"]
        ctx.check(f"enabled: one pack, its three blocks in order, got {packs}", [p["id"] for p in packs] == ["setup-blocks"]
                  and [b["key"] for b in packs[0]["blocks"]] == ["pack:setup-blocks:prefs", KEY, "pack:setup-blocks:about"]
                  and state["packs"] == packs and packs[0]["name"] == "Setup blocks")
        form, check, note = packs[0]["blocks"]
        ctx.check(f"the form: its two fields with the defaults, after model, untouched, got {form}",
                  [f["key"] for f in form["fields"]] == ["style", "depth"] and form["values"] == {"style": "short", "depth": 2}
                  and form["after"] == "model" and form["state"] == "" and form["config_key"] == "packs.settings.setup-blocks"
                  and form["fields"][0]["enum"] == ["short", "long"] and form["help"].startswith("How long"))
        ctx.check(f"the check: its four lines, got {check}", [check[w] for w in ("what", "cost", "time", "writes")]
                  == ["asks the pack's script whether the review service answers", "free", "seconds", "nothing"]
                  and check["help"] == "Three Setup blocks of its own, one of each kind.")
        ctx.check("the note: its markdown", note["text"].startswith("# Before you start") and note["kind"] == "note")
        _s, got = _call(e, "GET", "setup/packs/setup-blocks/prefs")
        ctx.check(f"a form's GET is the pack config shape, its fields only, got {sorted(got)}", sorted(got) ==
                  ["block", "fields", "key", "name", "pack", "problems", "values"] and list(got["values"]) == ["style", "depth"])
        ctx.check("an unknown block is 404", _call(e, "GET", "setup/packs/setup-blocks/nope")[0] == 404)


@test
def test_a_form_save_writes_the_packs_settings_and_marks_it_done(ctx: Ctx):
    with _Env() as e:
        status, body = _call(e, "POST", "setup/packs/setup-blocks/prefs", {"values": {"style": "medium"}})
        ctx.check(f"a value the schema refuses: 422 with its line, nothing written, got {status} {body}", status == 422
                  and body["problems"][0].startswith("packs.settings.setup-blocks.style") and "packs" not in e.config()
                  and _states(e) == {})
        status, body = _call(e, "POST", "setup/packs/setup-blocks/prefs", {"values": {"extra": "x"}})
        ctx.check(f"a key the block does not show: 422, got {status} {body}", status == 422 and "not a field of the Review preferences"
                  in body["error"] and "packs" not in e.config())
        status, body = _call(e, "POST", "setup/packs/setup-blocks/prefs", {"values": {"style": "long", "depth": 3}})
        ctx.check(f"saved: 200, the values, the line, got {status} {body.get('lines')}", status == 200 and body["values"] == {"style": "long", "depth": 3}
                  and body["lines"] == ["packs.settings.setup-blocks: style = long, depth = 3 (saved to config.json)"])
        ctx.check(f"written to the pack's settings only, got {e.config().get('packs')}", e.config()["packs"] == {"settings": {"setup-blocks": {"style": "long", "depth": 3}}})
        ctx.check("the block is done", _states(e) == {"prefs": "done"} and body["block"]["state"] == "done")


@test
def test_the_note_is_dismissed_and_a_block_skipped(ctx: Ctx):
    with _Env() as e:
        status, body = _call(e, "POST", "setup/packs/setup-blocks/about", {})
        ctx.check(f"the note: dismissed, the fresh state, got {status} {body.get('lines')}", status == 200 and body["lines"] == ["setup-blocks: Before you start: read"]
                  and body["packs"][0]["blocks"][2]["state"] == "done")
        status, body = _call(e, "POST", "setup/packs/setup-blocks/reach", {"skip": True})
        ctx.check(f"a skip, got {status} {body.get('lines')}", status == 200 and body["lines"][0].startswith("setup-blocks: Reach the review service: skipped"))
        ctx.check(f"the state file, got {_states(e)}", _states(e) == {"about": "done", "reach": "skipped"})


@test
def test_the_check_runs_through_the_checks_job(ctx: Ctx):
    with _Env() as e:
        server = _Server()
        status, body = _call(e, "POST", "setup/packs/setup-blocks/reach", {}, server)
        data = _wait_summary(server)
        ctx.check(f"202, the job on the pack's key, got {status} {body}", status == 202 and body["job"]["keys"] == [KEY])
        ctx.check(f"running, then done, then the summary, got {[(d['key'], d['state']) for d in data]}",
                  [(d["key"], d["state"]) for d in data] == [(KEY, "running"), (KEY, "done"), ("summary", "finished")])
        ctx.check(f"the running frame says what it does, costs, takes, writes, got {data[0]['lines']}", data[0]["lines"] ==
                  ["asks the pack's script whether the review service answers. Cost: free. Time: seconds. Writes: nothing."]
                  and data[0]["title"] == "Reach the review service")
        ctx.check(f"its two lines, the block done, got {data[1]['lines']} {_states(e)}", data[1]["lines"] ==
                  ["review service: asked", "review service: answered"] and _states(e) == {"reach": "done"})
        from halo_harness.packs.setup_state import mark
        mark("setup-blocks", "reach", "", state_dir=e.state_dir)
        _forget_job()
        server = _Server()
        os.environ["HALO_SETUP_TEST_FAIL"] = "1"
        try:
            status, body = _call(e, "POST", "setup/check", {"checks": [KEY, "nope"]}, server)
            ctx.check(f"an unknown key beside it: 422 naming the offered keys, got {status} {body}", status == 422 and KEY in body["error"])
            status, body = _call(e, "POST", "setup/check", {"checks": [KEY]}, server)
            data = _wait_summary(server)
        finally:
            os.environ.pop("HALO_SETUP_TEST_FAIL", None)
        ctx.check(f"POST setup/check takes the key: red, its lines and the exit, got {status} {data[-2:]}", status == 202
                  and data[1]["state"] == "failed" and data[1]["lines"] == ["review service: asked", "review service: no answer", "exit 1"]
                  and data[-1]["ok"] is False and data[-1]["results"][0]["title"] == "Reach the review service")
        ctx.check("a red check leaves the block waiting", _states(e) == {})


@test
def test_no_block_sees_a_key_an_env_value_or_another_packs_settings(ctx: Ctx):
    from halo_harness.theme import set_config_value
    with _Env() as e:
        os.environ["OPENROUTER_API_KEY"] = FAKE_KEY
        os.environ["HALO_SETUP_TEST_ECHO_ENV"] = "1"
        set_config_value("packs.settings.another-pack", {"token": OTHER})
        server = _Server()
        try:
            answers = [_call(e, "GET", "setup/packs"), _call(e, "GET", "setup/state"), _call(e, "GET", "setup/packs/setup-blocks/prefs"),
                       _call(e, "POST", "setup/packs/setup-blocks/prefs", {"values": {"depth": 4}}),
                       _call(e, "POST", "setup/packs/setup-blocks/about", {})]
            answers.append(_call(e, "POST", "setup/packs/setup-blocks/reach", {}, server))
            data = _wait_summary(server)
            answers.append(_call(e, "GET", "setup/check"))
            from halo_harness.checks.pack import _env
            from halo_harness.packs.discover import find
            env = _env(find("setup-blocks", cwd=e.cwd), "reach", e.cwd)
        finally:
            os.environ.pop("OPENROUTER_API_KEY", None)
            os.environ.pop("HALO_SETUP_TEST_ECHO_ENV", None)
        text = json.dumps([a[1] for a in answers]) + json.dumps(data)
        ctx.check("every answer came back", all(a[0] in (200, 202) for a in answers) and data[-1]["key"] == "summary")
        ctx.check("the fake provider key is in no answer and no frame", FAKE_KEY not in text)
        ctx.check("another pack's setting is in no answer", OTHER not in text)
        ctx.check(f"the check's environment is a pack hook's: no provider key, its own names, got {sorted(k for k in env if 'HALO_' in k)}",
                  "OPENROUTER_API_KEY" not in env and env["HALO_PACK_ID"] == "setup-blocks" and env["HALO_SETUP_BLOCK"] == "reach"
                  and env["CLAUDE_PLUGIN_ROOT"] == str(find("setup-blocks", cwd=e.cwd).root))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
