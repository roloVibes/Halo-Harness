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
from typing import Optional

KINDS = ("mcp", "tool", "skill", "tag", "app", "craft", "cli", "model", "os", "repo", "gpu", "pack")


def norm_need(need) -> str:
    return " ".join(str(need or "").strip().lower().split())


def has(cat: Optional[dict], need) -> Optional[str]:
    """Why `cat` meets `need` ("gridcraft (MCP server)"), or None."""
    if not isinstance(cat, dict):
        return None
    n = norm_need(need)
    kind, _, word = n.partition(":") if ":" in n and n.split(":", 1)[0] in KINDS else ("", "", n)
    if not word:
        return None
    k = kind or "any"
    for s in cat.get("mcp") or []:
        name = str(s.get("name") or "").lower()
        if k in ("any", "mcp", "app", "craft") and name == word:
            return f"{name} (MCP server)"
        for t in s.get("tools") or [] if isinstance(s.get("tools"), list) else []:
            tool = str(t.get("name") or "").lower()
            if k in ("any", "tool", "mcp") and word in (tool, f"{name}/{tool}"):
                return f"{name}/{tool} (MCP tool)"
    for key, label, kinds in (("skills", "skill", ("any", "skill")), ("tags", "tag", ("any", "tag")),
                              ("craft_apps", "craft app", ("any", "app", "craft"))):
        if k in kinds and word in [str(x).lower() for x in cat.get(key) or []]:
            return f"{word} ({label})"
    clis = cat.get("clis") if isinstance(cat.get("clis"), dict) else {}
    if k in ("any", "cli") and clis.get(word):
        return f"{word} {clis[word] if clis[word] != 'installed' else ''}".strip() + " (CLI)"
    for m in cat.get("models") or []:
        mid = str(m.get("id") or "").lower()
        if k in ("any", "model") and word in (mid, mid.split(":", 1)[-1], mid.rsplit("/", 1)[-1]):
            return f"{m.get('id')} (model)"
    media = cat.get("media") if isinstance(cat.get("media"), dict) else {}
    if k in ("any", "app") and word == "comfyui" and media.get("comfyui"):
        return "ComfyUI (media)"
    hw = cat.get("hardware") if isinstance(cat.get("hardware"), dict) else {}
    gpus = [str(g.get("name") or "") for g in hw.get("gpu") or [] if isinstance(g, dict)]
    if k in ("any", "gpu") and (word == "gpu" and gpus or any(word in re.findall(r"[a-z0-9]+", g.lower()) for g in gpus)):
        return f"{gpus[0] if word == 'gpu' else next(g for g in gpus if word in g.lower())} (GPU)"
    if k in ("any", "os") and word in (str(hw.get("os") or "").lower(), str(hw.get("distro") or "").lower()):
        return f"{word} (OS)"
    if k == "repo" and word in [str(p.get("repo") or p.get("name") or "").lower() for p in cat.get("projects") or []]:
        return f"the {word} repo"
    if k in ("any", "pack"):  # 3.2.0.0 R4: a pack's capability, only where it is available
        for p in cat.get("packs") or [] if isinstance(cat.get("packs"), list) else []:
            for c in p.get("capabilities") or [] if isinstance(p, dict) else []:
                if isinstance(c, dict) and c.get("available") and str(c.get("name") or "").lower() == word:
                    return f"pack {p.get('id')}: {c.get('name')}"
    return None


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


def assign(part: dict, entries: list, prefer: list, load: dict) -> dict:
    """Set `harness`, `harness_name`, `pinned`, `reason`, `unassignable` on `part` by the rules."""
    needs = [norm_need(n) for n in part.get("needs") or [] if norm_need(n)]
    part["needs"] = needs
    nobody = [n for n in needs if not any(has(e.get("catalog"), n) for e in entries)]
    part["pinned"], part["unassignable"] = False, None
    if nobody:
        part.update(harness=None, harness_name=None, unassignable=f"nobody in the fleet has {', '.join(nobody)}",
                    reason=f"unassignable: nobody in the fleet has {', '.join(nobody)}")
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
    if len(fit) == 1:
        e, whys = fit[0]
        part["pinned"] = bool(needs)
        reason = f"only {e.get('name')} has {', '.join(whys)}" if needs else f"{e.get('name')} is the only harness"
    elif chosen is not None:
        e, whys = chosen
        reason = why_lead or (f"{e.get('name')} has {', '.join(whys)}" if needs else f"the lead picked {e.get('name')}")
    else:
        e, whys = sorted(fit, key=lambda f: _rank(f[0], prefer, load))[0]
        rank = _rank(e, prefer, load)
        how = "first in fleet.mission.prefer" if rank[0] < len(prefer) else f"least busy ({rank[1]} live agents)"
        reason = (f"{e.get('name')} has {', '.join(whys)}; " if needs else f"{e.get('name')}: ") + how
    part.update(harness=str(e.get("harness")), harness_name=e.get("name"), reason=reason[:300],
                pack_needs=pack_needs(needs, whys))
    return part


def pack_needs(needs: list, whys: list) -> list:
    """3.2.0.0 R4: `[{need, pack}]` for the needs a pack capability meets (has()'s "pack <id>: <name>")."""
    return [{"need": n, "pack": str(w)[5:].split(":", 1)[0]} for n, w in zip(needs, whys) if str(w or "").startswith("pack ")]
