# The front-page media

Read this when you regenerate the front-page pictures and animations.

(Generated media -- images and video from local diffusion models through
ComfyUI -- is a different thing: see [COMFYUI.md](COMFYUI.md).)

The README's pictures are generated, not hand-captured from a live session:
the Studio ones by headless Chrome over fixture data, the TUI ones from the
real TUI over mock data. Nothing in them is a real key, path,
hostname, username or phone number: the scenes run on a scripted
`FakeController`, fixture rows, fixture contacts (reserved 555 numbers) and
the literal cwd `~/project`, with a frozen clock, seeded tips and a scratch
`BRIDGE_TEST_HOME`. The privacy scan runs over the SVGs like any other text;
the Studio pictures keep the two rules under
[No real name, no real path](#no-real-name-no-real-path-in-a-studio-picture).

## What is where

| Path | What it is | How it is made |
|---|---|---|
| `docs/media/<name>.svg` | The Textual export of one capture | `tools/capture_screens.py` |
| `docs/media/<name>.png` | The same SVG rendered at 2x by headless Chrome | `tools/capture_screens.py`, when Chrome is found |
| `docs/media/<name>.anim.svg` | Animated captures only (`turn-phase-line`, `steer-mid-turn`): the frames assembled into one looping SMIL SVG, each under 1 MB | `tools/capture_screens.py` |
| `docs/media/hero.png` | The README's first image: the wordmark over Studio's Session dashboard (a crop of `studio-session.png` across its whole width, the Map on the left and the Live column on the right, darkened at the top edge and behind the wordmark), the block art drawn as cells, never text, and one line under it, "The Claude Code-compatible harness for any model, with Studio: every agent, live."; 2560x720, rounded corners, the holo palette | `tools/hero_png.py` (`--check` says when it is stale) |
| `docs/media/social-preview.png` | The same picture at 1280x640, the wordmark centred, the line under it: the image for GitHub's Social preview (a hand upload, see below) | `tools/hero_png.py --social` |
| `docs/media/hero.svg` | The vector wordmark: the block-art wordmark from `halo_harness/banner.py` drawn as vector cells, three chips (Studio · every agent, live; any model; your Claude Code setup, in place), the same line; under 60 KB, so it carries no screenshot | `tools/hero_svg.py` |
| `docs/media/social-preview.svg` | The vector wordmark at 1280x640 with the same line, kept in step with `hero.svg` (the upload is the PNG) | `tools/hero_svg.py --social` |
| `docs/media/studio-session.gif` | The README's first picture after the hero: the Session dashboard working, the agent tree and the cost on the left, every agent's text, tool rows, hand-backs and an ask card scrolling in the Live column; 1500x900, 28 frames at 250 ms (7 s), looping, one shared palette that keeps the state colours | `tools/capture_session_anim.py` |
| `docs/media/studio-session.png`, `studio-session-live.png` | The stills beside it: the whole dashboard, and the Live column up close (scale 2) | `tools/capture_session_anim.py` |
| `docs/media/studio-roles-live.gif`, `studio-roles-live.png` | The Roles canvas while a session runs: cards lighting cyan, one waiting amber, one fading green, one failed red, the glow legend opening at the end; the still has the implementer's Live tab open | `tools/capture_session_anim.py --mode roles` |
| `docs/media/studio-<section>*.png` | Halo Studio in the browser: the Team, Roles, Fleet, Design and Orchestra captures through the shell, headless Chrome over fixture data | `tools/capture_studio.py --mode orchestra\|roles\|design\|fleet\|team` |
| `docs/media/studio-modes.png` | The eight Studio captures (Session, Team, Roles, Fleet, Design, Orchestra, Packs, Setup, the tab order) side by side with a section label and its `Alt+1`..`Alt+8` key each, the README's banner of the sections (3.3.0.0 R4: each tile 560 px wide, under 1 MB) | `tools/studio_modes_banner.py` (`--check` says when it is stale) |
| `docs/media/studio-setup.png` | The Setup section (3.3.0.0 R4; 3.3.1.0 R1 the pages) as `halo init` opens it (`?mode=setup&first=1`): the step rail over the first page, Providers, its line leading with "set up this box", OpenRouter set from a placeholder env file, a two-model fixture catalog, the halo-dev-cycle lineup, a passed last check; the banner's eighth tile and the README's first screenshot after install | `python tools/capture_studio.py --mode setup` (tools/capture_setup.py) |
| `docs/media/studio-packs.png` | The Packs section (3.2.0.0 R7): the Pack Manager with the shipped Documentation Review pack installed and enabled with bash, its Details, Sources, Settings and Templates | `python tools/capture_studio.py --mode packs` (tools/capture_packs.py) |
| `docs/media/diagrams/*.svg` | The explanatory diagrams, each under 60 KB, on their own dark card so they read on a light or a dark page: session flow, routes and the connectors bridge on the README, remote control and the agents model in the docs | drawn by hand |
| `docs/screenshots/*.svg` | The older TUI gallery (not on the README) | `scripts/screenshots.py` |
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

The Studio pictures:

```sh
python tools/capture_session_anim.py              # studio-session.gif, studio-session.png, studio-session-live.png
python tools/capture_session_anim.py --mode roles # studio-roles-live.gif, studio-roles-live.png
python tools/capture_studio.py --mode fleet       # one section's stills (orchestra, roles, design, fleet, team, packs, setup)
python tools/studio_modes_banner.py               # the eight-section banner, after any of the eight stills changed
python tools/hero_png.py                          # hero.png, after studio-session.png, the banner or the line changed
python tools/hero_png.py --social                 # social-preview.png, the same picture at GitHub's size
python tools/hero_png.py --check                  # both against a fresh render (exit 1 when stale)
python tools/hero_svg.py; python tools/hero_svg.py --social   # the two vector wordmarks
```

`tools/hero_png.py` takes its line from `tools/hero_svg.py`'s `TAGLINE` and
its cell shapes from `hero_svg.cell_rects`, so the PNGs and the SVGs say the
same thing and draw the same art; change the line there and rerun all four.

### No real name, no real path in a Studio picture

The Studio pictures are made on a real machine, so every Studio capture tool
goes through `tools/capture_identity.py` and keeps two rules:

1. **One placeholder identity.** Before a tool serves Studio, or enters a
   rig, it writes `fleet.name: you@studio` into the scratch home's config
   (and the rig's), and the harness's user and host read `you` and
   `studio`. The rail's Fleet tree, the status bar, the Fleet and Session
   maps, People and Health all draw `you@studio`; the fleet scene's member
   keeps its own made-up name, `kali@lab`. When a name Studio would draw is
   still this machine's `user@host`, or carries its user or host name, the
   tool stops with one line and exit code 2:

   ```
   capture stopped: Studio would draw this machine's own user or host name; every capture draws you@studio (tools/capture_identity.py)
   ```

2. **No absolute path.** The seeded Orchestra runs use a repo-relative test
   command (`python -m unittest -q test_basket`), the fleet scene's edits are
   repo-relative (`Edit: basket.py`), and when the system temp folder sits in
   a user profile (on Windows, the profile's `AppData\Local\Temp`) the tool moves
   its temp root to `%ProgramData%\halo-capture` (`HALO_CAPTURE_TMP` names
   another), so the scratch repos, homes and sessions Studio shows carry no
   profile path. Every page a tool counts (`--dom`) or shoots is read first:
   a home path (`Users\`, `Users/`, `home/`), `AppData`, or this machine's
   user or host name in its DOM stops the tool with one line and exit code 1,
   `capture stopped: the <page> page carries <what>: <the text near it, the
   names masked> (tools/capture_identity.py)`. The DOM is read, never the
   pixels.

`tests/test_capture_identity.py` parses the tools' source: each one calls the
helper before it serves and guards every page before it counts or shoots it.

Run both from a checkout with the repo on `PYTHONPATH`; no real `~/.halo` is
touched (the scenes scope `BRIDGE_TEST_HOME` to a scratch directory before any
import) and nothing is fetched except what Chrome itself loads for the SVG's
font.

### Uploading the social preview

GitHub has no API for the social preview: the owner uploads it once, by hand,
after `social-preview.png` changes. On github.com open the repository, then
**Settings -> General**, scroll to **Social preview**, choose **Edit -> Upload
an image...** and pick `docs/media/social-preview.png` (1280x640, under 1 MB).

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
  the README shows is named in `tools/captures.json` (the Studio stills are on
  that test's own list instead). The two Studio GIFs are Chrome renders too:
  `tests/test_studio_session_live.py` checks that they loop at 1500x900 under
  3 MB, and the README check keeps every image it shows under 1 MB.
- **Generated from the art:** the vector hero and social preview come from
  `tools/hero_svg.py` (deterministic; the art rows sit in each file's `<desc>`).
  `hero.png` and `social-preview.png` come from `tools/hero_png.py` (Pillow
  only, no fonts fetched: the line is Pillow's own default face): a rerun on one
  Pillow build is byte-identical. `tests/test_front_page_media.py` checks that
  both exist, are PNGs of their size and under 1 MB, and, where Pillow is
  installed, runs `--check`; pixel identity is pinned on Windows, where the
  committed pair is rendered (another FreeType build anti-aliases the line
  differently, so elsewhere a stale line is informational).
- **Not generated:** the five diagrams are hand-drawn SVGs. The tests check
  that they and the hero exist, stay under 60 KB, and that the hero carries the
  launch banner's rows.

## Adding a capture

1. Write a scene in `scripts/capture_scenes.py` or `scripts/capture_dialogs.py`
   (an `async def scene(size, theme) -> list[str]` returning one SVG per frame)
   and add it to `SCENES` at the bottom of `capture_dialogs.py`.
2. Add a line to `tools/captures.json`.
3. Run `python tools/capture_screens.py`, look at the PNG, commit `docs/media`.
