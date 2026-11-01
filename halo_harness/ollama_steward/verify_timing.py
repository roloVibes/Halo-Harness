"""halo_harness.ollama_steward.verify_timing -- the server log's reply rates for the fix loop (Halo 3.3.8.0 R4;
docs/MODELS-steward-servers.md "Measured in tok/s").

An OpenAI-dialect ledger line (llama-server, LM Studio, mlx_lm.server, the pool) carries no Ollama timing, so its
`eval_tok_s` is None and a fix judged from the ledger alone was measured in trims, cuts and errors only. The server's
own log prints a rate per reply (llama.cpp's print_timing: `eval time = ... tokens per second` -> a `timing` event,
server_rules.classify), so the before / after of a server-side fix folds those in:

    rates(state_dir, host, model=None, *, since=None, until=None, last=None, first=None) -> [tok/s]
        the `timing` events of that server (its name is the events' host) and model, oldest first, inside
        [since, until) (epoch seconds); `last` keeps the newest N, `first` the oldest N
    fold(stats, rates_) -> stats with `tok_s` the median of `rates_` when the ledger measured none, and `tok_s_from`
        ("the ledger" | "the server log's timing" | "")
Reads only.
"""

from __future__ import annotations

import statistics
from typing import Optional


def _same(a, b) -> bool:
    if not a or not b:
        return True
    from halo_harness.ollama_steward.profiles import short_model
    from halo_harness.providers.ollama import ollama_names_match
    return ollama_names_match(a, b) or short_model(a) == short_model(b) or str(a).lower() in str(b).lower() \
        or str(b).lower() in str(a).lower()


def rates(state_dir, host: str, model: Optional[str] = None, *, since: Optional[float] = None,
          until: Optional[float] = None, last: Optional[int] = None, first: Optional[int] = None) -> list:
    from halo_harness.ollama_steward.ledger import parse_at
    from halo_harness.ollama_steward.server_events import read_events
    if state_dir is None or not host:
        return []
    out = []
    for e in read_events(state_dir, since=7 * 86400.0, kind="timing", host=host):
        t = parse_at(e.get("at")) or 0.0
        if (since is not None and t < since) or (until is not None and t >= until) or not _same(e.get("model"), model):
            continue
        v = (e.get("data") or {}).get("eval_tok_s")
        if isinstance(v, (int, float)) and v > 0:
            out.append(float(v))
    if last:
        out = out[-int(last):]
    if first:
        out = out[:int(first)]
    return out


def fold(stats: dict, rates_: list) -> dict:
    out = dict(stats or {})
    if isinstance(out.get("tok_s"), (int, float)):
        out.setdefault("tok_s_from", "the ledger")
        return out
    if rates_:
        out.update(tok_s=round(statistics.median(rates_), 1), tok_s_from="the server log's timing",
                   timed=len(rates_))
    else:
        out.setdefault("tok_s_from", "")
    return out
