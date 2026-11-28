# A Claude Code session in Studio (watch only)

Read this when you want to see a Claude Code session in Studio: how to turn the watch-only view on and off, what Studio shows of it, what Halo reads and keeps, and how Claude Code may hand a bounded task to your own local models.

Halo can show a Claude Code session in Studio's Session section, as one more session with its agent blocks: the
main agent, its sub-agents, the tool each one runs, the plan and the objective. It is **watch only**: nothing is
typed into the session from Studio and nothing steers it. You stay inside Claude Code.

## Turn it on

```
halo guest install
```

This writes a small Claude Code plugin folder under Halo's own folder (`~/.halo/guest-plugin`) and prints the
Claude Code commands that add and turn it on. Halo runs none of them; you run them yourself:

```
claude plugin marketplace add "<the folder it printed>"
claude plugin install halo-guest@halo-local
claude plugin enable halo-guest
```

The plugin is installed switched off (`defaultEnabled: false`), so the third command is the one that turns it on.
From the next Claude Code session on, Studio lists it. `halo guest status` says whether a session is shown now, and
`halo doctor` has a row for it.

## Turn it off

```
claude plugin disable halo-guest
```

To remove it: `halo guest uninstall` removes the folder and prints the commands that remove the plugin from Claude
Code (`claude plugin uninstall halo-guest@halo-local`, `claude plugin marketplace remove halo-local`).

Turn the plugin off in Claude Code before you remove Halo: Claude Code keeps its own copy of the plugin, and with
Halo gone that copy starts a Python that is no longer there (Claude Code then shows a hook error and a failed tool
server).

`halo update` ends the bridge as it ends Halo's other processes, and says so first in one line: the Claude Code
session itself keeps running, and its view in Studio comes back when that session reconnects its tool servers or at
its next start (`halo update --check` says the same line as what would happen and ends nothing).

## What Studio shows

- The session is listed like any other, named **Claude Code** with **watch only** beside it.
- Main's block and one block per sub-agent, each with the tool it runs now. A sub-agent's goal is the description
  of the Agent call that started it. Claude Code does not say which call started which sub-agent, and its hooks
  can arrive out of order, so Halo gives a goal only when that call is the one call of its kind waiting and no other
  call or sub-agent of that kind comes within two seconds of it; otherwise the card says **goal not known** (a goal
  shown and then joined within those two seconds by another of its kind goes back to **goal not known**).
- Wherever the session's name shows (Live, the Map, the agent cards) it reads **Claude Code · watch only**; an
  agent's cost reads **not known**, and its Pause, Stop, Steer and Take over are off.
- The objective (the first line of your latest prompt of four words or more) and the plan, from Claude Code's to-do
  list or its task events. On newer models Claude Code keeps no to-do list unless you turn its to-do tools on (its
  tools reference, https://code.claude.com/docs/en/tools-reference : `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`); without one
  the plan chip says "no plan yet", as for any session. Halo changes no setting of Claude Code's.
- Cost and tokens read **not known**: Claude Code keeps its own count, and Halo does not read it.
- There is no Prompt box for it; Steer and Screenshot are off. Anything that would send into the session (a steer, a
  stop, an answer, a command) answers "watch only".

## What is read, and what is kept

Claude Code runs the plugin's hook for these events: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse,
PostToolUseFailure, SubagentStart, SubagentStop, TaskCreated, TaskCompleted, Notification, Stop, StopFailure,
PreCompact, SessionEnd. The hook keeps only the documented fields it needs, cut to size, and this is all of it:

- a tool's name, its id and its input as one line of at most 300 characters (a to-do list as its steps, an Agent call
  as its description, type and the first line of its prompt), its response or error cut to 2 KB, whether it was interrupted, how long it took;
- a prompt's first 200 characters;
- the last reply of a turn (Stop) and of each sub-agent (SubagentStop), cut to 2 KB; a failed turn's error and its
  details (200 characters);
- a notification's text and title (200 characters each) and its type;
- a task's id, its subject and its description (200 characters each);
- the session's title (200 characters), how it started (startup, resume, clear), its model, why it ended, what
  started a compaction;
- on every line: the session id, the folder, a sub-agent's id and type, and a time stamp.

It does not keep the transcript's path, and Halo never reads the transcript file.

