# Commands: the pack kit

Read this when you start a pack, check one, or install your own folder so every edit shows at once (`halo pack new`, `halo pack test`, `halo pack install --link`).

Part of [Commands](COMMANDS.md), which lists every part.

Halo 3.3.12.0 R4. The guide these commands serve is [PACK-AUTHORING.md](PACK-AUTHORING.md); the contract is
[EXTENSION_API.md](EXTENSION_API.md); the other `halo pack` verbs are [COMMANDS-packs.md](COMMANDS-packs.md).

### `halo pack new`

`halo pack new <id>` writes `<id>/` in the current folder: a pack that `halo pack inspect` reads clean, that installs
and enables with every grant it asks for, that `halo pack doctor` finds nothing wrong with, and that `halo pack test`
passes. Always written: `pack.yaml`, `.claude-plugin/plugin.json`, the entry command `commands/<id>.md` (`/<id>` once
the pack is enabled: what it is, its commands, workflows and lineups, and its default action), a `README.md` written
from the manifest (every file in one line, the permissions and what each lets the pack do, the Install section from
`requires:`), `HALO-PACK.md` (what a Halo session follows when pointed at the folder: the contract, the loop, the
rules), `CHANGELOG.md` and `tests/pack_test.py` (the pack's own test, `python -m tests.pack_test`). A folder already
there is one line and exit 1; a bad id is the id rule's line. Exit 0 written, 1 could not, 2 usage.

```sh
$ halo pack new demo --kinds agents,teams,workflows,studio
made demo at /work/demo: 24 files
kinds: agents, teams, skills, artifacts, workflows, studio
workflows brings agents, artifacts, skills (it uses them)
entry command: /demo (commands/demo.md), once the pack is enabled
next: cd /work/demo && halo pack test .
```

#### `--kinds`

The parts to write, comma separated, one working example each: `agents` (two bios with every section a bio has),
`teams` (a lineup with two roles, two tiers and acceptance), `skills` (two), `commands` (a second command), `hooks` (a
PostToolUse hook that appends a line to the pack's data folder), `mcp` (a stdio server with one tool), `events` (a kind,
its schema and a sample), `artifacts` (a schema and a sample), `workflows` (two stages, both roles, ending in the
artifact; it brings agents, artifacts and skills), `studio` (a section with a markdown panel, a table over
`data:rows.json` and a bundle panel, and a page of its own over its own routes: `studio/page.js`, `server/routes.py`), `bundle` (a `bundle:` block), `fleet` (a capability and an inspector line),
`policy` (a policy hook and its mode), `modes`, `setup` (a form, a check and a note), `themes` (a palette of the
pack's own; this Halo reads it from 3.3.12.0 R2) and `integration` (an open-source tool wrapped: `requires:` rg, a
command, an MCP server and a hook that use it). A word that is no kind is a usage line naming them.

#### `--all`

Every kind.

#### `--dir`

The folder the pack's folder goes in (the current folder by default).

#### `--name`

The pack's name (the id in words by default).

#### `--description`

One sentence, what the pack does: pack.yaml, the README, the entry command.

#### `--author`

The author pack.yaml and the LICENSE name.

#### `--github`

The default: also `LICENSE`, `.gitignore` and `.github/workflows/pack-test.yml`, which installs Halo Harness at the
tag of this release (`uv tool install git+https://github.com/roloVibes/Halo-Harness@v<version>`) on Ubuntu and
Windows and runs `halo pack test .`; the README gains "Install from GitHub".

#### `--no-github`

Leave those three out.

#### `--license`

The SPDX id pack.yaml and LICENSE carry (MIT by default, with its text; another id gets a LICENSE that names it).

### `halo pack test`

`halo pack test <folder | installed id>` makes every check against fakes, in a scratch home and project of its own
(`halo_harness.ext.testing`): never a model call, never the network, nothing of your own home read or written. The
manifest and every file it names; an install into the scratch home with every grant and `halo pack doctor` on that
copy; each bio and lineup loads; each skill and command parses and is offered; the entry command runs in a fake session
and lists every command, workflow and lineup; each hook runs once with a sample event of its matcher on stdin and exits
0 within its timeout (`"halo_test": {"exit": 2}` on a hooks.json entry declares another exit, `{"skip": "why"}` skips
it), its output JSON when it starts with `{`; each MCP server starts, answers `initialize` and `tools/list` (the tools a
bio or a policy of the pack names present) and stops; each event and artifact schema takes its sample
(`tests/samples/<events|artifacts>/<name>.json`); each workflow compiles to an Orchestra goal; each Studio panel's
source is there with the right type and a bundle module exports `mount` (and passes `node --check` when node is here);
each policy answers in shape for a call its `when.tools` names and is not asked about one it does not; each mode turns
on and off, read back; each Setup check runs green; each theme meets the contrast pins; the bundle block and a fake 24
GB card; each fleet capability; each requirement. 3.3.13.0 R2 (extension API 1.2): a section's view is there and
exports `mount`; the routes module imports through the pack's folder and answers `GET <prefix>/ping` in shape (a status
below 500); and, when no `--kinds` narrows the run, each of the pack's own `tests/test_*.py` runs as `python -m
tests.<name>` from its folder in a fresh scratch home and passes on exit 0 (the design pack's nine do).

A part that needs the network (an http hook, an MCP server by url), a model (a prompt hook) or a program not on this
machine (a hook's or a server's command, a requirement `used_by` names) is skipped with one line saying why. A doctor
row about this machine (no catalog model with a bio's tags, a fleet capability not available here) is a skip line too.

```sh
$ halo pack test .
halo pack test demo (/work/demo)
hooks/hooks.json: PostToolUse hook ${halo_python} ${CLAUDE_PLUGIN_ROOT}/hooks/log_write.py runs once with a sample PostToolUse event -- exit 1 (want 0): the hook broke
skip .mcp.json: MCP server rg: skipped, rg is not on PATH (pack.yaml requires rg)
RESULT: 31 checks, 29 passed, 1 failed, 1 skipped
```

Exit 0 when nothing failed (skips allowed), 1 when a check failed, 2 usage. `--json`: `{pack, ok, checks: [{kind,
file, what, ok, fix}], passed, failed, skipped, result}` (`ok` null for a skipped check). An installed id is tested
from its folder; nothing of the installed pack changes.

#### `--timeout`

Seconds each hook, MCP server answer and policy answer gets (10 by default).

#### `--verbose`

Print the checks that passed too (`ok   <file>: <what>`).

### `halo pack install --link`

#### `--link`

`halo pack install <folder> --link [--project]`: the installed pack is the folder itself, read in place. Nothing is
copied: a link file `<id>.link` goes in `~/.halo/packs/` (or the repo's `.halo/packs/`) through the journal (its row's
op is `link`), and state.json records the pack with `link: true`. Every reader -- `list`, `inspect`, `enable`, the
doctor, Studio, a session -- sees it as an installed pack, and an edit in the folder shows at the next read with no
reinstall. `halo pack update` and `halo pack rollback` have nothing to do for a link and say so in one line. The folder
must be on this machine.

### `halo pack unlink`

`halo pack unlink <id>` is `halo pack remove <id>`: for a linked pack the link file goes (journal op `unlink`) and the
folder stays as it is, since Halo never wrote in it; `--keep-config` keeps the record and its grants.

### The doctor's requirement rows

A pack's `requires:` tool entries ([EXTENSION_API.md](EXTENSION_API.md#requirements)): `halo pack doctor` prints one
warns row per tool not found here, `missing-requirement`, with the install line for this OS (Halo never installs
it), beside R3's `not-on-path` row for an `.mcp.json` command:

```sh
[WARN] demo: needs rg (command): rg is not on PATH; without it mcp:rg, hooks/rg_todos.py does not run -> install it: sudo apt install ripgrep -- Halo never installs a requirement
```
