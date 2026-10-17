// "How this works" for each section: what it is, five to eight numbered
// steps and the keys. The overlay (shell/SectionHelp.tsx) adds the section's
// panels with their `about` lines; the first-visit welcome shows the same.
// docs/STUDIO.md "How each section works" mirrors this copy.
import type { SectionId } from "../lib/store";

export type SectionHelpCopy = { what: string; steps: [string, string][]; keys: [string, string][] };

const PANEL_KEYS: [string, string][] = [
  ["?", "help for the focused panel; press it again (or away from a panel) for this page"],
  ["Alt+Arrows", "move the focused panel; Alt+Shift+Arrows resizes it"],
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
  orchestra: {
    what: "Several agents write to the same files at once and nothing is lost: a lead splits your goal into lanes, one worker per lane writes its part in its own git worktree, and a gate checks the result before it lands.",
    steps: [
      ["Write the goal", "WHAT YOU WANT, how Halo knows it is done (DONE WHEN) and when to give up (STOP WHEN), plus the files the workers share and the test the gate runs."],
      ["Press Run", "Dry run asks the lead for the split only: nothing is claimed or written."],
      ["The lead splits it into lanes", "Each lane claims a part of the files; one worker per lane builds its part in its own git worktree."],
      ["The gate checks DONE WHEN", "The parts merge one at a time, your test runs, and a part that fails goes back to its worker (up to the return cap)."],
      ["Read the report", "Every check with a tick or a cross, the finished branch and its sha, the tests, the cost and the time."],
    ],
    keys: [["Alt+1", "Orchestra"], ["J / K", "focus the next / previous lane at work"], ["F", "the Log follows the newest line"], ...PANEL_KEYS],
  },
  roles: {
    what: "A lineup says which agent, on which model, plays each role in your sessions. Studio shows it as cards you can arrange and edit; the files are ~/.halo/teams/<name>.yaml and ~/.halo/agents/<name>.yaml.",
    steps: [
      ["Pick a lineup", "In the toolbar, or start from a shipped one. Each card is one assignment: an agent bio in a role, with the model that resolves for it."],
      ["Read the boxes", "Cards sit in boxes by role: Main, Workers, Reviewers, Researchers... Groups in the toolbar hides or shows them."],
      ["Move and connect", "Drop a card into another box to change its role, or onto another card to make it report there."],
      ["Add an agent", "Drag a bio from the left list onto the canvas, or straight into a box."],
      ["Edit", "Select a card: the right side has Assignment, Agent (the bio), Lineup and YAML."],
      ["Validate, Save, Apply", "Validate runs the CLI's checks, Save writes the YAML to your scope, Apply makes it the lineup new sessions use."],
      ["Watch it work", "While a session runs, the cards whose agents work glow in their band colour; click one and its Live tab shows exactly what it types, with Steer, Pause and Stop."],
    ],
    keys: [["Alt+2", "Roles"], ["A", "lay the canvas out (click the canvas first)"], ["F", "fit it to the view (with the Live tab open: follow)"], ["J / K", "the next / previous card whose agent works: its Live tab opens"], ["Mod+S", "save the lineup"], ["Del", "remove the selected card"], ...PANEL_KEYS],
  },
  org: {
    what: "Your company of agents in Paperclip: an org chart with goals, issues, heartbeats and budgets. Halo's lineups become its agents, and Studio shows the company live.",
    steps: [
      ["Get Paperclip running", "The Start view's Install Paperclip runs npx paperclipai onboard (Node 24 or newer); an installed one starts with npx paperclipai run."],
      ["Link a company", "Link a company picks the one Studio shows (or make one from a lineup); Company says what is installed, running and linked."],
      ["Turn Org mode on", "Company's switch (or /org on, halo paperclip on). Off is the default: no agent runs on a heartbeat."],
      ["Read the boxes", "Org chart: each card is an agent (role, adapter, status, spend against its budget); a box holds one manager's reports, the top box is Leadership."],
      ["Change who reports to whom", "Drop a card into another box or onto a card; Studio asks first, then updates Paperclip. Drag a box's label strip to move the team."],
      ["Work with an agent", "Double-click a card: the Inspector edits its title, role, manager and budget, and Wakes, Pauses or Terminates it."],
      ["Follow the work", "Issues, goals, projects lists them live (every 3 s while Org shows); New issue assigns one and Paperclip wakes that agent."],
    ],
    keys: [["Alt+3", "Org"], ["A", "lay the chart out (click it first)"], ["F", "fit it to the panel"], ["+ / -", "zoom"], ["Mod+K", "Org: sync, Org: pull, Org: link company"], ...PANEL_KEYS],
  },
  design: {
    what: "Prototypes, pages, decks and logos made by your own apps and models. A project is a folder of artboards under ~/.halo/design/<slug>/, and every turn saves a new version.",
    steps: [
      ["Make or open a project", "The Start view names the first one; then Projects lists them all, and New project makes another."],
      ["Say what to design", "Write it in Thread and press Enter: the reply streams in as the turn works; Cancel turn stops it."],
      ["Look and compare", "Artboards: drag a card by its title (the places are saved with the project), slide back through its versions, Restore one."],
      ["Ask for notes", "Critique has a second model pin notes on an artboard; Contrast checks its text against its background; Send comments turns the pins into a turn."],
      ["Tidy up", "Rename or Delete an artboard, or Download its file."],
      ["Hand it off", "Export writes a folder, HTML, PNG, SVG or PDF; Handoff bundles it for the next Halo or Claude Code session."],
      ["Use your own files", "Assets: add or drop logos and photos; click one to put its path in the message."],
      ["Render pictures", "The palette's Media commands add the ComfyUI panels to the section."],
    ],
    keys: [["Alt+4", "Design"], ["Enter", "send the message (Shift+Enter: a new line)"], ["Mod+K", "Design: send, Design: cancel turn, Design: export, Design: new project"], ...PANEL_KEYS],
  },
  flow: {
    what: "A brief goes through your roles and a marketing org, ComfyUI renders the Art Director's prompt, you confirm the picture, then the posts go out and their metrics come back, all in one design project.",
    steps: [
      ["Write a brief", "On the Start view: the brief, the platforms, the budget and the design project; drop assets if you have them."],
      ["Press Run", "Run waits for your OK on the render, Run with --yes accepts every gate, Dry run keeps the posts dry."],
      ["The roles and the org work", "A planner and a researcher plan it; a strategist, a copywriter and an art director write the campaign and the image prompt."],
      ["Confirm the render", "ComfyUI renders it; the run waits in Renders until you Confirm, Redo with an instruction, or Stop."],
      ["Posts and metrics", "One post per platform through Postiz (dry runs unless the flow says live: true); Metrics samples how they do."],
      ["Read the report", "Report sums it up; New run in the rail goes back to the Start view."],
    ],
    keys: [["Alt+5", "Flow"], ...PANEL_KEYS],
  },
  fleet: {
    what: "Every Halo harness you run or joined, its sessions and every agent in them, live: what each one thinks, runs and writes, every decision that waits on you, what it all costs, and the controls to steer, pause, stop, take over or hand off any one agent.",
    steps: [
      ["See every harness", "This harness is the first box. Another machine joins with a pair code: Make a pair code on the Start view (or the palette), then halo fleet join on the other machine. People lists them all."],
      ["Answer what waits on you", "Attention is one queue of every card, gate, paused agent, spend cap and file conflict on every harness. A accepts, R denies or redoes with your text, S stops, O opens where it belongs."],
      ["Read the map", "Each session is a card, its agents a tree under it: a flowing outline works, amber waits on you, green just finished, red failed. By project shows each repo's dirty / ahead / behind; an amber dashed edge joins two agents editing one file."],
      ["Open an agent", "Click it (or J / K): Agent shows what it thinks as it types, each tool call with its result and diff, and what it hands back. Steer it with a nudge or a new task."],
      ["Pause, stop, hand off", "Pause holds it at its next step, Stop asks first. Take over gives it your brief; Hand to... passes it to another harness (a Paperclip issue with Org mode on, a hand-off note without) and stops it."],
      ["Know who can do what", "Capabilities has a spec card per harness: hardware, models, craft apps, MCP servers and their tools, skills, tags. Who can... ranks the fleet for what you need (gridcraft, a 4090, make a video) and picks the best one on the map."],
      ["Give the fleet one goal", "Mission (M): type the goal and Plan it; the hub's lead splits it into parts and gives each to the harness that can do it. The plan draws on the map, drag a part to another harness to move it, then Approve and Run; the report says who did what and what it cost per harness."],
      ["Watch the whole fleet", "Activity draws a lane per live agent (5, 15 or 60 minutes, tool calls as ticks) over the merged live log. Costs ticks today's spend and holds the caps; Health is a doctor summary per harness."],
      ["Record and replay", "Record saves a session or one agent as a single HTML file that plays anywhere. Replay plays a finished session on the Roles canvas: the cards light up in the order they worked."],
      ["Come back", "After ten minutes away, While you were away sums up what happened: sessions, cost, decisions and who made them, files, errors, hand-offs."],
    ],
    keys: [["Alt+6", "Fleet"], ...HOP_KEYS, ["P", "pause or resume the agent"], ["K", "in the Agent panel: stop it (asks first)"],
      ["M", "the Mission panel: one goal for the whole fleet"],
      ["A / R / S / O", "in Attention: accept, deny or redo (with a text), stop, open"], ["J / K", "in Attention: the next / previous row"], ...PANEL_KEYS],
  },
};
