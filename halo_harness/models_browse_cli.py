"""halo_harness.models_browse_cli -- Halo 3.3.5.0 R2: `halo models browse`, the library browser in a terminal.

    halo models browse [--source ollama|hf|all] [--fits] [--host H] [--window N]
                       [--intent code|chat|docs|images|embed] [--family F] [--quant Q] [--cap C] [--max-gb N]
                       [--license L] [--limit N] [--why] [--refresh] [--json] [query...]
                       3.3.6.0 R2: [--preset P] [--need cap[=verified|declared|expected|any]]... [--for-role ROLE]
                       [--ask "a local coder that can use tools"] [--exclude-crashed] [--save-template [--model M]
                       [--lineup L]]
    halo models browse <source>/<id>     one model's tags (ollama/qwen3.5) or one repo's files (hf/<org>/<repo>)

3.3.6.0 R2: each capability carries its truth mark -- ✓ verified (probed here), ◇ declared (metadata), ≈ expected
(the family, size or name), ? needs a probe; `--why` adds each row's rank line, its two verdicts and its cost
preview (models_library/search.py). `--save-template` writes the preset as a `local-<preset>` lineup (or the role
entry of `--lineup`).

Each row: the fit word on the host (fits / tight / spill / no / ?), the name and tag or file, its size on disk,
the card's chips, and the pull line (nothing is pulled here: 3.3.5.0 R3). The same rows as Studio's Local ->
Library (models_library/browse.py).
"""

from __future__ import annotations

import argparse
import json
import sys

INTENT_WORDS = {"docs": "long", "long": "long", "documents": "long", "code": "code", "chat": "chat",
                "images": "images", "vision": "images", "embed": "embed"}
FIT_WORDS = {"fits": "fits", "tight": "tight", "spill": "spill", "no": "no", "unknown": "?", "cloud": "cloud"}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo models browse", description="browse Ollama's library and the Hugging Face "
                                "Hub, each row with its fit on a host (nothing is pulled)")
    p.add_argument("query", nargs="*", help="words to look for; or <source>/<id> for one model's tags or files")
    p.add_argument("--source", choices=("ollama", "hf", "all"), default="all")
    p.add_argument("--fits", action="store_true", help="only rows that fit the host at the window (fits or tight)")
    p.add_argument("--host", default="", help="the Ollama host to fit against (default: the first in ollama.hosts)")
    p.add_argument("--window", type=int, default=None, help="the window to fit at (default: the host's max_ctx or 32768)")
    p.add_argument("--intent", default="", help="code | chat | docs | images | embed: rank by fit for that intent")
    p.add_argument("--family", default="")
    p.add_argument("--quant", default="")
    p.add_argument("--cap", default="", help="tools | vision | embedding | thinking")
    p.add_argument("--max-gb", type=float, default=None, help="only rows at most this size on disk (GB)")
    p.add_argument("--license", default="")
    p.add_argument("--limit", type=int, default=40, help="rows to print (0: every row)")
    p.add_argument("--why", action="store_true", help="print each row's fit reason with its numbers")
    p.add_argument("--refresh", action="store_true", help="read the sites again (the cache is a day; a search an hour)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--preset", default="", help="coder | reasoner | bulk | compactor | verifier | security | multimodal | "
                   "embeddings | offline: the preset's filter bundle")
    p.add_argument("--need", action="append", default=[], help="cap[=verified|declared|expected|any], repeatable")
    p.add_argument("--for-role", default="", help="a lineup role (verify, coder, planner ...): its preset")
    p.add_argument("--ask", default="", help='a plain sentence: "a local coder that can use tools"')
    p.add_argument("--exclude-crashed", action="store_true", help="grey the models that crashed on this host, put them last")
    p.add_argument("--save-template", action="store_true", help="write --preset as a role template (a lineup)")
    p.add_argument("--model", default="", help="with --save-template: the model the role gets")
    p.add_argument("--lineup", default="", help="with --save-template: put the role in this lineup instead")
    return p


def _gb(n) -> str:
    if not isinstance(n, (int, float)) or n <= 0:
        return "?"
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


def _chips(row: dict) -> str:
    chips = (row.get("card") or {}).get("chips") or {}
    return " ".join(v for k in ("think", "tools", "vision", "purpose", "window") if (v := chips.get(k)))


def _marks(row: dict) -> str:
    return " ".join(f"{c['cap']}{c['glyph']}" for c in row.get("chips") or [])


def row_line(row: dict) -> str:
    fit = FIT_WORDS.get((row.get("fit") or {}).get("level") or "unknown", "?")
    name = row.get("name") or row.get("id")
    gated = " (gated)" if row.get("gated") else ""
    grey = "  [crashed here]" if row.get("crashed") else ""
    marks = f"  [{_marks(row)}]" if row.get("chips") else ""
    return (f"  {fit:<5} {name:<44} {_gb(row.get('size_bytes')):>8}  {_chips(row) or '-'}{gated}{marks}{grey}  ->  "
            f"{row.get('pull_line')}")


