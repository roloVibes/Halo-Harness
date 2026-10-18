"""tests.test_fleet_cli -- Halo 3.0.5.0 "Fleet" round R2: `halo fleet ...` as
people run it, in child processes with their own homes (A runs the hub in
this process, `halo fleet pair | members | kick` run in home A, `halo fleet
join | status | leave | --once` in home B), the standalone `halo fleet
serve`, and terminal parity: the table rows, `/fleet` as text and the
FleetTable dialog's keys (steer, stop asks first, pause).
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fleet_hub_rig import HubRig, cli, wait_for
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _json(out: str) -> dict:
    try:
        return json.loads(out)
    except ValueError:
        return {}


@test
def test_pair_join_members_status_kick_leave_from_the_command_line(ctx: Ctx):
    with HubRig() as rig:
        rc, out, err = cli(rig.root_a, "pair", "--ttl", "5m", "--json")
        pair = _json(out)
        ctx.check(f"`halo fleet pair --json` in home A makes a code for the running hub, got {rc} {err[-200:]}",
                  rc == 0 and len(pair.get("code", "").split()) == 6 and pair.get("url") == rig.url()
                  and pair.get("hub_running") is True and pair["qr"].startswith("halo-fleet://join?"))
        rc, out, err = cli(rig.root_b, "join", pair.get("url", ""), "--code", pair.get("code", ""), "--share", "status",
                           "--json")
        joined = _json(out)
        ctx.check(f"`halo fleet join` in home B joins, got {rc} {err[-200:]}", rc == 0 and joined.get("ok")
                  and joined["hub"]["hub_id"] == rig.a_id and joined["share"] == "status"
                  and joined["allow_control"] == "ask")
        rc, out, err = cli(rig.root_b, "join", pair.get("url", ""), "--code", pair.get("code", ""))
        ctx.check(f"the same code again is refused (exit 1, the reason on stderr), got {rc}", rc == 1
                  and "not accepted" in err)
        _controller, act = rig.session()
        wait_for(lambda: rig.member_session_online(act.session_id))
        rows = []
        for _ in range(4):  # a loaded Windows runner can read B offline for one hub tick while its relay re-attaches
            rc, out, err = cli(rig.root_a, "members", "--json")
            rows = _json(out).get("members") or []
            if rc == 0 and rows and rows[0].get("online") is True:
                break
            time.sleep(2)
        ctx.check(f"`halo fleet members` lists B, online, and never a key, got {rows}", rc == 0 and len(rows) == 1
                  and rows[0]["name"] == "bob@member" and rows[0]["online"] is True and "key_hex" not in rows[0])
        rc, out, err = cli(rig.root_b, "status", "--json")
        st = _json(out)
        hub = (st.get("hubs") or [{}])[0]
        ctx.check(f"`halo fleet status` in B: the hub answers and sees B online, got {hub}", rc == 0
                  and hub.get("reachable") is True and hub.get("online") is True and hub.get("share") == "status")
        rc, out, err = cli(rig.root_a, "status", "--json")
        ctx.check("`halo fleet status` in A shows the hub it serves", rc == 0
                  and (_json(out).get("serving") or {}).get("members") == 1)
        rc, out, err = cli(rig.root_a, "kick", "nobody-here")
        ctx.check("kicking an unknown name says so (exit 1)", rc == 1 and "no member" in err)
        rc, out, err = cli(rig.root_a, "kick", "bob@member", "--json")
        ctx.check(f"`halo fleet kick bob@member` removes B, got {rc}", rc == 0 and _json(out)["kicked"]["id"] == rig.b_id)
        ctx.check("B's relay hears it", wait_for(lambda: getattr(rig.relay(), "state", None) == "kicked", 8))
        rc, out, err = cli(rig.root_b, "leave", "--json")
        ctx.check(f"`halo fleet leave` in B forgets the hub, got {rc} {out}", rc == 0 and len(_json(out).get("left") or []) == 1)
        from halo_harness.fleet import store
        ctx.check("B's fleet.json lists no hub now and its key is gone", store.hubs() == []
                  and not any((Path(rig.root_b) / ".halo" / "fleet" / "keys").glob("*.key")))
        rc, out, err = cli(rig.root_b, "--once")
        ctx.check(f"`halo fleet --once` prints the table with B's session, got {rc} {out[:300]}", rc == 0
                  and "HARNESS" in out and act.session_id[:8] in out and "(you)" in out)
        rc, out, _ = cli(rig.root_b, "--help")
        ctx.check("`halo fleet --help` prints the usage", rc == 0 and "halo fleet serve" in out and "halo fleet kick" in out)
        ctx.check("an unknown verb is a usage error (2)", cli(rig.root_b, "explode")[0] == 2)


@test
def test_halo_fleet_serve_runs_a_standalone_hub(ctx: Ctx):
    import os
    import tempfile
    root = tempfile.mkdtemp(prefix="fleet-serve-")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("BRIDGE_", "HALO_", "OPENROUTER_", "DATABRICKS_",
                                                                      "ANTHROPIC_", "OPENAI_", "ROLO_CLAUDE_", "TYPESAFE_"))}
    env.update(BRIDGE_TEST_HOME=root, BRIDGE_TEST_NO_BACKGROUND_NET="1", PYTHONPATH=str(Path(__file__).resolve().parent.parent))
    proc = subprocess.Popen([sys.executable, "-m", "halo_harness", "fleet", "serve", "--bind", "127.0.0.1", "--port", "0",
                             "--no-tls", "--name", "solo", "--json"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL, env=env, encoding="utf-8", errors="replace")
    try:
        lines = []
        end = time.monotonic() + 30
        while time.monotonic() < end and proc.poll() is None:
            line = proc.stdout.readline()
            lines.append(line)
            if line.strip().endswith("}"):
                break
        info = _json("".join(lines))
        ctx.check(f"the hub starts and says where, got {info}", info.get("ok") and info.get("tls") is False
                  and info.get("name") == "solo" and info.get("url", "").startswith("http://127.0.0.1:"))
        rc, out, err = cli(root, "pair", "--json")
        ctx.check(f"`halo fleet pair` finds the running hub, got {rc} {err[-200:]}", rc == 0 and _json(out).get("url") == info.get("url"))
        rc, out, err = cli(root, "status", "--json")
        serving = _json(out).get("serving") or {}
        ctx.check(f"`halo fleet status` reads its view over loopback, got {serving}", rc == 0 and serving.get("name") == "solo"
                  and serving.get("members") == 0 and serving.get("pair_code_active") is True)
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _view() -> dict:
    return {"harnesses": [
        {"id": "a" * 16, "name": "alice@hub", "local": True, "online": True, "sessions": [
            {"session_id": "s1" + "0" * 30, "status": "busy", "title": "fix the tests", "agents": [
                {"agent_id": "main", "parent": None, "name": "main", "state": "running", "current": "Bash: pytest", "cost_usd": 0.12},
                {"agent_id": "c1", "parent": "main", "name": "reviewer", "state": "paused", "current": "", "cost_usd": 0.01}]}]},
        {"id": "b" * 16, "name": "bob@member", "online": False, "version_mismatch": True, "sessions": []}], "hub": {}}


@test
def test_table_rows_text_and_the_fleet_dialog(ctx: Ctx):
    from halo_harness.fleet import table
    rows = table.rows(_view())
    ctx.check(f"one row per agent plus one for a harness with no session, got {len(rows)}", len(rows) == 3
              and rows[1]["depth"] == 1 and rows[2]["state"] == "away" and "!v" in rows[2]["harness_name"])
    text = table.render(rows, selected=1)
    ctx.check(f"the table shows harness, agent, state, current, cost, got {text!r}", "alice@hub (you)" in text
              and "  reviewer" in text and "Bash: pytest" in text and "$0.12" in text and "\n> " in text)
    sent: list = []
    real_send, real_snap = table.send, table.snapshot
    table.send = lambda row, cmd, source, **kw: (sent.append((row["agent_id"], cmd, kw)) or (True, f"{cmd}: done"))
    table.snapshot = lambda: (_view(), "local")
    try:
        from halo_harness.commands.builtins import _cmd_fleet
        out = _cmd_fleet("", None)
        ctx.check("`/fleet` as text is the same table", out.startswith("Fleet (this harness only):") and "reviewer" in out)

        async def body():
            from halo_harness.testing.fake_controller import FakeController
            from halo_harness.tui.app import BridgeApp
            from halo_harness.tui.dialogs.fleet_table import FleetTable
            app = BridgeApp(FakeController(), cwd="~/project")
            async with app.run_test(size=(140, 40)) as pilot:
                app.push_screen(FleetTable(_view(), "local"))
                await pilot.pause(0.3)
                ol = app.screen.query_one("#fleet-rows")
                ctx.check(f"the dialog lists the rows, got {ol.option_count}", ol.option_count == 3)
                await pilot.press("down", "p")
                await pilot.pause(0.3)
                await pilot.press("k")
                await pilot.pause(0.2)
                ctx.check("one k only asks", not any(c == "stop" for _a, c, _k in sent))
                await pilot.press("k")
                await pilot.pause(0.3)
                await pilot.press("s")
                await pilot.pause(0.1)
                await pilot.press(*"go", "enter")
                await pilot.pause(0.4)
                await pilot.press("escape")
                await pilot.pause(0.1)
                ctx.check("Esc closes it", type(app.screen).__name__ != "FleetTable")
        asyncio.run(body())
        ctx.check(f"p resumed the paused agent, k k stopped it, s steered it, got {sent}",
                  ("c1", "resume", {}) in sent and any(a == "c1" and c == "stop" for a, c, _k in sent)
                  and ("c1", "steer", {"text": "go"}) in sent)
    finally:
        table.send, table.snapshot = real_send, real_snap


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
