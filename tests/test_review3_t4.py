"""tests.test_review3_t4 -- pins for the 3.0.2.0 review fix pass, round T-tui
(split from _t and _t2 for the 250-line cap):

  * item 144 Esc interrupts a turn the remote bridge started
  * item 145 `!cmd` keeps the pending image chips and leaves their labels out
  * item 148 the lineup editor says when Instances is not a whole number
  * item 149 the form editors refuse a template/org file that does not load

Run: python -m tests.test_review3_t4
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import base64
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from halo_harness import events as ev  # noqa: E402

test, TESTS = new_registry()

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


def _app():
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    fake = FakeController(turns=[])
    return fake, BridgeApp(fake, cwd=str(REPO_DIR))


def _text(widget) -> str:
    return str(widget.renderable) if hasattr(widget, "renderable") else str(widget.render())


def _host():
    from textual.app import App
    return App()


@test
def test_item144_esc_interrupts_a_turn_started_outside_the_prompt(ctx: Ctx):
    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            app._local_events.put(ev.message_start(turn=1))
            await pilot.pause(0.3)
            pi = app.prompt_input
            pi.text = "a steer draft"
            await pilot.press("escape")
            await pilot.pause(0.1)
            ctx.check(f"Esc interrupted the turn, got {fake.interrupts}", fake.interrupts == 1)
            ctx.check(f"the draft is intact, got {pi.text!r}", pi.text == "a steer draft")
            app._local_events.put(ev.turn_done(turn=1))
            await pilot.pause(0.3)
            await pilot.press("escape")
            await pilot.pause(0.1)
            ctx.check(f"after the turn Esc clears the draft, got {pi.text!r}", pi.text == "" and fake.interrupts == 1)
    asyncio.run(body())


@test
def test_item145_bang_command_keeps_image_chips_and_drops_their_labels(ctx: Ctx):
    from halo_harness.tui.widgets.input import PromptInput

    async def body():
        fake, app = _app()
        png = Path(tempfile.mkdtemp(prefix="r3t-img-")) / "a.png"
        png.write_bytes(PNG_1X1)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            pi = app.prompt_input
            pi.add_image_chip(path=png, width=1, height=1, media_type="image/png")
            label = pi.images[0]["label"]
            pi.text = "!ls " + label
            await app.on_prompt_input_submitted(PromptInput.Submitted(pi.text, pi.pasted))
            await pilot.pause(0.4)
            ctx.check(f"the image is still pending, got {pi.images}", len(pi.images) == 1)
            ctx.check(f"its chip is back in the box, got {pi.text!r}", pi.text == label)
            ctx.check(f"the shell got only the command, got {fake.inline_shell_runs}", fake.inline_shell_runs == ["ls"])
    asyncio.run(body())


@test
def test_item148_lineup_save_reports_bad_instances_and_an_empty_role(ctx: Ctx):
    """3.1.1.0 R3: lineups are edited in Studio; its save (`PUT /api/lineup/<name>`) names a bad
    Instances count and an empty Role instead of dropping either, and writes nothing."""
    from halo_harness.studio.api import Request, dispatch
    state = Path(tempfile.mkdtemp(prefix="t4-148-")) / ".halo"
    state.mkdir(parents=True)
    raw = {"agents": [{"role": "main", "agent": "coder"}, {"role": "", "agent": "reviewer", "instances": "two"}]}
    status, body = dispatch(Request(method="PUT", path="lineup/t", query={}, body={"raw": raw}, cwd=state.parent,
                                    state_dir=state))
    problems = body.get("problems") or []
    ctx.check(f"422 naming the count and the role, got {status} {problems}", status == 422
              and any('"instances" must be a positive integer' in p for p in problems)
              and any('"role" is required' in p for p in problems))
    ctx.check("nothing was written", not (state / "teams" / "t.yaml").exists())


@test
def test_item149_form_editors_refuse_an_unloadable_file(ctx: Ctx):
    from halo_harness.orgs import orgs_dir
    from halo_harness.roles import role_templates_dir
    from halo_harness.tui import slash
    from halo_harness.tui.dialogs.init_wizard import OrgsStep

    notes, opened = [], []
    fake = SimpleNamespace(notify=lambda text, **kw: notes.append(text),
                           call_from_thread=lambda fn, *a, **kw: fn(*a, **kw),
                           controller=SimpleNamespace(list_models=lambda: []))
    real_roles, real_org = slash._open_roles_editor, slash._open_org_editor
    slash._open_roles_editor = lambda *a: opened.append("roles")
    slash._open_org_editor = lambda *a: opened.append("org")
    role_file = role_templates_dir() / "mine.json"
    org_file = orgs_dir() / "custom.json"
    try:
        for path in (role_file, org_file):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"roles": {"main": "or:a/b", "revi', encoding="utf-8")
        slash._roles_edit_form_worker(fake, "mine")
        slash._org_edit_form_worker(fake, "custom")
        OrgsStep._editor_worker(SimpleNamespace(app=fake, _open_editor_screen=lambda *a: opened.append("wizard"),
                                                _controller_models=lambda: []), "custom")
        ctx.check(f"no editor opened, got {opened}", opened == [])
        ctx.check(f"three refusals naming the file, got {notes}", len(notes) == 3 and all("cannot be loaded" in n for n in notes))
        ctx.check("both files are untouched", role_file.read_text(encoding="utf-8").endswith('"revi')
                  and org_file.read_text(encoding="utf-8").endswith('"revi'))
        role_file.unlink()
        slash._roles_edit_form_worker(fake, "mine")
        ctx.check(f"a missing template still opens a fresh form, got {opened}", opened == ["roles"])
    finally:
        slash._open_roles_editor, slash._open_org_editor = real_roles, real_org
        for path in (role_file, org_file):
            if path.exists():
                path.unlink()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
