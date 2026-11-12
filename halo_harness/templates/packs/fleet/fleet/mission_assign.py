"""halo_harness.fleet.mission_assign -- which harness can take which part of
a mission, in code (Halo 3.0.6.0 "Fleet Missions" round R7; 3.1.0.0 R2
renamed it from mission_plan_rules.py and moved the claim paths to
mission_claims.py). It runs before the lead sees the fleet (`unique_lines`:
what only one harness has, so the lead is told) and after it answers
(`assign`), and again, alone, after an owner's edit. No model call here.

* `has(catalog, need)`: a capability name is an MCP server (`gridcraft`), one
  of its tools (`gridcraft/write_range` or `write_range`), a skill, a tag, a
  craft app, a CLI that is installed (`nmap`), a model id, `comfyui`, `gpu`,
  a word of a GPU's name (`4090`), an OS or distro (`kali`), `repo:<name>`, or
  (3.2.0.0 R4) a pack's fleet capability that is available there (`docs.review`;
  why "pack doc-review: docs.review"). A `kind:` prefix (`mcp:`, `tool:`,
  `skill:`, `tag:`, `app:`, `cli:`, `model:`, `os:`, `pack:`) narrows it.
* `assign`: a part whose needs only one harness meets is pinned there; when
  several meet them the lead's pick stands, else `fleet.mission.prefer` (an
  ordered list of names) breaks the tie, then load (live agents), then the
  name; a need nobody has makes the part `unassignable` with the reason. A
  part's `pack_needs` lists its needs that are pack capabilities ({need, pack}),
  for Studio and for the worker, which checks them again before it runs.
"""

from __future__ import annotations

import re

from halo_harness.ext import core as _core

KINDS, norm_need, has = (_core.get("peers.needs", n) for n in ("KINDS", "norm_need", "has"))  # 3.4.0.0 D: core (peers/needs.py)


def able(entries: list, needs: list) -> list:
    """`[(entry, [why...])]` for every harness that meets all of `needs`."""
    out = []
    for e in entries:
        whys = [has(e.get("catalog"), n) for n in needs]
        if all(whys):
            out.append((e, whys))
    return out


def unique_lines(entries: list, limit: int = 40) -> list:
    """`only <name> has: a, b` lines (servers, craft apps, CLIs, skills, GPUs) for the lead's prompt."""
    seen: dict = {}
    for e in entries:
        cat = e.get("catalog") or {}
        names = {str(s.get("name")) for s in cat.get("mcp") or []} | set(map(str, cat.get("craft_apps") or []))
        names |= {f"cli:{k}" for k, v in (cat.get("clis") or {}).items() if v} | set(map(str, cat.get("skills") or []))
        names |= {"gpu"} if (cat.get("hardware") or {}).get("gpu") else set()
        names |= {str(c.get("name")) for p in cat.get("packs") or [] for c in p.get("capabilities") or [] if c.get("available")}
        for n in names:
            seen.setdefault(n.lower(), set()).add(str(e.get("name")))
    only: dict = {}
    for n, who in sorted(seen.items()):
        if len(who) == 1:
            only.setdefault(next(iter(who)), []).append(n)
    return [f"only {who} has: {', '.join(items[:limit])}" for who, items in sorted(only.items())]


def _rank(entry: dict, prefer: list, load: dict) -> tuple:
    names = [p.lower() for p in prefer]
    keys = (str(entry.get("name") or "").lower(), str(entry.get("harness") or "").lower())
    pos = next((i for i, p in enumerate(names) if p in keys), len(names))
    return pos, int(load.get(str(entry.get("harness")), 0)), str(entry.get("name") or "").lower()


def _nobody(nobody: list, away: list) -> str:
    """3.4.0.1 (defect 14): a member that is away still has its card: say who has it, and what brings it back."""
    names = sorted({str(e.get("name")) for e in away for n in nobody if has(e.get("catalog"), n)})
    if not names:
        new = sorted({str(e.get("name")) for e in away if not e.get("catalog")})  # 3.4.1.0 R5 (defect 36): a fresh join
        return f"nobody in the fleet has {', '.join(nobody)}" + (
            f"; {', '.join(new)} joined but {'has' if len(new) == 1 else 'have'} not sent {'its' if len(new) == 1 else 'their'} "
            "card yet (it goes with the first halo session there): open one, then plan again" if new else "")
    return (f"nobody online has {', '.join(nobody)}; {', '.join(names)} {'has' if len(names) == 1 else 'have'} it but "
            f"{'is' if len(names) == 1 else 'are'} offline (no halo session open there): open one, then plan again")


