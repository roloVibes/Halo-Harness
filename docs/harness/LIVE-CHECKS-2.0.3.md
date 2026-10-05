# 2.0.3 live-check record

One line per check that ran against something real -- a real daemon, a
real API, a real binary -- rather than the hermetic fakes every suite
run uses. Taken from `plans/STATUS.md` and `plans/2.0.3-release-notes-
for-fix-pass.md`; never a path, a LAN address, or a key. See
[LIVE-CHECKS.md](LIVE-CHECKS.md) for the project's general opt-in live
runbook; this file is 2.0.3's own result record, not a how-to.

## The build host (its own NVIDIA card, a real local Ollama daemon)

- Round 2: a plain `ol:` turn, a Read tool round trip, the `@default`
  host form, and a thinking model with `think` on the wire -- passed.
- Round 3: a 27B model's context fit to 16384, fully in GPU memory, with
  no reload across requests -- passed.
- Round 5 (`halo local`): listed the real daemon's six models plus the
  Hugging Face Hub cache -- passed.
- Round 5b part 1 (calibration): the arithmetic's own guess of 65536 for
  a 30B coder model was wrong; `halo ollama calibrate` measured the real
  ceiling as 32768 in two load steps, and a 27B model at 16384 --
  calibration corrected the guess, exactly as designed.
- Round 5b part 2 (constrained tool calls): the first implementation
  forced every post-tool-result turn into a tool-call schema and looped
  the model for 25 minutes (175 requests) before being stopped by hand --
  FAILED, fixed before commit (repair-only constraint plus a
  three-identical-calls guard); not re-run live after the fix.
- Round 5c (runtime fetch + served GGUF): a 251.9 MB CUDA llama.cpp build
  downloaded and was serving within 11 seconds; the served model
  answered a turn -- passed. Two defects surfaced and were fixed before
  commit: the release picker was reading the wrong GitHub endpoint, and
  Ollama's import path was using a request shape Ollama no longer
  accepts.
- Round 5c (Ollama import): a `.gguf` file imported into Ollama and the
  resulting model answered a turn -- passed.
- Round 5d (acceptance check): a 30B coder model scored 100% on all four
  `halo doctor --local` steps at 164.7 tokens/second; a 27B thinking
  model scored 4/4 PASS in 17 seconds -- passed. A follow-up fix was
  needed for the gym's text extraction on thinking models (too small an
  output-token budget read back as an empty reply).
- Round 5e (offline mode): an `ol:` turn answered normally with
  `--offline` set, and the same flag made OpenRouter and the Hugging
  Face router both refuse with the documented plain sentence -- passed.
  (STATUS.md records this without naming a machine; grouped here because
  every other round 5e item ran on the build host.)
- Round 6 (served GGUF, follow-up): a real tool-capable 3B GGUF served by
  the managed `llama-server` (release b11417, CUDA 12.4) completed both a
  plain turn and a Read tool round trip through `hf:local` -- passed,
  though the model called Read twice before answering (a known gym-
  scoring gap, not a failure -- see `docs/LOCAL-MODELS.md`'s known
  limits).
- Round 5i part 2 (Codex settings reader): confirmed live against the
  real installed Codex configuration (`config.toml`/`AGENTS.md` reading
  only -- no ChatGPT login present) -- passed.

## The Kali VM, against the LAN host

- `halo ollama` from the VM read the remote host's real state (version,
  loaded models) -- passed.
- A plain `ol:` turn and a Read tool round trip both completed over the
  LAN -- passed.
- The offload sentence reported the real numbers for a model split
  between GPU and system memory -- passed.
- This run found a MUST-FIX: a remote host with nothing loaded yet had no
  fit estimate at all, so Halo defaulted to the 131072 hard cap and the
  real GPU loaded a 30B model partially offloaded (19.9 of 24.2 GB in GPU
  memory). Fixed in round 5b: a conservative 32768 default for an unknown
  remote host, a learned per-host-and-model cap after the first load, and
  a visible suggestion in `/ollama`.
- `halo local` and the offline-mode refusal are both confirmed live
  (rounds 5 and 5e), but neither is separately pinned to the Kali-VM-
  against-the-LAN-host combination in STATUS.md or the fix-pass notes --
  see the build-host section above for where each is actually recorded.

## The Hugging Face router, with the owner's token

- `GET /v1/models`'s real shape: confirmed live 2026-10-04, per-provider
  (a `providers` list per model), not the flat shape the round 4
  implementation assumed -- 135 models visible for this token. This was
  a MUST-FIX (the round 4 parser read the wrong shape and found zero
  models and zero cost for every `hf:` turn); fixed before release --
  context, price, tools, and structured-output support now derive from
  the live `providers` rows, and the live-confirmed shape is now also the
  hermetic suite's own fixture.
- A plain turn, a Read tool round trip, and the `:cheapest` suffix all
  completed through Halo's `hf:` route -- passed.
- The reachability column correctly said reachable.
- STATUS.md's own round 4 line says "no live router check (no token on
  the build host; round 6)" -- that line is stale. The fix-pass notes
  record this run happening on 2026-10-04, after round 4 shipped, and it
  is the reason the round 4 catalog parser was fixed before the release;
  this record follows the fix-pass notes' dated, specific account.

## The Experiential gateway, with the owner's key

Probed directly against the real gateway (not yet through a Halo route --
`xp:` is 2.0.4 scope), to ground the 2026-10-04 research round:

- Models list: `GET /v1/models` returned 299 models for this key (the
  public catalog page shows about 1,089 -- the key's own enabled rungs
  decide what's visible).
- One completion: `qwen3.8-27b` answered "pong", billed through
  `usage.cost` (not a top-level `cost` field, contrary to what the docs
  alone say).
- The `usage` field refusal: driving the gateway through Halo's existing
  `or:` (OpenRouter) dialect with a base-URL override gets a plain 400 --
  "the parameter 'usage' is not supported by this gateway profile" --
  confirming the gateway needs its own request profile, not OpenRouter's.
- `jev-latest` answered 503 `unavailable_route` at that hour (a gateway-
  side routing state, not a Halo defect); `GET /api/v1/credits` returned
  real credit/usage totals.

## The owner's Mac

Pending -- no Apple Silicon machine was reachable to any 2.0.3 worker.
[docs/MAC.md](../MAC.md) is the quick-start the owner runs by hand on his
own machine; its own "Please confirm" section lists exactly what is
still open there (the menu-bar env-var method, the Apple memory-share
estimate, `mlx_lm.server`'s own flags).

## OpenAI API and Codex subscription

Fakes only. No OpenAI API key and no ChatGPT login were available on the
build host for either round (5i part 1, 5i part 2) -- every behavior is
verified against the parameterized fakes (`tests/helpers/mock_openai.py`,
`tests/helpers/fake_codex.py`) only. `docs/LOCAL-MODELS.md` marks both
routes "verified against the fake only until a key or login is
available"; the one exception is the Codex settings/`AGENTS.md` reader,
confirmed live above against the real installed config with no login
needed.
