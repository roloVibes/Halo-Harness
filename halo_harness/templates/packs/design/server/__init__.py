"""The design pack's server side: routes.py is what Studio imports (contributes.studio.routes); the rest are the
modules it reaches by relative imports -- the projects on disk (store.py, jsonio.py), a design turn (session.py,
turns.py, crafts.py, crafts_probe.py), the routes (api.py and the *_api.py beside it), the raw files (files.py),
the design system (sync.py), the second opinion (critique.py), contrast (contrast.py), knobs (controls.py), assets
(assets.py), exports and the handoff (export.py), and a ComfyUI render into a project (render.py). They import
nothing of Halo but `halo_harness.ext`.
"""
