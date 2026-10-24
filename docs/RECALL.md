# Recall

Read this when you search what Halo remembers -- memory topics, past sessions, the coach library, findings, decisions and your own notes (an Obsidian vault) -- or point it at a folder of your notes.

Recall is semantic search over what this machine holds, on a LOCAL
embedding model: `halo recall <query>`, `/recall <query>` in the TUI and
`halo -p`, Studio's recall box, `knowledge_search` for an agent. It is off
until `embeddings.model` is set in `~/.halo/config.json` (for example
`nomic-embed-text`, pulled on your Ollama host; `embeddings.base_url` points
at an OpenAI-compatible `/v1/embeddings` server instead; see
[COMMANDS-health.md](COMMANDS-health.md)). Nothing is embedded, and no host is
probed, before that.

The index is one file, `~/.halo/index/embeddings.jsonl`: one line per source
file with its kind, title, mtime and vector (`halo_harness/recall.py`). It
refreshes incrementally before each search: a file whose mtime matches its
line is never embedded again, and a line whose file is gone is pruned.
`halo recall --build-only` rebuilds it from scratch.

## Kinds

| Kind | Chip | What it indexes | Title | Pruned when |
|---|---|---|---|---|
| `memory` | `[memo]` | this project's auto-memory topic files (and a pack bio's namespace notes) | the topic's name | its file is gone |
| `session` | `[sess]` | every session log (title, first prompt, last answer) | the session's title | its file is gone |
| `coach_library` | `[lib]` | each coach library entry's EXPERIENCE.md ([ORCHESTRA.md](ORCHESTRA.md#the-library)) | its first heading | undone or forgotten |
| `finding` | `[finding]` | every current finding ([KNOWLEDGE.md](KNOWLEDGE.md)): its title, body and evidence | its title | superseded or forgotten |
| `decision` | `[decision]` | every current decision: its title, body, evidence and alternatives | its title | superseded or forgotten |
| `note` | `[note]` | every `.md` file under the folders `recall.sources` names ("Your own notes" below) | the front matter's `title`, else the first `# ` heading, else the file name | its file is gone, or its folder left `recall.sources` |

Each hit shows its score, its chip, its title and where it is: a finding or
a decision its id, who wrote it and the day (`+0.912 [finding] basket.py#total
passes ... (f-20261024-3c9a1e, gate, 2026-10-24)`), every other kind its
file. Studio's recall box and `GET /api/recall` give a finding or decision
hit its `ref` (the id), `by`, `when` and `confidence` too.
`rank_memory_topics` -- "which memory topics matter for this question" --
reads memory hits only.

## Searching

- `halo recall <query> [--k N] [--no-refresh] [--json]` -- this machine's index; exit 0 with hits, 1 with
  none, 2 when embeddings are not configured.
- `halo recall --fleet <query>` -- every online harness of the fleet answers from its own index
  ([FLEET.md](FLEET.md#recall-across-the-fleet-3120-r3)); only the hits leave a box, never the index.
- `halo recall [<query>] --namespace <pack>/<name> [--provenance]` -- one pack's memory namespace.
- `halo recall sources [--json]` -- the folders of your own notes, with their note counts.
- `halo knowledge search <words>` -- findings and decisions only; a plain word match when embeddings are off.
- `/recall [--fleet] <query>` -- the same in the TUI and `halo -p`.

## Your own notes

Your own notes join recall as a source: a folder of Markdown files, read in
place and never written. An Obsidian vault is one.

```sh
halo config set recall.sources '["~/vault", "~/work-notes"]'
halo recall sources
halo recall "the soup recipe with basil"
```

- Every `.md` file under each folder is indexed as kind `note`. `.obsidian/` -- and every other folder whose
  name starts with a dot (`.git/`, `.trash/`) -- is skipped, and so is any other file type and any note over
  2 MB.
- Its front matter (the `---` block Obsidian keeps tags and aliases in) is stripped from the embedded text;
  its title is the front matter's `title`, else its first `# ` heading, else its file name.
- Nothing is written to the folder: no index file, no cache, no front matter. The index lives in `~/.halo/index/`
  like every other kind's.
- `~` is your home. A folder outside your home needs no grant: you named it.
- The incremental rule holds: a note whose mtime did not change is not even opened again. A note you delete is
  pruned on the next search; take a folder out of `recall.sources` and its notes go from the index too.
- Your notes never leave this machine: a fleet recall answer leaves every `note` hit out
  ([FLEET.md](FLEET.md#recall-across-the-fleet-3120-r3)).

`recall.sources` takes a list (or one folder as a string); `halo recall
sources` prints each folder with its note count and says when one is not
there. See [CONFIG.md](CONFIG.md).

## What recall never does

It never writes a source (a vault, a memory folder, a session log), never
calls a model to rank or filter anything, never sends the index anywhere,
and never runs before embeddings are configured.
