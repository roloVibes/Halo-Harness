// "How this works" for each section: what it is, five to eight numbered
// steps, the keys and (3.1.1.0 R1) the glossary words it uses, each a link
// into the Glossary (docs/GLOSSARY.md; tests/test_glossary.py checks every
// word here has a paragraph). The overlay (shell/SectionHelp.tsx) adds the
// section's panels with their `about` lines; the first-visit welcome shows
// the same. docs/STUDIO.md "How each section works" mirrors this copy.
// 3.1.6.0 R6: a section's own Alt+N line is not here: the overlay puts the
// registry's key (routes/index.tsx SECTIONS) first, so a reorder moves it.
import type { SectionId } from "../lib/store";
import { WORDS } from "./crew/map/truthWords";

export type SectionHelpCopy = { what: string; steps: [string, string][]; keys: [string, string][]; terms: string[] };

const PANEL_KEYS: [string, string][] = [
  ["?", "help for the focused panel; press it again (or away from a panel) for this page"],
  ["Alt+Left / Alt+Right", "the focused drawer wider or narrower"],
  ["Mod+K", "every command, with its key"],
  ["Esc", "close the palette, a menu, the help or the Inspector"],
];

const HOP_KEYS: [string, string][] = [
  ["J / K", "hop to the next / previous live agent"],
  ["F", "follow it: its stream scrolls with it"],
  ["Space", "pin its stream: a mini stream stays on screen in every section"],
  ["Esc", "unpin the mini stream"],
];

