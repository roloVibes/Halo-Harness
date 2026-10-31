# Models: which models can see

Read this when you want to share a screenshot or an image with a model and need to know which models can see, how Halo knows, and what happens when the model in use cannot.

Part of [MODELS.md](MODELS.md).

## Which models can see (3.3.6.0 R6)

Every model has one vision fact: `true`, `false` or unknown, with one of the three truths
([MODELS-cards.md](MODELS-cards.md), the card) and the source that said it (`providers/vision_fact.py`). The first
that says wins:

| order | where | truth |
|---|---|---|
| 1 | the battery's image probe (`halo models probe <ref>`, Studio's Probe) | verified |
| 2 | the server's own row: `/api/show` capabilities (vision listed, or a list without it: no), a projector (`projector_info`, an mmproj file) | declared |
| 3 | a Hugging Face `config.json`: `vision_config`, an image processor, a vision architecture (a plain `...ForCausalLM`: no) | declared |
| 4 | the cloud catalog's modalities (`image` in the input modalities) | declared |
| 5 | the library's chips, the hub's pipeline tag | declared |
| 6 | the family: llava, `-vl`, `vision`, moondream, minicpm-v, gemma3 (past 1b), llama4, pixtral, mistral-small3.1 / 3.2 ... | expected (a yes only) |
| 7 | nothing | unknown ("eyes?"; the probe settles a local one) |

The same fact is read by every place that says "can see": the card's `vision` (with `vision_truth` and
`sources.vision`), the eye chip on every row (Local's Library, Models and Loaded now, the model picker, Setup's
Default model, Settings' `model` row), the Library's "can see images" need (`halo models browse --need vision`), the
`eyes` role's placement verdict, the measured card's modality, and the card's blocks ("reads images" in use-it-for,
"cannot see images" in don't). `halo models --vision` lists the models that can see; `halo models show <ref>` has
the `vision:` line. A `visual` lane (`roles.visual`) on a model the probe found blind is a WARN in
`halo doctor --local`, with the fix.

## The vision probe

The battery's last step (the probe set `battery-3`): one `/api/chat` turn with a 1 x 1 red PNG in `images` (its
bytes live in `providers/battery_probes.py`, no file) and "What colour is this image? Answer with one word.",
`num_predict` 24 (a thinking model that answers in thinking only is asked once more at 600). Red (or crimson,
scarlet) is a verified yes; an error that names images ("this model is missing data required for image input") or
an answer that says it cannot see is a verified no; anything else is unverified, and the declared fact stands. A
model whose `/api/show` lists no vision (and has no projector) is not asked: its declared no stands. The answer
is cached with the rest of the profile by the model's digest, the Ollama version and the probe set, so it runs once
per weights; the cost line says "one 1 px image, one tiny call". A Hugging Face local server is not probed yet.

## What a turn with an image does

A model that sees gets the image as an image block (Ollama's `images`, the OpenAI dialects' `image_url`, Anthropic's
`image`), read from its saved file each time a request is built; the log keeps the path only. A model that cannot
(or a local model nothing says sees) gets the eyes offer first ([COMMANDS-main-io.md](COMMANDS-main-io.md#the-eyes-offer)):
the visual lane for this turn, a model that sees describing it into the turn, or the text alone with the path. The
Local section's Loaded now page counts which loaded Ollama models can see, so the right one is loaded before you
share the screenshot.
