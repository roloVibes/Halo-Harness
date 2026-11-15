"""tests.test_studio_edit_target -- `halo studio --edit` without a browser (Halo
3.1.1.0 R3; 3.6.0.0 R5: Studio is the one editor of agents, workflows and maps).

1. an edit target (agent:<name>, workflow:<name>, map:<name>, the old bio: / lineup: / team, a bare name) and the URL
   it rides in: `?mode=agents&view=crew&edit=agent:coder#t=<token>`;
2. a Studio running for this home is focused, not started again: `POST
   /api/focus` puts a `focus` frame on the live feed of every open page;
   with no page open the browser opens the URL, and with no browser the URL
   is the answer; `--no-open` only prints it;
3. no Studio running: one is started in the background with `--edit`;
4. `halo studio --edit`, `halo agents edit` and `GET /api/field-help` (field_help.py's lines).
The DOM half (the bio form open on that bio, a focused page) is
tests/test_studio_edit_route.py (headless Chrome).
Run: python -m tests.test_studio_edit_target
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@contextlib.contextmanager
def _home():
    """A fresh home for one test, a running Studio over it (studio.json written), restored after."""
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    home = Path(tempfile.mkdtemp(prefix="halo-edit-target-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    from halo_harness.providers.config import default_state_dir
    from halo_harness.privateio import write_private_atomic
    from halo_harness.studio.server import start_server, studio_info_path
    state = Path(default_state_dir())
    state.mkdir(parents=True, exist_ok=True)
    proj = home / "project"
    proj.mkdir()
    srv = start_server(port=0, cwd=proj, state_dir=state)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    write_private_atomic(studio_info_path(state), json.dumps({"pid": 0, "port": srv.server_address[1], "token": srv.token, "owner_salt": srv.owner_salt}))
    try:
        yield SimpleNamespace(home=home, state=state, proj=proj, srv=srv)
    finally:
        srv.shutdown()
        srv.server_close()
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(home, ignore_errors=True)


@contextlib.contextmanager
def _stub(obj, name, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


def _out(fn, argv) -> "tuple[int, str]":
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = fn(argv)
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else 1
    return rc, buf.getvalue()


@test
def test_the_edit_target_and_its_url(ctx: Ctx):
    from halo_harness.studio import launch
    from halo_harness.studio.edit_target import parse, resolve
    from halo_harness.studio.server import url_for
    t, _ = parse("agent:coder")
    ctx.check(f"agent:coder opens Agents (1 · Agents), got {t}", t is not None and (t.kind, t.name, t.mode, t.view, t.text) == ("agent", "coder", "agents", "crew", "agent:coder"))
    t, _ = parse("workflow:code")
    ctx.check("workflow:<name> opens 2 · Workflows", t is not None and t.query() == "?mode=agents&view=workflows&edit=workflow:code")
    t, _ = parse("map:starter")
    ctx.check("map:<name> opens 3 · Map", t is not None and t.query() == "?mode=agents&view=map&edit=map:starter")
    t, _ = parse("bio:coder")
    ctx.check("an old bio: target opens 1 · Agents, marked old", t is not None and t.view == "crew" and t.old)
    t, _ = parse("lineup:halo-dev-cycle")
    ctx.check("an old lineup: target opens the Map, marked old", t is not None and t.query() == "?mode=agents&view=map&edit=lineup:halo-dev-cycle" and t.old)
    t, _ = parse("team")
    ctx.check("team opens the Map (3.6.0.0 R5)", t is not None and t.mode == "agents" and t.query() == "?mode=agents&view=map&edit=team")
    for bad in ("", "coder", "agent:", "agent:../etc", "org:x", "lineup:a/b"):
        got, why = parse(bad)
        ctx.check(f"{bad!r} is not a target, with a reason", got is None and why)
    fake = SimpleNamespace(server_address=("127.0.0.1", 4321), token="tok")
    ctx.check("url_for: the target in the query, the token in the fragment",
              url_for(fake, None, "agent:coder") == "http://127.0.0.1:4321/?mode=agents&view=crew&edit=agent:coder#t=tok")
    ctx.check("url_for without an edit is unchanged", url_for(fake, "agents") == "http://127.0.0.1:4321/?mode=agents#t=tok")
    ctx.check("the running Studio's URL carries it too",
              launch.url_from_info({"port": 99, "token": "x"}, None, "team") == "http://127.0.0.1:99/?mode=agents&view=map&edit=team#t=x")
    with _home() as h:
        ctx.check("a bare agent name resolves to agent:", resolve("coder", state_dir=h.state)[0].text == "agent:coder")
        ctx.check("a bare workflow name resolves to workflow:", resolve("code", state_dir=h.state)[0].text == "workflow:code")
        ctx.check("a bare map name resolves to map:", resolve("ship-it", state_dir=h.state)[0].text == "map:ship-it")
        ctx.check("an unknown bare name says so", resolve("no-such-thing", state_dir=h.state)[0] is None)


@test
def test_a_running_studio_is_focused_not_started_again(ctx: Ctx):
    from halo_harness.studio import launch
    from halo_harness.studio.edit_open import describe, open_edit
    from halo_harness.studio.edit_target import parse
    from halo_harness.studio.events import bridge_for
    opened, started = [], []
    with _home() as h, _stub(launch, "_open", lambda url: opened.append(url) or True), \
            _stub(launch, "launch_detached", lambda *a, **k: started.append(k) or "x"):
        page = bridge_for(h.srv).subscribe("all")
        page.get(0.5)  # the sessions frame every new page gets first
        r = open_edit(parse("map:starter")[0], cwd=h.proj, state_dir=h.state)
        frame = page.get(2)
        ctx.check(f"one open page: focused, got {r}", r["how"] == "focused" and r["pages"] == 1 and not opened and not started)
        ctx.check(f"the page got a focus frame naming the target, got {frame}",
                  frame and frame.get("event") == "focus" and (frame.get("data") or {}).get("edit") == "map:starter")
        ctx.check("the URL names the target", "?mode=agents&view=map&edit=map:starter#t=" in r["url"])
        ctx.check(f"the line says it opened in the open page, got {describe(r)!r}", describe(r).startswith("Opened map:starter in the Studio page"))
        bridge_for(h.srv).unsubscribe(page)
        r = open_edit(parse("agent:coder")[0], cwd=h.proj, state_dir=h.state)
        ctx.check(f"no page open: the browser opens the URL, got {r} {opened}", r["how"] == "opened" and opened == [r["url"]])
        with _stub(launch, "_open", lambda url: False):
            r = open_edit(parse("team")[0], cwd=h.proj, state_dir=h.state)
        ctx.check(f"no browser: the URL is the answer, got {r}", r["how"] == "printed" and describe(r).splitlines()[-1].startswith("Studio is at http") and "no longer read" in describe(r))
        r = open_edit(parse("agent:coder")[0], cwd=h.proj, state_dir=h.state, open_browser=False)
        ctx.check(f"--no-open only prints it, got {r}", r["how"] == "printed" and len(opened) == 1)
        status, body = launch.api_call(h.state, "POST", "focus", {"edit": "nope"})
        ctx.check(f"POST /api/focus refuses a non-target with its reason, got {status} {body}", status == 422 and "edit target" in body.get("error", ""))
        status, body = launch.api_call(h.state, "GET", "focus")
        ctx.check(f"GET /api/focus is 405, got {status}", status == 405)
        from halo_harness.studio import server as S  # the TUI's /studio: this process's own Studio, no studio.json
        (h.state / "studio.json").unlink()
        S._BACKGROUND["server"] = h.srv
        try:
            page = bridge_for(h.srv).subscribe("all")
            r = open_edit(parse("agent:coder")[0], cwd=h.proj, state_dir=h.state)
            ctx.check(f"the session's own Studio is focused too, got {r}", r["how"] == "focused" and r["pages"] == 1
                      and f":{h.srv.server_address[1]}/?mode=agents&view=crew&edit=agent:coder" in r["url"])
            bridge_for(h.srv).unsubscribe(page)
        finally:
            S._BACKGROUND.pop("server", None)
    ctx.check("nothing was started while a Studio ran", not started)


@test
def test_no_studio_running_starts_one_with_the_edit(ctx: Ctx):
    from halo_harness.studio import launch
    from halo_harness.studio.edit_open import open_edit
    from halo_harness.studio.edit_target import parse
    calls = []
    home = Path(tempfile.mkdtemp(prefix="halo-edit-none-"))
    try:
        with _stub(launch, "launch_detached", lambda mode, **k: calls.append((mode, k)) or "http://127.0.0.1:1/?mode=agents&edit=agent:coder#t=t"):
            r = open_edit(parse("agent:coder")[0], cwd=home, state_dir=home / ".halo")
        ctx.check(f"started, with --edit, got {r} {calls}", r["how"] == "started" and calls and calls[0][0] == "agents"
                  and calls[0][1].get("edit") == "agent:coder" and calls[0][1].get("open_browser") is True)
        with _stub(launch, "launch_detached", lambda mode, **k: ""):
            r = open_edit(parse("team")[0], cwd=home, state_dir=home / ".halo")
        ctx.check(f"a Studio that does not start says so, got {r}", r["how"] == "failed")
        argv = []

        class _P:
            stdout = io.StringIO("Halo Studio is at http://127.0.0.1:5/?mode=roles&edit=lineup:x#t=t\n")

            def poll(self):
                return None
        with _stub(launch.subprocess, "Popen", lambda a, **k: argv.append(a) or _P()):
            url = launch.launch_detached("roles", cwd=home, state_dir=home / ".halo", open_browser=False, edit="lineup:x", timeout=3)
        ctx.check(f"the background Studio is spawned with --edit, got {argv}", argv and "--edit" in argv[0]
                  and argv[0][argv[0].index("--edit") + 1] == "lineup:x" and "--mode" not in argv[0] and "--no-open" in argv[0])
        ctx.check(f"and its printed URL comes back, got {url!r}", url.endswith("edit=lineup:x#t=t"))
    finally:
        shutil.rmtree(home, ignore_errors=True)


@test
def test_the_cli_verbs_open_studio_on_the_thing(ctx: Ctx):
    from halo_harness import agents_cli, maps_cli, workflows_cli
    from halo_harness.studio import launch
    from halo_harness.studio.server import cmd_studio
    rc, text = _out(cmd_studio, ["--edit", "nope"])
    ctx.check(f"halo studio --edit nope: exit 2 with the reason, got {rc} {text!r}", rc == 2 and "agent:<name>" in text)
    with _home() as h, _stub(launch, "_open", lambda url: False):
        rc, text = _out(cmd_studio, ["--edit", "agent:coder", "--no-open"])
        ctx.check(f"halo studio --edit ... --no-open on a running Studio prints the URL, got {rc} {text!r}",
                  rc == 0 and "?mode=agents&view=crew&edit=agent:coder#t=" in text and text.startswith("Studio is at"))
        rc, text = _out(cmd_studio, ["--edit", "bio:coder", "--no-open"])
        ctx.check(f"an old bio: target says the old files' line, then the URL, got {rc} {text!r}",
                  rc == 0 and "no longer read" in text and "view=crew&edit=bio:coder" in text)
        saved = os.environ.pop("EDITOR", None), os.environ.pop("VISUAL", None)
        try:
            for mod, verb, name, want in ((agents_cli.cmd_agents, "agents", "coder", "edit=agent:coder"),
                                          (workflows_cli.cmd_workflows, "workflows", "code", "edit=workflow:code"),
                                          (maps_cli.cmd_maps, "maps", "starter", "edit=map:starter")):
                rc, text = _out(mod, ["edit", name])
                ctx.check(f"halo {verb} edit {name} on a starter (no editor): Studio on it, got {rc} {text!r}",
                          rc == 0 and "a starter (read-only)" in text and want in text)
        finally:
            for k, v in zip(("EDITOR", "VISUAL"), saved):
                if v is not None:
                    os.environ[k] = v


@test
def test_field_help_is_served_from_one_source(ctx: Ctx):
    from halo_harness import field_help
    from halo_harness.studio import launch
    with _home() as h:
        status, body = launch.api_call(h.state, "GET", "field-help")
        ctx.check(f"GET /api/field-help is 200, got {status}", status == 200)
        ctx.check("it is field_help.py's lines, every group", body == field_help.as_json()
                  and set(body) == {"identity", "bio", "lineup_sections", "lineup_fields", "assignment", "model_select", "pack", "lineup_defaults"})
        ctx.check("3.1.4.0 R4: every label of the model select has its line",  # routes/shared/ModelSelect.tsx reads them
                  all(body["model_select"].get(k) for k in ("runs_on", "card", "main", "bio", "orchestra", "design", "team", "more", "test", "refresh")))
        ctx.check("3.1.6.0 R1: every tier control on the canvas has its line",  # CanvasBar, TierBox, TierMenu read them
                  all(body["lineup_fields"].get(f"tiers.{k}") for k in ("add", "rename", "menu", "model", "trigger", "max_parallel", "delete")))
        status, _ = launch.api_call(h.state, "POST", "field-help", {})
        ctx.check(f"POST is 405, got {status}", status == 405)
    from halo_harness.teams_yaml import TOP_SECTIONS
    ctx.check("every lineup section has its line", all(field_help.LINEUP_SECTIONS.get(s) for s in TOP_SECTIONS))
    bundle = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "static" / "dist" / "studio.js"
    if bundle.is_file():
        js = bundle.read_text(encoding="utf-8", errors="replace")
        ctx.check("the bundle carries no copy of the lines", field_help.BIO["models.preference"] not in js
                  and field_help.LINEUP_SECTIONS["tiers"] not in js)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
