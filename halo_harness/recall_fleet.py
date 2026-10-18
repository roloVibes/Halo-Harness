"""halo_harness.recall_fleet -- recall across the fleet (Halo 3.1.2.0 R3,
docs/FLEET.md "Recall across the fleet").

`halo recall --fleet <query>` (and `/recall --fleet`, Studio's recall box
with its Fleet switch) asks the hub, which sends the read-only `recall`
fleet command `{query, k}` to every online member (fleet/hub_recall.py).
A member answers from its OWN index (recall.py): the index never leaves the
box, only the hits do, each

    {"score": 0.8123, "title": "...", "kind": "memory|session", "excerpt": "<= 300 chars", "harness": "<name>"}

and the hub merges them by score with its own. On a member:

    fleet.recall.share   true | false    false: it answers no recall (the hub shows it as not sharing)
    fleet.recall.hide    [kinds]         memory kinds never answered: `session`, `memory`, or a memory
                                         topic's own `type` (`user`, `feedback`, `project`, `reference`)

Every answer is a `recall_asked` line in the member's own journal (what was
asked, by whom, on which hub, how many hits). `SEARCH(query, k, home)` is
the seam (None: recall.search over that home's index); the check's `--fake`
and the tests swap it.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

SEARCH: Optional[Callable] = None
EXCERPT_CHARS = 300
MAX_K = 20
_READ_CAP = 64_000


class Shut(Exception):
    """This harness does not answer recall from a hub (fleet.recall.share: false)."""


def clean_query(raw) -> str:
    return " ".join(str(raw or "").split())[:500]


def clamp_k(raw, default: int = 8) -> int:
    try:
        return max(1, min(MAX_K, int(raw)))
    except (TypeError, ValueError):
        return default


def settings(home=None) -> dict:
    """`{share, hide}` from fleet.recall.share (default true) and fleet.recall.hide."""
    from halo_harness.fleet.identity import config_value
    from halo_harness.remote.fleet_identity import truthy
    share = truthy(config_value("fleet.recall.share", True, home), True)
    hide = config_value("fleet.recall.hide", [], home)
    hide = [hide] if isinstance(hide, str) else hide if isinstance(hide, list) else []
    return {"share": share, "hide": {str(h).strip().lower() for h in hide if str(h).strip()}}


def _search(query: str, k: int, home) -> list:
    if SEARCH is not None:
        return list(SEARCH(query, k, home) or [])
    from halo_harness.recall import search
    return search(query, state_dir=home, k=k)


def _flat(text: str) -> str:
    return " ".join(str(text or "").split())[:EXCERPT_CHARS]


def _session_text(path: Path) -> str:
    """A session log's title and first prompt, read from its first few hundred lines."""
    import json
    title, prompt = "", ""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh):
                if n > 400 or (title and prompt):
                    break
                try:
                    node = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(node, dict):
                    continue
                if node.get("type") == "meta" and node.get("title") and not title:
                    title = str(node["title"])
                elif node.get("type") == "user" and node.get("kind") is None and not prompt:
                    prompt = next((str(b.get("text")) for b in node.get("content") or []
                                   if isinstance(b, dict) and b.get("type") == "text" and b.get("text")), "")
    except OSError:
        return ""
    return prompt or title


def excerpt_of(hid: str, kind: str) -> "tuple[str, Optional[str]]":
    """`(excerpt, memory type)` read from the hit's own file on this box (the path never leaves it)."""
    path = Path(str(hid or ""))
    if not path.is_file():
        return "", None
    if kind == "session":
        return _flat(_session_text(path)), None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:_READ_CAP]
    except OSError:
        return "", None
    from halo_harness.config.frontmatter import parse
    front, body = parse(text)
    meta = front.get("metadata") if isinstance(front.get("metadata"), dict) else {}
    kind_word = front.get("type") or meta.get("type")
    return _flat(body), (str(kind_word).strip().lower() if kind_word else None)


def hits_of(raw: list, name: str, hide: set) -> "tuple[list, int]":
    """The index's hits as the fleet sees them: no id, no path; the hidden kinds dropped."""
    out, hidden = [], 0
    for h in raw:
        if not isinstance(h, dict):
            continue
        kind = str(h.get("kind") or "memory")
        if "excerpt" in h:
            excerpt, mtype = _flat(h.get("excerpt")), (str(h.get("type")).lower() if h.get("type") else None)
        else:
            excerpt, mtype = excerpt_of(str(h.get("id") or ""), kind)
        if kind in hide or (mtype and mtype in hide):
            hidden += 1
            continue
        out.append({"score": round(float(h.get("score") or 0.0), 4), "title": str(h.get("title") or "")[:200],
                    "kind": kind, "excerpt": excerpt, "harness": name})
    return out, hidden


