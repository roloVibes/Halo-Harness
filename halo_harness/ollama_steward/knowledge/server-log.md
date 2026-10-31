# Reading a host's server log for fit and failure

Read this when you want to know which server-log lines say whether a load fit and why a call broke, how to read the log on another machine, and what the log cannot tell you.

The API says what is loaded; the log says whether it fit and why it broke. Halo reads it read-only, on this machine and over a host's `ssh:` entry, and never changes a server setting. [S46][S47]

## The lines, by kind

| Kind | The line | Example | What it says |
|------|----------|---------|--------------|
| fit | `load_tensors: offloaded N/N layers to GPU` | `offloaded 41/41 layers to GPU` | every layer on the GPU; fewer than all is a spill [S46][S30] |
| fit | `llama_kv_cache: CUDA0 KV buffer size = ...` | `CUDA0 KV buffer size = 1904.00 MiB` | the window's cache on the GPU [S46][S30] |
| fit | `CPU KV buffer size = ...` | `CPU KV buffer size = 272.00 MiB` | any real value is a spill of the cache to system RAM [S46] |
| fit | `sched_reserve: graph ... splits = N` | `graph splits = 2` | 2 is all on the GPU; 14 or 117 is CPU-spilled [S46] |
| fit | `msg="starting llama-server" cmd="..."` | `-c 65536 -np 1 --cache-type-k q8_0 --flash-attn on` | the load command: the window times the slots, the KV type and flash attention in force for that load [S4][S30] |
| headroom | `gpu memory id=0 library=CUDA available="X GiB" free="Y GiB"` | `available="20.6 GiB" free="21.0 GiB"` | the memory the scheduler placed the load against [S46][S30] |
| truncation | `truncating input prompt limit=X prompt=Y keep=4 new=Z` | `limit=2050 prompt=23536 keep=4 new=2050` | the prompt overflowed the window and its middle was dropped; Y is the real prompt in tokens [S46][S4] |
| truncation | `stop processing: n_tokens = N, truncated = 1` | `n_tokens = 65535, truncated = 1` | the reply ran into the window's end [S13][S30] |
| failure | `CUDA error: an illegal memory access` | as quoted | a CUDA abort: llama-server dies [S46] |
| failure | `llama-server terminated` / `llama runner terminated` | `exit status 0xc0000409` | on Windows 0xc0000409 is the death after a CUDA abort, not a second bug [S46] |
| failure | `\| 500 \|` and `\| 499 \|` | `\| 499 \| 4.2862269s \|` | a failed request; a client that closed the connection [S46][S30] |
| failure | `aborting chat request due to client closing the connection` | as quoted | a client timeout, not a server fault [S46] |
| failure | `client connection closed before llama-server finished loading` | as quoted | an aborted load: the next try starts it again from zero [S46][S4] |

## A load result and a crash

- `llama-server started in X seconds` closes a load: Halo keeps its layers, splits, KV buffers, window, KV type and flash attention as one load result, the evidence the fit badge cites ("verified -- 41/41 layers, splits = 2, 258 tok/s"). [S47]
- The load command names a blob (`blobs/sha256-...`), not the model: the request's `template selection` line after the load names it, and Halo waits up to 25 lines for it. [S47][S30]
- A crash is fingerprinted with the load it died in: the measured 2026-10-29 shape was flash attention on, a q8_0 KV cache and a spilled window, then a CUDA illegal memory access, then exit 0xc0000409; the staged 0.40.13 update carried the fix. [S46][S42]

## Gotchas

- The log rotates on an upgrade or a restart: read the whole set, `server.log`, `server-1.log`, `server-2.log`, ... by modification time, not only `server.log`. [S46][S8]
- `server.log` can hold invalid UTF-8 and ripgrep stops early on it without a word: use `grep -a`, or read bytes and decode with replacement, as Halo does. [S46][S47]
- On a systemd Linux the log is the journal (`journalctl -u ollama`); on Windows `%LOCALAPPDATA%\Ollama\server*.log` plus `app.log`; on a Mac or a user install `~/.ollama/logs/server*.log`. [S8][S46]
- A host with no `ssh:` entry has no log here: a fleet member's ledger push carries the events of the server it serves, else only `/api/ps` says the fit (`size_vram < size` is a spill). [S47]

## What the log does not show

- Request bodies: `OLLAMA_DEBUG_LOG_REQUESTS=1` does not log them on 0.40.13, not even with `OLLAMA_DEBUG=1`. [S46]
- To see exactly what Halo sends, run a logging proxy: start `ollama serve` yourself (not the tray app) with `OLLAMA_HOST=127.0.0.1:11436` and bind the proxy on 11434; on Windows the port-based firewall rule covers the new listener; a listener with SO_REUSEADDR can bind a port Ollama still holds, so stop every ollama process and check the port is free first. [S46]
- The debug window: `OLLAMA_DEBUG=1` and a restart on that machine shows much more (very verbose) and still no request bodies; turn it off after. Halo says how and never sets it. [S46][S47]
