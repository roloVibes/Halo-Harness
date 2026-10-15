"""halo_harness.fleet.capabilities_who -- "who can do this?" over the fleet's
capability catalogs (Halo 3.0.6.0 "Fleet Missions" round R6). Plain scoring
in code, no model:

    rank(entries, q) -> [{harness, name, score, matches: [{kind, name, why}]}]   best first

`entries` are `{harness, name, catalog}`. Every catalog becomes items of a
kind -- mcp_tool (a server, and each of its tools), skill, tag, model,
craft_app, cli, hardware -- each with a name and a description. The query
is cut into words (lower case, letters and digits; filler words such as
"who", "can", "a" dropped). An item scores

    EXACT (10)   its whole name is the query, or one query word
    NAME (4)     for each query word that is a word of its name
    DESC (1)     for each other query word found in its description

and a tag item counts double (the owner said so). A harness's score is the
sum of its best TOP item scores; its matches are those items, with why.
"""

from __future__ import annotations

import re
from typing import Iterable

EXACT, NAME, DESC = 10.0, 4.0, 1.0
TOP = 5
KINDS = ("mcp_tool", "skill", "tag", "model", "craft_app", "cli", "hardware")
STOP = frozenset("a an and any are be best build can could create do does for from get has have help how i in is it "
                 "make me my need of on one or our please run should some someone something that the this to us use "
                 "we what which who whom will with would you".split())
CRAFT_WORDS = {"gridcraft": "spreadsheets, workbooks, formulas, charts, tables (an Excel-class app)",
               "deckcraft": "presentations, slide decks, slides, charts (a PowerPoint-class app)",
               "wordcraft": "documents, letters, reports, docx word processing (a Word-class app)",
               "soundcraft": "audio, music, mixing, recording, a digital audio workstation (a Pro Tools-class app)",
               "cadcraft": "CAD drawings, 2D/3D drafting, floor plans, dxf (an AutoCAD-class app)"}
_WORD = re.compile(r"[a-z0-9]+")


def words(text: str) -> list:
    return [w for w in _WORD.findall(str(text or "").lower()) if w not in STOP]


def query_words(q: str) -> list:
    return list(dict.fromkeys(words(q)))


def items(cat: dict) -> list:
    """`[(kind, name, desc)]` for one catalog."""
    from halo_harness.design.crafts import APPS
    out = []
    for s in cat.get("mcp") or []:
        tools = s.get("tools") if isinstance(s.get("tools"), list) else []
        out.append(("mcp_tool", str(s.get("name")), f"MCP server, {len(tools)} tools"))
        out += [("mcp_tool", f"{s.get('name')}/{t.get('name')}", str(t.get("desc") or "")) for t in tools]
    out += [("skill", str(n), "skill") for n in cat.get("skills") or []]
    out += [("tag", str(t), "tag the owner set") for t in cat.get("tags") or []]
    for m in cat.get("models") or []:
        why = ("best for " + ", ".join(m["best_for"])) if m.get("best_for") else "local model" if m.get("local") else "model"
        out.append(("model", str(m.get("id")), f"{why} ({m.get('provider') or '?'})"))
    for m in (cat.get("media") or {}).get("models") or []:
        out.append(("model", str(m.get("name")), f"ComfyUI {m.get('kind')} model"))
    out += [("craft_app", str(a), str((APPS.get(a) or {}).get("for") or CRAFT_WORDS.get(a) or "craft app"))
            for a in cat.get("craft_apps") or []]
    out += [("cli", str(k), f"command-line tool {v}") for k, v in (cat.get("clis") or {}).items() if v]
    hw = cat.get("hardware") or {}
    for g in hw.get("gpu") or []:
        vram = g.get("vram_gb")
        out.append(("hardware", str(g.get("name")), "GPU" + (f" {vram:g} GB VRAM" if isinstance(vram, (int, float)) else "")))
    if hw.get("cpu"):
        out.append(("hardware", str(hw["cpu"]), f"CPU, {hw.get('cores') or '?'} cores"))
    for k in ("os", "distro"):
        if hw.get(k):
            out.append(("hardware", str(hw[k]), "operating system"))
    if isinstance(hw.get("ram_gb"), (int, float)):
        out.append(("hardware", f"{hw['ram_gb']:g} GB RAM", "memory ram"))
    return out


def _tool_words(name: str) -> list:
    """`gridcraft/write_range` -> its own words; the server half is the server item's."""
    return words(name.split("/", 1)[1] if "/" in name else name)


def score_item(kind: str, name: str, desc: str, qwords: list) -> "tuple[float, str]":
    if not qwords:
        return 0.0, ""
    nw = _tool_words(name) if kind == "mcp_tool" else words(name)
    whole = " ".join(nw)
    if whole and (whole == " ".join(qwords) or (len(nw) == 1 and nw[0] in qwords)):
        s, why = EXACT, "name is the query" if whole == " ".join(qwords) else f"name is \"{nw[0]}\""
    else:
        hits = [w for w in qwords if w in nw]
        dwords = set(words(desc))
        dhits = [w for w in qwords if w not in hits and w in dwords]
        s = NAME * len(hits) + DESC * len(dhits)
        bits = ([f"name has {', '.join(hits)}"] if hits else []) + ([f"description has {', '.join(dhits)}"] if dhits else [])
        why = "; ".join(bits)
    if s and kind == "tag":
        s, why = s * 2, why + " (a tag counts double)"
    return s, why


def rank(entries: Iterable[dict], q: str, *, top: int = TOP) -> list:
    qwords = query_words(q)
    out = []
    for e in entries:
        cat = e.get("catalog") or {}
        scored = []
        for kind, name, desc in items(cat):
            s, why = score_item(kind, name, desc, qwords)
            if s > 0:
                scored.append((s, kind, name, why))
        if not scored:
            continue
        scored.sort(key=lambda x: (-x[0], KINDS.index(x[1]), x[2]))
        best = scored[:top]
        out.append({"harness": e.get("harness"), "name": e.get("name"), "local": bool(e.get("local")),
                    "score": round(sum(x[0] for x in best), 2), "matched": len(scored),
                    "matches": [{"kind": k, "name": n, "why": w, "score": s} for s, k, n, w in best]})
    out.sort(key=lambda r: (-r["score"], str(r.get("name") or "")))
    return out


def lines(ranked: list, q: str) -> list:
    """`halo fleet who` / `/fleet who`'s text."""
    if not query_words(q):
        return [f"\"{q}\" has no words to look for (try a tool, an app, a skill, a model or a GPU)."]
    if not ranked:
        return [f"No harness lists anything that matches \"{q}\"."]
    out = [f"Who can: {q}"]
    for i, r in enumerate(ranked, 1):
        out.append(f"{i:>2}. {r.get('name')}  score {r['score']:g}  ({r['matched']} match{'es' if r['matched'] != 1 else ''})")
        out += [f"      {m['kind']:<10} {m['name']:<36} {m['why']}" for m in r["matches"]]
    return out
