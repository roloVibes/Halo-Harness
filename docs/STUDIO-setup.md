# Studio: the Setup section

Read this when you set this box up from Studio's Setup section: what each block writes and the routes behind it.

Part of [Halo Studio](STUDIO.md), which lists every part.

## Setup: the wizard's blocks as forms (3.3.0.0)

**What it is** (3.3.0.0 R1). This box's setup on one page, `Alt+8` (`halo studio --mode setup`,
`?mode=setup`, `/studio setup`): the terminal wizard's blocks (`halo init`) as forms you fill in any order,
each with its own **Save** and its own line (`saved`, `1 changed` or `problem`, with the lines the server
answered under it). The status strip on top says what is set now: the providers set up here, the default
model, the lineup, the permission mode and the terminal theme. The rail lists the blocks with their line;
a click brings the block's panel back and focuses it. Every block writes the key the wizard writes in
`~/.halo/config.json`, the same as `halo config set`, and the page reads the state again whenever
config.json or a lineup moves on disk (a `halo config set` in a terminal shows at once).

## What each block writes

| Block | Writes | The same as |
|---|---|---|
| Default model | `model` (a ref the catalog of the providers set up here lists) | `halo config set model <ref>` |
| Permissions | `permission_mode` (`auto`, `acceptEdits`, `default` or `plan`) | `halo config set permission_mode <mode>` |
| Terminal theme | `theme` (the six TUI themes, each swatch in its own colours; Studio's own dark / light switch is this browser's) | `/theme <name>` |
| Team | One model for everything: `team` removed, `roles.enabled` false; `auto` with no `team` set: `roles.enabled` true only; a lineup: its `roles.*`, `team: <name>`, `roles.enabled` true | the wizard's Team step (`lineup_choice.py`, which both call) |
| Providers, Local models | (3.3.0.0 R2) | `halo init` |
| Linux fixes, Check | (3.3.0.0 R3) | `halo doctor` |

## The routes

`GET setup/state` (every block's value and rows; a provider is only `set` or not, no key is
ever in it), `POST setup/config {key, value}` (only `model`, `permission_mode` and `theme`; a value the
block does not list is a 422 with `problems` and nothing is written), `POST setup/team {lineup}` (a lineup
name, `one-model` or `auto`) and `GET setup/team/<name>/preview` (the Team step's preview lines); each
write answers the fresh state and the lines it wrote (`studio/setup_api.py`, `studio/setup_state.py`).
