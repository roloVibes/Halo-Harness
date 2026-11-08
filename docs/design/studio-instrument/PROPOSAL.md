# Halo Studio: the "Instrument" look

A look proposal in the shape `docs/STUDIO-redesign-brief.md` asks for: one palette in the seventeen tokens, the derived variables, component specs, section mock-ups, motion, and the why. Mock-ups are in `mockups/html` (self-contained, open in any browser) and `mockups/png` (1440×900, 1280×800 for the four core screens, 390 wide for Session on a phone).

Nothing in this proposal renames a section or panel, changes a shortcut, or touches a `data-testid`. It restyles. Two shell changes are flagged as separate notes at the end (rail order, rail collapse).

## 1. Palette: `instrument` (dark posture)

Add as one more entry in `halo_harness/themes/palettes.py`. If it becomes the brand look, replace `holo`'s values.

| token | hex | on `surface` | notes |
|---|---|---|---|
| bg | `#07090C` | | page ground, near black |
| bg2 | `#0B0E12` | | rail, header, status bar |
| surface | `#0F1318` | | panel |
| surface2 | `#151A21` | | nodes, chips, inputs inside a panel |
| border | `#232A33` | | 1 px hairlines, panel edge |
| line | `#1A2028` | | row separators, HUD cell dividers |
| text | `#E6EDF3` | 15.8 | |
| muted | `#9AA6B2` | 7.5 | secondary text, glance lines |
| faint | `#7D8995` | 5.2 | captions, timestamps, tier labels |
| accent | `#22D3EE` | 10.3 | cyan: working, selection, focus ring |
| accent2 | `#F5A524` | 9.1 | amber: waiting, asks, attention badge |
| accent_ink | `#031317` | 10.5 on accent | text on an accent fill |
| ok | `#3DD68C` | 9.9 | done |
| warn | `#F5A524` | 9.1 | same as accent2 on purpose |
| bad | `#FF5C6A` | 6.2 | failed, stop |
| user | `#A78BFA` | 6.8 | your own steers, steward events |
| tool | `#67E8F9` | 12.9 | TOOL rows, running timers |

Every text token clears 4.5:1 on `bg`, `surface` and `surface2` (lowest pair: `faint` on `surface2`, 4.9). `accent_ink` on `accent` is 10.5. Ratios computed with the WCAG 2.x formula; the per-palette contrast test should pass without exceptions.

A light twin is not proposed. The owner rejected a light posture during review; `paper` stays the light default.

## 2. Derived variables (`tokens.css`)

```css
/* glass: none in this look. Surfaces are solid. */
--glass: var(--surface);
--glass-border: var(--border);

/* glow: a 1px ring, never a blur */
--glow-accent: 0 0 0 1px color-mix(in srgb, var(--accent) 55%, transparent);
--glow-warn:   0 0 0 1px color-mix(in srgb, var(--warn) 60%, transparent);
--glow-ok:     0 0 0 1px color-mix(in srgb, var(--ok) 50%, transparent);
--glow-bad:    0 0 0 1px color-mix(in srgb, var(--bad) 60%, transparent);

/* grid: dot grid on map canvases only (Session Map, Roles Live). Static. */
--grid-dot: #1F2630;          /* derive: mix(border 70%, bg) */
--grid-size: 16px;
--grid: radial-gradient(var(--grid-dot) 1px, transparent 1px) 0 0 / var(--grid-size) var(--grid-size);

/* soft tints: state fills behind text, 6-8% */
--soft-accent: color-mix(in srgb, var(--accent) 8%, transparent);
--soft-warn:   color-mix(in srgb, var(--warn) 6%, transparent);
--soft-ok:     color-mix(in srgb, var(--ok) 8%, transparent);
--soft-bad:    color-mix(in srgb, var(--bad) 8%, transparent);
--soft-user:   color-mix(in srgb, var(--user) 8%, transparent);

/* radii */
--r-panel: 6px; --r-card: 4px; --r-control: 4px; --r-chip: 3px; --r-badge: 2px;

/* shadow scale: one level, menus and floating cards only */
--shadow-0: none;
--shadow-1: 0 16px 40px rgba(0,0,0,.7);

/* spacing */
--s-1: 4px; --s-2: 8px; --s-3: 12px; --s-4: 16px; --s-5: 20px; --s-6: 28px;

/* type */
--font-data: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace;
--font-prose: Inter, -apple-system, "Segoe UI", system-ui, sans-serif;
--t-title: 600 12px/1 var(--font-data);   letter-spacing: .12em; text-transform: uppercase;
--t-body:  400 13px/20px var(--font-prose);
--t-data:  400 12px/18px var(--font-data);
--t-caption: 500 10.5px/16px var(--font-data); letter-spacing: .1em; uppercase for labels
--t-node-name: 600 13px/18px var(--font-prose);

/* motion */
--dur-fast: 160ms; --dur-base: 240ms; --dur-slow: 600ms;
--ease-out: cubic-bezier(.2,.8,.2,1);
--ease-linear: linear;
```

