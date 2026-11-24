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

**The browser the Browser tool drives is the session's child** (3.6.0.6): Halo starts one Chrome, Chromium, Edge or
Brave per session on the first Browser call, talks to it over a pipe (no network port), and ends it with the session
like every other child: `Browser.close` asks it to close, waits up to 3 s, then every process still carrying its
profile is ended by pid (on Windows every process of the browser's own Job object). On Linux and macOS the browser
starts helpers of its own that carry no profile and run on after it (its crash handler; on macOS the updater it
wakes): they inherit a mark the browser is started with (`HALO_BROWSER` in its environment), and once the browser is
gone each one still carrying it is asked to end and, still there at most a second later, ended by pid. Every orderly way out (the terminal
app's quit and force quit, Studio ending a session or stopping, the end of `halo -p`) does this before any other stop,
so the browser always gets that polite close and writes what it holds. `halo ps` lists it as `browser` while it runs.
A hard end of Halo closes the pipe and the browser ends itself; a sign-in made in the last seconds before Halo is
killed may be lost. What the browser may leave on the machine is Halo's kept profile only: its temp files go to a
folder of its own, `~/.halo/browser/tmp/<pid>-<n>` (on Linux and macOS, a home so deep that the browser's socket path
would not fit gets `/tmp/halo-browser-<uid>/<pid>-<n>` instead), removed when it ends. One thing stays on purpose: Halo's own browser profile,
`~/.halo/browser/profile` (with `browser.profile` at its default, `kept`), so a sign-in made once is there next
time; it is never your own browser's profile. With `browser.profile` set to `clean` each session's profile is
thrown away at its end, and one a hard end left behind is removed by the next start.

**An editor Halo opens for you is yours**: Ctrl+E (`/editor`), `/mcp` e and `halo agents|workflows|maps edit`
start your `$VISUAL` / `$EDITOR` without Halo's marker, as `halo --tmux` starts tmux, so a GUI editor that stays open
(`code --wait`, `gedit`) is never ended when Halo quits.

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
   - Windows: every child is in Halo's Job object, which Windows ends together with Halo (a tool's shell command
     too, with every program it started: Git Bash's own children no longer leave it);
   - a shell command a tool started is in the ledger as `shell` while it runs (`halo ps` lists it), so the closing
     procedure and the reaper end its whole group even where its environment cannot be read (macOS);
   - every Halo child (Studio's server first) watches the Halo that started it and closes within two seconds;
   - Linux and macOS: from Halo's first child on, a tiny reaper process waits for Halo and, if it dies without a
     word, ends what it started (a program Halo waits on, such as an orchestra worker's `sudo` or a git clone,
     included); a Halo that starts no child (`halo ps`, a `halo stop` with nothing to stop) starts no reaper;
   - an `isolation: user` worker carries the lead's owner variables through sudo and ends itself with the lead.
3. **The sweep at start**: every `halo` launch first stops what an earlier Halo left with no living owner, with one
   line: "halo: stopped a Studio server left from 2026-11-14 22:10".
4. **The Halo process itself** never waits on the network to leave. A terminal session's background checks (who is
   signed in, the model catalog, your balances, whether an update is out) are given two seconds at a quit, all of
   them together; a check still waiting then is left behind, and the process ends half a second after its last
   line. The update check's `git` runs in a group of its own and ends with everything it started the moment Halo
   leaves. A quit where nothing is stuck does not wait at all.

Every child carries `HALO_OWNER=<id>` in its environment, so a stray is always findable.

## Studio belongs to the launch that started it

`halo init`, `halo`, `/studio` and `halo studio` each own the Studio they start; `halo init` hands its Studio to the
session it starts in the same terminal. A launch never adopts a leftover: the sweep at start has already stopped any
Studio whose owner is gone. A Studio of this home whose owner is alive (another terminal's session, or a `halo
studio` you run yourself) is used as it is: `halo init` opens Setup in it and says whose it is, the doors (`halo setup
...`, `halo studio --edit ...`) open their page in it, and it stays with the launch that started it -- leaving does
not stop it. A session Studio's **New session** started belongs to that Studio: when the Studio stops, the session
gets its own `shutdown` first (its turn ends at a tool boundary) and the terminal reads one line naming it with the
`halo --resume <id>` that reopens it. When none runs, `halo setup ...` and `halo studio --edit ...`
start one and stay in the foreground while it serves: Ctrl+C there ends both. A browser page
whose Studio has gone says "Studio has stopped" and stops asking.

## Seeing and stopping

    halo ps                 every live process of Halo for this home: kind, pid, age, owner (alive / gone / none),
                            kept on purpose or not; the sessions running on this home (kind `session`: listed,
                            never stopped -- a session ends from its own terminal); and any stray a scan finds by
                            its HALO_OWNER marker
    halo ps --forget <pid>  remove the ledger record of a process Halo cannot prove is its own; nothing is signalled
    halo stop <pid|kind>    stop those
    halo stop --orphans     stop what has no living owner and was not asked to stay
    halo stop --all         stop everything listed for this home, kept things too

`halo doctor` has one row when something has no living owner: "N processes of Halo have no living owner", with
`halo stop --orphans`. The stray scan reads `/proc` on Linux and `ps -E` on macOS; on Windows it lists no strays
(Windows does not let one process read another's environment cheaply), and the Job object is what ends them.

Halo sends a signal only to a process it can prove is its own: its pid AND the start time recorded when Halo started
it. A record whose start time could not be read then is never signalled: `halo stop` answers "still running" for it,
and on Windows `/update` does not install while it may still run. Halo drops such a record by itself once the pid
provably runs a program that started after the record was written (Windows and macOS; on Linux, for records written
by 3.6.0.1 or later). For one it cannot decide, look at the pid in Task Manager or `ps`: if it is another program,
`halo ps --forget <pid>` removes the record and signals nothing; if it is Halo's, stop it where it runs. A record whose
process runs and is proven Halo's is refused (`halo stop <pid>` ends that one). A forgotten process, if it was Halo's
after all, is no longer ended when Halo closes.

## What Halo cannot end on macOS

One case is not covered on a Mac. A program that a tool command starts and that leaves Halo's process group (it
calls `setsid` or `daemon()`, as `ssh -fN`, `ssh -f -M` or a `nohup setsid ...` line do) is no longer reached through
the shell command's group. Halo then finds it only by the `HALO_OWNER` marker in its environment, read with `ps -E`.
macOS shows no environment for its own system programs (`/usr/bin/ssh`, `/bin/sleep` and the like), so such a
program is not found: Halo does not end it on the way out, `halo ps` does not list it, and `halo stop --orphans`
does not reach it. A program from Homebrew or your own build is found as on Linux.

The same holds, for a few milliseconds, for a shell command whose ledger row is not written yet when Halo is killed
hard.

What to do:

- If it is meant to stay (an ssh tunnel you use after Halo), start it with a kept marker, for example
  `HALO_OWNER=kept-tunnel ssh -fN gpu-box`, so it is plainly yours.
- If it is not, end it yourself when you are done: `ssh -O exit gpu-box` for a ControlMaster, or `ps -ax` to find its
  pid and `kill <pid>`.

On Linux the same program is found (`/proc` shows its environment), and on Windows Halo's Job object ends it.

## Halo's own Python never imports from your folder

Halo starts its helpers with `python -P -m halo_harness ...` (Python 3.11 and later; on 3.10 a two-line bootstrap
drops the same entry), so a project folder that holds a `halo_harness/` checkout, or a `json.py` beside its code, is
never imported by Halo. `PYTHONSAFEPATH` is not set for the helpers: it would reach your own commands run through
Halo's tools.
