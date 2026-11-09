# Writing a pack: the kit, the loop, the checks

Read this when you write a pack, or point a Halo session at a folder to write one, and want it to work the first time.

Halo 3.3.12.0 R4. A pack is a folder Halo installs, enables and removes ([PACKS.md](PACKS.md)); its contract is
[EXTENSION_API.md](EXTENSION_API.md). This page is the way to build one that is known to work, for a person and for a
Halo session alike: the commands are [COMMANDS-packs-kit.md](COMMANDS-packs-kit.md).

## Start

```sh
halo pack new my-pack --kinds agents,teams,workflows,commands   # or --all for every kind
cd my-pack
halo pack test .                          # every check against fakes: RESULT: N checks, N passed, 0 failed
halo pack install . --link --project      # the installed pack is this folder: an edit shows at once
halo pack enable my-pack --grant-all
```

**Or take the template on GitHub:** https://github.com/roloVibes/halo-pack-template is the `--all --github` folder as a
GitHub template repository ("Use this template", then `python rename.py <id>`; its workflow runs `halo pack test .`).

`halo pack new` writes a complete pack: one working example of each kind you ask for, `pack.yaml`, the entry command
`commands/my-pack.md` (`/my-pack` in a session lists what the pack brings and runs its default action), a README written
from the manifest, `HALO-PACK.md`, `CHANGELOG.md`, `tests/pack_test.py`, and (by default) the GitHub files. Change the
examples into your own; delete the ones you do not need, and take them out of `contributes` too.

**Point a Halo session at it.** From inside the folder, `halo --team pack-author` runs the lineup Halo ships for this:
the `pack-author` bio carries the one-page contract and the loop below and reads `HALO-PACK.md` first; a
`pack-researcher` finds and evaluates open-source tools to wrap; a `pack-reviewer` reads the pack against the checklist
at the end of this page. Several sessions can work on several pack folders at once: each has its own folder, its own
link and its own `halo pack test`.

## The kinds and when to use each

| Kind | Use it when the pack should ... | What the kit writes |
|---|---|---|
| `agents` | bring agents with their own model needs, tools, skills, memory and prompt | `agents/lead.yaml`, `agents/checker.yaml`: every section a bio has |
| `teams` | hand those agents roles that work together | `teams/crew.yaml`: two roles, two tiers, acceptance |
| `workflows` | run a repeatable job of several stages, each with its role, ending in a typed result | `workflows/flow.yaml`: draft then check, ending in `report` |
| `skills` | teach a session how to do one thing, cited by a bio or a workflow | `skills/brief/`, `skills/checklist/` |
| `commands` | give the user a slash command | `commands/hello.md` (the entry command is always written) |
| `hooks` | react to a session's tool calls or events | `hooks/hooks.json` + `hooks/log_write.py` (PostToolUse) |
| `mcp` | give the model tools of its own | `.mcp.json` + `mcp/words_server.py` (one tool) |
| `events` | tell Studio, bios' triggers and workflows that something happened | `events/note.added.json` + its sample |
| `artifacts` | produce a typed document Studio draws | `artifacts/report.json` + its sample |
| `studio` | show something in Studio | a section: a markdown panel, a table over `data:rows.json`, a bundle panel |
| `fleet` | offer a capability other harnesses can send work to | a capability and an inspector line |
| `policy` | decide tool calls before they run while a mode is on | `policy/guard.py` and the `careful` mode |
| `modes` | have a runtime switch of its own | the `focus` mode |
| `setup` | ask the owner for settings or check the machine once | a form, a check and a note in Studio's Setup |
| `themes` | ship a palette | a dark palette, every token, AA-clean (Halo reads it from 3.3.12.0 R2) |
| `bundle` | keep a local model ready while it is on | a `bundle:` block: needs, reservation, routing |
| `integration` | wrap an open-source tool | `requires:` rg, a command, an MCP server and a hook that use it |

## Expansion packs