def answer(fields: dict, *, by: str = "", hub: str = "", home=None) -> dict:
    """The member's side of `recall {query, k}`: its own index, its own settings, a journal line."""
    from halo_harness.fleet import identity, journal
    query, k = clean_query((fields or {}).get("query")), clamp_k((fields or {}).get("k"))
    home = Path(home) if home is not None else identity.home()
    me = identity.harness(home)
    cfg = settings(home)
    if not cfg["share"]:
        raise Shut(f"{me['name']} does not share its recall (fleet.recall.share: false)")
    hits, hidden = hits_of(_search(query, k, home) if query else [], me["name"], cfg["hide"])
    journal.append(home, "recall_asked", harness=me["id"], harness_name=me["name"], by=by or None, hub=hub or None,
                   query=query[:200], k=k, hits=len(hits), hidden=hidden or None)
    return {"harness": me["name"], "hits": hits, "hidden": hidden}


def local_hits(query: str, k: int, home=None, *, for_member: bool = False) -> "tuple[list, str]":
    """This harness's own hits for a merged view, and a note when there are none to give."""
    from halo_harness.fleet import identity
    home = Path(home) if home is not None else identity.home()
    cfg = settings(home)
    if for_member and not cfg["share"]:
        return [], "not shared (fleet.recall.share: false)"
    try:
        hits, _hidden = hits_of(_search(query, k, home), identity.fleet_name(home), cfg["hide"] if for_member else set())
    except Exception as e:  # a broken index never stops the fleet's answer
        return [], f"{type(e).__name__}: {e}"[:200]
    if not hits and SEARCH is None:
        from halo_harness.providers.embeddings import embeddings_enabled
        if not embeddings_enabled():
            return [], "embeddings are not configured here (embeddings.model)"
    return hits, ""


def merge(groups: list, k: int) -> list:
    """Every group's hits in one list, best score first (ties: harness, then title), at most k."""
    rows = [h for g in groups for h in g or []]
    rows.sort(key=lambda h: (-float(h.get("score") or 0.0), str(h.get("harness") or ""), str(h.get("title") or "")))
    return rows[:max(1, int(k))]


def ask(query: str, k: int = 8) -> "tuple[int, dict]":
    """`halo recall --fleet`: the hub this machine runs, else the first hub it joined, else 409."""
    from halo_harness.fleet import identity, store
    from halo_harness.fleet.hub import running_call
    query, k = clean_query(query), clamp_k(k)
    got = running_call(identity.home(), "POST", "local/recall", {"query": query, "k": k}, timeout=60.0)
    if got is not None:
        return got
    hubs = [h for h in store.hubs() if h.get("state", "joined") == "joined"]
    if not hubs or identity.offline():
        return 409, {"error": "no fleet to ask: this machine runs no hub and joined none "
                              "(`halo studio --fleet` here, or `halo fleet join` to one)", "hits": [], "harnesses": []}
    from halo_harness.fleet import protocol
    from halo_harness.fleet.relay import HubError, HubLink
    entry = hubs[0]
    key = store.key_for(entry)
    if key is None:
        return 409, {"error": f"no pair key for {entry.get('name')}: `halo fleet join` it again", "hits": [], "harnesses": []}
    link = HubLink(entry, key, identity.harness()["id"], timeout=60.0)
    try:
        body = link.request("POST", protocol.PREFIX + "/recall", protocol.doc(query=query, k=k))
    except HubError as e:
        return 502, {"error": f"{entry.get('name')}: {e}", "hits": [], "harnesses": []}
    finally:
        link.close()
    mine, note = local_hits(query, k)
    rows = [{"harness": identity.harness()["id"], "name": identity.fleet_name(), "local": True, "state": "answered",
             "hits": len(mine), "note": note or None}] + list(body.get("harnesses") or [])
    return 200, {"query": query, "k": k, "hits": merge([mine, body.get("hits") or []], k), "harnesses": rows,
                 "hub": entry.get("name"), "at": time.time()}


def table(hits: list, harnesses: Optional[list] = None) -> str:
    """The merged hits as one table: score, harness, title, excerpt; then who did not answer and why."""
    lines = [f"  {'score':>7}  {'harness':<18} {'title':<36} excerpt"] if hits else ["  no matches across the fleet"]
    for h in hits:
        lines.append(f"  {float(h.get('score') or 0):>+7.3f}  {str(h.get('harness') or '-')[:18]:<18} "
                     f"{str(h.get('title') or '')[:36]:<36} {str(h.get('excerpt') or '')[:90]}")
    for r in harnesses or []:
        if r.get("state") != "answered" or r.get("note"):
            lines.append(f"  ({r.get('name')}: {r.get('state')}{' -- ' + str(r['note']) if r.get('note') else ''})")
    return "\n".join(lines)


def fleet_text(query: str, k: int = 8) -> str:
    """`/recall --fleet <query>` in the TUI and in `halo -p`."""
    if not clean_query(query):
        return "/recall --fleet <query> -- every online harness of the fleet answers from its own index"
    status, body = ask(query, k)
    if status != 200:
        return f"/recall --fleet: {body.get('error')}"
    return f"/recall --fleet {clean_query(query)}\n\n" + table(body.get("hits") or [], body.get("harnesses") or [])
