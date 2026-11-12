# Replays: scrub a run back in time, save it as one file, film a clip, compare two runs, read its report card

Read this when you want to see what a session looked like at an earlier moment on Studio's Agents -> Live, save a run's replay as one file to open on another machine, turn a stretch of it into an animated clip, compare two runs side by side (`halo replay list | save | open | clip | compare`), or read a finished run's report card (`halo report`).

The scrubber, the file and the clip are 3.4.1.0 "Time" (round R1); a goal run saved as a file and Compare are round
R2; the report card is round R3. They are core: they read this machine's sessions and
`<state>/replays/` (`~/.halo/replays/`), with the fleet pack on or off. [Studio: Agents -> Live](STUDIO-live.md) has
the canvas they redraw; `halo replay <session> --model <ref>` (re-run one turn on another model) is a different verb,
in [COMMANDS-sessions.md](COMMANDS-sessions.md#halo-replay).

## The scrubber

Under Live's canvas, one bar: **Play** / Pause, the speed (**1x**, **4x**, **16x**), the clock ("0:22 / 1:40"), the cost
the session had spent at that moment, what is drawn, **Save this run's replay**, **Export a clip** and **Now**. Under
them the session's time axis:

- **bands**: what the busiest agent was doing over each stretch, in the 3.3.16.2 words and colours -- waiting on you,
  running a tool, thinking, writing, idle;
- **marks**: one tick per spawn (a sub-agent started, its task), hand-off (it handed back, the first line), ask (a
  question, a plan review or a permission card), failure and finish. Hover a tick for what it was.

Drag anywhere on the axis and the canvas is redrawn **as it was at that moment**: who existed, in which block, each one's
state and what it ran, the plan's line labels (a hand-off shows on its line for eight seconds of replay time), the
sentence under the bar (what waited on you first, then who was doing what) and the cost so far, under a
"replay -- <time>" banner in muted colours. Play runs it forward from there (from the start when it stands at the end);
**Now** (or Esc, or the banner's Back to now) returns to what runs.

Over the session drawn now the bar shows its axis up to this second (read when the pointer comes to it); dragging back
rewinds that session. History's rows (a session, a goal run, a mission, a saved file), a goal run's report (Replay), the
empty state's Replay the last session, an agent's history ("replay") and the palette all open on this one bar: there is
no other replay control (Cast's replay bar went in 3.4.1.0).

A goal run's or a mission's replay is coarse: the record holds each lane's or part's start and end, so the scrub shows
who existed and how each ended, not each step; the bar says so. A goal run SAVED as a file (below) holds each lane's
state changes from its record -- joined, writing, written, in review, sent back, merged, failed -- so its file plays
finer than that. A mission is the fleet pack's: it is not saved as a file here, and it is compared from its report.

## What a past moment can and cannot show

Everything comes from the session's transcripts on disk (`<state>/sessions/<project>/<id>.jsonl` and each sub-agent's
beside it), so a session from before 3.4.1.0 replays too. They hold who started when with what task, every text,
thought, tool call and result with its time, each hand-back, each failure, the running cost, a question or plan review
the agent put to you (its words, and when you answered), and each permission card it waited on (when it opened, when
you answered, and how).

An older session cannot show **what a permission card asked**: before 3.4.1.0 the turn's record kept only its times and
the answer, so its mark reads "a permission card (answered allow after 6 s)". From 3.4.1.0 on the record keeps the
card's words ("Bash: rm -rf build"). Live-feed-only facts (a tool's last output line at the near zoom level, the pieces
of a thought as they streamed) are not in the transcript and are not replayed.

## The replay file

**Save this run's replay** first says what the file holds, what it costs (nothing: no model call) and where it writes,
then writes ONE file, `<state>/replays/<session or goal run>-<yyyymmdd-hhmmss>.halo-replay`. A session and a goal run
(3.4.1.0 R2) save the same way, from the scrubber or `halo replay save <id>`. It is JSON:

| Key | What |
|---|---|
| `format`, `version` | `"halo-replay"`, `1` |
| `kind`, `id`, `session_id`, `run_id`, `title`, `saved`, `halo` | `session` or `run` (a goal run: its lead and lanes are the agents), its file id, the session or the run, its title, when it was saved, the Halo that saved it |
| `started`, `ended`, `cost_usd` | the span and the total |
| `agents` | each agent: id, parent, name, role, bio, lineup, model, end state, start, end, cost, task (its first line) |
| `states`, `costs`, `agent_costs` | each state change in time order; the session's running cost; each agent's own |
| `marks`, `bands` | the scrubber's ticks and phase bands |
| `plan` | the lineup's blocks as they were when it was saved (its graph and enabled squares), so another machine draws them |
| `facts` | (R2) the record's own figures: the cost each call priced once, the models nothing priced, the tokens, each model's cost, the retries, the failed calls, the steers -- what Compare reads; (R3) `artefacts` (each file an Edit / Write call wrote, by its path inside the project; one outside it by its name only; a goal run's: what merged and its workflow's saved outputs) and `answer` (the first line of main's last text) -- what the report card reads |
| `includes` | what the file holds, in words (what Save showed) |

It never holds the prompts, tool inputs or outputs, thoughts, the working directory or any path outside the project (R3:
the files it wrote are named by their path inside it), and every string passes
`redact.sanitize_node`, the redactor `halo export --sanitize` and `halo session export` use (`tests/test_replay_file.py`
seeds a key in the title, a task, a question and a hand-back and checks none reaches the file).

**Open it anywhere**: History's **Open a file** (a file from this disk, made here or on another machine; it is kept under
`<state>/replays/` so History lists it), or `halo replay open <file>`. A file of an older shape -- a `GET fleet/replay`
answer saved as is (3.0.5.0 to 3.4.0.0) -- opens as version 1; a newer version than this Halo reads says to update.
The version stays 1 in R2: `kind: run`, `run_id` and `facts` are new keys a version-1 reader ignores, and a file saved
before them still opens and compares (its figures then come from its agents; what it never held is "unknown").

## Export a clip

**Export a clip** films the range From .. To (prefilled: the start to where the scrubber stands) at the scrubber's speed
on Live and writes ONE animated file, `<state>/replays/clips/<id>-<from>-<to>.webp` (GIF where Pillow has no animated
WebP): **1200 px wide**, 5 frames a second, **at most 30 seconds** (a range that would run longer is played faster to
fit, and it says so). It is filmed the way the front-page captures are: headless Chrome draws Live at each moment and
Pillow assembles the frames. It says the frames, length, width, format and path before it writes; a session not saved
yet is saved first, said. It needs Chrome (`HALO_CHROME`, else the usual install) and Pillow
(`uv tool install "halo-harness[images]"`); without either it says which and writes nothing. Saying what it will write
needs neither (3.4.1.0 R6): without Pillow the dialog and `halo replay clip --dry-run` still give the frames, width,
path and cap, with one line saying what to install, and Export stays off until it is there.

## Compare two runs

On History (Agents -> Live's bar, `History · N`) every row has a tick. Tick two -- any two of a session, a goal run and a
saved replay file -- and press **Compare**: a page of the drawer (the drawer widens; **Back** returns to the list with
the ticks kept). Nothing opens by itself, and a third tick lets the oldest go.

- **What differed** first: three plain lines derived from the rows ("B used glm-5.3 (60 % of its cost); A did not.",
  "A cost 40 % less ($0.0300 against $0.0500)."), the biggest difference first, then what was the same. No model call.
- **The two runs over one time axis**: two columns, each run's agents as lanes in their blocks (a session's lineup, a goal
  run's lead and lanes), each lane its phase segments in the scrubber's colours (writing, a tool, waiting on you) on one
  scale, so the shorter run ends earlier.
- **The rows**: how it ended, wall time, cost, tokens, the models used (each one's share of the cost and of the agents'
  time), agents spawned, asks to you, failures (failed agents and failed model calls), retries (a provider's retries; a
  goal run's pieces sent back). The better figure carries a WORD in its cell -- cheaper, faster, fewer, finished -- not
  only a colour; "same" names neither; models and agents spawned are neither better nor worse.

Every figure comes from the run's own record, never a live counter: a session's transcripts (each call once: a
sub-agent's rolled-up total is not added to its own transcript's calls), a goal run's report and lanes, a file's `facts`.
A cost Halo cannot price is **unknown** -- the priced part with a "+" (`$0.0120+`), or "unknown" when nothing was priced,
never $0 -- and the better cost is not marked on that row; tokens a record does not hold are unknown too.

**One run, before and after.** Tick one row and press **Compare before / after**: A is the run up to a moment and B from
it on -- by default its first steer, else halfway; **split at** moves it. Wall time is not marked there (a shorter
stretch is not faster); a stretch's cost is the running cost's difference, unknown only when an unpriced call fell in
it; tokens are not counted per moment.

A mission is the fleet pack's: ticking one says "a mission is compared from its report" and Compare leaves it out.
`halo replay compare <a> <b> [--split T] [--json]` prints the same rows and lines; `--json` is the data (`a`, `b` with
their `figures` and `lanes`, `rows` [{key, label, a: {value, text}, b, better, word}], `differed`, `split`, `axis`).

## The report card

One card per finished run -- a session, a goal run, a saved `.halo-replay` file -- rendered **from its record**: never
hand-written, no model call, nothing written (`live/report_card.py`). It reuses Compare's figures for one run (the
nine cells: how it ended, wall time, cost, tokens, models, agents spawned, asks, failures, retries), then:

- **the story** in about ten lines, in order: who was asked what, what each handed back, each ask and failure, how it
  ended (main's last answer's first line); a longer run keeps every ask and failure and says how many steps it left out;
- **where the time went**: by phase (waiting on you, running a tool, thinking, writing, idle: the scrubber's bands) and
  by block (each block's agents and their agent time);
- **where the money went**: by model (each one's cost and share) and by block;
- **what failed and what happened next** (the next thing the record holds), the failed model calls, the retries (a
  goal run's: the pieces the gate sent back);
- **what waited on you** and for how long (a question until its answer, a permission card until you answered it);
- **which model did what**: each model and the agents that ran on it with their tasks;
- **the artefacts**: the files it wrote with their paths inside the project;
- **what this record cannot show**, in words, never a blank: a goal run's coarse record, a file saved before R2 (no
  tokens, retries or failed calls) or R3 (no files), an older permission card's words, an untimed wait, a cost Halo could
  not price ("unknown" or the priced part with a "+", never $0), what only Live showed as it happened.

**Where it opens**: each History row's **Report** door (a mission's report is the fleet pack's mission page, not a card);
the row Live shows for the session that ended last when nothing runs (a row, never a pop-up); a goal run's card is the
FIRST block of its report page in History (one page per goal run: the plan, the lanes, the gate, the merge, the outcomes
and the artefacts follow it). **Copy Markdown** puts the same card on the clipboard. A `.halo-replay` file opened on
another machine gives the same card (its `facts` carry what the card needs). `halo report <session|run|file>` prints the
Markdown; `--json` prints the card's data (`format: halo-report-card`, `story`, `time`, `money`, `failures`, `waits`,
`models`, `artefacts`, `cannot`, `cells`).

## The verbs

```sh
halo replay list [--json]                                      # the saved replays, newest first
halo replay save <session> [--lineup NAME] [--dry-run] [--json]  # says what it holds and where, then writes it
halo replay open <file> [--no-studio] [--json]                 # checks it, keeps it under replays/, opens Live on it
halo replay clip <file|id> [--from T] [--to T] [--speed N] [--dry-run] [--json]   # T: seconds or m:ss
halo replay compare <a> <b> [--split T] [--json]              # two runs side by side; a, b: session id, goal run id, file
halo report <session|run|file> [--json]                        # the run report card (R3): Markdown, or its data
```

`save` takes a goal run id of the repo you are in as well as a session id.

`open` starts Studio (or reuses the running one) at `?mode=agents&view=live&replay=<id>`; `&at=<seconds>` opens it at
that moment. Studio's routes: `GET replays`, `GET replays/plan?session=|run=`, `POST replays/save {session}|{run}`,
`GET replays/compare?a=&b=[&split=]`, `GET replays/report?ref=` (the card and its Markdown), `POST replays/import`,
`GET replays/<id>`, `GET|POST replays/<id>/clip`, `GET replays/clips/<name>` (studio/replays_api.py).