export const SECTION_HELP: Record<SectionId, SectionHelpCopy> = {
  agents: { // 3.6.0.0 R5, 3.6.0.2 R52: four tabs -- make an agent, make a workflow, connect them on the map, watch a session run
    terms: ["step", "hand-off", "when", "live map", "replay", "report card", "waiting path", "orchestra run", "gate"],
    what: "Your agents in four tabs: 1 · Agents makes an agent (its name, what it does, its model, what it may use, how careful; Try it, Save), 2 · Workflows puts your agents in steps, in order, and 3 · Map connects them -- who main hands work to, and when; 4 · Live shows what a session is doing now, drawn on the map it really follows. Every session runs on a map (the starter map until you pick one); History under the map replays what ran. The files live in ~/.halo/crew/.",
    steps: [
      ["Pick the tab", "1 · Agents, 2 · Workflows, 3 · Map or 4 · Live, first on each tab's bar (keys 1, 2, 3, 4; for this release C lands on the Map, L on Live, W on Workflows). Agents opens on Live while a session is open, else on the tab used last. Nothing else opens on its own."],
      ["1 · Agents", "Your agents on the left (tagged new or not used yet), then the starters to copy; the form on the right. Write it for me fills the builder box below; Try it runs the agent on a throwaway copy of the repo and says what it used and cost."],
      ["2 · Workflows", "A workflow is your agents in steps: each step's agents (side by side ones work at the same time), what it gets, what it hands on, when it runs, and Repeat until. The drawing beside the form follows the list. Try it runs it on a throwaway copy."],
      ["3 · Map", "main is always at the left. Drag an agent or a workflow from Agents and workflows onto a box: that box hands work to it, and the When card opens at the line. Drag a box's dot to another box for a chain. New sessions run on this makes it the map new sessions run on."],
      ["4 · Live", `The session you pick, drawn on the map it really follows: each box with its agents and their state, a workflow as its steps, every hand-off lighting its line and leaving a trace, work outside the lines dashed. Click a box: Pause, Stop or steer it there. The ${WORDS.feed} (its button on the bar) shows what the agents say and do, line by line.`],
      ["History and goal runs", "Under the map, History lists finished runs, newest first; Replay it on the map plays one back with the scrubber, Report card says it in ten lines. Run a goal on the Map's bar opens the goal form in the drawer; a running goal's pages open there too."],
      ["Hover, then click", "Rest the pointer on a box or Tab to it: a card says what it is after a moment. A click opens everything in the drawer. Settings -> Studio turns the cards off."],
      ["Attention", "The chip at the right of each tab's bar counts every decision that waits on you, amber while any does; it (or A) opens the queue: A accepts, R denies or redoes with your text, S stops, O opens where it belongs."],
    ],
    keys: [["1 / 2 / 3 / 4", `Agents, Workflows, ${WORDS.map}, ${WORDS.live} (outside a text field)`], ["A", "the Attention queue"], ...PANEL_KEYS],
  },
  session: {
    terms: ["harness", "hand-off", "gate", "glance"], // 3.4.1.0 R4: the glance
    what: "Your own session, live: one live column of every agent at work, as it happens, is the main thing; the map of this harness's agents, what the chosen session costs and the rest are buttons in the bar above it. Other machines' sessions are listed on Agents -> Live.",
    steps: [
      ["Open it", "/studio in a terminal session opens Studio here on that session (halo studio --session from a shell); Alt+1, the palette, Watch in Session on Agents' Live tab or a live run in Agents: Runs, and Open in Session on a node's menu on Agents -> Live land here too."],
      ["Watch everything at once", `${WORDS.feed}, the whole stage: every agent's text, tool calls with their times and results, hand-backs and asks, in the order they happen, each line tagged with its agent and its state. Scroll up (or type a steer) to hold the view, N new rows · follow to come back; click a tag to follow one agent; the Steer box is always at the foot and names its target, the outlined row (click a row or press Tab to change it); Export saves the trace.`],
      ["Read the map", "Each agent sits under the one that spawned it, its children fanned out, with its model, its cost and the tool it runs now (Bash 12s). Cyan works, amber waits on you, green just finished and fades, red failed and stays. Click an agent: its session becomes the chosen one."],
      ["Read the cost", "The spend ticks up beside its sparkline the moment the terminal's does; the context bar turns amber past 80 % and red past 95 %; the tokens, your turns and the cost per turn, and each agent's own share in one stacked bar (a finished sub-agent counts once)."],
      ["Open what you need", `${WORDS.live}, Cost, Agent (its streams, Steer, Pause, Stop, Follow, Pin), Activity (the lanes and the full log) and Attention (one key each) are buttons in the bar above the ${WORDS.feed}; a click opens one as a drawer beside it (Activity takes the ${WORDS.feed}'s place as its tab), Reset layout closes them all.`],
      ["Glance from a phone", "The \"...\" menu's Open the glance (or the palette, or halo studio --mode glance): one phone-width page -- what runs, what waits on you as big buttons, the spend against its cap -- here, or on a phone through an SSH forward of Studio's port. Settings -> Studio -> Alerts can add one browser notification when something starts waiting on you."],
    ],
    keys: [...HOP_KEYS, ["P", "pause or resume the agent"], ["K", "in the Agent panel: stop it (asks first)"],
      ["Esc", `in the ${WORDS.feed}: show every agent again after a tag click`], ["A / R / S / O", `in Attention, or on the newest ask card in the ${WORDS.feed}: accept, deny or redo (with a text), stop, open`], ...PANEL_KEYS],
  },
  packs: {
    terms: ["pack", "lineup", "bio", "capability", "orchestra run"], // 3.2.1.0 R1: "pack" is in the glossary
    what: "The Pack Manager: find a pack in the places you trust (the folders and git urls of packs.sources, and the packs Halo ships), read what it brings and what it asks for, then install, grant, enable, set up, update or remove it. Every button runs the same code as halo pack, and every line it answers is the one the terminal prints.",
    steps: [
      ["Find a pack", "Sources lists each place a bare id is looked for, in order, with the packs it holds; Add source puts a folder or a git url in packs.sources. Click a name to read the pack before you install it."],
      ["Install it", "Install copies it into ~/.halo/packs/<id>/ (or this repo's .halo/packs/), disabled: nothing of it runs yet. It shows in Installed."],
      ["Read what it brings", "Details: its extension API and Halo ranges beside this Halo's, the packs it requires, what keeps it from running here (in the doctor's words), each permission it requests and what needs it, and everything it contributes."],
      ["Grant and enable", "Pick the permissions to grant with their toggles, then Enable: its agents, maps, Studio section, capabilities and workflows run from now on; a contribution whose permission you did not grant stays off."],
      ["Set it up", "Settings is the pack's own form (its config.schema): Save checks the values, then writes packs.settings.<id>."],
      ["Use its templates", "Templates: Run a pack's workflow: the Map's Run a goal form, filled in (its 1.x bios and lineups are read as agents and maps)."],
      ["Keep it healthy", "Each row counts the doctor's lines; Update shows its migration notes and what changes before anything is replaced (your changed files stay) and keeps the old version: Roll back brings it back; Remove asks first, then deletes only the pack's own files and lists what of yours stays."],
    ],
    keys: PANEL_KEYS,
  },
  setup: {
    terms: ["setup", "provider", "env file", "lineup"], // 3.3.0.0 R1: "setup", "provider" and "env file" are in the glossary
    what: "This box's setup one page at a time, the page halo init opens: the steps in order, one block per page with its own Save, then a Summary. Every block writes its key in ~/.halo/config.json, the same as halo config set; keys go to the env file and are never shown back. Nothing opens on its own here. halo init --terminal is the terminal wizard.",
    steps: [
      ["Follow the rail", "The rail on top lists the steps in the wizard's order: the current one lit, a done one ticked. Click any step to open its page; the line under it says what is set now."],
      ["Set a provider up", "Providers: one card per provider. Paste a key (or a host), Save & test writes it to the env file, turns the provider on and reads its model list. Ollama's finders (Find, Scan, Add, Measure) open under its card."],
      ["Point at your local models", "Local models: the folders your model files are in and the runtime that serves them (llama-server or mlx_lm). Nothing here is required."],
      ["Pick the default model", "Default model lists the catalog of the providers set up here, grouped by provider, with what each model is best at; search, pick one, Save (Enter saves too)."],
      ["Pick the permission mode", "Permissions: auto, acceptEdits, default or plan, each with what it allows; Save writes the mode every new session starts in."],
      ["Pick the theme", "Theme: one of ten palettes for halo in your terminal and for Studio, each swatch drawn in its own colours; Settings -> Themes has the modifiers and a preview."],
      ["Pick the map", "Team: One model for everything, starter (the default) or a map, with its preview; Apply writes what the wizard's Map step writes."],
      ["Run the check", "Check: doctor, the model catalog and one hello call are ticked; the quick gym and the guided first run say what they cost first. Linux fixes is a step only when this box needs them."],
      ["Read the Summary", "One row per step with what it holds and a Change jump, the last check with Run the ticked checks, and the guided first run's card."],
    ],
    keys: [
      ["Ctrl+Left / Ctrl+Right", "Back / Next (outside a text field)"],
      ["Enter", "in a block's field: that block's Save"],
      ["?", "this help"],
      ["Mod+K", "every command, with its key"],
    ],
  },
  settings: {
    terms: ["config key", "setup", "provider"], // 3.3.3.0 R2: "config key" joins the glossary
    what: "Every config key of ~/.halo/config.json, the ones halo config set and a dozen features write, one page per group: each row is one key with its help line, its value against its default, Reset to default and the exact halo config set line. A change saves at once and says when it takes effect. Nothing opens on its own here; halo settings [group] opens a group's page from a terminal.",
    steps: [
      ["Pick a group", "The rail on the left lists the groups (General, Agents and roles ... Local) with how many of their keys are set; a click opens its page."],
      ["Read a row", "Title, one help line, the control, and under it the default it falls back to and when a change takes effect: now, in the next session, or on the next launch."],
      ["Change a key", "A switch or a choice saves on the click; a number or a text saves on Enter or when you leave the field; a list or JSON saves with its Save. The row says saved and when it takes effect."],
      ["Go back to the default", "A row marked default is not in config.json. Reset to default takes a key you set back out, and the marker returns."],
      ["Keys with entries", "A key with a placeholder (a connector, a provider, an Ollama host's field) is a table of the entries saved, each with its own control and Reset; Edit as JSON writes the whole section."],
      ["Search", "The box in the page head finds a row across every group by its title, key or help line; Mod+K lists every row as Settings: <title>."],
      ["The same from a terminal", "Each row's footer is the halo config set line that does the same; halo settings --terminal lists a group's keys with their values."],
    ],
    keys: [
      ["Enter", "in a number or text field: save it"],
      ["Ctrl+Enter", "in a list or JSON box: save it"],
      ["?", "this help"],
      ["Mod+K", "every command and every Settings row"],
    ],
  },
  local: {
    terms: ["host", "steward", "profile", "fit plan", "speed card", "library", "quant"], // 3.3.5.0 R1: "host", "speed card"; R2: "library", "quant"
    what: "Everything about the machines that serve your local models and the models they serve, one page at a time: Resources (the live GPU, VRAM, RAM and CPU, and every call to a local server as it happens), Hosts (every server Halo knows, with Load, Unload and Make it fit), Models (every installed model with its card, its fit meter and the intent filter), Library (what could be installed from Ollama's library and the Hugging Face Hub, each with a fit badge), then Hugging Face, Benchmarks and Steward, which the next rounds fill. Four ideas run through every page: the fit meter, why on every number, intents not model names, and make it fit. Nothing opens on its own; halo local opens it from a terminal.",
    steps: [
      ["Pick a page", "The rail on the left lists the seven pages; a click opens one, and the page last open comes back next time."],
      ["Watch the card", "Resources: one strip per host, sampled once a second while the page is open: the VRAM bar names what holds it, the GPU line is the last minute, RAM, CPU and the temperature beside them; hover a number for its source."],
      ["Watch the calls", "Under the strips the traffic view lists every call to a local server, newest at the foot, the steward's server events between them; filter by host, model, machine or kind, and Follow keeps the newest in view."],
      ["Load and unload", "Hosts: every server as a card with what is loaded and what is installed; Load warms a model at its profile's window, Unload lets it go; a host another machine serves goes through its fleet member, as its owner allows."],
      ["Make it fit", "A host whose models do not fit its card together offers the fit plan's chosen option in one click, with Undo beside it."],
      ["Find the right model", "Models: pick what you want a model for (code, chat, long documents, images, embed) and the rows rank by fit for this card; Use as default and Make it the coder lane are one click each."],
      ["Browse the library", "Library: search Ollama's library and the Hugging Face Hub; each row's fit badge follows the host and window you pick, a click shows its other tags or files, Copy takes its pull line."],
      ["What comes next", "Hugging Face, Benchmarks and Steward say what they will hold and the commands that do that work today."],
      ["Media on ComfyUI", "The palette's Media lines add Media status, Media models and Workflows: each opens as a drawer over the page's right edge until you close it."], // 3.3.13.0 R2: Design's before
    ],
    keys: [
      ["?", "this help"],
      ["Mod+K", "every command, Local: <page> among them"],
      ["Esc", "close the palette, a menu or the help"],
    ],
  },
};