Chrome sizes: rail 52 px (expanded 176 px), header 48 px, HUD strip 40 px, panel title row 40 px, status bar 26 px.

## 3. Component specs

States are rest / hover / focus / active / disabled / selected / busy. Where a state is not listed it is the rest state.

**Button** (`lib/ui/Button`). 30 px tall, `--r-control`, `surface` fill, `border` hairline, `--t-data` mono. Hover: fill `surface2`, border lifts to `#36404C` (mix border 70%, text). Focus: 1 px `accent` outline at 2 px offset, no ring blur. Active/on: border and text `accent`, fill `--soft-accent`. Primary (one per screen at most): fill `accent`, text `accent_ink`. Danger text: `bad` on a normal button. Disabled: 40% opacity, no hover. Busy: label swaps to a mono timer, e.g. `running 12 s`.

**Kbd**. 16 px tall, 10.5 px mono, 1 px `border`, `--r-chip`, text `muted`. Inside a primary button: border and text take `accent_ink` at 30% / 100%.

**Field**. 30 px (36 px for Steer and Prompt), `bg` fill, `border` hairline, mono 12 px, a leading `>` or `›` glyph in `faint` (accent when focused). Focus: border `accent`. Invalid: border `bad`, one line under it in `bad`.

**Surface / panel frame**. `surface` fill, `border` hairline, `--r-panel`, no shadow. Four corner ticks, 10 × 1 px in `accent`, drawn with background-image (see mock-up CSS). Title row 40 px: state square, title in `--t-title`, glance line in `--t-data` `muted`, then `?` and `⋯` ghost buttons. Three faces: **glance** = title row only, 40 px; **detail** = title row + body; **strip** = 44 px, title + glance line, one click opens detail. Collapsed = glance face with the body height animated to 0 over `--dur-base`. Selected panel (keyboard focus inside it): corner ticks go from `accent` to `text`.

**HudStrip / HudCell**. 40 px strip under the header, `bg` fill, cells separated by `line`. Cell: 10.5 px caps label in `faint`, value in 12 px mono `text`. A bar inside a cell is 6 × 80 px, `surface2` track, `accent` fill; amber past 80%, red past 95%. Values change in place, no animation.

**Rail** (`shell/Rail`). 52 px, `bg2`, `border` on the right. Items 40 × 40, icon 19 px stroke 1.5, `faint`; hover `text` on `surface`; selected `accent` on `surface` with a 2 px `accent` bar on the left edge. Attention badge: 15 px amber square, `--r-badge`, count in `accent_ink`-dark (`#1A1203`). Groups separated by a 22 px hairline. Bottom: connection square, then a chevron that expands the rail to 176 px with labels and shortcuts; the choice persists per browser. Tooltip on hover: name and `⌥n`.

**Header**. 48 px, `bg2`, section name in `--t-title`, a `/` separator in `border`, the session or page picker as a button, then the figures in `muted` mono; right side holds the command palette field (300 px), `+ panel`, `focus ⇧F`, `?`.

**StatusBar**. 26 px, `bg2`, 11 px mono: connection square + CONNECTED, version, harness, then counts coloured by state, right side host figures and `⌘K`.

**Inspector**. Fixed 344 px column, `surface`, `border` on the left. Head: agent name 16 px prose, state in caps `accent`/`warn`/`ok`/`bad`, close `✕`. Mono key/value grid (64 px keys in `faint`). Actions row: pause, stop (text `bad`), follow, pin. Tabs: 36 px, mono caps, selected `accent` with a 1 px `accent` underline and `bg` fill. Live tab body is a terminal-style stream in `bg` with the caret blinking at 1 Hz (the only idle animation, and only while the agent is working). Steer field pinned at the foot. Opens on selection, closes on `Esc` or `✕`, never on section load.

