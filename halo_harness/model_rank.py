"""halo_harness.model_rank -- the one order every model pick breaks a tie by (Halo 3.3.16.2, "from a session's
own review": an equal score went to the model whose NAME sorted first, so `claude-opus-4-1` beat
`claude-opus-4-6`; price and what was measured played no part).

`ranked(items, key)` sorts by the caller's terms, then what is still equal by the provider you have
credentials for (asked only for a tie that reaches it), then the ref. The two shipped orders:

strongest (`STRONGEST`): the kind's score, then (1) the measured first-time success for the kind here
(`MIN_N` checked tasks or more; fewer counts as `NEUTRAL_RATE`, neither proven nor failed), (2) within one
model family the newer version (`version_of`: `4.6` > `4.1`, `v4.1` > `v4`, `5.3` > `5`, a newer date
suffix > an older one; a model with a newer sibling among the candidates ranks below the newest of each
family, an id with no version counts as the newest of its own), (3) the larger context, (4) the lower
blended price (none counts last), (5) a provider with a key here, (6) the ref.
cheapest (`CHEAPEST`): the lower price (callers drop the unpriced), the higher score, then 1-3, 5, 6.

`why(a, b, key, names)` -> "same score as <b>: newer" when `a` won on a later term, else "". Items are dicts
(`ref`, `score`, `price`, `context`, `provider`, `measured` = (passed, n), `local`) or models_auto's
candidates (`ref`, `score`, `price`, `local`, `facts`).
"""

from __future__ import annotations

import re
from typing import Callable, Optional

MIN_N = 3
NEUTRAL_RATE = 0.5
# a best-at kind -> the outcome task kind (outcomes/kinds.py) its measured success is recorded under
TASK_KIND = {"code": "code", "research": "research", "visual": "media", "design": "media", "audio": "media",
             "video": "media", "pdf": "media"}
STRONGEST = ("score", "measured", "newer", "context", "cheaper")
CHEAPEST = ("cheaper", "score", "measured", "newer", "context")
_FIRST = {"score": "score", "cheaper": "price"}
_WORDS = {"newer": "newer", "context": "larger context", "cheaper": "cheaper", "score": "higher score",
          "main": "main's own model", "local": "runs here", "learned": "measured better here"}
_INF = float("inf")
_SPLIT = re.compile(r"([-_:/@ ]+)")
_NUM = re.compile(r"^v?(\d+(?:\.\d+)*)$")
_GLUED = re.compile(r"^([a-z]+)(\d+(?:\.\d+)*)$")
_DATE8 = re.compile(r"^(?:19|20)\d{6}$")
_ISO_DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})-(\d{2})-(\d{2})(?!\d)")


def version_of(ref) -> Optional[tuple]:
    """`(family, runs, date)`, None when the id carries no version. The family is the id with each version
    run as `#` and the date dropped (`-` `_` ` ` read alike, so `4-6` and `4.6` match); `runs` the version
    numbers in order (`claude-opus-4-6` -> ((4, 6),)); `date` YYYYMMDD or 0."""
    parts = _SPLIT.split(_ISO_DATE.sub(r"\1\2\3", str(ref or "").strip().lower()))
    toks, seps = parts[0::2], parts[1::2]
    skel: list = []
    runs: list = []
    date, prev_num = 0, False
    for i, tok in enumerate(toks):
        raw = seps[i - 1] if i else ""
        sep = raw if any(c in raw for c in ":/@") else ("-" if raw else "")
        m, g = _NUM.match(tok), _GLUED.match(tok)
        if _DATE8.match(tok):
            date, prev_num = max(date, int(tok)), False
        elif m and prev_num and sep == "-" and not tok.startswith("v"):
            runs[-1] = runs[-1] + tuple(int(x) for x in m.group(1).split("."))  # 4-6 is one version, 4.6
        elif m or g:
            runs.append(tuple(int(x) for x in (m or g).group(m and 1 or 2).split(".")))
            skel.append(sep + ("#" if m else g.group(1) + "#"))
            prev_num = True
        else:
            skel.append(sep + tok)
            prev_num = False
    return ("".join(skel), tuple(runs), date) if runs or date else None


def family_ranks(refs) -> dict:
    """`{ref: rank}`: 0 for the newest of its family among `refs` (and for an id with no version), 1 for the
    next older version, and so on; equal versions share a rank."""
    groups: dict = {}
    out = {}
    for ref in refs:
        out[ref] = 0
        v = version_of(ref)
        if v:
            groups.setdefault(v[0], []).append((ref, (v[1], v[2])))
    for members in groups.values():
        newest_first = sorted({k for _r, k in members}, reverse=True)
        for ref, k in members:
            out[ref] = newest_first.index(k)
    return out


def _field(it, name):
    if isinstance(it, dict):
        return it.get(name)
    facts = getattr(it, "facts", None) or {}
    if name == "context":
        return facts.get("context_tokens")
    if name == "provider":
        return facts.get("provider")
    return None if name == "measured" else getattr(it, name, None)


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _counted(it) -> Optional[tuple]:
    m = _field(it, "measured")
    return (int(m[0]), int(m[1])) if isinstance(m, (tuple, list)) and len(m) == 2 and (_num(m[1]) or 0) >= MIN_N \
        else None


def rate(it) -> float:
    m = _counted(it)
    return m[0] / m[1] if m else NEUTRAL_RATE


