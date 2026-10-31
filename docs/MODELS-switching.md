# Models: switching models and effort on a local model

Read this when you move a session from one model to another (`/model`, a lineup's per-task pick, a resumed session, a compaction model) or wonder what the effort level does on a local model.

Part of [Models](MODELS.md), which lists every part.

## Switching models (3.3.5.0)

Every model has its own window, and a local one often a much smaller one
than the model a conversation started on. Before 3.3.5.0 the fit was per
call: the window was picked for the model of that call, and a request that
did not fit was compacted on its way out, silently, with the old model's
images, thinking blocks and tool calls still in the history. Now a model
change is one explicit step, `agent/model_switch.py`, run by:

- `/model <ref>` (the TUI, the picker, a remote `set_model`): the step runs
  in the session's worker between turns;
- `halo -p --model X --resume` (or `--continue`) on a session that last ran
  on another model: the step runs when the session starts and says its line
  before the first call;
- a lineup's per-task pick (`auto`, a role's model, an Agent call's own
  `model`): a child starts fresh, so its first request is what gets fitted
  (below);
- the compaction model (`compactionModel`, the `compaction` role): its own
  window is checked before the summary call;
- a steward profile (`ollama.profiles`) that lowers a model's window below
  the live prompt: the next call fits first.
- (3.3.5.0 R1) a session that STARTS on a local model whose card says it
  cannot take what it would be sent -- no tool calling, no vision while the
  history holds images, a history larger than its window: the step runs
  before the first call (`why: "start"`), says "this session runs on
  ol:<model>: window ..." and what it fitted, drops the tool catalog for a
  no-tools model and sets the reply reserve. A local model that can take
  everything gets no line.

### The step

1. **The target's window, with its source**
   (`agent/model_window.window_of`): the steward profile, the learned cap,
   the server's loaded window, the model's trained context, the host's
   `max_ctx`, the server's default, or the cloud catalog's context; the
   first that knows wins and is named. [LOCAL-MODELS.md](LOCAL-MODELS.md#the-window-of-a-model-and-where-it-came-from)
   has the sources per server kind.
2. **One line before anything moves**, in the transcript, the session log
   (a `model_switch` node holding the whole report) and Studio's Live:

   ```
   switching to ol:qwen3.5:9b@lan: window 32,768 (learned cap); this conversation is 48,210 tokens -> compacting to fit · effort: think off
   switching to ol:qwen3.5:9b@lan: window 65,536 (trained context); fits (11,400 of 65,536) · effort: think off
   ```

3. **The history fitted.** When the conversation is past `compact_at` of the
   target's window (the profile's `compact_at`, 0.8 when unset; never more
   than the window minus the reply reserve), it is compacted before the first
   call to the new model, through the ordinary compaction path with
   `trigger: "switch"`. `/model` compacts on the model being left, whose
   window holds the history (a compaction model writes the summary instead,
   its own window checked first); the other paths find the session already
   on the target and compact before its first call. The tool catalog is
   re-capped for the new window's class (Ollama's `tools_max`), and what the
   target cannot take is converted on the wire (the log is never rewritten,
   so a switch back gets everything back):
   - an image becomes its caption (`[Image: <path> (image/png 800x600; this
     model takes no images)]`) when the model has no vision;
   - thinking blocks are dropped when the model has no thinking, and on the
     Anthropic dialect a thinking block another provider wrote (no
     signature) is dropped either way;
   - tool calls and results are re-shaped by each dialect's builder (native
     Ollama, OpenAI chat, Anthropic); a call id with characters the
     Anthropic API refuses is rewritten the same way in the call and its
     result; when the model has no tool support (`/api/show` names no
     `tools`, or the tool-call probe said no) every call and result becomes
     text (`[tool call: Read {...}]`, `[result of Read: ...]`) and no tools
     are sent;
   - the converted history always holds a user turn with text, so it never
     reaches a Qwen 3.5 model as "no user query found in messages".
