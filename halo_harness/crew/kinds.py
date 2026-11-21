"""halo_harness.crew.kinds -- the kinds of helper THIS session can start (3.6.0.10 MW, rule M2), as one pure list over
the agents a new session's start gives its runtime (`agent/loop.py`: `AgentRuntime(agents=...)`):

    kinds(agents, restriction=None, plain=None) -> [{"name", "words", "part"}]
    names(rows) -> [name]

In this order, each name once (a dict's keys):
  "his"       his own agents: crew yours or this project's (crew/spec.py `crew:yours`, `crew:project`)
  "auto"      Auto's seven, in the map's order, while each is still the shipped card (`crew:starter`)
  "other"     every other agent that is not a built-in (~/.claude/agents, a project's .claude/agents, a pack's,
              a plugin's, `--agents`)
  "built-in"  config/agents_md.py BUILTIN_NAMES but general-purpose (what a call naming no kind gets: the clause);
              one is out when its lower-cased name or its role is a name listed before it
A restriction (an `--agent` session's `tools: Agent(...)`) keeps only the names the start's own check passes
(agent/subagent.py: `subagent_type not in restriction` refuses). Words: his and the others', the first sentence of the
description cut after 8 words; Auto's, its card's routing words then its `use_for` words (templates/crew/plain/
session.yaml), at most 8; a built-in's, its own few words. Pure: it reads no file (the plain card is the one the start
loaded, crew/plain.py caches it) and keeps nothing between calls.
"""

from __future__ import annotations

import re
from typing import Optional

WORDS_MAX = 8
CLAUSE = "general-purpose"
BUILTIN_WORDS = {"Judge": "pass or fail a result", "Tester": "run tests, report", "Explore": "find code, read-only",
                 "Plan": "plan, outline", "Coder": "implement, fix", "Reviewer": "review", "Researcher": "research"}
HIS = ("crew:yours", "crew:project")
STARTER = "crew:starter"
BUILT_IN = "built-in"


def _first_sentence(text) -> str:
    """The first sentence of `text`, cut after WORDS_MAX words, no closing stop or comma."""
    text = " ".join(str(text or "").split())
    m = re.search(r"[.!?](\s|$)", text)
    sentence = text[:m.start()] if m else text
    return " ".join(sentence.split()[:WORDS_MAX]).rstrip(",;:.!?")


def _card_words(plain, name: str) -> str:
    """Auto's card for `name`: its routing words, then its own `use_for` words, at most WORDS_MAX."""
    if plain is None:
        return ""
    card = plain.card_of(name)
    words = [str(w) for w, c in plain.routing.items() if c == card]
    for w in (plain.cards.get(card) or {}).get("use_for") or []:
        if str(w) not in words:
            words.append(str(w))
    return ", ".join(words[:WORDS_MAX])


def _source(spec) -> str:
    return str(getattr(spec, "source", "") or "")


def kinds(agents: Optional[dict], restriction=None, plain=None) -> list:
    agents = dict(agents or {})
    if restriction is not None:
        agents = {n: sp for n, sp in agents.items() if n in restriction}
    agents.pop(CLAUSE, None)
    if plain is None and any(_source(sp) == STARTER for sp in agents.values()):
        from halo_harness.crew.plain import load
        plain = load()
    from halo_harness.config.agents_md import BUILTIN_NAMES
    his, auto, other, built = [], [], [], []
    for name, spec in agents.items():
        src = _source(spec)
        if src in HIS:
            his.append({"name": name, "words": _first_sentence(getattr(spec, "description", "")), "part": "his"})
        elif src == STARTER:
            words = _card_words(plain, name) or _first_sentence(getattr(spec, "description", ""))
            auto.append({"name": name, "words": words, "part": "auto"})
        elif src == BUILT_IN and name in BUILTIN_NAMES:
            built.append((name, spec))
        else:
            other.append({"name": name, "words": _first_sentence(getattr(spec, "description", "")), "part": "other"})
    rows = his + auto + other
    listed = {r["name"].lower() for r in rows}
    for name, spec in built:
        role = str(getattr(spec, "role", "") or "").lower()
        if name.lower() in listed or (role and role in listed):
            continue
        rows.append({"name": name, "words": BUILTIN_WORDS.get(name) or _first_sentence(getattr(spec, "description", "")),
                     "part": "built-in"})
    return rows


def names(rows) -> list:
    return [r["name"] for r in rows or []]
