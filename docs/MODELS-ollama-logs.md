# Models: the Ollama server log

Read this when you want to know how Halo reads an Ollama host's server log, whether that log is live, how the log drives a call's recovery, what a crash fingerprint holds and what Halo proposes when a crash repeats, how a failed local call walks the degradation ladder, what the answer post-mortem reads and how the model shelf retires a model.

Part of [Models](MODELS.md), which lists every part.

## Logs (3.3.6.0 R3)

The API says what is loaded; the server log says whether it fit and why it broke. Halo reads that log read-only on
every host it can and treats it as the source of truth for fit and failure. It never changes a host-side Ollama
setting, never restarts a server and never turns on `OLLAMA_DEBUG`: when more detail would help it says how, as one
stated action, and reads what appears. The lines it reads, by kind, are in the steward's knowledge
(`halo ollama explain server-log`).

### Where the log is read

- **This machine.** `%LOCALAPPDATA%\Ollama\server.log` and its rotated `server-1.log`, `server-2.log`, ... (with
  `app.log` beside them) on Windows, `~/.ollama/logs/server*.log` on a Mac or a user install, the journal
  (`journalctl -u ollama`) on a systemd Linux. The whole rotation set by modification time, as bytes: a line with
  invalid UTF-8 is shown with a replacement mark, never a silent stop.
- **Another machine, with an `ssh:` entry** on its `ollama.hosts` entry: one command per read over that entry
  (`ssh -o BatchMode=yes`): `sh -c` over the files or the journal on a Mac or Linux, PowerShell on Windows. The bytes
  travel as base64, so the offsets stay exact; the platform that answered is kept, and per host the offset or the
  journal cursor (`<state>/ollama/server-log-remote.json`). A rotation reads the old file's end, then the new one.
  The steward's job reads every such host every 30 seconds; `halo ollama events --host H` reads it now.