4. **The reply reserve**: the profile's `num_predict`, else the window
   class's default (2,048 under 16k, 4,096 under 32k, 8,192 under 64k, 16,384
   above), sent as the reply's room on a local model.

`/model` then prints the report: "on ol:qwen3.5:9b@lan: compacted to 21,300
tokens; 2 images to captions; tools 64; reply reserve 8,192".

Halo 3.3.5.0 R0b: before the step's first line, `/model` prints the target's
model card -- its `how` lines, the exact way Halo will call it -- and after
the report, when the target cannot run the main agent here, the main-model
line with the coder-lane offer ([MODELS-cards.md](MODELS-cards.md)):

```
ol:qwen3-coder:30b@lan, a coding model -- how Halo calls it:
  no think field (the model does not think)
  no tools: answers only (tool turns in the history go as text)
  images as captions (no vision)
  window 65,536 (the card's fit), reserve 16,384
  dialect: native (/api/chat)
switching to ol:qwen3-coder:30b@lan: window 65,536 (the card's fit); fits (9,800 of 65,536)
on ol:qwen3-coder:30b@lan: no tools (answers only); reply reserve 16,384
qwen3-coder:30b is a coding model with no tool calling on this server: it can write and answer but cannot act; as the main agent it would not run tools
Keep it as the coder lane under ol:qwen3.8:27b@lan (lineup 'local-coder'), or go ahead anyway.
```

### A child on another model

A sub-agent on another model than its parent's (`agent/model_switch_child.py`)
gets the same step for its first request: when its system prompt, tools and
the prompt it is handed are past `compact_at` of its window, the prompt is
cut to fit (its head kept) with one line at the cut ("[... 21,000 tokens of
this task's text were cut to fit ol:qwen3.5:9b@lan's window (32,768 tokens)]"),
the child's transcript gets the switch line, and the parent's view shows it
as the child's first event.

### When the request will not fit (3.3.5.0 R4)

A switch fits the history to the new model's window before its first call;
a conversation that grows past the window later meets the preflight: before
the call one line ("prompt 41,104 tokens · window 32,768 · usable 16,386 ·
this will be cut") and three answers -- compact, a bigger-window model on the
same host (a switch with `why: preflight`, the same step as `/model`, kept
for the rest of the session) or send anyway, ordered so the task survives the
cut. A compaction on a local model is sized to the window of the model it
runs on. See [MODELS-prompt-budget.md](MODELS-prompt-budget.md#the-preflight).

### The steward knows

Each ledger line carries `switched_from` (the previous call's model in the
session, when it differs) and `fitted` (a switch step ran before the call);
the rule `switch-without-fit` flags a call to another model with no step
before it. See [MODELS-ollama-steward.md](MODELS-ollama-steward.md#switch-without-fit).

## Effort on a local model

The effort level is a cloud idea. On a local model it does one of two
things, and the status bar says which (`providers/effort_on.py`):

| The model | What the level does | The status bar |
|---|---|---|
| a cloud route | the route's own levels, as before | the level (`high`) |
| an Ollama model with the `thinking` capability | Ollama's `think` field: low and below off, medium and above on; gpt-oss takes low / medium / high | `think on`, `think off`, `think high`, or `think default` when no field is sent |
| an Ollama model without it | nothing | `effort n/a` (muted) |
| a Hugging Face local server (llama-server, LM Studio, vLLM, mlx) | nothing: no effort field is sent | `effort n/a` (muted) |

`/effort` on a model whose effort does nothing answers "ol:qwen3-coder:30b
has no adjustable effort: n/a (it would set think on/off on a thinking
model)" and keeps the level for the next model that can use it. On a
thinking model it lists the real options; `/effort on`, `/effort off` or
`/effort default` (and low / medium / high on gpt-oss) save the choice for
that model as `models.think.<ref>` ([CONFIG.md](CONFIG.md)), which wins over
the level from then on. Studio's session header, the model pickers' rows
(`think on/off`, `effort n/a`) and the switch line carry the same word.
