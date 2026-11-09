# Changelog

## 1.0.0 (Halo 3.3.13.0)

- The Design section leaves Halo's core and ships as this pack: the page (`studio/design.js`, built from `studio/src/`
  on Studio's own React and parts), the routes (`server/routes.py`, under `/api/packs/design/design/`), `/design`, the
  Render panel (a ComfyUI workflow into a project; the core's Media render before), the Settings strip (`model`,
  `budget_usd`), and the projects in the pack's data folder (a `~/.halo/design` is moved there once).
- `halo design ...` is gone: every verb is a panel or a route of the section (`GET crafts?probe=1` is `halo design doctor
  --probe`).
