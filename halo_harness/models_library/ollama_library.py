"""halo_harness.models_library.ollama_library -- Halo 3.3.5.0 R2: Ollama's library, read from ollama.com.

    parse_catalog(html) -> [entry]   https://ollama.com/library: one `<li>` per model under `<div id="repo">`
    parse_tags(html, model) -> [tag] https://ollama.com/library/<model>/tags: one `div.group px-4 py-3` per tag
    catalog(state_dir, refresh=False) -> {models, source, at, note}
    tags(state_dir, model, refresh=False) -> {tags, source, at, note}

entry {name, description, capabilities [tools, vision, thinking, embedding, audio, ...], cloud, sizes ["8b", ...],
pulls ("120.7M"), pulls_n, tags_count, updated ("1 year ago"), updated_at (the title's date)}; the chips are told
apart by their class: `bg-indigo-50` a capability, `bg-cyan-50` cloud, `bg-[#ddf4ff]` a size.
tag {tag ("9b"), name ("qwen3.5:9b"), size_text, size_bytes (the smaller of a range; decimal GB as the page
prints it), context, context_text ("256K"), input ["Text", "Image"], latest, digest, updated}; a cloud tag (no
size cell) is left out.

The parsers are pinned to the page's markup (tests/fixtures/library/*.html): when the markup moves, ShapeChanged
is raised, one test fails, and the source answers from the snapshot (snapshot.py) and says why. Under
BRIDGE_TEST_NO_BACKGROUND_NET the source is the snapshot only.
"""

from __future__ import annotations

import html as _html
import re
from typing import Optional

from halo_harness.models_library import cache, snapshot