FIXED_WORDS = {"gpu", "comfyui"}


def vocabulary(entries: list) -> set:
    """3.4.1.1 (42): every capability word any harness's card lists -- MCP servers and tools, skills, tags, craft apps,
    CLIs (installed or not), models, GPU name words, OS and distro, pack capabilities -- and `gpu`, `comfyui`."""
    out = set(FIXED_WORDS)
    for e in entries:
        cat = e.get("catalog") if isinstance(e.get("catalog"), dict) else {}
        for s in cat.get("mcp") or []:
            out.add(str(s.get("name") or "").lower())
            out |= {str(t.get("name") or "").lower() for t in s.get("tools") or [] if isinstance(t, dict)}
        for key in ("skills", "tags", "craft_apps"):
            out |= {str(x).lower() for x in cat.get(key) or []}
        out |= {str(k).lower() for k in (cat.get("clis") or {})} if isinstance(cat.get("clis"), dict) else set()
        for m in cat.get("models") or []:
            mid = str(m.get("id") or "").lower()
            out |= {mid, mid.split(":", 1)[-1], mid.rsplit("/", 1)[-1]}
        hw = cat.get("hardware") if isinstance(cat.get("hardware"), dict) else {}
        out |= {str(hw.get(k) or "").lower() for k in ("os", "distro")}
        out |= {w for g in hw.get("gpu") or [] if isinstance(g, dict) for w in re.findall(r"[a-z0-9]+", str(g.get("name") or "").lower())}
        out |= {str(c.get("name") or "").lower() for p in cat.get("packs") or [] if isinstance(p, dict)
                for c in p.get("capabilities") or [] if isinstance(c, dict)}
    return out - {""}


def named(text: str, entries: list) -> list:
    """3.4.1.1 (42): the harnesses `text` names (`kali@kali`, its id), by whole word, in the fleet's order."""
    low = " " + " ".join(str(text or "").lower().replace("`", " ").replace('"', " ").split()) + " "
    out = []
    for e in entries:
        keys = {str(e.get("name") or "").lower(), str(e.get("harness") or "").lower()} - {""}
        if any(re.search(r"(?<![\w@.-])" + re.escape(k) + r"(?![\w@-])", low) for k in keys):
            out.append(e)
    return out


def unknown_needs(part: dict, entries: list, away: list = ()) -> list:
    """3.4.1.1 (42): the part's bare needs no card's vocabulary knows (the lead's `shell`): not one harness lists such a
    capability, installed or not."""
    every = list(entries) + list(away or [])
    words = vocabulary(every)
    return [n for n in (norm_need(x) for x in part.get("needs") or []) if n and n.split(":", 1)[0] not in KINDS
            and n not in words and not any(has(e.get("catalog"), n) for e in every)]


def said_by(part: dict, entries: list, goal: str = "") -> "tuple[list, str]":
    """The harnesses the part's own words name, else the goal's; and which named them."""
    own = named(f"{part.get('title') or ''} {part.get('brief') or ''}", entries)
    return (own, "the part") if own else (named(goal, entries), "the goal")


def vocab_problems(parts: list, entries: list, away: list = (), goal: str = "") -> list:
    """3.4.1.1 (42): the lead's first answer is sent back for a need no card knows, unless the owner named the harness
    (`assign` then drops it); a second answer that keeps it is taken (a capability nobody has: unassignable)."""
    return [f"part {p.get('id')}: no harness lists {', '.join(u)} -- name only capabilities from THE FLEET blocks, and "
            "leave out what every harness has (a shell, a file system)"
            for p in parts if (u := unknown_needs(p, entries, away)) and not said_by(p, entries, goal)[0]]


