"""halo_harness.outcomes -- verified outcomes and measured routing (Halo 3.1.8.0
round R3, docs/OUTCOMES.md).

Every agent task ends with evidence of its kind, read out of its transcript
(nothing new is asked of the model); the Orchestra gate reads the evidence
rather than the summary; every outcome is one line per bio and model in
`~/.halo/coach/outcomes.jsonl`; and a bio may route by what was measured.

* `transcript.py` -- a transcript (session-log nodes or agent_transcript
  entries) as tool calls with their results; finding a session's log.
* `evidence.py`   -- `gather(transcript, bio, cwd=...) -> Evidence`, the
  kinds and their one mapping, `evidence.json`, the evidence lines.
* `lane.py`       -- an Orchestra lane's evidence (`<run>/lanes/<n>/evidence.json`),
  the gate's once-only send-back for missing evidence, the judge's block.
* `session.py`    -- a session sub-agent's evidence and outcome at its end.
* `records.py`    -- `outcomes.jsonl`: the rows, the Orchestra run's rows, reading them.
* `measured.py`   -- success per model and kind, and the words that say it.
* `routing.py`    -- `models.preference: measured`: the pick by measured rate.
* `cli.py`        -- `halo outcomes` and `halo models --measured`.
"""
