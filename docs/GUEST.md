# A Claude Code session in Studio (watch only)

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
PreCompact, SessionEnd. The hook keeps only the documented fields it needs, cut to size: a tool's input as one line
of at most 300 characters (a to-do list as its steps, an Agent call as its description, type and the first line of
its prompt), a tool's response or error 2 KB, a prompt its first 200 characters, the session id and the folder. It
does not keep the transcript's path, and Halo never reads the transcript file.

While the session lives, these lines sit in one spool file under Halo's run folder (`~/.halo/run/guest/`, readable
by you alone), with the session's registry row. When the session ends, both are removed. Halo keeps no log of a
Claude Code session; Claude Code keeps its own.

Halo reads, stores and forwards nothing of your Claude login, sets none of its variables and points nothing of
Claude Code at Halo. It starts nothing of Claude Code's. The hook always exits at once with nothing on its output,
so it can never slow or stop Claude Code. Nothing leaves your machine and no new port is opened: the bridge opens
the same loopback control socket every Halo session opens.

## How it works

- The hook (`note.py`, standard library only) appends one line to the spool of its own Claude Code process. With no
  bridge up it writes nothing. The spool never passes 4 MB.
- The bridge (`halo guest serve`) is the plugin's MCP server: Claude Code starts it as its own child, it offers the
  model no tools, and it ends when Claude Code ends it. It turns the lines into the session's agent blocks and is
  listed for Studio exactly as a Halo session is.

## What Claude Code does not document, and what Halo does then

- **Which process the hook's parent is.** Halo matches a hook to its bridge by Claude Code's process id (the parent
  of both; a Windows Python launcher between them is stepped over). If the parent were another process, the hook
  finds no bridge and writes nothing: the session is not shown, and nothing wrong is shown. A line whose folder is
  not the session's project folder (or one inside it), or of another session id than the session's, is dropped and
  counted (`halo guest status` reads the bridge's row; the bridge's `status` names the count).
- **Which Agent call started which sub-agent.** Paired by order and type; when that is not sure: "goal not known".
- **The order of async hooks.** Lines carry a time stamp and are ordered by it; a tool's result that comes before
  its call is paired by the tool's id.
- **The folder Claude Code starts its MCP server in.** The plugin passes Claude Code's project folder; when it is not
  given, the bridge's own folder is taken.

## Not in this release

Handing work out to agents Halo runs, any MCP tool, reading the transcript (cost, tokens, replies as they are
written), steering, a Claude Code session on another machine, and any change to `halo mcp serve`.
