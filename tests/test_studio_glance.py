"""tests.test_studio_glance -- the glance's doors and their guard (Halo 3.4.1.0 R4 "Time"; studio/glance_door.py,
studio/owner_proof.py, docs/STUDIO-live.md "The glance"), over a real Studio and a fake session behind its real control
socket (tests/helpers/glance_rig.py); no Chrome, no model call:

1. every route the glance adds or reuses (GET glance/door, fleet, fleet/attention, fleet/caps, fleet/conflicts,
   fleet/costs, settings/values, settings/catalog, an agent's tail; POST fleet/attention/answer; /api/events) refuses a missing token (401; the feed
   403), a wrong token (the same) and a cross-origin request with the right token (403 "foreign origin");
2. an answer -- from Attention or the glance -- needs the owner proof as well: the token alone is 403 and the card
   still waits; with the proof the card is answered allow;
3. the page itself: `/?mode=glance` answers a navigation with the owner salt, a cross-origin fetch with neither the salt
   nor a CORS header, and a Host that is not this loopback address with 403;
4. GET glance/door: this machine's address; no SSH server: this-machine-only, said plainly, no code; an SSH server
   answering: the phone's steps and a code that reads back as the address with its token;
5. `halo studio --mode glance`: the word opens `?mode=glance` (a page, not a section), the terminal says the phone's
   line; nothing in the door binds or listens;
6. `studio.alerts` is a Settings -> Studio row (none by default, browser the one channel; any other word refused), the
   browser is asked only from the Alerts block's click, and a second channel is one entry of CHANNELS.
Run: python -m tests.test_studio_glance
"""
from __future__ import annotations

import json
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.owner_rig import fetch  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
EVIL = "http://evil.example"


def _rig():
    from tests.helpers.glance_rig import GlanceRig
    return GlanceRig()


def _base(rig) -> str:
    return f"http://127.0.0.1:{rig.server.server_address[1]}"


def _call(rig, method: str, path: str, body=None, *, token: "str | None" = "", owner: bool = True, origin: str = ""):
    from halo_harness.studio.owner_proof import HEADER, header_for
    heads = {}
    tok = rig.server.token if token == "" else token
    if tok:
        heads["Authorization"] = "Bearer " + tok
    if owner:
        heads[HEADER] = header_for(rig.server)
    if origin:
        heads["Origin"] = origin
    data = json.dumps(body).encode() if body is not None else (b"{}" if method == "POST" else None)
    status, _h, raw = fetch(f"{_base(rig)}/api/{path}", method=method, data=data, headers=heads)
    try:
        return status, json.loads(raw.decode("utf-8") or "{}")
    except ValueError:
        return status, {"raw": raw[:200]}


