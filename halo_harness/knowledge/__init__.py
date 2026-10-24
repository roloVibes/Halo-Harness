"""halo_harness.knowledge -- knowledge that outlives a session (Halo 3.1.8.0
round R4, docs/KNOWLEDGE.md).

Two recall kinds Halo verified: a `finding` (a fact established with
evidence: what, where, the evidence lines, who found it, when) and a
`decision` (a choice taken with its reason: what, why, the alternatives, who
took it, when). They are Markdown files with a small front matter under
`<state>/knowledge/`, written by the places that already know them, indexed
by recall like memory and sessions, carried over the fleet like the coach
library, and cited by the agents that reuse them. Nothing here is a
classifier, and no model is asked to confirm anything.

* `store.py`   -- the files: write, read, list, supersede, forget, the ids, `_meta.json`.
* `frontmatter.py` -- an entry's text: its front matter, its one-line fields, the confidence rule.
* `search.py`  -- search through recall (a plain word match when embeddings are off).
* `cite.py`    -- the snapshot an agent receives (and its cite line), the ids an agent's text names,
                  "reused by" from outcomes.jsonl, an Orchestra worker's brief block.
* `writers.py` -- the judge, the gate, the coach's Apply and the supervisor's answers write them
                  (`knowledge.write: false` turns every writer off).
* `sources.py` -- recall's sources: the entries (kinds finding / decision) and the owner's own notes
                  (`recall.sources`, kind note, read in place).
* `share.py`   -- over the fleet: a member's answer to the `knowledge` command, `halo knowledge fetch`.
* `cli.py`     -- `halo knowledge add|list|show|search|forget|supersede|fetch`.

The agents' tools are `knowledge_add` and `knowledge_search` (tools/knowledge.py).
"""