- **Another machine, no `ssh:` entry.** The ladder: a fleet member that serves it pushes its new server events with
  its ledger push (the hub ties them to the host by the member's address), else only `/api/ps` says the fit
  (`size_vram < size` is a spill).

### Is logging live

`ollama_steward/log_status.py` gives every host one status, on the hardware card (`log`, `log_path`, `readable`),
`halo ollama hardware`'s `log:` line, Local -> Hosts and Local -> Logs:

| State | When |
|---|---|
| live | the newest log line is newer than the ledger's newest call to that host minus 60 s, or lines arrive with no calls |
| stale | the ledger has calls in the last 15 minutes the log never saw (Ollama writes elsewhere, or it is an old file) |
| quiet | no calls and no log lines in the last 15 minutes |
| unreadable | the file or the ssh read did not answer |
| on that machine, no ssh entry | the ladder above: a member's push, or `/api/ps` only |
| missing | no log where Ollama writes it on this machine |

`debug: on` is added when debug-level lines appear. The debug window is said, never done: "set `OLLAMA_DEBUG=1` and
restart Ollama on <host>; very verbose; it still does not log request bodies; turn it off after". To see what Halo
sends, the logging proxy in the knowledge does.

### The log drives recovery

After each call to a host whose log is readable from here, the loop reads the log lines since the call began
(`agent/ollama_log_recovery.py`, at most 2 s: a read every 0.2 s until the call's `[GIN]` line is there; one read over
ssh, only for a host whose ssh read answered before) and keeps the events for that model and the unattributed ones in
the call's window. The kinds go on the call's ledger line (`log_events`). Then:

- **`prompt-trimmed`.** The log's `limit / prompt / keep` replace the reply-count guess: the recovery sizes the new
  window from the real prompt, and the line says "the log shows the prompt was cut at 2,050 of 23,536 tokens on pc
  (the request's window 4,096): re-sent with a 32k window". A call whose log shows its `[GIN]` line and no cut is
  never called trimmed from the counts alone.
- **`cpu-spill`.** One line with the layers on the GPU and the fit option (the profile's fix, else the fit plan's).
- **A crash** (a failed load, out of GPU memory, a CUDA error, a runner that died): its fingerprint is written at
  once and the line names it ("... -- crashed here on <date>: CUDA error ... (halo ollama crashes --why)").
- **`reply-cut`.** The reply reserve line.

The preflight takes the log's last cut of the model in this session as its evidence: when Halo's estimate fell short of
the real prompt, the next send that would not fit is a decision before the bad answer, with "(the log cut this model's
prompt at 2,050 of 23,536 tokens at 14:03)" on its line.

### Crash forensics

A fingerprint (`ollama_steward/fingerprints.py`, `fingerprint_facts.py`) now carries the load it died in: the
`starting llama-server` command, `offloaded N/N layers`, the graph splits, the CUDA and CPU KV buffers, the KV type
and flash attention in force at that load (the startup block's and the command's, not the card's now), the Ollama
version, the `num_ctx` the ledger line nearest the crash asked for, and the load time. The command names a blob, not
the model; the request's `template selection` line names it, else the call the loop read it for. `halo ollama crashes
--why` prints each fact with where it came from; each new fingerprint is one plain-language line in the steward's notes.

### A crash that repeats

A fingerprint seen twice with the same settings is one `error` finding (rule `crash-repeats`, `rules_crash.py`).
Halo's side is its proposal, through the steward's apply modes (`ollama.steward.apply`): a smaller window in the
profile (half the crash window, never under 8,192, never over the battery's usable window). The host's side is said
only: f16 KV (`OLLAMA_KV_CACHE_TYPE=f16`), flash attention off (`OLLAMA_FLASH_ATTENTION=0`; Ollama takes neither per
request), a fitted twin (`halo ollama tune <model> --window N`), and on a Windows host with an update staged
"0.40.13 is staged on <host>; the crash fix is in it -- restart Ollama there".

### The fit badge cites the log

See [the model card](MODELS-cards.md#the-fit-badges-evidence-3360-r3): a model's last load on its host, as the log or
`/api/ps` says it, with the tok/s the ledger measured.

## The degradation ladder (3.3.6.0 R4)

When a local call fails, Halo walks one explicit ladder, one rung per failure, each rung one line, one pass per turn
(`agent/degrade.py`, `local.ladder` in [CONFIG.md](CONFIG.md)):

1. **repair** -- the dialect's repair loop: the call asked once more with what was wrong (an empty reply, a reply
   that did not parse); for broken tool arguments the repair round is this rung;
2. **smaller-ask** -- one re-send with the lean prompt and the tool budget's six most relevant tools ("rung 2: a
   smaller ask -- 6 tools instead of 31, the lean prompt");
3. **other-local** -- the nearest probed local model with tools that shares the card with the resident one, through
   the switch step;
4. **cloud** -- only when `routing.escalation` allows it (its `to`; `ask: true`, no policy or a trigger outside its
   `when` says why it was not taken and goes on): it is the escalation policy, never a second one;
5. **ask** -- one question to the user with what was tried; the turn ends there.

The triggers: an empty reply twice, an empty reply with no tool call from a model the battery found with no tool
calling, the prompt cut twice (the log or the counts), two failed tool calls between rounds (`tool_failures`). A rung
that does not fit the trigger is passed (repair only answers an empty or unparsed reply). The worst case adds four
calls to a turn. The rungs taken ride the turn's ledger lines (`ladder`) and the post-mortem shows them;
`local.ladder: off` leaves the plain failure lines of the table in [MODELS-cards.md](MODELS-cards.md).

## The answer post-mortem's sources (3.3.6.0 R4)

"Why this answer?" (`agent/postmortem.py`; Studio's Live rows, `/why [turn]`, `halo session postmortem`) rebuilds one
assistant turn from what was recorded, no request sent: the turn's ledger lines (`session`, `turn`: `trimmed`, the
read `prompt_eval_count` against `estimate_tokens` and `num_ctx_sent`, `composition`, `tools_count`, `done_reason`,
`cache_reused_pct`, `log_events`, `dialect_record`, `ladder`, `loop`) and the session log (a thinking block and no text in
the turn's last answer). The line names the first causes found, in this order: the prompt cut (where and how much),
an empty reply from a small budget (`num_predict` hit), thinking only, memory over half the prompt, no tools offered;
a turn with none says "nothing cut; 92 % of the prompt reused from cache". A sub-agent's turn reads its own
`agent-<id>` lines.

## The model shelf (3.3.6.0 R4)

`models_library/shelf.py`: per installed model its last use (the ledger's newest answered call on that host), its
size on disk, whether a role picked it (a small, compaction or repair call, or a role, lineup or the default naming
it) and "never used"; the Models rows show a hint once it is idle ("not used in 30 days, 17 GB"). **Retire** is the
existing delete with its uses card first (a live session on it waits; a use asks for force) plus one line in
`~/.halo/ollama/shelf.jsonl` `{model, digest, size, host, retired_at, why, repull}`, the re-pull line `ollama pull
<model>` or a fitted twin's recipe; **Re-pull** is the existing pull job. Nothing deletes without the button or
`halo models retire`; `halo models shelf [--repull <model>]` lists both sides.