def _row(rig, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, got = _call(rig, "GET", "fleet/attention")
        rows = [r for r in got.get("rows") or [] if r.get("kind") == "permission"] if status == 200 else []
        if rows:
            return rows[0]
        time.sleep(0.2)
    return {}


@test
def test_every_glance_route_refuses_without_the_token_or_from_another_origin(ctx: Ctx):
    with _rig() as rig:
        routes = [("GET", "glance/door"), ("GET", "fleet"), ("GET", "fleet/attention"), ("GET", "fleet/caps"),
                  ("GET", "fleet/conflicts"), ("GET", "fleet/costs"),
                  ("GET", "settings/values"), ("GET", "settings/catalog"), ("GET", f"sessions/{rig.sid}/agents/main/tail?n=5"),
                  ("POST", "fleet/attention/answer")]
        for method, path in routes:
            ctx.check(f"{method} {path}: no token -> 401", _call(rig, method, path, token=None)[0] == 401)
            ctx.check(f"{method} {path}: a wrong token -> 401", _call(rig, method, path, token="not-the-token")[0] == 401)
            status, got = _call(rig, method, path, origin=EVIL)
            ctx.check(f"{method} {path}: another origin, the right token -> 403 foreign origin, got {status} {got}",
                      status == 403 and got.get("error") == "foreign origin")
        events = f"{_base(rig)}/api/events?sessions=all"
        ctx.check("the feed: no token -> 403", fetch(events)[0] == 403)
        ctx.check("the feed: a wrong token -> 403", fetch(events + "&t=not-the-token")[0] == 403)
        ctx.check("the feed: another origin -> 403", fetch(f"{events}&t={rig.server.token}", headers={"Origin": EVIL})[0] == 403)
        ctx.check("with the token they answer", _call(rig, "GET", "glance/door")[0] == 200 and _call(rig, "GET", "fleet/caps")[0] == 200)


@test
def test_an_answer_needs_the_owners_proof(ctx: Ctx):
    from halo_harness.studio.owner_proof import NEEDS_OWNER, needs_owner
    ctx.check("fleet/attention/answer is an owner route", needs_owner("POST", "fleet/attention/answer")
              and not needs_owner("GET", "fleet/attention"))
    with _rig() as rig:
        rig.ask("ask")
        row = _row(rig)
        ctx.check(f"the card is a row of the queue: {row.get('id')}", str(row.get("id", "")).endswith(":perm_1"))
        status, got = _call(rig, "POST", "fleet/attention/answer", {"id": row.get("id"), "key": "a"}, owner=False)
        ctx.check(f"the token alone: 403 naming the owner's page, got {status} {got}", status == 403 and got.get("error") == NEEDS_OWNER)
        ctx.check("and the card still waits", rig.decision("perm_1") is None)
        status, got = _call(rig, "POST", "fleet/attention/answer", {"id": row.get("id"), "key": "a"})
        deadline = time.time() + 20
        while rig.decision("perm_1") is None and time.time() < deadline:
            time.sleep(0.1)
        d = rig.decision("perm_1")
        ctx.check(f"with the proof: answered allow, got {status} {got} {d}", status == 200 and getattr(d, "action", None) == "allow")


@test
def test_the_page_carries_the_salt_to_a_navigation_only(ctx: Ctx):
    with _rig() as rig:
        page = f"{_base(rig)}/?mode=glance"
        nav = {"Sec-Fetch-Site": "none", "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate"}  # 3.4.1.2: one the person made
        status, heads, body = fetch(page, headers=nav)
        ctx.check(f"a navigation: the shell's page with the salt, got {status}", status == 200 and b"data-owner-salt" in body
                  and "frame-ancestors 'self'" in heads.get("Content-Security-Policy", ""))
        status, heads, body = fetch(page, headers={"Origin": EVIL, "Sec-Fetch-Dest": "empty"})
        ctx.check(f"another origin's fetch: no salt, no CORS header, got {status}", b"data-owner-salt" not in body
                  and not any(k.lower() == "access-control-allow-origin" for k in heads))
        ctx.check("a Host that is not this loopback address: 403", fetch(page, headers={"Host": f"192.0.2.7:{rig.server.server_address[1]}"})[0] == 403)


@test
def test_the_door_says_where_the_glance_is(ctx: Ctx):
    from halo_harness.studio import glance_door
    from tests.helpers.qr_decode import decode
    keep = glance_door.SSH_PORT
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    glance_door.SSH_PORT = closed.getsockname()[1]
    closed.close()
    try:
        with _rig() as rig:
            status, got = _call(rig, "GET", "glance/door")
            port = rig.server.server_address[1]
            ctx.check(f"this machine's address, got {got.get('here')}", status == 200 and got.get("here") == f"http://127.0.0.1:{port}/?mode=glance")
            ctx.check(f"no SSH server: this-machine-only, said plainly, no code: {got.get('line')!r}",
                      got.get("ssh") is False and "this-machine-only" in got.get("line", "") and got.get("qr") == [] and got.get("steps") == [])
            ssh = socket.socket()
            ssh.bind(("127.0.0.1", 0))
            ssh.listen(4)
            glance_door.SSH_PORT = ssh.getsockname()[1]
            try:
                got = _call(rig, "GET", "glance/door")[1]
            finally:
                ssh.close()
            ctx.check(f"an SSH server: the phone's steps: {got.get('steps')}", got.get("ssh") is True and len(got.get("steps") or []) == 3
                      and f"forward the phone's port {port} to 127.0.0.1:{port}" in got["steps"][0] and got.get("lan"))
            matrix = [[int(ch) for ch in row] for row in got.get("qr") or []]
            ctx.check("its code reads back as the address with its token",
                      bool(matrix) and decode(matrix) == f"http://127.0.0.1:{port}/?mode=glance#t={rig.server.token}")
    finally:
        glance_door.SSH_PORT = keep


@test
def test_halo_studio_mode_glance(ctx: Ctx):
    from halo_harness.studio import glance_door, launch, modes
    from halo_harness.studio.server import STUDIO_MODES, STUDIO_SECTIONS
    ctx.check("glance is a page word, not a section", modes.check("glance") == ("glance", "") and "glance" not in STUDIO_MODES
              and "glance" not in STUDIO_SECTIONS)
    ctx.check("its URL is ?mode=glance", launch._query("glance", None) == "?mode=glance")
    keep = glance_door.SSH_PORT
    glance_door.SSH_PORT = 1  # nothing answers there
    try:
        line = glance_door.over_ssh(48761, "glance")
    finally:
        glance_door.SSH_PORT = keep
    ctx.check(f"the terminal says the phone's line: {line!r}", line.startswith("Over SSH: ssh -L 48761:127.0.0.1:48761")
              and "The glance: This page is this-machine-only" in line and glance_door.note(48761, "session") == "")
    src = (REPO / "halo_harness" / "studio" / "glance_door.py").read_text(encoding="utf-8")
    ctx.check("the door binds and listens on nothing", not any(w in src for w in (".bind(", ".listen(", "serve_forever", "HTTPServer")))


@test
def test_the_alert_setting_and_its_channels(ctx: Ctx):
    from halo_harness.settings_catalog import rows
    row = next((r for r in rows() if r.key == "studio.alerts"), None)
    ctx.check(f"a Settings -> Studio row, none by default: {row}", row is not None and row.group == "studio" and row.kind == "enum"
              and row.default == "none" and row.choices == ("none", "browser") and row.effect == "now")
    with _rig() as rig:
        status, got = _call(rig, "POST", "settings/set", {"key": "studio.alerts", "value": "signal"})
        ctx.check(f"a channel this build does not have is refused, got {status}", status == 422)
        ctx.check("browser is taken", _call(rig, "POST", "settings/set", {"key": "studio.alerts", "value": "browser"})[0] == 200)
    alerts = (UI / "lib" / "alerts.ts").read_text(encoding="utf-8")
    ctx.check("the channels are one table", "export const CHANNELS: Record<string, Channel> = { browser };" in alerts)
    asking = [p.relative_to(UI).as_posix() for p in UI.rglob("*.ts*") if "requestPermission" in p.read_text(encoding="utf-8")]
    ctx.check(f"only the browser channel's ask calls requestPermission: {asking}", asking == ["lib/alerts.ts"])
    callers = [p.relative_to(UI).as_posix() for p in UI.rglob("*.tsx") if ".ask()" in p.read_text(encoding="utf-8")]
    ctx.check(f"and only the Alerts block's click calls ask: {callers}", callers == ["routes/settings/AlertsBlock.tsx"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio glance"))
