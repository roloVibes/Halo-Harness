"""tests.test_slash_ollama -- `/ollama` (Halo 3.3.4.0 R5; commands/ollama_slash.py, commands/builtins._cmd_ollama,
tui/slash._handle_ollama) on the panel fixture (tests/helpers/ollama_panel_seed.py through
tests/test_ollama_steward_api.Panel: two hosts, a Hugging Face local server, the ledger, a note, review mode;
the card and the catalog through studio/ollama_hosts_view.READERS). No server, no model call:

1. bare `/ollama`: the job's status line, the last note (its cost line), each host's card line, the last hour's
   rollups, the local server's lines, "next: the Models section"; after a review pass, the proposals with
   `halo ollama steward apply <id>`; after an apply, the profile and who set it;
2. `/ollama findings | plan | explain <kind>` pass through to the CLI's formatters; `--host` narrows;
3. `/ollama hosts` keeps the per-host analysis (2.0.3 round 3) and, in the TUI, its dialog; every other
   `/ollama` prints in the transcript.
Run: python -m tests.test_slash_ollama
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import ollama_panel_seed as S  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_ollama_steward_api import Panel  # noqa: E402

test, TESTS = new_registry()


def _slash(args: str = "") -> str:
    from halo_harness.commands.builtins import HeadlessFacade, _cmd_ollama
    return _cmd_ollama(args, HeadlessFacade(cwd=Path.cwd()))


@test
def test_bare_ollama_is_the_stewards_view(ctx: Ctx):
    with Panel(hosts=[S.PC, S.SAMUS]) as p:
        text = _slash("")
        ctx.check(f"the mode and the job's status line, got {text[:200]!r}", text.startswith("Ollama steward (mode review)")
                  and "steward job: not running" in text)
        ctx.check("the last note and its cost line", f"last note" in text and S.NOTE in text and S.COST in text)
        ctx.check("pc's card line: the GPU, the server's settings, ComfyUI",
                  "'pc' (http://192.0.2.10:11434): GPU 0: a 24 GB card" in text and "KV cache f16" in text
                  and "other: ComfyUI 2.0 GiB" in text)
        ctx.check("the last hour's rollups per model", "qwen3.8:27b: 7 calls" in text and "trims 1, cuts 1" in text
                  and "qwen3.5:9b: 2 calls" in text)
        ctx.check("the local server's lines and the rest of Hugging Face", "local server 'llama-box'" in text
                  and "llama-3.1-8b: 3 calls" in text and "next, the Models section (3.3.5.0)" in text)
        ctx.check("no proposal before a pass", "proposals (review mode)" not in text)
        p.api("POST", "ollama/steward/run")
        text = _slash("")
        ctx.check("the review pass's proposals with their apply line",
                  "proposals (review mode):" in text and "halo ollama steward apply window-small-" in text)
        fid = next(r["id"] for r in p.api("GET", "ollama/steward")[1]["proposals"] if r["rule"] == "window-small")
        p.api("POST", "ollama/steward/apply", {"id": fid})
        text = _slash("--host pc")
        ctx.check(f"after the apply: the profile and who set it, only pc, got {text[-600:]!r}",
                  "profile qwen3.8:27b: num_ctx 65536 (by steward)" in text and "'samus'" not in text
                  and f"[{fid}]" not in text)
        ctx.check("a host that is not configured says so", "no configured host named 'nowhere'" in _slash("--host nowhere"))
        ctx.check("never a model call", p.model_calls == [])


@test
def test_findings_plan_and_explain_pass_through(ctx: Ctx):
    with Panel(hosts=[S.PC, S.SAMUS]) as p:
        found = _slash("findings")
        ctx.check(f"findings: the CLI's lines, got {found[:300]!r}", "[window-small-" in found and "change: num_ctx" in found)
        ctx.check("findings --host samus: none there", "no findings" in _slash("findings --host samus"))
        plan = _slash("plan --host pc")
        ctx.check(f"plan: the fit plan's lines, got {plan[:300]!r}", plan.startswith("'pc':") and "one-at-a-time" in plan
                  and "OLLAMA_KV_CACHE_TYPE=q8_0" in plan)
        ctx.check("explain cpu-spill answers from the knowledge", "cpu-spill" in _slash("explain cpu-spill").lower())
        ctx.check("an unknown argument says what there is", "/ollama findings | plan" in _slash("frobnicate"))
        ctx.check("never a model call", p.model_calls == [])


class _App:
    def __init__(self):
        self.ran: list = []
        self.notes: list = []
        self.screens: list = []
        self.controller = SimpleNamespace(run_slash=lambda name, args: self.ran.append((name, args)) or f"/{name} {args}")
        self.transcript = SimpleNamespace(add_note=lambda text, kind="note": self.notes.append(text))

    def run_worker(self, work, **kw):
        return work()

    def call_from_thread(self, fn, *a, **k):
        return fn(*a, **k)

    def push_screen(self, screen):
        self.screens.append(type(screen).__name__)

    def notify(self, text, **kw):
        self.notes.append(text)


@test
def test_the_tui_prints_and_hosts_opens_the_dialog(ctx: Ctx):
    from halo_harness.tui import slash
    app = _App()
    asyncio.run(slash._handle_ollama(app, "findings --host pc"))
    ctx.check(f"/ollama findings runs the builtin and prints, got {app.ran} {app.notes}",
              app.ran == [("ollama", "findings --host pc")] and app.notes == ["/ollama findings --host pc"])
    seen = []
    saved = slash._ollama_analyses
    slash._ollama_analyses = lambda args: seen.append(args) or []
    try:
        asyncio.run(slash._handle_ollama(app, "hosts --host pc --refresh"))
    finally:
        slash._ollama_analyses = saved
    ctx.check(f"/ollama hosts opens the dialog with the rest, got {seen} {app.screens}",
              seen == ["--host pc --refresh"] and app.screens == ["OllamaStatus"])
    from halo_harness.providers import ollama_panel
    calls = []
    real = ollama_panel.analyze_host
    ollama_panel.analyze_host = lambda h, force=False: calls.append((h.name, force)) or {}
    real_fmt = ollama_panel.format_host_analysis
    ollama_panel.format_host_analysis = lambda a: "analysis"
    try:
        with Panel(hosts=[S.PC, S.SAMUS]):
            out = _slash("hosts pc --refresh")
    finally:
        ollama_panel.analyze_host, ollama_panel.format_host_analysis = real, real_fmt
    ctx.check(f"in -p, /ollama hosts is the per-host analysis, got {calls} {out!r}", calls == [("pc", True)] and out == "analysis")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
