# Documentation Review (doc-review)

The reference pack Halo ships. It reviews a repo's Markdown documents: a
reviewer bio reads each file, a judge keeps the findings that matter and a
writer bio turns them into one typed review report, which Studio draws. It
uses every part of the extension API, so it is also the pack to copy when
you make your own: every file is explained below in one line.

## Use it

```
halo pack install doc-review                  # Halo finds it: the shipped folder is the last place it looks
halo pack enable doc-review --grant bash      # add --grant hooks and --grant mcp:lint for the plugin half
halo workflow run doc-review/review --input docs=docs
halo pack remove doc-review                   # its own files go; what you made stays, each one listed
```

In Studio, the Packs section (`Alt+7`) does the same: Sources lists this pack
with Install, Details shows what it brings with a Grant toggle per
permission, and Templates has Run review (the Orchestra form, filled in).
Once enabled, its own section "Docs review" comes after the core sections.

## The API version

`halo_api: {min: "1.0", max: "1.9"}`: it is written against extension API
1.0 (`halo_harness.ext.API_VERSION`), and a 1.x Halo keeps every name it
uses. `halo` is the Halo it needs (the release it ships in: `{min: "3.2"}`
from 3.2.0.0). Install refuses a pack whose range this Halo is outside, with
one line saying which: `pack doc-review needs extension API 1.2 to 1.9; this
Halo has 1.0`.

## Make your own pack from this one

1. Copy this folder and name the copy after your pack's id (lower case,
   digits and `-`, no `--`): `my-checks/`.
2. In pack.yaml set `id: my-checks`, your `name`, `version`, `description`,
   `author` and `license`; keep `halo_api`.
3. Keep the parts you want, delete the rest, and list what is left under
   `contributes` (a bio or lineup file that is not listed is a doctor line).
4. Ask for each permission your parts need under `permissions`; nothing
   that needs one runs until the user grants it.
5. Check it: `halo pack inspect ./my-checks` (what it offers, what it
   requests, every problem) and, once installed, `halo pack doctor`.
6. Install it from the folder (`halo pack install ./my-checks`), from a git
   url (`halo pack install https://example.com/you/my-checks.git`), or by
   id from a folder of packs you add once: `halo pack sources add ~/packs`,
   then `halo pack install my-checks`.

A pack's Python imports `halo_harness.ext` and nothing else of Halo.

## Versioning your pack

- **Ranges.** `halo_api: {min, max}` says which extension API versions it
  works with: `min` is the one you wrote it against; a minor version only
  adds names, so `max: "1.9"` (or no `max`, which means "this major only")
  is safe; a new major may drop a name that `halo pack doctor` has warned
  about for a minor version first. `halo: {min, max}` names Halo releases,
  when your pack needs something a release added.
- **Your own version** is semver (`version: 1.2.0`): a fix is a patch, a
  new part a minor, a change a user must act on a major.
- **Migrations.** For each change a user must know about, add an entry to
  `migrations`:

  ```yaml
  migrations:
    - {from: 1.1.0, to: 1.3.0, note: settings key lint.level is now lint.strictness, settings: {lint.level: lint.strictness}}
  ```

  `halo pack update` prints every note between the installed and the new version
  before it replaces anything, and moves each `settings` key you list from
  the old name to the new one in the user's `packs.settings.<id>` (a key the
  user already set under the new name wins). That rename is the only change
  Halo makes for you; say everything else in the note.
- **Test an update** before you publish it: install the old version, point
  it at the new folder (or bump `version` in your working copy) and run
  `halo pack update <id> --dry-run`: it prints the notes, the files that
  change and the settings it renames, and changes nothing. Then `halo pack
  update <id>`; if something is off, `halo pack rollback <id>` brings the old
  version back (and its settings names).
- **A new id is a new pack.** Renaming a pack's id makes users install it
  again; nothing carries over from the old id.

## Every file

| File | What it is |
|---|---|
| `pack.yaml` | The manifest: id, version, the API range, what it contributes, its settings schema, the permissions it requests. |
| `README.md` | This guide. |
| `agents/reviewer.yaml` | The reviewer bio (`doc-review--reviewer`): asks for a model with long context, needs bash, keeps its own memory namespace. |
| `agents/writer.yaml` | The writer bio (`doc-review--writer`): extends the reviewer, prefers the claude-sonnet family, may edit files. |
| `agents/helper.md` | A Claude-plugin agent (`doc-helper`) that answers questions about a docs folder. |
| `teams/review.yaml` | The review lineup (`doc-review--review`): the writer leads, the reviewer checks, two tiers, its acceptance and workflow. |
| `workflows/review.yaml` | The review workflow: read each Markdown file, judge the findings (you approve the plan), write the report. |
| `artifacts/review-report.json` | The review report's schema: a summary and one row per finding; Studio draws it as a table. |
| `events/review.done.json` | The schema of the review.done event (file, findings). |
| `studio/notes.md` | The Review notes panel of its Studio section. |
| `studio/checks.json` | The rows of its Checks panel. |
| `fleet/checklist.md` | The line a fleet mission's inspector shows for a part this pack runs. |
| `skills/check-links/SKILL.md` | A skill: check the relative links of a Markdown file. |
| `commands/review.md` | A slash command: review the named document. |
| `hooks/hooks.json` | A PostToolUse hook on Write (runs with the `hooks` grant). |
| `hooks/note.py` | The hook: notes the file in the pack's data folder and publishes review.done. |
| `.mcp.json` | The lint MCP server's command (starts with the `mcp:lint` grant). |
| `mcp/lint_server.py` | The lint server: `check_links` and `check_headings` over a Markdown file. |
| `.claude-plugin/plugin.json` | The Claude-plugin manifest of the pack's plugin half. |

## Its settings and permissions

Settings (`config.schema`): `style` (short or long) and `max_findings`;
change them in Studio (Packs: Settings, or the section's Settings panel) or
with `halo config set packs.settings.doc-review.style long`.

Permissions it requests: `bash` (the reviewer's tools, the docs.review
capability), `hooks` (hooks/hooks.json) and `mcp:lint` (the lint server).
The hook and the server run with Halo's own Python: `.mcp.json` and
`hooks/hooks.json` name it `${halo_python}`, which Halo expands when it
starts them, and their `PYTHONPATH` starts with Halo's package root. Run by
hand with a Python that cannot import Halo, they keep to their defaults.

More: docs/PACKS.md (using packs) and docs/EXTENSION_API.md (the contract).