def _head(ans: dict) -> str:
    src = ans.get("sources") or {}
    words = []
    if "ollama" in src:
        words.append(f"Ollama: {src['ollama']}")
    if "hf" in src:
        words.append(f"Hugging Face: {src['hf']}")
    h = ans.get("host") or {}
    host = (f"fit on {h['name']} at {ans.get('window'):,}" + ("" if h.get("card") else " (no hardware card read yet)")
            if h.get("name") else "no Ollama host to fit against")
    return " · ".join(words + [host])


def _print_rows(rows: list, limit: int, why: bool) -> None:
    for r in rows[: limit or None]:
        print(row_line(r))
        if why:
            print(f"        {(r.get('fit') or {}).get('why', '')}")
            if r.get("why_this_rank"):
                v = r.get("verdicts") or {}
                rr = (v.get("role_ready") or {})
                ready = "yes" if rr.get("ok") else "not yet" if rr.get("ok") is None else "no"
                print(f"        fits: {(v.get('fits') or {}).get('word', '?')} · role-ready: {ready} ({rr.get('why', '')})")
                print(f"        cost: {(r.get('cost') or {}).get('text', '')}")
                print(f"        rank: {r['why_this_rank']}")
                if r.get("crashed"):
                    print(f"        {r['crashed']['line']}")


def cmd_models_browse(argv) -> int:
    a = _parser().parse_args(list(argv))
    from halo_harness.config.paths import bridge_home
    from halo_harness.models_library import browse
    state = bridge_home()
    if a.refresh:
        browse.refresh(state)
    words = [w for w in a.query if w]
    one = words[0] if len(words) == 1 and "/" in words[0] and words[0].split("/", 1)[0] in ("ollama", "hf") else ""
    if one:
        source, mid = one.split("/", 1)
        ans = browse.detail(state, source, mid, host=a.host, window=a.window)
        if a.json:
            print(json.dumps(ans, indent=2, default=str))
            return 0
        print(f"{one}: {len(ans['rows'])} {'tags' if source == 'ollama' else 'files'}"
              + (f" · fit on {ans['host']} at {ans['window']:,}" if ans.get("host") else "")
              + (f" · {ans['note']}" if ans.get("note") else ""))
        _print_rows(ans["rows"], a.limit, a.why)
        return 0 if ans["rows"] else 1
    intent = INTENT_WORDS.get(a.intent.lower(), "") if a.intent else ""
    if a.intent and not intent:
        print(f"halo models browse: --intent takes code, chat, docs, images or embed (not {a.intent!r})", file=sys.stderr)
        return 2
    if a.save_template:
        from halo_harness.models_library.presets import save_template
        ok, lines, _name = save_template(a.preset, state_dir=state, model=a.model, lineup=a.lineup)
        for line in lines:
            print(line if ok else f"halo models browse: {line}", file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1
    ans = browse.library(state, source=a.source, q=" ".join(words), host=a.host, window=a.window, fits=a.fits,
                         intent=intent, family=a.family, quant=a.quant, cap=a.cap, max_gb=a.max_gb, license=a.license,
                         per=2000, search=_spec(a))
    if a.json:
        print(json.dumps(ans, indent=2, default=str))
        return 0
    print(_head(ans))
    s = ans.get("search") or {}
    if s.get("bundle"):
        bd = s["bundle"]
        print(f"  search: {bd.get('title')} -- needs {', '.join(f'{k} {v}' for k, v in bd['needs'].items()) or 'nothing'}"
              + (f" · fit {', '.join(f'{k}={v}' for k, v in bd['fit'].items())}" if bd.get("fit") else "")
              + (f" · understood: {', '.join(s['understood'])}" if s.get("understood") else ""))
    for k, note in (ans.get("notes") or {}).items():
        if note:
            print(f"  ({'Ollama' if k == 'ollama' else 'Hugging Face'}: {note})")
    _print_rows(ans["rows"], a.limit, a.why)
    shown = min(len(ans["rows"]), a.limit or len(ans["rows"]))
    print(f"{ans['total']} rows" + (f" (the first {shown}: --limit 0 prints every row)" if shown < ans["total"] else "")
          + "; `halo models browse ollama/<model>` or `hf/<repo>` lists its tags or files")
    return 0


def _spec(a) -> dict:
    from halo_harness.models_library.search import norm_needs
    spec = {"preset": a.preset, "for_role": a.for_role, "sentence": a.ask, "needs": norm_needs(a.need),
            "exclude_crashed": a.exclude_crashed}
    return {k: v for k, v in spec.items() if v}
