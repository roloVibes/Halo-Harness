"""tests.test_models_auto -- the `auto` pick (Halo 3.1.9.0 R2, "the Auto
lineup"), halo_harness/models_auto.py, on R1's seeded catalog
(tests/helpers/catalog_facts_seed.py) built into a best-at index:

1. a need and a band choose the model, and the reason is one line naming the
   deciding need and the price (an image in the task + low: the cheapest
   vision model; planning + mid: the best reasoning model within 3x the
   cheapest; review + high: the strongest; no needs: cheap and fast; tools;
   a video, and a video no model takes falling back to vision);
2. no candidate -> main's model, saying so; an empty index says so too;
3. a tie goes to main's own model, then (band low) to a local one;
4. the same index gives the same pick whatever its order;
5. the needs: attachments, kind words, a long input, the media fallback;
   `models.needs` is validated on a bio.
Fixture caches only, no model call. Run: python -m tests.test_models_auto
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import catalog_facts_seed as S  # noqa: E402

test, TESTS = new_registry()
_ROWS: dict = {}


def _index() -> dict:
    """The seeded catalog's best-at rows (built once for the module)."""
    if not _ROWS:
        from halo_harness.models_best_at import rebuild
        with S.home("models-auto-") as (_root, state):
            env = S.seed(state)
            _ROWS.update(rebuild(state, list(S.rows_by_ref(state, env).values()))["rows"])
    return _ROWS


def _pick(**kw):
    from halo_harness.models_auto import pick
    kw.setdefault("main_ref", "or:v/eyes")
    return pick(None, rows=kw.pop("rows", _index()), **kw)


@test
def test_each_need_and_band_picks_and_says_why(ctx: Ctx):
    p = _pick(task_text="describe shot.png", band="low", role="media media")
    ctx.check(f"an image in the task, band low: the cheapest vision model, got {p.line()!r}",
              p.line() == "auto: dbx:databricks-gemini-9-flash -- an image in the task, the cheapest vision model "
                          "($0.10/$0.40 per 1M)" and p.kinds == ["vision"] and not p.fallback)
    p = _pick(needs=["reasoning"], task_text="plan the migration", band="mid", role="planner planner planner")
    ctx.check(f"planning, band mid: the best reasoning model within 3x the cheapest, got {p.line()!r}",
              p.line() == "auto: dbx:databricks-gemini-x-pro -- planning needs reasoning, the best reasoning model "
                          "within 3x the cheapest ($1.00/$4.00 per 1M)")
    p = _pick(needs=["reasoning"], task_text="review the diff", band="high", role="reviewer reviewer reviewer")
    ctx.check(f"review, band high: the strongest reasoning model, got {p.line()!r}",
              p.ref == "ant:opus" and p.reason.startswith("review needs reasoning, the strongest reasoning model ($4.00/"))
    p = _pick(task_text="write the release notes", band="mid", role="writer custom writer")
    ctx.check(f"no needs: cheap and fast, got {p.line()!r}",
              p.line() == "auto: or:v/cheap -- no special needs, the best cheap, fast model within 3x the cheapest "
                          "($0.10/$0.40 per 1M)")
    p = _pick(needs=["tools"], task_text="fix the bug", band="low", role="coder coder coder")
    ctx.check(f"tools, band low: the cheapest model that states tool calls, got {p.line()!r}",
              p.ref == "or:v/cheap" and p.reason.startswith("the bio asks for tools, the cheapest tools model"))
    p = _pick(task_text="watch clip.mp4", band="low", role="media")
    ctx.check(f"a video in the task: the cheapest video model, got {p.line()!r}",
              p.ref == "or:v/ears" and p.reason.startswith("a video in the task, the cheapest video model"))
    no_video = {r: e for r, e in _index().items() if "video" not in ((e.get("facts") or {}).get("modalities_in") or [])}
    p = _pick(task_text="watch clip.mp4", band="low", role="media", rows=no_video)
    ctx.check(f"no model takes video: vision reads the Media tool's frames, got {p.line()!r}",
              p.kinds == ["vision"] and "no model takes video, so vision reads the Media tool's frames: the cheapest "
                                        "vision model" in p.reason)
    ctx.check(f"the alternatives are the next candidates, best first, got {p.alternatives}",
              len(p.alternatives) == 3 and p.ref not in p.alternatives)
    every = [_pick(task_text=t, band=b) for t in ("a.png", "b.pdf", "x") for b in ("low", "mid", "high")]
    ctx.check("every reason is one line", all("\n" not in x.reason and x.reason for x in every))