def term(name: str, it, ranks: dict):
    """One term's sort value (smaller ranks first)."""
    if name == "score":
        return -(_num(_field(it, "score")) or 0.0)
    if name == "measured":
        return -rate(it)
    if name == "newer":
        return ranks.get(_field(it, "ref"), 0)
    if name == "context":
        return -(_num(_field(it, "context")) or 0.0)
    if name == "cheaper":
        p = _num(_field(it, "price"))
        return _INF if p is None else p
    raise ValueError(f"unknown rank term {name!r}")


def key_for(names, items) -> Callable:
    """A sort key over `names` (the terms above) for these `items` (the family ranks are among them)."""
    ranks = family_ranks([_field(it, "ref") for it in items])
    return lambda it: tuple(term(n, it, ranks) for n in names)


def strongest_key(items) -> Callable:
    return key_for(STRONGEST, items)


def cheapest_key(items) -> Callable:
    return key_for(CHEAPEST, items)


def has_credentials(provider: str) -> bool:
    """True when this box has credentials for `provider` (config and env reads, never a network call); True
    when it cannot tell, so an unknown provider is never put last for it."""
    if not provider:
        return True
    try:
        from halo_harness.providers.config import listing_effective_env
        from halo_harness.providers.enablement import credentials_present
        return bool(credentials_present(provider, env=listing_effective_env()))
    except Exception:
        return True


def _keyed_check(keyed) -> Callable:
    cache: dict = {}

    def check(it) -> bool:
        provider = str(_field(it, "provider") or "")
        if _field(it, "local"):
            return True
        if isinstance(keyed, dict):
            return bool(keyed.get(provider, True))
        if provider not in cache:
            cache[provider] = has_credentials(provider) if keyed is None else bool(keyed(provider))
        return cache[provider]
    return check


def _ref(it) -> str:
    return str(_field(it, "ref") or "")


def ranked(items, key: Callable, *, keyed=None) -> list:
    """`items` sorted by `key(it)`; items still equal go to the provider you have credentials for (`keyed`: a
    `{provider: bool}`, a callable, or None = ask this box), then by ref."""
    items = list(items)
    keys = [key(it) for it in items]
    pre = sorted(zip(keys, items), key=lambda t: (t[0], _ref(t[1])))
    check, out, i = _keyed_check(keyed), [], 0
    while i < len(pre):
        j = i + 1
        while j < len(pre) and pre[j][0] == pre[i][0]:
            j += 1
        group = [it for _k, it in pre[i:j]]
        if len({str(_field(it, "provider") or "") for it in group}) > 1:
            group.sort(key=lambda it: (not check(it), _ref(it)))
        out += group
        i = j
    return out


def why(a, b, key: Callable, names, *, keyed=None) -> str:
    """"same score as <b>: newer" -- the term that put `a` before `b` when they tied on the first one; ""
    when the first term decided or there is no `b`."""
    if b is None or a is None:
        return ""
    ka, kb = key(a), key(b)
    if ka[0] != kb[0]:
        return ""
    same = f"same {_FIRST.get(names[0], names[0])} as {_ref(b)}"
    for n, x, y in zip(names, ka, kb):
        if x != y:
            return f"{same}: {_measured_words(a, b) if n == 'measured' else _WORDS.get(n, n)}"
    check = _keyed_check(keyed)
    return f"{same}: " + ("you have its provider's key" if check(a) != check(b) else "by name")


def _measured_words(a, b) -> str:
    mine, theirs = _counted(a), _counted(b)
    if mine:
        return f"measured {mine[0]}/{mine[1]} here"
    return f"{_ref(b)} measured {theirs[0]}/{theirs[1]} here" if theirs else "measured here"


def auto_tie(ordered: list, primary: Callable, key: Callable, names, main_ref: str, band: str) -> str:
    """models_auto._choose's tie words: "; a tie, so main's own model", "; a tie, so the local one" (band
    low), else "; same score as X: newer"; "" when the band's own rule decided."""
    if len(ordered) < 2 or primary(ordered[1]) != primary(ordered[0]):
        return ""
    best = ordered[0]
    if best.ref == main_ref:
        return "; a tie, so main's own model"
    if band == "low" and best.local:
        return "; a tie, so the local one"
    words = why(best, ordered[1], key, names)
    return f"; {words}" if words else ""


def measured_of(facts: dict, kind: str) -> Optional[tuple]:
    """`(passed, n)` for a best-at kind from a row's `measured.outcomes` (the task kind it maps to), or None."""
    task = TASK_KIND.get(kind)
    measured = facts.get("measured") if isinstance(facts, dict) else None
    outcomes = measured.get("outcomes") if isinstance(measured, dict) else None
    stat = outcomes.get(task) if isinstance(outcomes, dict) and task else None
    return (int(stat.get("passed") or 0), int(stat.get("n") or 0)) if isinstance(stat, dict) else None


def entry_item(ref: str, entry: dict, kind: str) -> dict:
    """A best-at index entry (models_best_at) as a rank item for `kind`."""
    from halo_harness.capabilities_strengths import blended_price
    facts = entry.get("facts") if isinstance(entry.get("facts"), dict) else {}
    return {"ref": ref, "score": (entry.get("scores") or {}).get(kind, 0), "price": blended_price({**facts, "ref": ref}),
            "context": facts.get("context_tokens"), "provider": facts.get("provider") or "",
            "measured": measured_of(facts, kind), "local": facts.get("local") is True}
