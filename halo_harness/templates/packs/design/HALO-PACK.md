# HALO-PACK.md: working on the Design pack

You are working in the folder of a Halo pack Halo ships. Read this page first, then follow its loop for every change.
The full guide is Halo's `docs/PACK-AUTHORING.md`; the contract is `docs/EXTENSION_API.md` (this pack uses its 1.2
parts: a section's view, `api.lib`, a pack's own routes, the host services).

## What this pack is

`design` (pack.yaml: `id`), "Design": the Design section of Halo Studio, out of Halo's core since 3.3.13.0. It brings:

- Studio section `design` -- Design, drawn whole by `studio/design.js` (`sections[0].view`)
- its routes, `/api/packs/design/design/...`, answered by `server/routes.py` (`contributes.studio.routes`)
- `/design` (`commands/design.md`, `studio: design`: it opens the section)
- settings `model` and `budget_usd` (`config`), a palette line, and `requires:` for the seven craft apps

## The contract in one page

- **pack.yaml** is the manifest; `halo_api: {min: "1.2", max: "1.9"}`: the view, the routes and `ext.host` are 1.2.
- **Code** imports `halo_harness.ext` and nothing else of Halo: `from halo_harness.ext import host` for what Halo does
  for it (the state folder, models for a task, the registered MCP servers and a probe, the tool env, a URL fetch, Halo as
  a child process, ComfyUI), `data_dir`, `get_config`, `testing`. The server modules import each other relatively.
- **The page** (`studio/src/`, TypeScript) imports React and `@halo/<part>` (ui, api, events, store, theme, util,
  widgets, workspace); the build takes them from Studio (`api.lib`), so nothing of the shell is copied in. After a
  change: `npm run build` in `halo_harness/studio/ui` (it type-checks this folder too and rebuilds `studio/design.js`).
- **Permissions**: `studio-script` (the page) and `studio-routes` (the routes); nothing runs until granted.

## The loop

1. Edit the files.
2. `halo pack test .` -- the kit's checks (the manifest, the doctor, the view module exports `mount`, the routes answer
   `GET ping` in shape) and the pack's own `tests/test_*.py`, each in a scratch home.
3. `halo pack install . --link --project` once, then `halo pack enable design --grant-all`.
4. Try it: `/design`, the Design section in Studio.
5. `halo pack doctor` -- nothing about this pack left. Then go back to 1.

## The rules

- **No telemetry.** The pack sends nothing anywhere on its own; a design system read from a URL goes through Halo's one
  network door (`host.fetch`), which offline mode closes.
- **No secret in a file.** The doctor's privacy scan reads every file of the pack.
- **The projects are the owner's.** They live in the pack's data folder; disabling or removing the pack leaves them.
