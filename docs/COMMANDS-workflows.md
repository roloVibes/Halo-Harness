# Commands: workflows

Read this when you list, show, make, try or run a workflow from the command line (`halo workflows`).

Part of [Commands](COMMANDS.md), which lists every part.

## `halo workflows`

(3.6.0.0 R5) Your workflows: one file each in `~/.halo/crew/workflows/` (workflow/1: your agents in steps, in order;
side by side ones work at the same time; Repeat until), a trusted project's in `.halo/crew/workflows/`, and the
starters Halo ships (code, plan, review, research, media; read-only, copy one to make it yours). Studio's Agents -> 2
· Workflows is the full editor ([CREW-FORMATS.md](CREW-FORMATS.md)); when main hands a workflow work is a line on the
map (`halo maps`, Agents -> 3 · Map).

```sh
halo workflows list                                  # yours, this project's, then the starters
halo workflows show review                           # its file, and the maps it is on
halo workflows new my-review --from review           # one of yours: a copy (or, without --from, a blank one-step one)
halo workflows copy review                         # your own copy (my-review), to edit; --as names it (3.6.0.0 R5d)
halo workflows edit my-review                        # your $VISUAL / $EDITOR on your file; else Studio on it
halo workflows try my-review "review the login change"   # on a throwaway copy of this repo, step by step, with its cost
halo workflows run my-review "review the login change"   # here, for real, on the step runner (each step's agents as
                                                         # children of a session on your default model)
```

`enable`, `disable` and `when` went with the board of squares (3.6.0.0 R5): the map says when main hands a workflow
work.

## `halo workflow`, `halo blocks`

(3.6.0.0 R5) Each prints one line and exits 0: `halo workflow` -- "use halo workflows"; `halo blocks` -- "starters:
halo workflows new <name> --from <starter>". A pack's Orchestra workflow still compiles to a goal run:

### `halo orchestra new --workflow`

`halo orchestra new --workflow <pack>/<name> [--input K=V ...]` makes the
compiled run without starting it (`halo orchestra run <run>` starts it).
