# What runs, and what stops it

Halo starts other programs: Studio's server, sub-agents, your tool commands, MCP servers, local model servers and
more. The rule since 3.6.0.0: **no process Halo started is alive five seconds after the Halo that started it is gone,
however it went** -- you quit, pressed Ctrl+C, it got SIGTERM, you closed the terminal, or it was killed hard. The
only exceptions are the things you asked to keep running; Halo names each one on the way out, with the command that
stops it.

## What may keep running, because you asked

| What | Started with | Stopped with |
|---|---|---|
| a background run | `halo --bg ...` | `halo bg stop <id>` |
| the LAN host (and its duty steward) | `halo host serve`, `halo host steward on` | `halo host stop`, `halo host steward off` |
| the supervisor | `halo supervise --daemon` | `halo supervise stop` |
| a local model server you marked kept | `halo local serve ... --keep` (or "keep" in Studio) | `halo local stop <model>` |
| the updater | `halo update` / `/update` | it ends by itself |

Nothing else: not Studio, not the Ollama steward, not a sub-agent, not an MCP server.

## How a closing works

1. **The closing procedure** (halo_harness/closing.py) runs on every way out that runs any code at all: a quit,
   Ctrl+C, SIGTERM, SIGHUP, an error, a closed console window on Windows. What this Halo started is asked to stop
   the way it stops itself (Studio's stop route, a model server's stop), then signalled as a process group or tree,
   then ended hard -- within 3 s + 2 s. When all is well it prints nothing.
2. **A hard kill** runs no code in Halo, so the children notice on their own:
   - Windows: every child is in Halo's Job object, which Windows ends together with Halo;
   - every Halo child (Studio's server first) watches the Halo that started it and closes within two seconds;
   - Linux and macOS: a tiny reaper process waits for Halo and, if it dies without a word, ends what it started.
3. **The sweep at start**: every `halo` launch first stops what an earlier Halo left with no living owner, with one
   line: "halo: stopped a Studio server left from 2026-11-14 22:10".

Every child carries `HALO_OWNER=<id>` in its environment, so a stray is always findable.

## Studio belongs to the launch that started it

`halo init`, `halo`, `/studio` and `halo studio` each own the Studio they start; `halo init` hands its Studio to the
session it starts in the same terminal. A launch never uses a Studio it did not start. `halo setup ...`, `halo studio
--edit ...` and `halo replay open` stay in the foreground while the Studio they started serves: Ctrl+C there ends
both. A browser page whose Studio has gone says "Studio has stopped" and stops asking.

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
