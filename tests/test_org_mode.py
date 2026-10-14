"""tests.test_org_mode -- Halo 3.0.2.0: Org mode is a switch, off by default.

- `paperclip.enabled` is False on a fresh config; `set_org_mode` writes it and
  pauses/resumes the linked company's Halo agents over the fake Paperclip
  (other agents untouched); unreachable Paperclip still flips the switch.
- `halo paperclip-run` answers idle (exit 0, no network) while off.
- `/org on|off` flips it and explains; `halo paperclip status` leads with it.
- Studio: `GET /api/pc/status` carries `enabled`; `POST /api/pc/mode` flips it.

Run: python -m tests.test_org_mode
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.fake_paperclip import FakePaperclip  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_studio_org import _Studio  # noqa: E402
from halo_harness.paperclip.mode import EXPLAINER, mode_line, org_mode_enabled, set_org_mode  # noqa: E402

test, TESTS = new_registry()


def _state() -> Path:
    from halo_harness.providers.config import default_state_dir
    return Path(default_state_dir())


@test
def test_off_by_default_and_the_switch_pauses_and_resumes_halo_agents(ctx: Ctx):
    from halo_harness.paperclip.client import Paperclip, save_config
    ctx.check("a fresh config has Org mode off", org_mode_enabled() is False)
    ctx.check("the off line names the session as the orchestrator", "only your session orchestrates" in mode_line(False))
    fake = FakePaperclip(company_name="Halo Harness")
    try:
        halo = fake.add_agent("worker", adapterType="process", adapterConfig={"command": "halo", "args": ["paperclip-run"]}, metadata={"halo_lineup": "balanced", "halo_slot": "worker"})
        other = fake.add_agent("ceo", adapterType="claude_local", adapterConfig={})
        save_config({"base_url": fake.base_url, "company_id": fake.company["id"]}, _state())
        client = Paperclip(fake.base_url)
        on = set_org_mode(True, state_dir=_state(), client=client)
        ctx.check(f"on resumes the Halo agent only, got {on}", on["enabled"] is True and on["agents"] == ["worker"])
        ctx.check("the switch is written", org_mode_enabled() is True)
        actions = [(m, p) for (m, p, _b, _h) in fake.requests if m == "POST" and "/api/agents/" in p]
        ctx.check(f"a resume was posted for the Halo agent, got {actions}", any(p.endswith(f"/agents/{halo['id']}/resume") for _m, p in actions)
                  and not any(other["id"] in p for _m, p in actions))
        off = set_org_mode(False, state_dir=_state(), client=client)
        ctx.check(f"off pauses it, got {off}", off["enabled"] is False and off["agents"] == ["worker"] and org_mode_enabled() is False)
    finally:
        fake.close()
    unreachable = Paperclip("http://127.0.0.1:9", timeout=0.3)
    res = set_org_mode(True, state_dir=_state(), client=unreachable)
    ctx.check(f"an unreachable Paperclip still flips the switch and says so, got {res}",
              res["enabled"] is True and org_mode_enabled() is True and "not running" in res["note"])
    set_org_mode(False, state_dir=_state(), client=unreachable)


@test
def test_heartbeat_answers_idle_while_off(ctx: Ctx):
    from halo_harness.paperclip.adapter import run_heartbeat
    set_org_mode(False, state_dir=_state(), client=None)
    out = io.StringIO()
    calls = []
    code = run_heartbeat({"PAPERCLIP_API_URL": "http://127.0.0.1:9", "PAPERCLIP_AGENT_ID": "a", "PAPERCLIP_COMPANY_ID": "c"},
                         runner=lambda *a, **k: calls.append(a) or (0, "x"), out=out)
    ctx.check(f"exit 0 and no model call, got {code} {calls}", code == 0 and not calls)
    ctx.check(f"the reason names the switch, got {out.getvalue()!r}", "Org mode is off" in out.getvalue() and "halo paperclip on" in out.getvalue())


@test
def test_slash_org_on_off_and_cli_status_lead_with_the_mode(ctx: Ctx):
    from tests.helpers.fake_home import build_fake_home
    from halo_harness.commands.builtins import HeadlessFacade, _cmd_org
    from halo_harness.commands.registry import Registry
    fh = build_fake_home()
    facade = HeadlessFacade(cwd=fh["proj"], registry=Registry.discover(fh["proj"], fh["home"]), model_ref="or:mock/model", permission_mode="default")
    on = _cmd_org("on", facade)
    ctx.check(f"/org on turns it on and says who orchestrates, got {on!r}", on.startswith("Org mode: ON") and org_mode_enabled() is True)
    off = _cmd_org("off", facade)
    ctx.check(f"/org off turns it off and explains, got {off!r}", off.startswith("Org mode: off") and EXPLAINER in off and org_mode_enabled() is False)
    from halo_harness.paperclip.cli import cmd_paperclip
    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_paperclip(["status"])
    ctx.check(f"halo paperclip status leads with the mode, got {buf.getvalue()[:60]!r}", buf.getvalue().startswith("Org mode: off"))
    from halo_harness.commands.builtins import _BUILTIN_SPECS
    ctx.check("the /org usage names on|off", "on|off" in _BUILTIN_SPECS["org"][2])


@test
def test_studio_status_carries_the_switch_and_mode_flips_it(ctx: Ctx):
    with _Studio() as s:
        status, st = s.call("GET", "/api/pc/status")
        ctx.check(f"status carries enabled=False and the explainer, got {status} {list(st)[:4]}", status == 200 and st.get("enabled") is False and "orchestrate" in st.get("explainer", ""))
        status, res = s.call("POST", "/api/pc/mode", {"enabled": True})
        ctx.check(f"POST mode turns it on, got {status} {res}", status == 200 and res.get("enabled") is True and org_mode_enabled() is True)
        status, st = s.call("GET", "/api/pc/status")
        ctx.check("status now says enabled", st.get("enabled") is True)
        s.call("POST", "/api/pc/mode", {"enabled": False})
        ctx.check("and off again", org_mode_enabled() is False)
    js = (REPO_DIR / "halo_harness" / "studio" / "static" / "legacy" / "org.js").read_text(encoding="utf-8")
    ctx.check("the header has the switch and the off state explains", 'id="org-mode-switch"' in js and "Org mode is off" in js and "org.offState" in js)
    css = (REPO_DIR / "halo_harness" / "studio" / "static" / "legacy" / "studio.css").read_text(encoding="utf-8")
    ctx.check("the Org header hides outside Org mode (the owner saw it over Roles)",
              'body:not([data-mode="org"]) #org-badges { display: none; }' in css and '$("org-badges").innerHTML = ""' in js)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    print_results(results, passed, failed, skipped)
    sys.exit(1 if failed else 0)
