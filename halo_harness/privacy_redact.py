"""halo_harness.privacy_redact -- the one redaction for what leaves this machine (Halo 3.4.1.2, PACKS-5 / SERVERS-6).

A saved replay, `halo export --sanitize`, `/export --sanitize`, `halo session export`, the report card's Markdown and
`halo bugreport` all call `redact`, so a spelling caught for one is caught for all:

    redact(obj, *, root=None, strict=False, known=None) -> obj        (a str, or a list / dict walked leaf by leaf)

secrets   redact.sanitize_text's shapes (keys by prefix, NAME=value, `"name": "value"`, headers, URL credentials, PEM),
          plus Groq `gsk_`, xAI `xai-`, Perplexity `pplx-` keys, JWTs, a token in a URL (`#t=`, `?t=`, `?k=`,
          `&key=`, `access_token=` ...), a bare random token of 30+ characters, and the current values of this
          process's secret environment variables (and the caller's `known`), also percent-encoded or JSON-escaped;
          `strict` (the bug report's wider surface) adds every 32+ hex and 40+ base64 run
paths and  live/replay_private.scrub: the project's paths relative (`root`), the home `~` (any spelling, 8.3 too), the
names     user and machine names `<user>` / `<machine>` everywhere but in a path inside the project and the title,
          checked once more after percent-decoding and NFKC folding; control characters dropped
A dict keeps the redactor's JSON pass too (a `"NAME": "value"` pair split across a key and its value).
"""

from __future__ import annotations

import json
import os
import re
from typing import Iterable, Optional
from urllib.parse import quote, unquote

RED = "<redacted>"
_EXTRA = (
    re.compile(r"(?<![A-Za-z0-9])gsk_[A-Za-z0-9]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])xai-[A-Za-z0-9]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])pplx-[A-Za-z0-9]{20,}"),
    re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]{4,}){1,2}"),  # a JWT (or its first parts)
    re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{20,}"),
)
#: a token or key carried in a URL: Studio's `#t=`, a pack's raw-file `?k=`, the usual query names
_URL_KEY = re.compile(r"(?i)([#?&;](?:t|k|token|key|api[_-]?key|access[_-]?token|auth|sig|signature|code)=)"
                      r"(?!<redacted>)[^&#\s\"'<>\\]{6,}")
_BARE = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{30,}(?![A-Za-z0-9_-])")
_HEX_RUN = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{32,}(?![0-9A-Za-z])")
_B64_RUN = re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{40,}={0,2}(?![A-Za-z0-9+/])")


def _random(tok: str) -> bool:
    """A random token, not a word or an identifier: 3+ digits, 3+ capitals and 3+ small letters."""
    return (sum(c.isdigit() for c in tok) >= 3 and sum(c.isupper() for c in tok) >= 3
            and sum(c.islower() for c in tok) >= 3)


def env_secret_values(extra: Optional[Iterable[str]] = None) -> tuple:
    """Every current value of a secret-shaped environment variable of this process (and `extra`), 4+ characters (the
    bug report's floor before 3.4.1.2)."""
    from halo_harness.redact import _GENERIC_SECRET_NAME, _SECRET_ENV_NAMES
    generic = re.compile(f"^(?:{_GENERIC_SECRET_NAME})$", re.IGNORECASE)
    names = {n.upper() for n in _SECRET_ENV_NAMES} - {"DATABRICKS_HOST"}
    vals = [v for k, v in os.environ.items() if v and (k.upper() in names or generic.match(k))]
    vals += [v for v in extra or () if isinstance(v, str)]
    return tuple(sorted({v for v in vals if len(v) >= 4}, key=len, reverse=True))


def _spellings(value: str) -> list:
    out = [value, json.dumps(value)[1:-1], json.dumps(value, ensure_ascii=False)[1:-1], quote(value, safe=""),
           quote(value)]
    return [s for s in dict.fromkeys(out) if len(s) >= 4]


def secrets_text(s: str, *, strict: bool = False, known: tuple = ()) -> str:
    from halo_harness.redact import sanitize_text
    s = sanitize_text(s)
    for pat in _EXTRA:
        s = pat.sub(RED, s)
    s = _URL_KEY.sub(lambda m: m.group(1) + RED, s)
    s = _BARE.sub(lambda m: RED if _random(m.group(0)) else m.group(0), s)
    if strict:
        s = _B64_RUN.sub(RED, _HEX_RUN.sub(RED, s))
    for value in known:
        for spelled in _spellings(value):
            s = re.sub(re.escape(spelled), RED, s, flags=re.IGNORECASE)
    import unicodedata
    for decoded in (unquote(s), unicodedata.normalize("NFKC", s)):  # it held one once decoded or folded
        if decoded != s and secrets_text(decoded, strict=strict, known=known) != decoded:
            return secrets_text(decoded, strict=strict, known=known)
    return s


def _leaves(obj, fn):
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [_leaves(v, fn) for v in obj]
    if isinstance(obj, dict):
        return {(fn(k) if isinstance(k, str) else k): _leaves(v, fn) for k, v in obj.items()}
    return obj


def redact(obj, *, root=None, strict: bool = False, known: Optional[Iterable[str]] = None, homes=None, users=None,
           machines=None):
    """`obj` with every secret, path and name rule above applied; a dict that the JSON pass would break comes back as
    `{"type": ..., "_sanitize_error": ...}` (never the original)."""
    from halo_harness.live.replay_private import scrub
    vals = env_secret_values(known)
    out = _leaves(obj, lambda s: secrets_text(s, strict=strict, known=vals))
    if isinstance(out, (dict, list)):
        from halo_harness.redact import sanitize_text
        try:
            out = json.loads(sanitize_text(json.dumps(out, ensure_ascii=False)))
        except (TypeError, ValueError):
            kind = obj.get("type", "?") if isinstance(obj, dict) else "?"
            return {"type": kind, "_sanitize_error": "redaction produced invalid JSON; node omitted"}
    return scrub(out, root, homes=homes, users=users, machines=machines)