A pack is to a session what an expansion is to a card game: it adds cards without changing the rules. Its agents are
new bios (`<id>--lead`), its lineup a new way to combine them (`halo --team <id>--crew`), its workflows new jobs a session
or the Orchestra can be asked to run (`halo workflow run <id>/flow`), its skills new know-how a bio or a workflow
stage cites (`<id>:brief`), its commands new slash commands. Roles, Team and Orchestra show them as the pack's: Roles
lists the bios and the lineup under "pack <id>", Team offers the lineup like any other, Orchestra runs the workflow with
the lineup whose `workflows:` names it. The kit's set is the pattern: two bios that show every section, a lineup with
two roles and tiers, a workflow that uses both roles and ends in the pack's artifact, two skills (one the workflow
cites). A bio's `description` is the line Auto and a lineup's routing read to pick it: write it as "Pick me to ...".

## The loop

1. Edit the files.
2. `halo pack test .` -- read each failure line, `<file>: <what> -- <fix>`, change that file, run it again.
3. `halo pack install . --link --project` once; then `halo pack enable <id> --grant ...` with the grants you need.
4. Try it: `/<id>` in a session, the lineup, the workflow, the pack's section in Studio.
5. `halo pack doctor` -- until nothing about the pack is left. Back to 1.

## Testing

`halo pack test` makes every check in a scratch home and project of its own, never a model call, never the network
([COMMANDS-packs-kit.md](COMMANDS-packs-kit.md#halo-pack-test) lists them). What it checks, and why: every value of
pack.yaml (an install checks the same, so a pack that passes installs), the doctor on an installed copy (what the
owner would see), that each part loads where a session loads it, that each process the pack starts (a hook, an MCP
server, a policy, a Setup check) starts, answers in the shape Halo reads and stops in time. What it cannot check
without a model or the network: what a bio, a lineup or a workflow produces when it runs, a prompt hook, an http hook,
an MCP server reached by url, and a tool that is not installed here -- each is a skip line, not a failure.

`tests/pack_test.py` runs the same checks through `halo_harness.ext.testing` (stable in API 1.1) and then the pack's
own: `report.add(file, what, ok, fix)`. Since 3.3.13.0 `halo pack test` also runs each `tests/test_*.py` of the pack
as `python -m tests.<name>` from its folder, one check per module (exit 0 passes): the shipped signal pack's tests
drive its whole conversation through fakes that way. A pack that keeps a program running declares it under
`contributes.services` (EXTENSION_API.md "Services"); a command that should run a program instead of prompting the
model says `run:` in its frontmatter. The kit's policy example adds one, `testing.ask_policy(PACK, "guard", "Write",
{"file_path": ".git/config"})` answering deny. A schema's sample lives in `tests/samples/events/<kind>.json` or
`tests/samples/artifacts/<name>.json`; a hooks.json entry may say `"halo_test": {"exit": 2}` (it is meant to exit 2)
or `{"skip": "why"}`.

## How Studio shows the pack

While the pack is enabled its section comes after Studio's own (the rail's diamond), each panel drawn by Studio from
the data: markdown never as HTML, a table from a JSON file of the pack or of its data folder, a bundle panel only once
the owner grants `studio-script`. Its palette line, its event lines and its attention rows show where the core ones do;
its Setup blocks show in Setup; its bios and lineup in Roles. With `--link`, an edit to a panel's file shows at its next
read. [EXTENSION_API.md](EXTENSION_API.md#studio-contributions) has every key.

## How the fleet sees it

A `contributes.fleet` capability is one entry in this harness's capabilities catalog, available or not and why; a
mission part that needs it goes only to a harness that runs the pack with the grants it requires, and the worker checks
again before the part runs. An advertisement leaves the machine, so a value under `contributes.fleet` never holds a
secret, an environment reference or a path ([EXTENSION_API.md](EXTENSION_API.md#fleet-capabilities)).

## Themes

A pack's palette (`--kinds themes`, from 3.3.12.0 R2) is `contributes.themes: [{id, label, posture, palette}]` with every
token of the palette set, each `#rrggbb`, meeting the same contrast pins the ten core palettes meet (`halo pack test`
checks them). While the pack is enabled the palette is `<id>/<palette id>`: it shows in `/theme`, in Studio's header
menu and on Settings -> Themes under the pack's name, with the `-daltonized` and `-ansi` variants. Disabling or removing
the pack while its palette is in use puts back the theme that was in use before, in one line.

