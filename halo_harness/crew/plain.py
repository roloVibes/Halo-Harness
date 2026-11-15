"""halo_harness.crew.plain -- what a plain session answers (Halo 3.6.0.0 R5b; the coordinator's rule: "the default map
is a drawing of what a plain session already did, never a new rule").

A session that names no map (and none in config) holds a `PlainMap` (crew/map_control.py): it draws the starter map
and answers every question the loop, agent/subagent.py, models_auto_spawn and the Agent tool ask a session's control
from ONE file, `templates/crew/plain/session.yaml` (read from the package only, never a copy in ~/.halo):

- `cards`: who main may hand work to by name (a call's `role`, or the words in `routing` / a card's `use_for`), each
  card's model (`auto`: picked at spawn from its `needs` and `budget.band`; your `roles.<name>` wins), its prompt and
  the "how this works" text after it, its `acceptance` check on a hand-back;
- `delegation`: depth and parallel hand-offs (a knob you set yourself, `agents.max_depth` / `agents.max_concurrent`,
  wins); `tiers`: main hands work to the pool, a pool card does its work itself;
- no money cap, no escalation, no stages, no shared memory, no hooks, no extra permissions.

    load() -> Plain | None        the file read (None when it cannot be read): a session's control on its own (an
                                  `--agent` session, a Session built directly), or under a PlainMap's drawing
    Plain.role_table() -> dict    {card: "auto" | "default"}: the session's role table rides under it
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Optional

from halo_harness.crew.map_control import NoRules

FILE = Path(__file__).resolve().parent.parent / "templates" / "crew" / "plain" / "session.yaml"
NAME = "auto"  # the name a plain session's control answers to (the Agent tool's words say so)
HOW = "## How this team works"


_CACHE: dict = {}


def _read() -> Optional[dict]:
    """The file, read once per process (it ships in the package and does not change under a running Halo)."""
    if "raw" not in _CACHE:
        from halo_harness.crew.store import read
        raw = read(FILE)
        _CACHE["raw"] = raw if isinstance(raw, dict) else None
    return _CACHE["raw"]


def load() -> "Optional[Plain]":
    raw = _read()
    return Plain(raw) if raw is not None else None


def tier_line(tiers: list, caller: Optional[str], target: Optional[str]) -> Optional[str]:
    """None when `caller` may hand work to `target` (one tier down, or either is not on a card); else the rule."""
    def index(name):
        return next((t["index"] for t in tiers if name and name in t["members"]), None)
    n, m = index(caller), index(target)
    if n is None or m is None or m == n + 1:
        return None
    here = tiers[n]
    if n + 1 >= len(tiers):
        return (f"`{caller}` (tier {n} `{here['name']}`) is in the last tier: it does its work itself and "
                f"spawns no lineup member; `{target}` is in tier {m}")
    return (f"`{caller}` (tier {n} `{here['name']}`) may spawn only into the next tier down "
            f"(tier {n + 1} `{tiers[n + 1]['name']}`); `{target}` is in tier {m}")


class Plain(NoRules):
    """The answers of a plain session, from the file. Thread-safe where it counts (parallel children report back)."""

    name = NAME
    is_map = False
    default = True
    escalation: dict = {}
    permissions: dict = {}
    stages: list = []
    context: dict = {}
    tiers_declared = True

    def __init__(self, raw: dict) -> None:
        self.raw = raw
        self.name = str(raw.get("name") or NAME)
        self.cards = {str(c["name"]): c for c in raw.get("cards") or [] if isinstance(c, dict) and c.get("name")}
        self.lock = threading.Lock()
        self.reports: list = []
        self.spend_usd = 0.0
        self.turn_count = 0

    # -- no money cap: the spend is counted, never a stop ----------------------------------------------------------
    def budget_refusal(self) -> Optional[str]:
        return None

    def record_spend(self, usd: float) -> None:
        with self.lock:
            self.spend_usd += float(usd or 0.0)

    def record_turn(self, turns: int = 1) -> None:
        with self.lock:
            self.turn_count += int(turns or 0)

    # -- the sections -------------------------------------------------------------------------------------------
    @property
    def delegation(self) -> dict:
        return dict(self.raw.get("delegation") or {})

    @property
    def routing(self) -> dict:
        return dict(self.raw.get("routing") or {})

    @property
    def budget(self) -> dict:
        return dict(self.raw.get("budget") or {})

    @property
    def tiers(self) -> list:
        return [{"index": i, "name": t.get("name"), "members": list(t.get("members") or []), "purpose": t.get("purpose"),
                 "implicit": False, "max_parallel": None, "model": None, "trigger": None}
                for i, t in enumerate(self.raw.get("tiers") or []) if isinstance(t, dict)]

    @property
    def template(self) -> dict:
        return {"name": self.name}

    @property
    def aliases(self) -> dict:
        return {n: self.assignment_for(n) for n in self.cards}

    def starter_of(self, card: str) -> str:
        """The starter map's agent drawn for a card (its own name unless the file says)."""
        return str((self.cards.get(card) or {}).get("starter") or card)

    def card_of(self, starter: str) -> str:
        return next((n for n in self.cards if self.starter_of(n) == starter), starter)

    def needs_of(self, card: str) -> list:
        return [str(n) for n in (self.cards.get(card) or {}).get("needs") or []]

    def role_table(self) -> dict:
        """{card: its model value}: `auto` (picked at spawn), `default` for main (the session's model)."""
        return {n: str(c.get("model") or "auto") for n, c in self.cards.items()}

    def yields_to(self, config_key: str) -> bool:
        from halo_harness.theme import get_config_value
        return get_config_value(config_key, default=None) is not None

    # -- one card ------------------------------------------------------------------------------------------------
    def assignment_for(self, target: Optional[str]) -> Optional[dict]:
        card = self.cards.get(target or "")
        if card is None:
            return None
        out = {"role": card.get("role") or target, "agent": card.get("agent") or target}
        if card.get("use_for"):
            out["use_for"] = list(card["use_for"])
        return out

    def bio_for(self, target: Optional[str]) -> Optional[dict]:
        card = self.cards.get(target or "")
        if card is None:
            return None
        return {"name": card.get("agent") or target, "kind": card.get("kind"),
                "models": {"preference": card.get("model") or "auto", "needs": self.needs_of(target)},
                "context": {"system_prompt": card.get("prompt") or ""}, "acceptance": dict(card.get("acceptance") or {})}

    def member_context_addition(self, target: Optional[str], **_k) -> str:
        if target not in self.cards:
            return ""
        about = str(self.raw.get("about") or "").strip()
        parts = [str(self.cards[target].get("prompt") or "").strip(), f"{HOW}\n\n{about}" if about else ""]
        return "\n\n".join(p for p in parts if p)

    def route_call(self, tool_input: dict, description: str) -> "tuple[Optional[str], Optional[str]]":
        """`(word, card)` for an Agent call that names no `role`: the first routing word in its description or
        prompt, else a card's own `use_for` word; `(None, None)` when nothing names one."""
        if tool_input.get("role"):
            return None, None
        text = f"{description or ''}\n{tool_input.get('prompt') or ''}".lower()
        for word, card in self.routing.items():
            if re.search(rf"\b{re.escape(str(word).lower())}\b", text):
                return word, card
        for card, entry in self.cards.items():
            for word in entry.get("use_for") or []:
                if isinstance(word, str) and re.search(rf"\b{re.escape(word.lower())}\b", text):
                    return word, card
        return None, None

    # -- main and the pool ---------------------------------------------------------------------------------------
    def main_alias(self) -> Optional[str]:
        return "main" if "main" in self.cards else None

    def spawn_refusal(self, caller: Optional[str], target: Optional[str], root: bool = False) -> Optional[str]:
        return tier_line(self.tiers, caller, target)

    def reports_for(self, target: Optional[str]) -> bool:
        """A hand-back from a card is reported to main on its next turn; any other sub-agent through its own result."""
        return bool(target) and target in self.cards

    def record_report(self, target: Optional[str], one_line: str) -> str:
        line = f"[team {self.name}] {target or 'member'} -> main: {one_line}"
        with self.lock:
            self.reports.append(line)
        return line