**Map node** (Session Map, Roles Live, Fleet Tree). 184 × 84 (Session) or 192 × 112 (Roles Live), `surface2` fill, `border` hairline, `--r-card`. Row 1: state square + name (`--t-node-name`) + role in 10.5 px caps `faint` (Roles Live only) + `⋯`. Row 2: current activity, mono 11 px, in the state colour. Row 3: model name only (no provider prefix) and cost, mono 11 px `muted`; Roles Live adds the elapsed time. State: an inset 2 px rule across the top in the state colour, border at 55% of that colour. Working: the rule is cyan, and only the activity text changes while it runs. Waiting: amber, three pulses then steady. Done: green, border and rule fade to `border` over 10 s. Failed: red, stays until clicked. Selected: 1 px `text` outline at 3 px offset. Linked highlight: hovering the agent anywhere else on the page applies the same outline. Model names are the resolved model only; host and provider live in the inspector.

**Edges**. 1.5 px, `#2A323D` at rest (mix border 60%, surface2). Working: `accent` at 25% as the base plus a 4/8 dash in `accent` moving toward the child at 12 px per 0.8 s. Waiting: solid amber. Done: solid green, fades with the node. Failed: 2/4 dotted red. One edge per parent → child, orthogonal segments, no curves.

**Tier bands** (Roles Live). Full-width translucent `surface` at 60% with `line` top and bottom, label in 10.5 px caps `faint` at the left: `T0 · MAIN`, `T1 · SPAWNED BY MAIN`. An Auto-spawned agent that matches no card gets an `auto` chip in `accent`/`accent_ink` and a dashed `accent` note card under it saying why it was picked.

**Live rows**. Grid: time (62 px mono `faint`), kind (50 px, 10.5 px bold caps in the kind colour: TOOL `tool`, TEXT `muted`, THINK `faint`, OUT/STATE `ok`, ASK `warn`, SPAWN `accent`, ERR `bad`, YOU `user`), agent tag (96 px: state square + name mono), then the line, which wraps with `overflow-wrap: anywhere`. Inline code in `surface2` chips. The row of the agent under the pointer takes `--soft-accent`. Below 720 px wide the time, kind and tag share one row and the line runs under them.

**Ask card**. Inside the row, `--soft-warn` fill, 1 px amber border, `--r-control`; four buttons with their Kbd: A allow · R deny · S stop · O open. On a phone the four buttons go to a 2 × 2 grid.

**Steer box**. Foot of Live and of the inspector. Header line in mono: `STEER main` in `accent` bold caps, the target's current activity in `muted`, `tab: change target` on the right. 36 px field with a `›` prompt glyph, pause and stop beside it. Finished agent: the field is replaced by one line, `tester finished · 1m02s`, no input.

**Toast** (`lib/ui/Toasts`). Bottom right, 300 px, `surface2`, `border`, `--shadow-1`, one line and a path in mono. Arrives: 16 px rise + fade over 220 ms. Holds 4 s. Leaves: fade 180 ms. Errors stay until dismissed and show `bad` on the state square.

**Dialog**. Centered, 480 px, `surface`, `border`, `--shadow-1`, corner ticks. Title in `--t-title`. The confirmation body always has three mono lines before the buttons: `DOES`, `COSTS`, `WRITES` (see the Packs detail panel for the pattern). Primary on the right.

**Palette** (command palette). 560 px, 60 px from the top, `surface`, `border`, `--shadow-1`. Field with a `>` glyph. Results: 36 px rows, section name in `faint` caps on the left, command text, shortcut Kbd on the right. Selected row: `surface2` and a 2 px `accent` bar on the left, same as the rail.

**Menu** (the `+` panel menu). 300 px, anchored under its button, `surface`, `#36404C` border, `--shadow-1`. Header line in caps `faint`. Rows: state square, panel name, a muted hint (`· open`, `· 1 waits on you`), key on the right. Open panels are `muted`; the keyboard row is `surface2` with `↵ add` in `accent`. Footer: `reset layout`.

**Tabs**. 36 px, mono caps, `faint`; selected `accent` with a 1 px underline, panel-coloured fill. Never more than five.

**Empty / ErrorState**. Empty: one line in `muted` plus one button. Error: one line in `bad` and a path in mono; no stack traces in the panel, `open` takes you to the log.

**Skeleton**. `surface2` blocks, no shimmer. Appear only after 300 ms of waiting.

**FitMeter** (Local). 8 px track in `surface2`, fill in `ok` under 80%, `warn` 80–95%, `bad` past 95%. Fills once from 0 to its value over `--dur-slow` with `--ease-out` when the row first appears, then moves in place. Caption under it in mono 11 px: `9.1 of 24 GB · fits with room`.

