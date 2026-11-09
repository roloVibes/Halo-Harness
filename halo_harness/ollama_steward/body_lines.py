"""halo_harness.ollama_steward.body_lines -- a log line that carries a request's text is not a server event (Halo
3.3.14.0 R2, REVIEW #23 LOCAL-3).

    is_body_line(line) -> bool   Ollama's debug `prompt="..."` / `msg="chat request"` lines, a `"messages":` /
        `"content":` / `"prompt":` JSON body (llama-server --verbose, LM Studio's echoed request), and the member lines of
        a pretty-printed body (`  "role": "user",`, `{`, `],`)
    count(lines) -> int          how many of `lines` are body lines (the scans add it to the server's read state as
        `body_lines_skipped`)

The steward's classifiers (server_rules.classify, server_rules_hf.classify, engines/steward.classify) and its line
readers (server_context.Rules, server_context_hf.Rules) skip these lines, so a prompt or a tool result that says "CUDA
out of memory" or "exited with code 1" never becomes a finding, a crash fingerprint or a reply-cut proposal. The host
replaces the same lines by their size before a peer reads a log (host/routes_view.scrub_line).
"""

from __future__ import annotations

import re

BODY = re.compile(r'(\bprompt="|"prompt"\s*:|"messages"\s*:|"content"\s*:|\bmessages=\[|\bsystem="|'
                  r'msg="(chat|completion|generate|embed) request")')
_MEMBER = re.compile(r'^\s*(?:[{}\[\]],?\s*$|"[^"]*"\s*:)')


def is_body_line(line) -> bool:
    text = str(line or "")
    return bool(BODY.search(text) or _MEMBER.match(text))


def count(lines) -> int:
    return sum(1 for x in lines or () if is_body_line(x))


def noted(st: dict, lines) -> dict:
    """`st` (a server's read state in the steward's ledger folder) with `body_lines_skipped` raised by these lines'."""
    n = count(lines)
    if n:
        st["body_lines_skipped"] = int(st.get("body_lines_skipped") or 0) + n
    return st
