"""scripts/realcheck -- the parts of `scripts/realcheck.py` (Halo 3.6.0.0 R11): Halo driven the way a person drives it.

procs   every process on the machine that belongs to a scratch home (its path in the command line or the environment,
        or Halo's own `HALO_OWNER` marker), with its parent, start time and CPU time; and the kill that only ever
        touches those
term    a real terminal for a child: a pty on Linux and macOS, a pseudoconsole on Windows; Ctrl+C, close, hard kill
fakes   the fake model provider and the fake Ollama the steps talk to (loopback only)
report  the step table, its JSON and the Markdown for a CI step summary
steps*  the steps themselves
"""
