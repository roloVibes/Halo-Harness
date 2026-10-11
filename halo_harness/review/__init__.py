"""halo_harness.review -- `/review` and `halo review` (Halo 2.0.10 round 1).

Parallel dimension reviewers (read-only sub-agents on the `reviewer` role), a
judge that adjudicates every finding (the `judge` role), a severity-first
ranking in the ReportFindings shape, and an optional fix pass (the `coder`
role) that re-verifies each fix. A review reports; it never gates anything.
See docs/REVIEW.md.

Modules: `target` (what to review), `dimensions` (the five reviewer prompts and
levels), `findings` (the typed finding and tolerant JSON parsing), `agents`
(the sub-agent specs and one-child runner), `run` (reviewers), `verify`
(judge, dedup, ranking), `fix` (coder pass), `render` (text and JSON), `cli`
(`halo review`), `slash` (`/review`).
"""
