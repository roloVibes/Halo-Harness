"""tests.test_steward_explain -- Halo 3.3.4.0 R4: `halo ollama explain`
(ollama_steward/explain.py) answers from the knowledge files with no model:
every alert kind of knowledge/symptoms.md prints its row (symptom, cause,
the Halo-side change, the server-side recommendation); every event kind the
server-log rules raise and every rule name answers (its own row or the row it
belongs to); every listed topic and the brief's named ones (scheduler,
memory, log, local-servers, kv-cache, parallel, margin) answer with text
taken from the knowledge files; no argument lists both; `--sources` prints
the SOURCES.md rows the answer's tags name; an unknown word says so and
exits 1. No network, no model.
Run: python -m tests.test_steward_explain
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
KDIR = Path(__file__).resolve().parent.parent / "halo_harness" / "ollama_steward" / "knowledge"
NAMED = ("scheduler", "memory", "log", "local-servers", "kv-cache", "parallel", "margin")
RULES = ("window-asked-small", "window-small", "window-large", "two-windows", "cpu-spill", "reply-cut", "no-compaction",
         "compaction-failed", "cut-resent", "slow-box", "thrash")


def _cli(*argv) -> "tuple[int, str]":
    from halo_harness.ollama_steward.explain import cmd_ollama_explain
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = cmd_ollama_explain(list(argv))
    return rc, out.getvalue()


def _knowledge() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(KDIR.glob("*.md")))


@test
def test_every_kind_prints_its_row(ctx: Ctx):
    from halo_harness.ollama_steward.explain import explain, symptom_rows
    rows = symptom_rows()
    ctx.check(f"the table parses ({len(rows)} rows, thrash among them)", len(rows) >= 19 and "thrash" in rows)
    text = (KDIR / "symptoms.md").read_text(encoding="utf-8")
    for kind, cells in rows.items():
        lines, ok = explain(kind)
        ctx.check(f"{kind}: answers", ok and lines[0] == kind)
        for label in ("symptom", "cause", "Halo-side change", "server-side recommendation"):
            got = next((x for x in lines if x.strip().startswith(label + ":")), "")
            ctx.check(f"{kind}: {label} is the table's own cell", got.split(": ", 1)[-1] == cells[label]
                      and cells[label].replace("|", "\\|") in text or cells[label] in text)


@test
def test_every_event_kind_and_rule_name_answers(ctx: Ctx):
    from halo_harness.ollama_steward.explain import explain
    from halo_harness.ollama_steward.server_rules import KINDS
    for kind in KINDS:
        lines, ok = explain(kind)
        ctx.check(f"event kind {kind}: answers ({lines[0] if lines else ''})", ok and len(lines) > 1)
    for rule in RULES:
        lines, ok = explain(rule)
        ctx.check(f"rule {rule}: answers with a row", ok and any(x.strip().startswith("cause:") for x in lines))


@test
def test_every_topic_answers_from_the_knowledge(ctx: Ctx):
    from halo_harness.ollama_steward.explain import explain, topics
    every = _knowledge()
    listed = topics()
    ctx.check(f"the brief's topics are listed or found, listed {len(listed)}", all(t in listed or explain(t)[1]
                                                                                  for t in NAMED))
    for t in sorted(set(listed) | set(NAMED)):
        lines, ok = explain(t)
        body = [x.strip() for x in lines if x.strip() and not x.endswith(".md") and ".md: " not in x]
        ctx.check(f"{t}: answers ({len(lines)} lines)", ok and bool(body))
        stray = [x for x in body if x not in every]
        ctx.check(f"{t}: every line is the knowledge's own text, stray {stray[:1]}", not stray)
    lines, _ok = explain("kv-cache")
    ctx.check("kv-cache is memory.md's KV cache section", lines[0] == "memory.md: The KV cache")
    lines, _ok = explain("margin")
    ctx.check("margin is the compute buffer, minimum and margin section", "margin" in lines[0])
    lines, _ok = explain("parallel")
    ctx.check("parallel finds OLLAMA_NUM_PARALLEL's lines", any("OLLAMA_NUM_PARALLEL" in x for x in lines))


@test
def test_no_argument_lists_both_and_sources_are_cited(ctx: Ctx):
    rc, out = _cli()
    ctx.check("no argument: exit 0, the kinds and the topics", rc == 0 and "Alert kinds" in out and "Topics" in out
              and "thrash" in out and "kv-cache" in out)
    rc, out = _cli("cpu-spill", "--sources")
    ctx.check(f"--sources lists the cited rows, exit {rc}", rc == 0 and "Sources:" in out
              and "S12: llama.cpp server README" in out and "S32:" in out)
    tags = {int(n) for n in __import__("re").findall(r"\[S(\d+)\]", out.split("Sources:")[0])}
    listed = {int(n) for n in __import__("re").findall(r"^\s+S(\d+):", out, __import__("re").M)}
    ctx.check(f"exactly the tags the answer carries, {sorted(tags)} vs {sorted(listed)}", tags == listed and tags)
    rc, out = _cli("no-such-thing")
    ctx.check("an unknown word says so, lists what there is, exits 1",
              rc == 1 and "nothing in the steward's knowledge names" in out and "Alert kinds" in out)


@test
def test_halo_ollama_explain_is_wired(ctx: Ctx):
    from halo_harness.ollama_cli import cmd_ollama
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = cmd_ollama(["explain", "thrash"])
    ctx.check(f"`halo ollama explain thrash` answers, exit {rc}", rc == 0 and out.getvalue().startswith("thrash"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