While the session lives, these lines sit in one spool file under Halo's run folder (`~/.halo/run/guest/`, readable
by you alone), with the session's registry row. When the session ends, both are removed. A bridge ended hard (`halo
update`'s stop on Windows, a closed console, a killed process) cannot remove them: from then on the hook writes
nothing there (the mark beside the spool names its bridge by its process id and start time, and the hook checks
that this bridge still runs), so the file never grows, and it is removed at the next of these: `halo update` right
after its stops, `halo guest status`, `halo guest uninstall`, `halo doctor`, a Studio start, a bridge's start.
Halo keeps no log of a Claude Code session; Claude Code keeps its own.

Halo reads, stores and forwards nothing of your Claude login, sets none of its variables and points nothing of
Claude Code at Halo. It starts nothing of Claude Code's. The hook always exits at once with nothing on its output,
so it can never slow or stop Claude Code. Nothing leaves your machine and no new port is opened: the bridge opens
the same loopback control socket every Halo session opens.

## How it works

- The hook (`note.py`, standard library only) appends one line to the spool of its own Claude Code process. With no
  bridge up, or when the bridge its mark names no longer runs, it writes nothing. The spool never passes 4 MB.
- What a hook costs: each tool call starts it twice (before and after the call); each start is one short Python
  process (on Windows two, a launcher and the interpreter, and it reads the process list once) that checks its
  bridge and appends one line. Claude Code runs it in the background and does not wait for it, and it ends itself
  within a second.
- The bridge (`halo guest serve`) is the plugin's MCP server: Claude Code starts it as its own child, it offers the
  model no tools, and it ends when Claude Code ends it. It turns the lines into the session's agent blocks and is
  listed for Studio exactly as a Halo session is.

## What Claude Code does not document, and what Halo does then

- **Which process the hook's parent is.** Halo matches a hook to its bridge by Claude Code's process id (the parent
  of both; a Windows Python launcher between them is stepped over). If the parent were another process, the hook
  finds no bridge and writes nothing: the session is not shown, and nothing wrong is shown. The session's id is the
  one the first line names (Claude Code's own session start comes before the bridge is up). A line whose folder is
  not the session's project folder (or one inside it), or of another session id than the session's, is dropped and
  counted; `halo guest status` prints the count. A /clear or a resume starts another id in the same session: the
  plan and the objective start again.
- **Which Agent call started which sub-agent.** Paired by order and type; when that is not sure: "goal not known".
- **The order of async hooks.** Lines carry a time stamp and are ordered by it; a tool's result that comes before
  its call is paired by the tool's id.
- **The folder Claude Code starts its MCP server in.** The plugin passes Claude Code's project folder; when it is not
  given, the bridge's own folder is taken.

## Hand-outs: Claude Code hands a bounded task to one of your local models

Off until you turn it on. With it on, Claude Code (as main) can hand one bounded task to an agent Halo runs on one of
**your own** local models, and Studio shows that agent as a child of the session's main (or of the Claude Code
sub-agent that asked, when that is sure). The point: bounded work on your own machine, not on your Claude tokens.

**Turn it on**: `halo config set guest.hand_out local`, then start a new Claude Code session (or reconnect the
`halo-guest` server with `/mcp`): the bridge reads the setting once, when it starts. **Turn it off**: `halo config
set guest.hand_out off` and the same restart. `off` and `local` are the only values read; any other reads as off and
`halo doctor` says so.

The tools Claude Code then sees (named `mcp__plugin_halo-guest_halo-guest__<tool>`):

- `halo_models`: your local models Halo may use, with what Halo knows of each (window, measured speed and cold load,
  tool calling, the tuner's guide line marked as the tuner's); what is not known says so.
- `halo_hand_out`: one task (a goal, up to 10 acceptance checks, up to 50 files, a model, a mode, the caps); it answers
  when the job ends (`wait: false`: a job id at once).
- `halo_job`: a job's state, step, turns, tokens and minutes.
- `halo_job_result`: its answer text (in parts of 20,000 characters), its answer to each check (or "not answered"),
  what it was denied, turns, tokens and cost.
- `halo_job_stop`: stop a job.

**Which models**: Ollama hosts only: `ol:<model>` or `ol:<model>@<host>` whose host has **no key**, in its entry
in `ollama.hosts` or in Halo's env file (a host with a key is an account somewhere, such as Ollama Cloud, not your
machine), **and** whose address is local by the same test `--offline` applies (loopback, a private address, a
single-label or `.local` name, or an entry you marked `offline_ok`).
Anything else (an `hf:`, `or:`, `ant:`, `dbx:`, `local:` or `oai:` model, a Claude model, a keyless host on a public
address) is refused with one line that names the allowed ones.
With no model named, Halo's default model is taken when it is one of these. Before a start Halo reads the host's
model list once: "does not answer" and "is not on <host>" are said before anything starts.

**What a worker may do**: in mode `none` it has no tools and answers from what it was sent; in mode `read_only` its
only tools are Read, Grep and Glob, held to the session's project folder whatever the path or pattern (a read anywhere
else, a Glob pattern with `..` that climbs out included, is a recorded denial).
In both it runs **no** command, edits nothing, starts no sub-agent, no tool server and no `claude` (`--strict-mcp-config`
leaves out the claude.ai connectors too) and reaches nothing on the network but this machine and your own local hosts
(`--offline`); an ask is a recorded denial (nobody is asked), never a wait. It can never be given a Claude model, your
Claude login, a shell line or a Bash prompt. No mode edits.

**A sealed run**: no settings file changes what a worker may do. It runs `--bare` with no settings layer read
(`--setting-sources ""`) and its own Claude config folder (an empty folder of the job's): none of your hooks run
(Halo's, Claude Code's own, a project's, a plugin's), none of your allow rules, added folders, `env` block or
permission mode reach it, and nothing under `~/.claude` is read or written by it. Every model it would call (its
small model, a title, an escalation, a fallback) must be one of the models above: anything else is refused before a
request is built, so a gateway on this machine in front of a paid account is never reached. Its environment carries no
secret at all: no name with TOKEN, KEY, SECRET, CREDENTIAL or PASSWORD in it, no `AWS_*`, no
`GOOGLE_APPLICATION_CREDENTIALS`, no proxy setting, no `HALO_MODEL` / `HALO_MODEL_SMALL`.

**Where its words go**: to the model on your own machine or your own local host, nothing else. The worker is a `halo
-p` process on your machine. What its model is sent: Halo's own system prompt for a `-p` run (the same for every
`halo -p`; no session's system prompt is changed), the environment block every session has (the folder, the system,
the date, the git branch, status and recent commits), and the task (a user prompt: the goal, the files' names, the
checks). **No instruction file** (no CLAUDE.md, AGENTS.md or rules, yours or the project's), no memory and nothing of
your `~/.claude` goes into it. In `read_only` the files it reads in the project folder go to the model too.

**Stopping a job**: `halo_job_stop`, the worker's Stop in Studio (its row is Halo's own: its Stop works, its cost and
tokens show; every other row of the Claude Code session stays watch only), a cancel of the call in Claude Code, `halo
stop`, or the session's end. A stop asks the agent to end at its next step, then ends its process.

**Caps**: 12 turns (up to 40), 10 minutes of wall clock (up to 60), two jobs at once per session and one per host; a
third is refused (no queue). A job that hits a cap answers `stopped` with what it had.

**What is kept**: each job's record and result, in the bridge's memory and in `~/.halo/run/guest/<pid>.job.<id>.json`
(yours alone) while the session lives, and beside it the job's own folder (`<pid>.job.<id>.plans/`: plan mode's plan
file and the worker's empty Claude config folder, removed when the job ends); removed at the session's end, and a dead
session's by the same sweeps as the spool. A worker keeps **no** session: no transcript, no entry in the session list,
no memory (`halo -c` after a hand-out continues your own last session, as before); what a worker ended hard leaves is
removed at the job's end and by the sweep. Halo's own counts of the traffic on your host (the Local tab's model, tokens
and timing, never words) count a worker's calls as they count every call. Halo writes nothing under `~/.claude`.

**Closing**: every worker ends with the bridge that started it, however the bridge ends (its input closes, it is killed
hard, Claude Code is killed, `halo update`, `halo stop`): on Windows the bridge's own Job holds it, on Linux and macOS
the worker watches the bridge and ends within two seconds of it going. `halo ps` names a running worker ("Claude Code
hand-out"); Studio draws it under the session's main and not as a session of its own while that session lives (a
worker whose session is gone shows as a session, so it can be stopped).

**Limits**: a job does not outlive its session (no resume); Claude Code
does not document which sub-agent made an MCP call: the worker goes under that sub-agent only when the hook line of
the call (same tool, same arguments, close in time) is the only one, else under main.

## Not in this release

An editing mode, paid or cloud models, MCP tasks, a queue, a second model reviewing a result, applying a patch,
resuming a job after its session ended, anything that tells Claude Code when to hand out (a skill, a sub-agent
definition), reading the transcript (cost, tokens, replies as they are written), steering, a Claude Code session on
another machine, and any change to `halo mcp serve`.
