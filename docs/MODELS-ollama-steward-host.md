# Models: the steward and the host

Read this when the model you tune is served by a `halo host` and you want to know where the steward runs, how its fixes land on that host and what comes back.

Part of [Models](MODELS.md), which lists every part.

## Three homes, one vocabulary (3.3.7.0 R2)

The steward ([MODELS-ollama-steward.md](MODELS-ollama-steward.md)) is the model-backed role that keeps local models
working well. It has three homes, and the same typed vocabulary in each ([HOST.md](HOST.md#the-vocabulary)):

1. **A strong or cloud model inside a harness** -- the best judgement; it lands through the host from any machine on
   the LAN.
2. **A cheap local model inside a harness** -- offline, slower thinking; the same path.
3. **The duty steward on the host** -- `halo host steward on --model REF`, an opt-in separate process that closes the
   loop when no harness is attached ([HOST.md](HOST.md#the-duty-steward)).

Which one acts is a matter of what runs: the rules and the guards are the same, and none of them is a model. The host
itself (`halo host`) is never a steward: it senses, applies, measures and reports.

## Landing through the host

When the host and model of a change are served by a paired host (`ollama_steward/host_client.for_host`), the
steward's apply (`steward.apply_change`, so both the rules' auto changes and the model's proposals) sends it as
`control/set_num_ctx`, `set_num_predict`, `set_keep_alive` or `set_tools_max`, with `evidence.finding` = the
finding's id and the steward's `why`. The steward's journal gets one line:

| Journal kind | When |
|---|---|
| `host-apply` | the host took it; it verifies it now (`host_change` is its change id); this harness mirrors the field in its own profile (`by: "hub"`) |
| `host-pending` | queued for the host's owner (`fleet.allow_control: ask` there) -- the line names `halo host allow <id>` |
| `host-refused` | the host's one line: a missing grant, a guard (one change at a time, the cooldown, the rate limit), an invariant |
| `host-verdict` | the host's verdict on a `host-apply` (`kept` / `reverted`, its line); a reverted change takes the mirror back |

The verdicts come back on the steward job's tick (`ollama_steward/host_land.sync`), and the job emits them as
`change` frames. `host_for` and `compact_at` are client-side decisions: they land in this harness's profile as before.

## What a peer's steward reads from the host

- **The host's findings** (`GET findings`): the rules over the host's own ledger -- every client's calls once peers
  push theirs (`POST ledger`) -- and its server events. A peer's steward job folds them into its run under its own
  names for the host and model, keeping the host's id (so a fix cites a finding the host knows); a finding the local
  rules already made is not repeated.
- **`where: client` findings** are the harness's to fix (H10.4): a prompt that outgrew its window, a reply cut with
  no room, a compaction that did not run. They arrive as this harness's own finding, the host named as the source,
  the line saying what to do here ("compact", "a bigger-window model"); compaction and the preflight do the rest.
- **The host's profiles** come back in the answer to each ledger push, under this machine's names, so a fix the host
  keeps reaches this machine's next call.
