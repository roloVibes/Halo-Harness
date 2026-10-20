"""halo_harness.orchestra.coach_probe_prompt -- the prompt the run's lead
drafts the probe's candidates from (Halo 3.1.6.0 R2; coach_probe.draft asks
it). 3.1.6.0 R3: when the coach's library cites entries for the run
(orchestra/coach_citations.py), their Lessons come in as "What earlier runs
like this learned" -- the lead may propose what fits; nothing is inherited.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.orchestra import jsonl

SHAPE = ('{"pairs": [{"invariant": {"lead": {"model": "<ref>", "effort": "low|medium|high|xhigh|max", "prompt_notes": '
         '"..."}, "workers": {"model": "<ref>", "prompt_notes": "...", "max_iterations": 40, "tools": {"allow": [...], '
         '"deny": [...]}}, "bios": {"<bio>": {"model", "prompt_notes", "max_iterations", "tools"}}, "why": "..."}, '
         '"domain": {"workers": {"prompt_notes": "..."}, "bios": {"<bio>": {"prompt_notes": "...", "use_for": '
         '["word"]}}, "plan": [{"job": "job-2", "after": ["job-1"]}], "why": "..."}}]}')


def money(x) -> str:
    return f"${float(x or 0):.4f}"


def draft_prompt(f: dict, k: int, cards: list, lessons: str = "") -> str:
    g = f["goal"]
    report = jsonl.read_json(Path(f["run_dir"]) / "report.json", {}) or {}
    lanes = "\n".join(f"  lane {l['n']} ({l['job']}): bio {l['bio'] or '(none)'}, model {l['model'] or '(the role table)'}, "
                      f"${l['cost_usd']:.4f}" for l in f["lanes"]) or "  (no lanes)"
    jobs = "\n".join(f"  {j.get('id')}: {j.get('title')} (claims {', '.join(j.get('claims') or [])})"
                     + (f", after {', '.join(j['after'])}" if j.get("after") else "") for j in f["jobs"]) or "  (none)"
    seen = "\n".join(f"  - [{c.get('severity')}] {c.get('kind')}: {c.get('text')} (why: {'; '.join(c.get('why') or [])})"
                     for c in cards) or "  - (no card)"
    return (f"You led this Orchestra run. Before the coach offers a change, it will run the same goal again under "
            f"candidate setups of the run's harness and compare what each delivers. Draft {k} pair(s) of candidates.\n\n"
            "Each pair has two kinds: `invariant` changes how the agents work whatever the goal (planning, tool use, "
            "context budget, delegation: the lead's model and effort, the workers' model, notes, max_iterations, "
            "tools); `domain` adds what this goal needs (procedure, knowledge, constraints: notes per bio, use_for "
            "words, a plan edit `after`). Keep each note under 600 characters and name only the bios and jobs below.\n\n"
            f"WHAT YOU WANT: {g.what}\nDONE WHEN: {g.done_when}\nSTOP WHEN: {g.stop_when}\n\n"
            f"The run: {report.get('status')}, tests {'pass' if report.get('tests_ok') else 'fail'}, "
            f"{money(report.get('cost_usd'))}, {float(report.get('elapsed_s') or 0):.1f}s\n{lanes}\n"
            f"The plan's jobs:\n{jobs}\nThe run's bios: {', '.join(f['bios']) or '(none)'}\n"
            f"The lineup: {f['lineup'] or '(none)'}; the lead role {f['lead_role']}, the worker role {f['worker_role']}\n"
            f"The coach's cards from the run's files:\n{seen}\n\n{lessons}"
            f"Answer with JSON only, {k} pair(s) in this shape (leave out what you do not change):\n{SHAPE}\n")
