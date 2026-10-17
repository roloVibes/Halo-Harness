"""tools/design_demo.py -- a demo Halo Design project for the Studio capture
(Halo 3.0.1.0 round D3): "Launch page" with an HTML hero artboard that reads
--space and --accent from :root and ships two knobs, a VectorCraft-style logo
artboard whose render.svg is drawn by hand, two open comments, a small design
system and two history lines (3.0.7.0 R3: with the model's reply text, the
thread the Design section draws). `seed(state_dir)` returns the project.
"""

from __future__ import annotations

import json
from pathlib import Path

HERO = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Launch page hero</title>
<style>
:root{--space:32px;--accent:#7c5cff;--bg:#0f1020;--text:#f2f2fb;--muted:#9a9db8;--radius:14px}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,sans-serif}
nav{display:flex;justify-content:space-between;align-items:center;padding:calc(var(--space)/2) var(--space)}
nav b{letter-spacing:.04em}nav a{color:var(--muted);margin-left:calc(var(--space)/1.5);text-decoration:none}
.hero{display:grid;grid-template-columns:1.1fr .9fr;gap:var(--space);align-items:center;padding:var(--space)}
h1{font-size:46px;line-height:1.08;margin:0 0 calc(var(--space)/2)}h1 em{font-style:normal;color:var(--accent)}
p{color:var(--muted);margin:0 0 var(--space);max-width:42ch}
.btn{display:inline-block;padding:12px 22px;border-radius:var(--radius);background:var(--accent);color:#fff;font-weight:600;text-decoration:none;margin-right:12px}
.btn.alt{background:transparent;border:1px solid var(--muted);color:var(--text)}
.shot{aspect-ratio:4/3;border-radius:var(--radius);background:linear-gradient(135deg,var(--accent),#21d4fd);display:grid;place-items:center;color:#fff;font-weight:700;opacity:.92}
</style></head><body>
<nav><b>PULSE</b><span><a href="#">Product</a><a href="#">Pricing</a><a href="#">Docs</a></span></nav>
<section class="hero"><div><h1>Ship the change, <em>not the meeting</em>.</h1>
<p>Pulse turns every pull request into a one-minute walkthrough your whole team can follow.</p>
<a class="btn" href="#">Start free</a><a class="btn alt" href="#">Watch the demo</a></div>
<div class="shot">product screenshot</div></section>
</body></html>
"""

LOGO = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" width="240" height="240">
<rect width="240" height="240" rx="48" fill="#0f1020"/>
<path d="M44 132h38l16-44 28 88 20-60 14 16h36" fill="none" stroke="#7c5cff" stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="196" cy="132" r="9" fill="#21d4fd"/>
</svg>
"""

KNOBS = [{"name": "Spacing", "kind": "range", "target": "css:--space", "min": 8, "max": 72, "step": 2, "value": 32, "unit": "px"},
         {"name": "Accent colour", "kind": "color", "target": "css:--accent", "value": "#7c5cff"}]

SYSTEM = {"name": "Pulse", "tokens": {
    "colors": {"--accent": "#7c5cff", "--bg": "#0f1020", "--text": "#f2f2fb", "--muted": "#9a9db8"},
    "spacing": {"--space": "32px"}, "radii": {"--radius": "14px"},
    "typography": {"font-families": "system-ui, sans-serif", "--h1": "46px"}},
    "components": [{"name": "Button"}, {"name": "Nav"}, {"name": "Hero"}], "sources": ["by hand"]}


TEXT_1 = """## Made two artboards

- **hero**: the landing page hero, a nav, the headline, two buttons and a screenshot area.
- **logo-mark**: a pulse line in a rounded square, drawn in VectorCraft.

Look at the headline weight first; the accent is `--accent` on `:root`."""

TEXT_2 = """Changed **hero** (v2):

1. The headline is 46 px now.
2. Two knobs: *Spacing* (`--space`) and *Accent colour* (`--accent`).

```css
:root { --space: 32px; --accent: #7c5cff; }
```"""


def seed(state_dir: Path):
    from halo_harness.design.store import Project
    p = Project.create("Launch page", model="or:anthropic/claude-sonnet-4.5", state_dir=Path(state_dir))
    hero = p.artboard_dir(p.add_artboard("Hero", "prototype")["id"])
    (hero / "index.html").write_text(HERO.replace("46px", "40px"), encoding="utf-8")
    (hero / "controls.json").write_text(json.dumps(KNOBS, indent=2), encoding="utf-8")
    logo = p.artboard_dir(p.add_artboard("Logo mark", "vector", app="vectorcraft")["id"])
    (logo / "render.svg").write_text(LOGO, encoding="utf-8")
    (logo / "source.json").write_text(json.dumps({"app": "vectorcraft", "kind": "vector", "title": "Logo mark", "document": "logo.vcraft"}), encoding="utf-8")
    first = p.snapshot(note="first hero")
    p.log_turn({"prompt": "A landing page hero for Pulse, a code-review walkthrough tool, with a vector logo mark.", "model": p.meta()["model"], "cost": 0.0412, "code": 0, "versions": first,
                "text": TEXT_1, "tool_calls": 6, "elapsed": 41.2})
    (hero / "index.html").write_text(HERO, encoding="utf-8")
    second = p.snapshot(note="bigger headline")
    p.log_turn({"prompt": "Bigger headline, and add knobs for spacing and the accent colour.", "model": p.meta()["model"], "cost": 0.0187, "code": 0, "versions": second,
                "text": TEXT_2, "tool_calls": 3, "elapsed": 18.7})
    p.save_system(SYSTEM)
    p.add_comment("hero", "Make the screenshot area feel less empty: add a faint grid.", x=78, y=52, version=2)
    p.add_comment("hero", "Nav links look too close to the logo.", x=40, y=7, version=2)
    return p