@test
def test_no_candidate_and_no_index_run_on_mains_model(ctx: Ctx):
    no_audio = {r: e for r, e in _index().items() if "audio" not in ((e.get("facts") or {}).get("modalities_in") or [])}
    p = _pick(task_text="transcribe talk.wav", rows=no_audio, main_ref="or:v/eyes")
    ctx.check(f"no audio model: main's model, saying so, got {p.line()!r}",
              p.fallback and p.ref == "or:v/eyes" and p.reason == "no model in the catalog has audio; using main's")
    p = _pick(task_text="x", rows={}, main_ref="or:v/eyes")
    ctx.check(f"an empty index: main's model, saying how to build one, got {p.line()!r}",
              p.fallback and p.ref == "or:v/eyes" and "`halo models analyze` builds it" in p.reason)
    tool_less = {"xp:xp-text-1": _index()["xp:xp-text-1"]}
    p = _pick(task_text="x", rows=tool_less, main_ref="or:v/eyes")
    ctx.check(f"a model that states no tool calls is never picked, got {p.line()!r}", p.fallback)


@test
def test_a_tie_goes_to_main_then_to_a_local_model(ctx: Ctx):
    p = _pick(needs=["reasoning"], task_text="review", band="high", role="reviewer", main_ref="ant:opus-5.5")
    ctx.check(f"band high, main among the strongest: main's own model, got {p.line()!r}",
              p.ref == "ant:opus-5.5" and p.reason.endswith("; a tie, so main's own model"))

    def row(price, local):
        return {"kinds": ["bulk"], "scores": {"bulk": 1.0}, "facts": {"price_in_per_m": price, "price_out_per_m": price,
                                                                      "tools": True, "local": local}}
    rows = {"hf:free-model": row(0.0, False), "ol:qwen3:8b": row(0.0, True), "or:v/one-cent": row(0.01, False)}
    p = _pick(task_text="x", band="low", rows=rows, main_ref="or:v/main")
    ctx.check(f"band low, two free models: the local one, got {p.line()!r}",
              p.ref == "ol:qwen3:8b" and p.reason.endswith("(free, local); a tie, so the local one"))
    p = _pick(task_text="x", band="low", rows=rows, main_ref="hf:free-model")
    ctx.check(f"band low: main's own model comes before the local one, got {p.line()!r}",
              p.ref == "hf:free-model" and p.reason.endswith("; a tie, so main's own model"))


@test
def test_the_pick_is_deterministic_given_the_index(ctx: Ctx):
    rows = _index()
    reversed_rows = dict(reversed(list(rows.items())))
    for kw in ({"task_text": "a.png", "band": "low"}, {"needs": ["reasoning"], "band": "mid", "role": "planner"},
               {"needs": ["long-context"], "band": "high"}, {"task_text": "x", "band": "mid"}):
        a, b, c = _pick(**kw), _pick(**kw), _pick(rows=reversed_rows, **kw)
        ctx.check(f"{kw}: the same pick every time and in any order, got {a.ref} / {b.ref} / {c.ref}",
                  (a.ref, a.reason, a.alternatives) == (b.ref, b.reason, b.alternatives) == (c.ref, c.reason, c.alternatives))


@test
def test_needs_from_the_task_the_kind_and_the_bio(ctx: Ctx):
    from halo_harness.agents_yaml import validate_agent_bio
    from halo_harness.models_auto import LONG_INPUT_CHARS, derive_needs, is_auto
    ctx.check("an attached image asks for vision", derive_needs((), "", [{"type": "image"}]) == [("vision", "an image attached")])
    ctx.check("an attached PDF path asks for pdf", derive_needs((), "", ["C:/docs/spec.PDF"]) == [("pdf", "a PDF attached")])
    ctx.check("audio and video paths in the text", [n for n, _w in derive_needs((), "a.mp3 then b.mkv")] == ["audio", "video"])
    ctx.check("a word that only looks like an extension is not one", derive_needs((), "remove the .move file") == [])
    ctx.check("the kind words: judge asks for reasoning", derive_needs((), "", (), "judge") == [("reasoning", "judging needs reasoning")])
    ctx.check("a long input asks for long-context", derive_needs((), "x" * (LONG_INPUT_CHARS + 1)) == [("long-context", "a long input")])
    ctx.check("a media agent naming no modality asks for vision", derive_needs((), "look at it", (), "media")[0][0] == "vision")
    ctx.check("the bio's needs, in NEEDS order", [n for n, _w in derive_needs(["tools", "reasoning"])] == ["reasoning", "tools"])
    ctx.check("`auto` is the literal, any case", is_auto("auto") and is_auto(" AUTO ") and not is_auto("default"))
    ok = validate_agent_bio({"models": {"preference": "auto", "needs": ["vision", "tools"]}})
    bad = validate_agent_bio({"models": {"preference": "auto", "needs": ["telepathy"]}})
    ctx.check(f"models.needs is validated, got {ok} / {bad}", ok == [] and bad and "models.needs" in bad[0])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
