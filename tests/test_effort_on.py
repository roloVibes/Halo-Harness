"""tests.test_effort_on -- Halo 3.3.5.0 R0 (e): the effort tag follows the
model (`providers/effort_on.py`). No server, no model call:

1. `effort_on`: `levels` on a cloud route, `think` on an Ollama model with
   the thinking capability (on / off, gpt-oss graded), `none` on an Ollama
   model without it and on every Hugging Face local server;
2. `models.think.<ref>` remembers a choice per model and wins over the level
   on the wire (`build_ollama_request_body`'s `think`);
3. `/effort` on a `none` model answers "<model> has no adjustable effort: n/a
   (it would set think on/off on a thinking model)" and keeps the level; on a
   `think` model it lists the real options and `/effort off` saves
   `models.think`;
4. the status bar's segment: `think on`, and a muted `effort n/a`; `/model`
   names the word;
5. a picker row's word (`row_word`).
Run: python -m tests.test_effort_on
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="m0-effort-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _ref(provider, model, *, local=False, raw=None):
    return SimpleNamespace(provider=provider, model=model, host=None, local=local, mlx=False, raw=raw or f"x:{model}")


def _session(ref, *, thinks=None, effort=None, source=None):
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.routing import Route
    s = SimpleNamespace(model_ref=ref, effort=effort, effort_source=source, effort_requested=None, settings=None,
                        provider_profile=resolve_profile(Route(provider=ref.provider, upstream_model=ref.model,
                                                               dialect="ollama" if ref.provider == "ollama" else "openai-chat")))
    if thinks is not None:
        s._ollama_supports_thinking = thinks
    return s


@test
def test_the_three_kinds(ctx: Ctx):
    from halo_harness.providers.effort_on import NA_WORD, effort_on
    cloud = effort_on(_ref("openrouter", "vendor/m"), None, effort="high")
    ctx.check(f"a cloud route: levels, the level as the word, got {cloud}", cloud["kind"] == "levels" and cloud["word"] == "high")
    t = effort_on(_ref("ollama", "qwen3.5:9b"), {"capabilities": ["completion", "thinking"]}, effort="low", explicit=True)
    ctx.check(f"a thinking Ollama model at low: think off, got {t}", t["kind"] == "think" and t["word"] == "think off"
              and t["options"] == ["on", "off", "default"])
    t = effort_on(_ref("ollama", "qwen3.5:9b"), {"capabilities": ["thinking"]}, effort="medium", explicit=True)
    ctx.check("medium and above: think on", t["word"] == "think on")
    t = effort_on(_ref("ollama", "qwen3.5:9b"), {"capabilities": ["thinking"]}, effort="high", explicit=False)
    ctx.check("a carried level (not chosen this session) sends no think field: think default", t["word"] == "think default")
    g = effort_on(_ref("ollama", "gpt-oss:20b"), {"capabilities": ["thinking"]}, effort="xhigh", explicit=True)
    ctx.check(f"gpt-oss is graded: think high, got {g}", g["word"] == "think high" and "medium" in g["options"])
    n = effort_on(_ref("ollama", "qwen3-coder:30b"), {"capabilities": ["completion", "tools"]}, effort="high")
    ctx.check(f"no thinking capability: none / effort n/a, got {n}", n["kind"] == "none" and n["word"] == NA_WORD)
    hf = effort_on(_ref("huggingface", "Qwen/Qwen3-8B", local=True), None, effort="high")
    ctx.check(f"every Hugging Face local server: none, got {hf}", hf["kind"] == "none" and hf["word"] == NA_WORD)


@test
def test_models_think_wins_on_the_wire(ctx: Ctx):
    from halo_harness.providers.effort_on import set_think_choice, think_choice_for
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_request import build_ollama_request_body
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.routing import Route
    raw = "ol:qwen3.5:9b@lan"
    set_think_choice(raw, "off")
    ctx.check("the choice is kept per ref (a ref's own dots kept)", think_choice_for(raw) == "off" and think_choice_for("ol:other") is None)
    route = Route(provider="ollama", upstream_model="qwen3.5:9b", dialect="ollama")
    host = OllamaHost(name="lan", url="http://192.0.2.10:11434")
    body = lambda **kw: build_ollama_request_body(system_text="s", messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
                                                  route=route, profile=resolve_profile(route), host=host, **kw)
    b = body(effort="high", think_choice=think_choice_for(raw))
    ctx.check(f"models.think off beats the level high, got think={b.get('think')!r}", b.get("think") is False)
    b = body(effort="high", think_choice="default")
    ctx.check("default sends no think field", "think" not in b)
    b = body(effort="high", think_choice="on", supports_thinking=False)
    ctx.check("a model with no thinking never gets the field, whatever the choice", "think" not in b)
    b = body(effort="low")
    ctx.check("no choice: the level decides (low = off)", b.get("think") is False)
    set_think_choice(raw, None)
    ctx.check("cleared", think_choice_for(raw) is None)


@test
def test_effort_command_on_local_models(ctx: Ctx):
    from halo_harness.commands.builtins import _cmd_effort
    s = _session(_ref("ollama", "qwen3-coder:30b", raw="ol:qwen3-coder:30b"), thinks=False, effort="medium")
    out = _cmd_effort("", SimpleNamespace(session=s, effort=None))
    ctx.check(f"bare /effort on a model with no thinking, got {out!r}",
              out.startswith("ol:qwen3-coder:30b has no adjustable effort: n/a (it would set think on/off on a thinking model)"))
    out = _cmd_effort("high", SimpleNamespace(session=s, effort=None))
    ctx.check(f"/effort high there keeps the level for the next model, got {out!r}",
              "n/a" in out and "'high' is kept" in out and s.effort == "high" and s.effort_source == "session")
    t = _session(_ref("ollama", "qwen3.5:9b", raw="ol:qwen3.5:9b@m0"), thinks=True, effort="medium", source="session")
    out = _cmd_effort("", SimpleNamespace(session=t, effort=None))
    ctx.check(f"bare /effort on a thinking model lists the real options, got {out!r}",
              "think on" in out and "Options: on, off, default" in out)
    out = _cmd_effort("off", SimpleNamespace(session=t, effort=None))
    from halo_harness.providers.effort_on import set_think_choice, think_choice_for
    ctx.check(f"/effort off saves models.think for that model, got {out!r}",
              think_choice_for("ol:qwen3.5:9b@m0") == "off" and "think off" in out)
    out = _cmd_effort("high", SimpleNamespace(session=t, effort=None))
    ctx.check(f"a level while a choice is saved says the choice wins, got {out!r}", "wins over the level" in out and "think off" in out)
    set_think_choice("ol:qwen3.5:9b@m0", None)
    hf = _session(_ref("huggingface", "Qwen/Qwen3-8B", local=True, raw="hf:local/Qwen/Qwen3-8B"))
    ctx.check("a Hugging Face local server answers n/a", "has no adjustable effort: n/a" in _cmd_effort("", SimpleNamespace(session=hf, effort=None)))
    from halo_harness.commands.builtins import _cmd_model
    out = _cmd_model("", SimpleNamespace(session=t, model_ref="ol:qwen3.5:9b@m0", effort=None))
    ctx.check(f"/model names the word, got {out!r}", "Effort: think on" in out)


@test
def test_status_bar_shows_the_word(ctx: Ctx):
    from textual.widgets import Static
    from halo_harness.tui.slash import _effort_status_text
    from halo_harness.tui.widgets.statusbar import StatusBar
    t = _session(_ref("ollama", "qwen3.5:9b", raw="ol:qwen3.5:9b"), thinks=True, effort="high", source="flag")
    n = _session(_ref("ollama", "qwen3-coder:30b", raw="ol:qwen3-coder:30b"), thinks=False, effort="high", source="flag")
    ctx.check(f"the status text on a thinking model, got {_effort_status_text(t)!r}", _effort_status_text(t) == "think on")
    ctx.check("and on one without", _effort_status_text(n) == "effort n/a")
    captured = []
    original = Static.update
    Static.update = lambda self, content="": captured.append(content)
    try:
        bar = StatusBar(cwd="")
        bar.set_effort(_effort_status_text(t))
        ctx.check(f"the segment reads think on, got {captured[-1].plain!r}", "think on" in captured[-1].plain)
        bar.set_effort(_effort_status_text(n))
        text = captured[-1]
        span = next((s for s in text.spans if text.plain[s.start:s.end].strip() == "effort n/a"), None)
        ctx.check(f"effort n/a is shown, muted, got {text.plain!r} {span}", span is not None and "dim" in str(span.style))
    finally:
        Static.update = original


@test
def test_picker_row_words(ctx: Ctx):
    from halo_harness.providers.effort_on import row_word
    ctx.check("a thinking Ollama row", row_word("ol:qwen3.5:9b@lan", {"reasoning": {"kind": "native"}}) == "think on/off")
    ctx.check("gpt-oss", row_word("ol:gpt-oss:20b", {"capabilities": ["thinking"]}) == "think low/medium/high")
    ctx.check("a coder with no thinking", row_word("ol:qwen3-coder:30b", {"capabilities": ["tools"]}) == "effort n/a")
    ctx.check("a Hugging Face local row", row_word("hf:local/Qwen/Qwen3-8B", {}) == "effort n/a")
    ctx.check("a cloud row has none", row_word("or:vendor/model", {}) == "")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