## Wrapping an open-source tool

Many packs are a session's way into a tool someone else maintains. Before you wrap one, evaluate it, and write the
evaluation into the README (the `pack-researcher` bio does this):

- **License**: an OSI license that sits beside the pack's own (MIT, Apache-2.0, BSD, MPL ...). Never copy its code into
  the pack: the pack calls the installed tool, and `requires:` says where it comes from.
- **Maintenance**: the last release and the last commit; an issue tracker that answers.
- **Telemetry**: whether it phones home, and how to switch that off. The shipped concord pack is the example: Concord's
  telemetry is on by default upstream, and the pack sets `CONCORD_TELEMETRY_DISABLED=1` in `.mcp.json` and in every hook
  command, and says so in its description.
- **What it reads and writes**, and whether it needs the network.
- **How it installs** on Windows, Linux and macOS: one line each.

Then declare it (`requires:`, [EXTENSION_API.md](EXTENSION_API.md#requirements)), wrap it, and test it with the fakes.
The kit's `integration` example wraps ripgrep: `mcp/rg_server.py` finds `rg` on PATH, runs it as an argument list with
`--` before the user's pattern (never a shell string), checks the input first (a pattern of at most 200 characters, a
folder inside the project), has a time limit and cuts the output; `hooks/rg_todos.py` reads its output after a Write.
Halo never installs a requirement: the doctor names a missing one with the install line, `halo pack test` skips what it
gates, the Pack Manager's row says "needs rg". The shipped concord template is the fuller model (an MCP binary, hooks
and a policy).

## Local-first packs

Local models and the steward are the core a pack stands on, and a pack uses them as the owner's own sessions do:

- **A bio asks for a local model by what it must do**: `models.capabilities: [local, tools]` (and a family name in
  `models.preference`). A pack's bio never names a route (`ol:...`, `or:...`): the pick is the best local model in the
  owner's catalog with those tags, on this machine or a paired host, and with none it runs on the owner's default model
  -- the cloud tier it falls back to. An owner who wants one model pins it in a clone of the bio (`ol:<model>@<host>`,
  `hf:local/...`), Studio's Clone.
- **A model held ready** is a `bundle:` block (`--kinds bundle`): `needs` (each role and the models that can fill it),
  `reservation` (the one held while the pack is on), `routing` (where other work goes). The Local tab's fit badge and
  `halo pack verdict <id>` say whether it fits this machine before anything downloads; `halo pack test` checks the
  block against the bundle schema and a fake 24 GB card.
- **The steward** watches every local call the pack's agents make exactly as it watches the owner's own: the pack adds
  nothing there and configures nothing. A pack cannot contribute steward rules today; that is on the roadmap.

## Publishing

1. Put the folder in a git repo; `--github` (the default) wrote `LICENSE`, `.gitignore` and
   `.github/workflows/pack-test.yml`, which runs `halo pack test .` on Linux and Windows against a pinned Halo tag.
2. Move `version` in pack.yaml and add the release to `CHANGELOG.md`; a change the user must act on also gets a
   `migrations` entry.
3. Tag it (`v0.2.0`) and use the CHANGELOG entry as the release notes.
4. Users add it once and install it by id: `halo pack sources add https://github.com/<you>/<pack>` then `halo pack
   install <id>`. `halo pack update <id>` clones the repo again, says each migration note between the two versions,
   and keeps the old version for `halo pack rollback`.

## Before you share it

- `halo pack doctor`: nothing about the pack.
- `halo pack test .`: 0 failed (and each skip line understood).
- The README is true: every file, every permission and what it lets the pack do, the Install section for each tool.
- The permissions are the least the parts use.
- No secret, personal path or address in any file; no telemetry.
- `version` and `CHANGELOG.md` moved together.
