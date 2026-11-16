# What runs, and what stops it

Read this when you want to know which processes Halo starts, which ones may keep running after it, and how to list or stop them (`halo ps`, `halo stop`).

Halo starts other programs: Studio's server, sub-agents, your tool commands, MCP servers, local model servers and
more. The rule since 3.6.0.0: **no process Halo started is alive five seconds after the Halo that started it is gone,
however it went** -- you quit, pressed Ctrl+C, it got SIGTERM, you closed the terminal, or it was killed hard. The
only exceptions are the things you asked to keep running; Halo names each one on the way out, with the command that
stops it.

## What may keep running, because you asked

| What | Started with | Stopped with |
|---|---|---|
| a background run | `halo --bg ...` | `halo bg stop <id>` |
| the LAN host | `halo host serve` | `halo host stop` |
| the supervisor | `halo supervise --daemon` | `halo supervise stop` |
| a local model server you marked kept | `halo local serve ... --keep` (or "keep" in Studio) | `halo local stop <model>` |
| the pool's server you marked kept | `halo local serve --pool <model> --keep` | `halo pool stop` |
| a pool worker's rpc-server | `halo host rpc on` | `halo host rpc off` |
| the updater and its window | `halo update` / `/update` | it ends by itself |
| the Signal pack's link helper | `/signal link` | it ends by itself (after the scan, or 3 minutes) |

On Windows a kept thing leaves Halo's Job object. When the program that started Halo holds it in a Job object of
its own that does not let anything leave (some terminals and services do), Halo starts the kept thing from outside
every Job instead; when even that cannot be done, Halo says so in one line: that thing then ends when the program
that started Halo closes. Starting it from outside means handing its command and environment (your keys included) to
a small helper through a file in your own temp folder for a moment; the helper deletes the file as it reads it, and a
folder a halo ended hard left behind is removed the next time.

Nothing else: not Studio, not the Ollama steward, not the host's duty steward (`halo host steward on` runs it as
the host's child, ending with the host, or in the foreground when no host runs), not a sub-agent, not an MCP server.
Each kept thing is in the ledger marked so: `halo ps` lists it and the Halo that started it names it on the way out.

**A daemon a tool command starts ends with Halo too**: a tmux server, an ssh ControlMaster, gpg-agent, a dev server
started in the background. On Linux and macOS Halo names each one it ends on the way out ("halo: ended tmux (pid
N), left running by a tool command ..."). A tmux server started that way also ends the sessions you opened in it
later. To keep one past Halo, the command starts it with a kept marker, for example
`HALO_OWNER=kept-tmux tmux new-session -d -s work`; `halo ps` then lists it as kept and you stop it yourself. On
Windows such a daemon is in Halo's Job object and ends with it.

A stop that reads a pid from a file (`halo host stop`, `halo host steward off`, `halo host rpc off`, `halo pool stop`,
the ledger) signals it only when the start time recorded with it matches the process that has that pid now. A record
left by a reboot or a hard kill is cleared and said, never signalled.

## How a closing works

1. **The closing procedure** (halo_harness/closing.py) runs on every way out that runs any code at all: a quit,
   Ctrl+C, SIGTERM, SIGHUP (unless it was started ignoring it: `nohup halo ... &` survives the hangup), an error,
   a closed console window on Windows. What this Halo started is asked to stop
   the way it stops itself (Studio's stop route, a model server's stop), then signalled as a process group or tree,
   then ended hard -- within 3 s + 2 s. When all is well it prints nothing.
2. **A hard kill** runs no code in Halo, so the children notice on their own:
   - Windows: every child is in Halo's Job object, which Windows ends together with Halo;
   - every Halo child (Studio's server first) watches the Halo that started it and closes within two seconds;
   - Linux and macOS: a tiny reaper process waits for Halo and, if it dies without a word, ends what it started
     (a program Halo waits on, such as an orchestra worker's `sudo` or a git clone, included);
   - an `isolation: user` worker carries the lead's owner variables through sudo and ends itself with the lead.
3. **The sweep at start**: every `halo` launch first stops what an earlier Halo left with no living owner, with one
   line: "halo: stopped a Studio server left from 2026-11-14 22:10".

Every child carries `HALO_OWNER=<id>` in its environment, so a stray is always findable.

## Studio belongs to the launch that started it

`halo init`, `halo`, `/studio` and `halo studio` each own the Studio they start; `halo init` hands its Studio to the
session it starts in the same terminal. A launch never adopts a leftover: the sweep at start has already stopped any
Studio whose owner is gone. A Studio of this home whose owner is alive (another terminal's session, or a `halo
studio` you run yourself) is used as it is: `halo init` opens Setup in it and says whose it is, the doors (`halo setup
...`, `halo studio --edit ...`) open their page in it, and it stays with the launch that started it -- leaving does
not stop it. A session Studio's **New session** started belongs to that Studio: when the Studio stops, the session
gets its own `shutdown` first (its turn ends at a tool boundary) and the terminal reads one line naming it with the
`halo --resume <id>` that reopens it. When none runs, `halo setup ...`, `halo studio --edit ...` and
`halo replay open` start one and stay in the foreground while it serves: Ctrl+C there ends both. A browser page
whose Studio has gone says "Studio has stopped" and stops asking.

## Seeing and stopping

    halo ps                 every live process of Halo for this home: kind, pid, age, owner (alive / gone / none),
                            kept on purpose or not; and any stray a scan finds by its HALO_OWNER marker
    halo stop <pid|kind>    stop those
    halo stop --orphans     stop what has no living owner and was not asked to stay
    halo stop --all         stop everything listed for this home, kept things too

`halo doctor` has one row when something has no living owner: "N processes of Halo have no living owner", with
`halo stop --orphans`. The stray scan reads `/proc` on Linux and `ps -E` on macOS; on Windows it lists no strays
(Windows does not let one process read another's environment cheaply), and the Job object is what ends them.

## Halo's own Python never imports from your folder

Halo starts its helpers with `python -P -m halo_harness ...` (Python 3.11 and later; on 3.10 a two-line bootstrap
drops the same entry), so a project folder that holds a `halo_harness/` checkout, or a `json.py` beside its code, is
never imported by Halo. `PYTHONSAFEPATH` is not set for the helpers: it would reach your own commands run through
Halo's tools.
