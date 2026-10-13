"""halo_harness.perm_words -- word-level helpers for the DENY/ASK side of
the permission engine (3.0.2.0 review fix pass, round A): `{a,b}` brace
expansion of a reader's file word, and the string a shell receives through
`-c`. Leaf module; it only finds text a shell would really use.
"""
from __future__ import annotations

import re

_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh"})
_C_CLUSTER_RE = re.compile(r"-[A-Za-z]*c[A-Za-z]*")


# ---- words -----------------------------------------------------------------

def brace_expand(word: str, _limit: int = 64) -> list:
    """`.{env,bak}` -> [`.env`, `.bak`] (nested groups too, at most `_limit`
    results); a word with no comma group comes back unchanged."""
    m = None
    depth = 0
    for i, c in enumerate(word):
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}" and depth:
            depth -= 1
            if depth == 0:
                m = (start, i)
                break
    if m is None:
        return [word]
    start, end = m
    inner, parts, buf, d = word[start + 1:end], [], [], 0
    for c in inner:
        if c == "," and d == 0:
            parts.append("".join(buf))
            buf = []
            continue
        d += c == "{"
        d -= c == "}" and d > 0
        buf.append(c)
    parts.append("".join(buf))
    if len(parts) < 2:
        tail = brace_expand(word[end + 1:], _limit)
        return [word[:end + 1] + t for t in tail][:_limit]
    out: list = []
    for p in parts:
        for w in brace_expand(word[:start] + p + word[end + 1:], _limit):
            out.append(w)
            if len(out) >= _limit:
                return out
    return out


def shell_c_payload(tokens: list):
    """The command string `sh|bash|zsh|dash|ksh [-opts] -c STRING` (also a
    clustered `-lc`/`-ec`) hands to the shell, or None. `tokens` must start
    at the shell word (wrappers already stripped)."""
    if not tokens or tokens[0].replace("\\", "/").rsplit("/", 1)[-1] not in _SHELLS:
        return None
    has_c = False
    i = 1
    while i < len(tokens) and tokens[i][:1] in ("-", "+") and tokens[i] not in ("-", "--"):
        tok = tokens[i]
        if _C_CLUSTER_RE.fullmatch(tok):
            has_c = True
        elif tok in ("-o", "+o", "-O", "+O"):
            i += 1
        i += 1
    if tokens[i:i + 1] == ["--"]:
        i += 1
    return tokens[i] if has_c and i < len(tokens) else None