**WindowedRows**. Row height 36 px (Local traffic, Packs list), 44 px (agents). Header row in 10.5 px caps `faint`. Hover `surface2`. Selected: `surface2` plus the 2 px `accent` bar.

**Swatch / ThemeMenu**. Unchanged mechanics; swatches use `--r-chip` and a 1 px `border`.

## 4. Sections

The mock-ups show the one-thing-per-section defaults.

- **Session** (`01-session`). Map on the left (712 px), Live on the right, Activity as a 132 px strip under both. HUD strip carries spend, turns, context, elapsed, model and the live counts. Cost, Agent, Attention and Prompt wait in the `+` menu (`05-session-plus-menu`). Focus (`06-session-focus`) drops rail, header, HUD and status bar and leaves a 24 px chip at the top with the session, spend, counts and `⇧F back`. Phone (`07-session-phone`): header, session picker strip, Map (scrolls sideways), Live full width, Steer pinned, five-tab bar (live · map · cost · attention · prompt).
- **Roles Live** (`02-roles-live`). Plan | Live switch first in the header, then the session picker, spread | compact, zoom, fit, focus. Whole page is the tree with tier bands; inspector at the right opens on selection. At 1280 the tree is 920 px wide and scrolls inside the panel; `fit` scales it to the panel.
- **Local** (`03-local`). Page rail at the left (188 px, counts on the right of each page), Resources: host panels with a VRAM bar that names what holds it, then the figure cells (GPU, RAM, CPU, temp, power) with 10-step tick bars, each titled with its source, then Traffic.
- **Packs** (`04-packs`). List with version, what the pack adds (chips), size, state; detail panel at the right with the `DOES / COSTS / WRITES / TOUCHES` block above the contents and the changelog, actions at the foot.

## 5. Motion

Four animations carry meaning. Everything else is still.

1. **An agent starts and ends.** New node: edge draws from the parent over 240 ms, node fades in over 240 ms `--ease-out`. While working: the 4/8 dash on its edge moves toward it; the top rule is solid. On finish: node and edge go `ok`, then fade to rest over 10 s linear.
2. **A receipt ladder climbs** (inspector Receipts tab, Orchestra). Each rung fills `ok` 160 ms after the previous, bottom up, once.
3. **The fit meter fills** once to its value over 600 ms `--ease-out`.
4. **A toast arrives**: 16 px rise and fade over 220 ms; leaves with a 180 ms fade.

Also allowed: the working-state square blinks at 1.4 s (50% opacity at the midpoint) and the inspector caret at 1 Hz, both only while that agent is working. Waiting pulses three times then holds. `prefers-reduced-motion: reduce` turns all of it into instant state swaps; the dash stops and the edge shows solid `accent` instead.

Nothing moves on section load. The dot grid is static. There are no glows, blurs or gradient washes.

## 6. Why

The current look says "demo": glow, blur, bracketed HUD corners on everything, cyan on cyan. It reads as a mood before it reads as a console. Instrument keeps the Minority Report lineage where it carries information (corner ticks mark a panel; cyan means work is happening; amber means you are needed) and removes it where it does not (no glow, one shadow level, hairlines instead of bands). Mono for data and sans for names keeps the density readable at 1280 and on a phone. State is told four ways at once (square glyph, colour, rule, text) so colour alone never carries meaning. The result says: this is the instrument panel for a machine you own, and every pixel of chrome is here because it tells you something.

## Separate notes (not part of the look)

- **Rail order.** Session · Team · Roles · Fleet · Local, divider, Orchestra · Packs · Design, divider, Setup · Settings. Local moves up because it is checked as often as Fleet. Shortcuts stay as they are today (`Alt+1..0`); only the visual order changes. If the maintainer prefers shortcuts to follow the order, that is a second change with its own tests.
- **Rail collapse.** The rail defaults to icons; a chevron (and `⌥[`) expands it to 176 px with labels. Persist per browser like layouts.
- **Linked highlight** across Live rows, Map nodes and Roles Live nodes already exists for Live→Map (the brief says hover a line lights the node). The spec extends it to the inspector and the Attention queue; it is a small change in the Fleet stores' hover scope.
- **Model names.** Show the resolved model id without the provider prefix on nodes, tags and the HUD; keep the prefix in the inspector's `model` line and in tooltips.
