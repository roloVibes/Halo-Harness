"""tests.test_advise -- Halo 3.3.7.0 R4: the roster adviser (models_library/advise.py, advise_rules.py, advise_lines.py,
local_advise_cli.py, studio/local_advise_api.py) on a fixture roster, no model, no request:

1. the four kinds: no embedding model = gap; three 27B of one family = overlap (keep the measured best, retire the
   others, what it frees); the verifier on the coder's family = mismatch (point it at another family); a superseded
   family = freshness (the library's newer line); each with what it costs and one action that names its one thing;
   (the overlap never retires a model a lane names; a newer line already installed is the overlap's, not freshness);
2. ranked by value per gigabyte; the re-run fingerprint changes with the roster, an Ollama version or the hosts;
3. `halo local advise --json` and GET local/advise answer the same suggestions through the real inputs (a scratch home
   whose host's catalog and card come through the Ollama panel's READERS seam).
Run: python -m tests.test_advise
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.search_rig import SearchHome, box_card  # noqa: E402

test, TESTS = new_registry()


def row(name: str, params: str, gb: float, family: str = "qwen35", caps=("tools",), digest: str = "") -> dict:
    return {"model": name, "name": name, "size": int(gb * 1e9), "digest": digest or f"sha256:{abs(hash(name)) % 10 ** 8}",
            "capabilities": list(caps), "details": {"family": family, "parameter_size": params, "quantization_level": "Q4_K_M"}}


ROSTER = [row("qwen3.8:27b", "27.3B", 17.7, caps=("tools", "vision")), row("qwen3.8:27b-gpu", "27.3B", 17.7),
          row("qwen3.6:27b", "27.3B", 17.8), row("gemma3:12b", "11.8B", 8.2, family="gemma3", caps=("vision",)),
          row("qwen3-coder:30b", "30.5B", 18.6, family="qwen3moe")]


def inp(rows=None, lanes=None, version="0.40.13") -> dict:
    return {"hosts": [{"name": "box", "budget_gb": 23.6, "version": version, "rows": list(ROSTER if rows is None else rows)}],
            "profiles": [{"model": "qwen3.8:27b-gpu", "host": "box", "tools": "yes", "agentic_ready": True,
                          "speed": {"tok_s": 48.0}}],
            "lanes": lanes if lanes is not None else [{"lane": "main", "model": "qwen3.8:27b", "host": "box"},
                                                      {"lane": "coder", "model": "qwen3-coder:30b", "host": "box"},
                                                      {"lane": "verify", "model": "qwen3.8:27b", "host": "box"}],
            "gaps": [], "preview": None, "crashes": []}


@test
def test_the_four_kinds(ctx: Ctx):
    from halo_harness.models_library.advise import advise
    got = advise(None, inp=inp())
    by = {}
    for s in got["suggestions"]:
        by.setdefault(s["kind"], []).append(s)
    gap = next((s for s in by.get("gap", []) if "embedding" in s["says"]), None)
    ctx.check(f"no embedding model is a gap with a one-click add, got {gap}", gap and gap["action"]["verb"] == "add"
              and "memory search, dedupe" in gap["unlocks"] and gap["cost"]["download_gb"] > 0 and gap["cost"]["minutes"] >= 1
              and gap["cost"]["beside"] == "co-reside" and "ollama pull" in gap["action"]["cli"])
    ov = (by.get("overlap") or [None])[0]
    ctx.check(f"three 27B of one family overlap: keep the measured best, retire the others, got {ov}",
              ov and "3 qwen models of about 27.3B" in ov["says"] and "keep qwen3.8:27b-gpu" in ov["says"]
              and ov["action"]["verb"] == "retire" and "17.8 GB" in ov["frees"] and "retiring qwen3.6:27b" in ov["frees"]
              and "qwen3.8:27b stays while main, verify name it" in ov["says"])
    mm = (by.get("mismatch") or [None])[0]
    ctx.check(f"the verifier on the coder's family is a mismatch, got {mm}", mm and "same family as your coder" in mm["says"]
              and mm["action"]["verb"] in ("point", "add"))
    fr = [s for s in by.get("freshness", []) if s["says"].startswith("gemma3:12b")]
    ctx.check(f"a superseded family is freshness, got {[s['says'] for s in by.get('freshness', [])]}",
              fr and "newer line in the library: gemma4" in fr[0]["says"]
              and not any(s["says"].startswith("qwen3.6:27b") for s in by.get("freshness", [])))
    ctx.check("every suggestion has one action and its line", all(s["action"]["verb"] in ("add", "retire", "point", "none")
                                                                  and s["line"].startswith(f"[{s['kind']}] ")
                                                                  for s in got["suggestions"]))
    vals = [s["value_per_gb"] for s in got["suggestions"]]
    ctx.check(f"ranked by value per gigabyte, got {vals}", vals == sorted(vals, reverse=True))
    ctx.check(f"the head line, got {got['head']!r}", got["head"].startswith("roster: 5 models on 1 host; "))


@test
def test_a_full_roster_is_quiet_and_the_fingerprint_moves(ctx: Ctx):
    from halo_harness.models_library.advise import advise, fingerprint
    rows = [row("qwen3.8:27b", "27.3B", 17.7, caps=("tools", "vision")), row("nomic-embed-text:latest", "137M", 0.3,
                                                                                 family="nomic-bert", caps=("embedding",)),
            row("gemma4:12b", "12B", 8.0, family="gemma4")]
    lanes = [{"lane": "main", "model": "qwen3.8:27b", "host": "box"}, {"lane": "verify", "model": "gemma4:12b", "host": "box"}]
    got = advise(None, inp=inp(rows, lanes))
    ctx.check(f"no gap, no overlap, no mismatch, got {got['lines']}", got["kinds"]["gap"] == 0 and got["kinds"]["overlap"] == 0
              and got["kinds"]["mismatch"] == 0)
    a, b, c = fingerprint(inp()), fingerprint(inp(version="0.40.14")), fingerprint(inp(ROSTER[:-1]))
    ctx.check("a new Ollama version or a roster change re-runs it", len({a, b, c}) == 3 and a == fingerprint(inp()))


@test
def test_the_command_and_the_route(ctx: Ctx):
    from halo_harness.local_advise_cli import cmd_advise
    from halo_harness.studio.api import Request, dispatch
    with SearchHome(card=box_card(), catalog={"models": ROSTER}) as h:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_advise(["--host", "box", "--json"])
        cli = json.loads(out.getvalue())
        st, api = dispatch(Request(method="GET", path="local/advise", query={"host": "box"}, body={}, cwd=h.root,
                                   state_dir=h.state))
        text = io.StringIO()
        with contextlib.redirect_stdout(text):
            cmd_advise(["--host", "box"])
    ctx.check(f"halo local advise --json, got {rc} {cli.get('head')}", rc == 0 and cli["kinds"]["gap"] >= 1
              and cli["kinds"]["overlap"] == 1)
    ctx.check(f"GET local/advise answers the same, got {st} {api.get('head')} due={api.get('due')}", st == 200
              and [s["id"] for s in api["suggestions"]] == [s["id"] for s in cli["suggestions"]]
              and api["due"] is False and "nothing changed" in api["due_why"])
    ctx.check(f"the plain lines are numbered, got {text.getvalue()[:300]!r}", "  1. [" in text.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
