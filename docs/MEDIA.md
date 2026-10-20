# The front-page media

Read this when you regenerate the front-page pictures and animations.

(Generated media -- images and video from local diffusion models through
ComfyUI -- is a different thing: see [COMFYUI.md](COMFYUI.md).)

The README's pictures are generated from the real TUI over mock data, not
hand-captured from a live session. Nothing in them is a real key, path,
hostname, username or phone number: the scenes run on a scripted
`FakeController`, fixture rows, fixture contacts (reserved 555 numbers) and
the literal cwd `~/project`, with a frozen clock, seeded tips and a scratch
`BRIDGE_TEST_HOME`. The privacy scan runs over the SVGs like any other text.

## What is where

| Path | What it is | How it is made |
|---|---|---|
| `docs/media/<name>.svg` | The Textual export of one capture | `tools/capture_screens.py` |
| `docs/media/<name>.png` | The same SVG rendered at 2x by headless Chrome | `tools/capture_screens.py`, when Chrome is found |
| `docs/media/<name>.anim.svg` | Animated captures only (`turn-phase-line`, `steer-mid-turn`): the frames assembled into one looping SMIL SVG, each under 1 MB | `tools/capture_screens.py` |
| `docs/media/hero.svg` | The README banner: the block-art wordmark from `halo_harness/banner.py` drawn as vector cells, the model chips, the tagline | `tools/hero_svg.py` |
| `docs/media/social-preview.svg` | The same wordmark at 1280x640 for GitHub's Settings -> Social preview (upload the PNG render by hand; GitHub has no API for it) | `tools/hero_svg.py --social` |
| `docs/media/studio*.png` | Halo Studio in the browser: the Orchestra, Roles, Design, Fleet and Team captures through the shell, headless Chrome over fixture data | `tools/capture_studio.py --mode orchestra\|roles\|design\|fleet\|team` |
| `docs/media/studio-modes.png` | The six Studio captures (Orchestra, Roles, Design, Fleet, Team, Session) side by side with a section label and its `Alt+1`..`Alt+6` key each, the README's Studio banner | `tools/studio_modes_banner.py` (`--check` says when it is stale) |
| `docs/media/diagrams/*.svg` | The four explanatory diagrams (session flow, routes, the connectors bridge, remote control), each under 60 KB, on their own dark card so they read on a light or a dark page | drawn by hand |
| `docs/screenshots/*.svg` | The older gallery under "What it looks like" | `scripts/screenshots.py` |
| `tools/captures.json` | The capture list: name, scene, size (default 120x40), theme, scale (2), and for an animation its frame durations | edited by hand |
| `scripts/capture_scenes.py`, `scripts/capture_dialogs.py` | The pilot scenes behind each capture, built on the helpers in `scripts/screenshots.py` | edited by hand |

## Regenerate

```sh
python tools/capture_screens.py            # every capture: SVG, animated SVG, PNG
python tools/capture_screens.py --check    # re-render the SVGs, compare with the committed ones
```

Useful flags: `--only name1,name2`, `--no-png`, `--out DIR`, `--chrome PATH`
(`HALO_CHROME` works too). The gallery of the older screenshots is the other
command, `python scripts/screenshots.py`.

Run both from a checkout with the repo on `PYTHONPATH`; no real `~/.halo` is
touched (the scenes scope `BRIDGE_TEST_HOME` to a scratch directory before any
import) and nothing is fetched except what Chrome itself loads for the SVG's
font.

## Chrome

PNG rendering needs Chrome or Chromium (`--headless=new`). The tool looks for
`--chrome`, `HALO_CHROME`, the usual Windows and macOS install paths and
`google-chrome` / `chromium` on `PATH`. With none of them found it writes the
SVGs, prints that the PNG step was skipped and exits 0; there is no Python
dependency for any of this.

## Every SVG carries an explicit size

Textual's export writes a `viewBox` only. An SVG with no intrinsic size is
laid out at about 300x150 px wherever it sits in an `<img>` -- GitHub's file
view, the page a README click opens, rendered every capture as a thumbnail.
`scripts/screenshots.py::sized_svg` adds `width`/`height` (the viewBox's own
numbers) to every export, the animation assembler writes them on its root,
and `tests/test_front_page_media.py` fails on any committed SVG without them.
A hand-drawn SVG (the hero, the diagrams) must carry them too.

## What is deterministic and what is not

- **Deterministic:** every SVG, including the animations. A rerun produces
  byte-identical files, and `tests/test_front_page_media.py` re-renders them
  (`--check`) and fails if a committed file differs. A fixture change that
  alters a scene fails there until the output is regenerated and committed.
- **Not deterministic:** the PNGs. They depend on the Chrome build and on the
  fonts it finds (the export names Fira Code and falls back to a system
  monospace), so they are never compared byte for byte. The tests check only
  that each capture's PNG exists, is a PNG, is under 1 MB, and that every PNG
  the README shows is named in `tools/captures.json`.
- **Generated from the art:** the hero and the social preview come from
  `tools/hero_svg.py` (deterministic; the art rows sit in each file's `<desc>`).
- **Not generated:** the five diagrams are hand-drawn SVGs. The tests check
  that they and the hero exist, stay under 60 KB, and that the hero carries the
  launch banner's rows.

## Adding a capture

1. Write a scene in `scripts/capture_scenes.py` or `scripts/capture_dialogs.py`
   (an `async def scene(size, theme) -> list[str]` returning one SVG per frame)
   and add it to `SCENES` at the bottom of `capture_dialogs.py`.
2. Add a line to `tools/captures.json`.
3. Run `python tools/capture_screens.py`, look at the PNG, commit `docs/media`.