CATALOG_URL = "https://ollama.com/library"
TAGS_URL = "https://ollama.com/library/{model}/tags"
_LI = '<li  class="flex items-baseline'
_CHIP = re.compile(r'<span\s+class="inline-flex items-center rounded-md (bg-\S+)[^"]*">([^<]+)</span>')
_NAME = re.compile(r'<a href="/library/([^"/?#]+)"')
_DESC = re.compile(r'<p class="max-w-lg[^"]*">(.*?)</p>', re.S)
_STAT = re.compile(r'<span\s*>([^<]+)</span>\s*<span class="hidden sm:flex">&nbsp;(Pulls|Tags)</span>')
_UPDATED = re.compile(r'<span class="flex items-center" title="([^"]*)">.*?Updated&nbsp;</span>\s*<span\s*>([^<]+)</span>', re.S)
_TAG_BLOCK = '<div class="group px-4 py-3">'
_TAG = re.compile(r'<input class="command hidden" value="([^"]+)"')
_CELL = re.compile(r'<p\s+class="col-span-2 text-neutral-500 text-\[13px\]">([^<]*)</p>')
_INPUT = re.compile(r'<div class="col-span-2 text-neutral-500 text-\[13px\] ">\s*(.*?)\s*</div>', re.S)
_DIGEST = re.compile(r'<span class="font-mono text-\[11px\]">([0-9a-f]+)</span>&nbsp;(?:·|&middot;|\S)&nbsp;([^<\n]+)')
_SIZE = re.compile(r"(\d+(?:\.\d+)?)\s*(KB|MB|GB|TB)", re.I)
_UNITS = {"kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12}


class ShapeChanged(ValueError):
    """The page's markup is not the one the parser was pinned to."""


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def count_of(text: str) -> Optional[int]:
    """"120.7M" -> 120700000, "93" -> 93."""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([KMB]?)\s*$", str(text or ""), re.I)
    if not m:
        return None
    mult = {"": 1, "k": 1e3, "m": 1e6, "b": 1e9}[m.group(2).lower()]
    return int(round(float(m.group(1)) * mult))


def size_of(text: str) -> Optional[int]:
    """"6.6GB - 7.6GB" -> 6600000000 (the smaller), "274MB" -> 274000000."""
    got = [float(n) * _UNITS[u.lower()] for n, u in _SIZE.findall(str(text or ""))]
    return int(min(got)) if got else None


def context_of(text: str) -> Optional[int]:
    """"256K" -> 262144, "2K" -> 2048, "1M" -> 1048576."""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([KM])\s*$", str(text or ""), re.I)
    if not m:
        return None
    return int(float(m.group(1)) * (1024 if m.group(2).upper() == "K" else 1024 * 1024))


def parse_catalog(page: str) -> list:
    start = page.find('<div  id="repo">')
    if start < 0 or _LI not in page[start:]:
        raise ShapeChanged('no <div id="repo"> list of <li> models on the library page')
    out = []
    for item in page[start:].split(_LI)[1:]:
        item = item.split("</li>", 1)[0]
        name = _NAME.search(item)
        if not name:
            raise ShapeChanged("a library <li> without its /library/<model> link")
        chips = _CHIP.findall(item)
        stats = {kind: val.strip() for val, kind in _STAT.findall(item)}
        upd = _UPDATED.search(item)
        desc = _DESC.search(item)
        out.append({"name": name.group(1), "description": _text(desc.group(1)) if desc else "",
                    "capabilities": [t.strip() for c, t in chips if c == "bg-indigo-50"],
                    "cloud": any(c == "bg-cyan-50" for c, _t in chips),
                    "sizes": [t.strip() for c, t in chips if c.startswith("bg-[#ddf4ff]")],
                    "pulls": stats.get("Pulls", ""), "pulls_n": count_of(stats.get("Pulls", "")),
                    "tags_count": count_of(stats.get("Tags", "")),
                    "updated": upd.group(2).strip() if upd else "", "updated_at": upd.group(1).strip() if upd else ""})
    if not out:
        raise ShapeChanged("the library page lists no model")
    return out


def parse_tags(page: str, model: str) -> list:
    blocks = page.split(_TAG_BLOCK)[1:]
    if not blocks:
        raise ShapeChanged(f"no tag rows on the tags page of {model}")
    out = []
    for b in blocks:
        tag = _TAG.search(b)
        if not tag:
            continue
        cells = _CELL.findall(b)
        if len(cells) < 2:
            continue  # a cloud tag (`:20b-cloud`): no size, nothing to install
        inp = _INPUT.search(b)
        dig = _DIGEST.search(b)
        full = tag.group(1)
        out.append({"tag": full.split(":", 1)[1] if ":" in full else full, "name": full,
                    "size_text": cells[0].strip(), "size_bytes": size_of(cells[0]),
                    "context_text": cells[1].strip(), "context": context_of(cells[1]),
                    "input": [w.strip() for w in _text(inp.group(1)).split(",") if w.strip()] if inp else [],
                    "latest": ">latest</span>" in b, "digest": dig.group(1) if dig else "",
                    "updated": _html.unescape(dig.group(2)).strip() if dig else ""})
    if not out:
        raise ShapeChanged(f"no tag names on the tags page of {model}")
    return out


def _snap_note(why: str) -> str:
    return f"the snapshot from {snapshot.taken()}: {why}"


def catalog(state_dir, *, refresh: bool = False) -> dict:
    """The catalog, live (a day in the cache) or the snapshot; `source` "live" | "snapshot <date>"."""
    if cache.offline() and "fetch" not in cache.SEAMS:
        return {"models": snapshot.models(), "source": f"snapshot {snapshot.taken()}", "at": snapshot.taken_at(),
                "note": _snap_note("background network reads are off")}
    try:
        models, at, how = cache.cached(state_dir, "ollama:catalog", CATALOG_URL, cache.CATALOG_TTL_S, parse_catalog,
                                       refresh=refresh)
        return {"models": models, "source": "live", "at": at, "note": "from the cache" if how == "cache" else ""}
    except (cache.FetchError, ShapeChanged) as e:
        return {"models": snapshot.models(), "source": f"snapshot {snapshot.taken()}", "at": snapshot.taken_at(),
                "note": _snap_note(str(e))}


def tags(state_dir, model: str, *, refresh: bool = False) -> dict:
    """One model's tags, live (a day) or the snapshot's."""
    model = str(model or "").strip().split(":", 1)[0]
    snap = snapshot.tags_of(model)
    if cache.offline() and "fetch" not in cache.SEAMS:
        return {"tags": snap, "source": f"snapshot {snapshot.taken()}", "at": snapshot.taken_at(),
                "note": _snap_note("background network reads are off")}
    try:
        got, at, how = cache.cached(state_dir, f"ollama:tags:{model}", TAGS_URL.format(model=model), cache.CATALOG_TTL_S,
                                    lambda t: parse_tags(t, model), refresh=refresh)
        return {"tags": got, "source": "live", "at": at, "note": "from the cache" if how == "cache" else ""}
    except (cache.FetchError, ShapeChanged) as e:
        return {"tags": snap, "source": f"snapshot {snapshot.taken()}", "at": snapshot.taken_at(), "note": _snap_note(str(e))}
