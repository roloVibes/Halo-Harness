"""tests.test_prompt_lean -- Halo 3.3.5.0 R4: the lean profile
(agent/prompt_lean.py), what Halo sends a local model or one with a window
under 64k. In-process, a fresh home of its own (topic files seeded here,
never the real memory directory); the loop rig for one real request:

1. the topic index: one pointer line per topic file (its name and one
   sentence), the `prompt.topics_max` newest by mtime, then "N more:
   `/memory topics`"; `/memory topics` lists them all;
2. the memory cap: MEMORY.md held to `prompt.memory_max_tokens`, its newest
   lines kept, the cut said in one line;
3. the tool cap by window class and by card: under 16,384 the core names, a
   32k model the built-in (core) set with the long tail dropped, under 65,536
   sixty-four, above it none; the steward profile's `tools_max` wins; a model
   whose card says no tools gets none;
4. `prompt.lean`: auto is local or a window under 64k; a cloud model with a
   large window is untouched; off turns it off for a local model too; through
   the rig the request a local model gets holds the pointer lines.
Run: python -m tests.test_prompt_lean
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="pb_lean-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _topics(n: int) -> "tuple[Path, list]":
    from halo_harness.config.memory import TopicFile
    d = Path(tempfile.mkdtemp(prefix="pb_topics-"))
    out = []
    for i in range(n):
        p = d / f"topic_{i:02d}.md"
        p.write_text("x", encoding="utf-8")
        t = time.time() - (n - i) * 60  # topic_{n-1} is the newest
        os.utime(p, (t, t))
        out.append(TopicFile(path=p, name=f"topic_{i:02d}", type="project",
                             description=f"Topic {i} holds the notes of round {i}. It also says a lot more after that.",
                             modified=None))
    return d, out


def _session(ref: str, window: int, **extra):
    from halo_harness.model import parse_model_ref
    return SimpleNamespace(model_ref=parse_model_ref(ref), model_profile=SimpleNamespace(context_tokens=window), **extra)


@test
def test_the_topic_index_as_pointers_the_newest_first(ctx: Ctx):
    from halo_harness.agent.prompt_lean import trim_topics
    _d, entries = _topics(20)
    head = "## Topic files (read on demand -- not included in full here)"
    full = head + "\n\n" + "\n".join(f"- {e.name} (project): {e.description}" for e in entries)
    out = trim_topics(full, entries, 12)
    lines = out.split("\n")[2:]
    ctx.check(f"12 pointers and the more line, got {len(lines)}", len(lines) == 13)
    ctx.check(f"the newest first, got {lines[:2]}", lines[0].startswith("- topic_19:") and lines[1].startswith("- topic_18:"))
    ctx.check(f"one sentence each, got {lines[0]!r}", lines[0] == "- topic_19: Topic 19 holds the notes of round 19.")
    ctx.check(f"the more line, got {lines[-1]!r}", lines[-1] == "8 more: `/memory topics` lists every topic file")
    ctx.check("shorter than the full list", len(out) < len(full) / 1.5)


@test
def test_memory_topics_lists_every_topic_file(ctx: Ctx):
    from halo_harness.commands.builtins import _cmd_memory
    from halo_harness.config.memory import MemoryIndex
    _d, entries = _topics(14)
    store = SimpleNamespace(enabled=True, memory_dir_path=Path("/m"),
                            load_index=lambda: MemoryIndex(text="", exists=True, topics=entries))
    out = _cmd_memory("topics", SimpleNamespace(memory_store=store))
    ctx.check(f"every topic file, got {out.splitlines()[:2]}", out.splitlines()[0].endswith(": 14") and len(out.splitlines()) == 15)


@test
def test_the_memory_cap_keeps_the_newest_and_says_the_cut(ctx: Ctx):
    from halo_harness.agent.prompt_composition import tokens_of
    from halo_harness.agent.prompt_lean import cap_memory
    body = "\n".join(f"- [entry {i}](e{i}.md) -- a memory line long enough to cost a few tokens each" for i in range(400))
    text = "Memory directory: /m\n\n# Memory (auto-loaded from MEMORY.md)\n\n# MEMORY.md\n" + body
    out = cap_memory(text, 1000)
    ctx.check(f"held near the cap, got {tokens_of(out)}", tokens_of(out) <= 1050)
    ctx.check("the newest entry kept, the oldest cut", "[entry 399]" in out and "[entry 0]" not in out)
    ctx.check("the heading kept", "# MEMORY.md" in out)
    last = out.splitlines()[-1]
    ctx.check(f"the cut said once, got {last!r}", last.startswith("[") and "older memory lines not sent" in last
              and "prompt.memory_max_tokens" in last and out.count("older memory lines") == 1)
    ctx.check("under the cap nothing changes", cap_memory(text, 100000) == text)


def _tools(names) -> list:
    return [{"name": n, "description": f"{n} tool", "input_schema": {"type": "object"}} for n in names]


@test
def test_the_tool_cap_by_window_and_by_card(ctx: Ctx):
    from halo_harness.agent.prompt_lean import _builtin_names, cap_tools, tools_cap
    from halo_harness.providers.ollama_fit import CORE_TOOL_NAMES
    builtin = _builtin_names()
    mcp = [f"mcp__fake__t{i}" for i in range(40)]
    catalog = _tools(builtin + mcp)
    s = _session("ol:tight:14b@lan", 32768)
    out, dropped = cap_tools(s, catalog)
    ctx.check(f"a 32k model gets the core (built-in) set, got {len(out)} of {len(catalog)}",
              [t["name"] for t in out] == builtin and dropped == len(mcp))
    small, _ = cap_tools(_session("ol:tiny:3b@lan", 12288), catalog)
    ctx.check(f"under 16,384 the core names, got {[t['name'] for t in small]}",
              sorted(t["name"] for t in small) == sorted(n for n in CORE_TOOL_NAMES if n in builtin))
    ctx.check("under 65,536 sixty-four, above it no cap", tools_cap(_session("ol:m@lan", 49152), 49152) == 64
              and tools_cap(_session("ol:m@lan", 131072), 131072) is None)
    s2 = _session("ol:tight:14b@lan", 32768, _lean_profile_tools_max=5)
    ctx.check("the steward profile's tools_max wins", len(cap_tools(s2, catalog)[0]) == 5)
    s3 = _session("ol:notools:7b@lan", 32768, _switch_caps={"tools": False, "model": "ol:notools:7b@lan"})
    ctx.check("a no-tools card gets none", cap_tools(s3, catalog) == ([], len(catalog)))
    ctx.check("the kept tools keep the catalog's order (a stable prefix)",
              [t["name"] for t in out] == [t["name"] for t in catalog if t["name"] in {x["name"] for x in out}])


@test
def test_lean_auto_on_off_and_cloud_untouched(ctx: Ctx):
    from halo_harness.agent.prompt_lean import active
    from halo_harness.theme import set_config_value, unset_config_value
    ctx.check("auto: a local model is lean", active(_session("ol:wide:14b@lan", 131072)))
    ctx.check("auto: a cloud model with a 200k window is not", not active(_session("ant:claude-opus-5-5", 200000)))
    ctx.check("auto: a cloud model under 64k is", active(_session("or:some/small-model", 32768)))
    set_config_value("prompt.lean", "off")
    try:
        ctx.check("off: a local model is not lean", not active(_session("ol:wide:14b@lan", 32768)))
    finally:
        unset_config_value("prompt.lean")
    from halo_harness.agent.prompt_wire import placement_for
    ctx.check("a cloud model keeps its memory where its snapshot put it", placement_for(_session("ant:claude-opus-5-5", 200000)) == "user")


@test
def test_a_local_request_carries_the_pointer_lines(ctx: Ctx):
    from halo_harness import events
    from tests.helpers.prompt_budget_rig import Rig, answer
    with Rig() as rig:
        rig.script("tight:14b", answer())
        s = rig.session("ol:tight:14b@lan")
        rig.run(s, [events.Command("user_input", {"text": "hi"})])
        system = rig.chats("tight:14b")[-1]["messages"][0]["content"]
        ctx.check("the topic index as pointer lines (name: sentence)", "\n- project_claude_bridge: " in system
                  and "(project):" not in system.split("## Topic files")[-1])
        tools = rig.chats("tight:14b")[-1].get("tools") or []
        from halo_harness.agent.prompt_lean import _builtin_names
        ctx.check(f"a 32k model's tools are the built-in set, got {len(tools)}", 0 < len(tools) <= len(_builtin_names()))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
