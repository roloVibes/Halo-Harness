"""tests.test_local_uses -- Halo 3.3.5.0 R3: `local_models_view.uses_of(ref)` (studio/local_uses.py) on a seeded home:
the `local-coder` lineup (written the way R0b's offer writes it), a role, the default model, `compactionModel`, a steward
profile on box (and one on another host) and a live session (the live-session reader's seam) all naming `ol:qwen3-coder:30b@box`; the card's
one line; a model nothing uses; the tag rule (`:latest`) and the host rule (another host's model of the same name is
not this one). No server is read.
Run: python -m tests.test_local_uses
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home  # noqa: E402

test, TESTS = new_registry()
CODER, SMALL = "ol:qwen3-coder:30b@box", "ol:qwen3.5:9b@box"
BOX = {"name": "box", "url": "http://127.0.0.1:1"}
OTHER = {"name": "other", "url": "http://127.0.0.1:2"}


class Seeded(Home):
    def __init__(self, live=()):
        super().__init__(hosts=[BOX, OTHER])
        self.live = list(live)

    def __enter__(self):
        super().__enter__()
        from halo_harness.agent.main_model_check import write_lane
        from halo_harness.studio import local_uses
        cfg = json.loads((self.state / "config.json").read_text(encoding="utf-8"))
        cfg.update(model=CODER, compactionModel="ol:qwen3-coder:30b@box", roles={"reviewer": CODER, "small": SMALL})
        cfg["ollama"]["profiles"] = {"box|qwen3-coder:30b": {"num_ctx": 32768, "by": "steward"},
                                     "other|qwen3-coder:30b": {"num_ctx": 8192, "by": "you"}}
        (self.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        ok, problems = write_lane({"coder": CODER, "orchestrator": SMALL, "lineup": "local-coder"}, cwd=self.root,
                                  state_dir=self.state)
        assert ok, problems
        local_uses.READERS["live"] = lambda: list(self.live)
        return self

    def __exit__(self, *exc):
        from halo_harness.studio import local_uses
        local_uses.READERS.clear()
        return super().__exit__(*exc)


@test
def test_every_place_that_names_the_coder(ctx: Ctx):
    from halo_harness.studio.local_models_view import uses_of
    live = [{"session_id": "s-live", "title": "fixing the parser", "model": CODER},
            {"session_id": "s-other", "title": "chat", "model": SMALL}]
    with Seeded(live) as h:
        u = uses_of(CODER, cwd=h.root, state_dir=h.state)
        ctx.check(f"the lineup and its role, got {u['lineups']}", u["lineups"] == [{"name": "local-coder", "role": "coder"}])
        ctx.check(f"the role, the default, the compaction model, got {u['roles']} {u['default_model']} {u['compaction']}",
                  u["roles"] == ["reviewer"] and u["default_model"] and u["compaction"])
        ctx.check(f"box's profile (not other's), got {u['profiles']}", u["profiles"] == ["box|qwen3-coder:30b"])
        ctx.check(f"the one live session on it, got {u['sessions']}", u["sessions"] == [{"id": "s-live", "title": "fixing the parser", "live": True}]
                  and u["live"] == 1 and u["any"])
        ctx.check(f"the card's line, got {u['line']!r}", u["line"] == "qwen3-coder:30b is the coder in `local-coder`, the "
                  "`reviewer` role, the default model (`model`), the compaction model (`compactionModel`) and the model of "
                  "1 profile; 1 live session is on it")


@test
def test_the_orchestrator_and_a_model_nothing_uses(ctx: Ctx):
    from halo_harness.studio.local_models_view import uses_of
    with Seeded() as h:
        u = uses_of(SMALL, cwd=h.root, state_dir=h.state)
        ctx.check(f"main in the lineup, the small role, got {u['lineups']} {u['roles']}",
                  u["lineups"] == [{"name": "local-coder", "role": "main"}] and u["roles"] == ["small"] and u["live"] == 0)
        ctx.check(f"its line, got {u['line']!r}", u["line"] == "qwen3.5:9b is the main in `local-coder` and the `small` role")
        none = uses_of("ol:nomic-embed-text@box", cwd=h.root, state_dir=h.state)
        ctx.check(f"nothing uses the embedder, got {none}", not none["any"] and none["line"] == "nomic-embed-text: nothing Halo knows of uses it")


@test
def test_the_tag_and_host_rules(ctx: Ctx):
    from halo_harness.studio.local_uses import refers_to, uses_of
    with Seeded() as h:
        ctx.check("a :latest tag is the same model", refers_to("ol:nomic-embed-text:latest@box", "nomic-embed-text", "box"))
        ctx.check("another host's model of the same name is not this one", not refers_to(CODER, "qwen3-coder:30b", "other"))
        ctx.check("no host: the default host (box, the first)", refers_to("ol:qwen3-coder:30b", "qwen3-coder:30b", "box"))
        ctx.check("a cloud ref never matches", not refers_to("or:qwen/qwen3-coder", "qwen3-coder:30b", "box"))
        other = uses_of("ol:qwen3-coder:30b@other", cwd=h.root, state_dir=h.state)
        ctx.check(f"on `other` only its own profile, got {other['profiles']} {other['roles']}",
                  other["profiles"] == ["other|qwen3-coder:30b"] and not other["roles"] and not other["lineups"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
