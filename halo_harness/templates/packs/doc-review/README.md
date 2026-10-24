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
uses. `halo: {min: "3.1"}` is the Halo it needs. Install refuses a pack
whose range this Halo is outside, with one line saying which.

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
The hook and the server run with the `python` on your PATH; where that
Python cannot import Halo they keep to their defaults.

More: docs/PACKS.md (using packs) and docs/EXTENSION_API.md (the contract).
