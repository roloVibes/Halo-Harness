# Replays: scrub a run back in time, save it as one file, film a clip

Read this when you want to see what a session looked like at an earlier moment on Studio's Agents -> Live, save a run's replay as one file to open on another machine, or turn a stretch of it into an animated clip (`halo replay list | save | open | clip`).

The scrubber, the file and the clip are 3.4.1.0 "Time" (round R1). They are core: they read this machine's sessions and
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
who existed and how each ended, not each step; the bar says so.

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
then writes ONE file, `<state>/replays/<session>-<yyyymmdd-hhmmss>.halo-replay`. It is JSON:

| Key | What |
|---|---|
| `format`, `version` | `"halo-replay"`, `1` |
| `kind`, `id`, `session_id`, `title`, `saved`, `halo` | a session's replay, its file id, the session, its title, when it was saved, the Halo that saved it |
| `started`, `ended`, `cost_usd` | the span and the total |
| `agents` | each agent: id, parent, name, role, bio, lineup, model, end state, start, end, cost, task (its first line) |
| `states`, `costs`, `agent_costs` | each state change in time order; the session's running cost; each agent's own |
| `marks`, `bands` | the scrubber's ticks and phase bands |
| `plan` | the lineup's blocks as they were when it was saved (its graph and enabled squares), so another machine draws them |
| `includes` | what the file holds, in words (what Save showed) |

It never holds the prompts, tool inputs or outputs, thoughts, the working directory or any path, and every string passes
`redact.sanitize_node`, the redactor `halo export --sanitize` and `halo session export` use (`tests/test_replay_file.py`
seeds a key in the title, a task, a question and a hand-back and checks none reaches the file).

**Open it anywhere**: History's **Open a file** (a file from this disk, made here or on another machine; it is kept under
`<state>/replays/` so History lists it), or `halo replay open <file>`. A file of an older shape -- a `GET fleet/replay`
answer saved as is (3.0.5.0 to 3.4.0.0) -- opens as version 1; a newer version than this Halo reads says to update.

## Export a clip

**Export a clip** films the range From .. To (prefilled: the start to where the scrubber stands) at the scrubber's speed
on Live and writes ONE animated file, `<state>/replays/clips/<id>-<from>-<to>.webp` (GIF where Pillow has no animated
WebP): **1200 px wide**, 5 frames a second, **at most 30 seconds** (a range that would run longer is played faster to
fit, and it says so). It is filmed the way the front-page captures are: headless Chrome draws Live at each moment and
Pillow assembles the frames. It says the frames, length, width, format and path before it writes; a session not saved
yet is saved first, said. It needs Chrome (`HALO_CHROME`, else the usual install) and Pillow
(`uv tool install "halo-harness[images]"`); without either it says which and writes nothing.

## The verbs

```sh
halo replay list [--json]                                      # the saved replays, newest first
halo replay save <session> [--lineup NAME] [--dry-run] [--json]  # says what it holds and where, then writes it
halo replay open <file> [--no-studio] [--json]                 # checks it, keeps it under replays/, opens Live on it
halo replay clip <file|id> [--from T] [--to T] [--speed N] [--dry-run] [--json]   # T: seconds or m:ss
```

`open` starts Studio (or reuses the running one) at `?mode=agents&view=live&replay=<id>`; `&at=<seconds>` opens it at
that moment. Studio's routes: `GET replays`, `GET replays/plan?session=`, `POST replays/save`, `POST replays/import`,
`GET replays/<id>`, `GET|POST replays/<id>/clip`, `GET replays/clips/<name>` (studio/replays_api.py).
