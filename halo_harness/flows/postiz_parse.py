"""halo_harness.flows.postiz_parse -- reading what the Postiz CLI prints.

* `parse_json(text)`: the first JSON value in the output (the CLI may print a
  banner line before it), None when there is none.
* `parse_integrations(text)`: `[{id, platform, name, disabled}]` from the JSON
  list `integrations:list` prints (items carry `id`, `identifier`, `name`,
  `disabled`), else from a column table with a header row.
* `find_id(value)`: the post id in a `posts:create` answer (`postId`, `id`,
  or the first one inside a list or a `posts` / `data` wrapper).
* `metric_totals(raw)` / `format_totals(totals, posts)`: views, likes,
  comments and shares out of an analytics answer, which is either a list of
  `{label, data: [{total, date}], ...}` series (the latest point counts) or
  a plain `{views: n, ...}` mapping.
* `parse_every("6h")`: seconds for `30s|15m|6h|1d|1w`, None when unreadable.
"""

from __future__ import annotations

import json
import re
from typing import Optional

_ID_KEYS = ("postId", "post_id", "id")
_WRAPPERS = ("posts", "post", "data", "result", "integrations")
_METRIC_LABELS = {
    "views": ("views", "view", "impressions", "impression", "plays", "play", "video_views", "views_count"),
    "likes": ("likes", "like", "favorites", "favourites", "like_count"),
    "comments": ("comments", "comment", "replies", "reply", "comment_count"),
    "shares": ("shares", "share", "retweets", "reposts", "repost", "shares_count"),
}
_LABEL_KEY = {name: key for key, names in _METRIC_LABELS.items() for name in names}


def parse_json(text):
    s, dec = str(text or ""), json.JSONDecoder()
    for m in re.finditer(r"[\[{]", s):
        try:
            return dec.raw_decode(s, m.start())[0]
        except ValueError:
            continue
    return None


def find_id(value) -> str:
    if isinstance(value, dict):
        for k in _ID_KEYS:
            if value.get(k) not in (None, ""):
                return str(value[k])
        for k in _WRAPPERS:
            if k in value and (r := find_id(value[k])):
                return r
    elif isinstance(value, list):
        for item in value:
            if r := find_id(item):
                return r
    return ""


def _truthy(v) -> bool:
    return v is True or str(v).strip().lower() in ("true", "yes", "y", "1", "disabled")


def _integration(d: dict) -> dict:
    platform = d.get("identifier") or d.get("platform") or d.get("providerIdentifier") or d.get("type") or ""
    return {"id": str(d.get("id")), "platform": str(platform).strip().lower(),
            "name": str(d.get("name") or d.get("display") or ""), "disabled": _truthy(d.get("disabled"))}


def _table(text: str) -> list:
    cols, rows = None, []
    for line in str(text or "").splitlines():
        cells = [c.strip() for c in re.split(r"\s*[|│┃]\s*|\t|\s{2,}", line) if c.strip()]
        low = [c.lower() for c in cells]
        if cols is None:
            if "id" in low and any(k in low for k in ("platform", "identifier", "provider", "type")):
                cols = {name: low.index(name) for name in ("id", "platform", "identifier", "provider", "type", "name",
                                                          "disabled") if name in low}
            continue
        if len(cells) <= max(cols.values()) or set(line.strip()) <= set("-+=|─┼│ "):
            continue
        get = lambda *names: next((cells[cols[n]] for n in names if n in cols), "")  # noqa: E731
        rows.append(_integration({"id": get("id"), "identifier": get("platform", "identifier", "provider", "type"),
                                  "name": get("name"), "disabled": get("disabled")}))
    return rows


def parse_integrations(text) -> list:
    data = parse_json(text)
    if isinstance(data, dict):
        data = next((data[k] for k in _WRAPPERS if isinstance(data.get(k), list)), [])
    if isinstance(data, list):
        return [_integration(d) for d in data if isinstance(d, dict) and d.get("id")]
    return _table(text)


def _number(v) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and re.fullmatch(r"\s*-?\d+(\.\d+)?\s*", v):
        return float(v)
    return None


def _series_value(item: dict) -> Optional[float]:
    points = item.get("data")
    if isinstance(points, list) and points:
        last = points[-1]
        return _number(last.get("total", last.get("value", last.get("count"))) if isinstance(last, dict) else last)
    return _number(item.get("total", item.get("value")))


def metric_totals(raw) -> dict:
    out: dict = {}

    def add(label, value) -> None:
        key = _LABEL_KEY.get(re.sub(r"[^a-z0-9]+", "_", str(label).lower()).strip("_"))
        if key and value is not None:
            out[key] = out.get(key, 0) + value

    def walk(node) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if "label" in node and any(k in node for k in ("data", "total", "value")):
                add(node["label"], _series_value(node))
                return
            for k, v in node.items():
                if _number(v) is not None:
                    add(k, _number(v))
                elif isinstance(v, (list, dict)):
                    walk(v)

    walk(raw)
    return {k: int(v) if float(v).is_integer() else v for k, v in out.items()}


def format_totals(totals: dict, posts: int = 0) -> str:
    parts = [f"{k} {totals[k]}" for k in ("views", "likes", "comments", "shares") if k in totals]
    return (", ".join(parts) + (f" across {posts} post{'s' if posts != 1 else ''}" if posts else "")) if parts else ""


def parse_every(text) -> Optional[float]:
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([smhdw])\s*", str(text or "").lower())
    return float(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[m.group(2)] if m else None