def assign(part: dict, entries: list, prefer: list, load: dict, away: list = (), goal: str = "") -> dict:
    """Set `harness`, `harness_name`, `pinned`, `reason`, `unassignable` on `part` by the rules (`away`: the members
    offline now, with their cards: named when only they have a need). 3.4.1.1 (42): a harness the part (or else the
    goal, `goal`) names wins over the lead's pick and the tie rules when it meets the needs; a bare need no card knows
    (the lead's `shell`) is dropped there (`dropped_needs`, the plan says so) instead of making the part unassignable."""
    said, by = said_by(part, entries, goal)
    unknown = unknown_needs(part, entries, away) if said else []
    needs = [n for n in (norm_need(x) for x in part.get("needs") or []) if n and n not in unknown]
    part["needs"], part["dropped_needs"] = needs, unknown
    nobody = [n for n in needs if not any(has(e.get("catalog"), n) for e in entries)]
    part["pinned"], part["unassignable"] = False, None
    if nobody:
        why = _nobody(nobody, list(away or []))
        part.update(harness=None, harness_name=None, unassignable=why, reason=f"unassignable: {why}"[:300])
        return part
    fit = able(entries, needs)
    if not fit:
        part.update(harness=None, harness_name=None,
                    unassignable=f"no one harness has all of {', '.join(needs)}: split the part",
                    reason=f"unassignable: no one harness has all of {', '.join(needs)}")
        return part
    picked = str(part.get("harness") or "").strip().lower()
    chosen = next(((e, w) for e, w in fit if picked and picked in (str(e.get("harness")).lower(),
                                                                   str(e.get("name") or "").lower())), None)
    why_lead = str(part.get("reason") or "").strip()
    said_fit = [(e, w) for e, w in fit if any(e is s for s in said)]
    if len(fit) == 1:
        e, whys = fit[0]
        part["pinned"] = bool(needs)
        reason = f"only {e.get('name')} has {', '.join(whys)}" if needs else f"{e.get('name')} is the only harness"
    elif len(said_fit) == 1:  # 3.4.1.1 (42): the owner named the harness
        e, whys = said_fit[0]
        part["pinned"] = True
        reason = f"{by} names {e.get('name')}" + (f", which has {', '.join(whys)}" if needs else "")
    elif chosen is not None:
        e, whys = chosen
        reason = why_lead or (f"{e.get('name')} has {', '.join(whys)}" if needs else f"the lead picked {e.get('name')}")
    else:
        e, whys = sorted(fit, key=lambda f: _rank(f[0], prefer, load))[0]
        rank = _rank(e, prefer, load)
        how = "first in fleet.mission.prefer" if rank[0] < len(prefer) else f"least busy ({rank[1]} live agents)"
        reason = (f"{e.get('name')} has {', '.join(whys)}; " if needs else f"{e.get('name')}: ") + how
    part.update(harness=str(e.get("harness")), harness_name=e.get("name"), reason=reason[:300],
                pack_needs=pack_needs(needs, whys), mode_note=mode_note(e))
    return part


ASKS = ("default", "plan", "acceptEdits")  # the modes in which some tool call asks first


def mode_note(e: dict) -> str:
    """3.4.0.1 (defect 16): the plan says per part when its harness's mode asks. 3.4.1.0 R5 (defect 32): a member
    of 3.4.1.0 on parks the ask as a card on that machine for `mission_ask_wait_min` (its card says how long); an
    older one refuses it (print mode, no one to answer)."""
    h = (e.get("catalog") or {}).get("harness") or {}
    mode, wait = str(h.get("permission_mode") or ""), h.get("mission_ask_wait_min")
    if mode not in ASKS:
        return ""
    allow = ("on that machine allow what the part runs with a rule (permissions.allow, e.g. Bash(nmap:*)) or "
             "`halo config set permission_mode auto`")
    if isinstance(wait, (int, float)) and not isinstance(wait, bool):
        return (f"{e.get('name')} runs mission parts in permission mode {mode}: writing its own outputs folder with the "
                f"Write tool needs no ask (the part's brief says so; a shell redirect there asks); any other tool call that would ask there waits as a card in its owner's Attention on that machine "
                f"for up to {wait:g} min (fleet.mission.ask_wait_min), then the part ends not done; to need no answer, "
                + allow)
    return (f"{e.get('name')} runs mission parts in permission mode {mode}: a tool call that would ask there is refused "
            "(a part has no one to answer it); " + allow)


def pack_needs(needs: list, whys: list) -> list:
    """3.2.0.0 R4: `[{need, pack}]` for the needs a pack capability meets (has()'s "pack <id>: <name>")."""
    return [{"need": n, "pack": str(w)[5:].split(":", 1)[0]} for n, w in zip(needs, whys) if str(w or "").startswith("pack ")]
