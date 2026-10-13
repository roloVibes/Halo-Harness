"""halo_harness.paperclip.mode -- the Org mode switch (Halo 3.0.2.0).

Two different things can orchestrate models on a machine running Halo:

- **Your session.** The model you picked, and with a lineup, one agent per
  role that the session spawns and waits for. It runs when you type, and
  stops when the turn ends. Roles mode in Studio edits exactly this.
- **Paperclip (Org mode).** A separate control plane with its own server,
  scheduler and database. It wakes agents on heartbeats and issues, and
  every wake is a fresh `halo paperclip-run` process, whether or not you
  have a Halo session open. Org mode in Studio is a window onto it.

Org mode is OFF by default (`paperclip.enabled` in `~/.halo/config.json`).
While it is off, `halo paperclip-run` answers every heartbeat with an idle
exit, Studio's Org canvas explains the two orchestrators and offers the
switch, and nothing runs that you did not type. Turning it on resumes the
linked company's Halo agents; turning it off pauses them (best effort: the
switch is the source of truth even when Paperclip is unreachable).
`halo paperclip on|off`, `/org on|off`, the wizard's Organizations step and
Studio's Org header all flip the same key.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

KEY = "paperclip.enabled"

EXPLAINER = (
    "Two things can orchestrate models here. Your session: the model you picked, and with a "
    "lineup, one agent per role, spawned when you type and gone when the turn ends (Roles). "
    "Paperclip: a separate control plane that wakes agents on heartbeats and issues, each wake a "
    "fresh `halo paperclip-run`, whether or not a Halo session is open (Org). Org mode is off by "
    "default; nothing runs that you did not type until you turn it on."
)


def org_mode_enabled() -> bool:
    from halo_harness.theme import get_config_value
    return bool(get_config_value(KEY, False))


def _is_halo_agent(agent: dict) -> bool:
    cfg = agent.get("adapterConfig") or {}
    args = cfg.get("args") or []
    return "paperclip-run" in [str(a) for a in args] or bool((agent.get("metadata") or {}).get("halo_lineup"))


def set_org_mode(enabled: bool, *, state_dir: Optional[Path] = None, client=None, timeout: float = 30.0) -> dict:
    """Write the switch, then pause (off) or resume (on) the linked
    company's Halo agents when Paperclip is reachable. Returns
    {"enabled", "agents": [names touched], "note": a one-line reason when
    nothing was touched}."""
    from halo_harness.theme import set_config_value
    set_config_value(KEY, bool(enabled))
    return sync_agents(enabled, state_dir=state_dir, client=client, timeout=timeout)


def sync_agents(enabled: bool, *, state_dir: Optional[Path] = None, client=None, timeout: float = 30.0) -> dict:
    """The courtesy half of `set_org_mode`, after the switch is written:
    network calls only, so a UI runs it off its event loop. `timeout` bounds
    each Paperclip request (the health probe is shorter still)."""
    out = {"enabled": bool(enabled), "agents": [], "note": ""}
    try:
        from halo_harness.paperclip.client import Paperclip, PaperclipError, load_config
        cfg = load_config(state_dir)
        company_id = cfg.get("company_id") or ""
        client = client or Paperclip.from_config(state_dir, timeout=timeout)
        if not company_id:
            out["note"] = "no company linked (halo paperclip link --company ...)"
            return out
        if not client.reachable():
            out["note"] = "Paperclip is not running; the switch still holds (heartbeats answer idle while off)"
            return out
        action = "resume" if enabled else "pause"
        for agent in client.agents(company_id):
            if not _is_halo_agent(agent):
                continue
            try:
                client.agent_action(agent.get("id", ""), action)
                out["agents"].append(str(agent.get("name") or agent.get("id")))
            except PaperclipError as e:
                out["note"] = f"{agent.get('name')}: {e.message}"
    except Exception as e:  # the switch is written; the pause/resume is a courtesy
        out["note"] = f"{type(e).__name__}: {e}"
    return out


def mode_line(enabled: Optional[bool] = None) -> str:
    on = org_mode_enabled() if enabled is None else enabled
    return ("Org mode: ON -- Paperclip wakes the company's agents on heartbeats and issues (halo paperclip off stops it)"
            if on else
            "Org mode: off -- only your session orchestrates; heartbeats answer idle (halo paperclip on, /org on, or Studio's Org header)")
