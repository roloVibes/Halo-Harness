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
    keys: [["Alt+1", "Orchestra"], ...PANEL_KEYS],
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
    ],
    keys: [["Alt+2", "Roles"], ["A", "lay the canvas out (click the canvas first)"], ["F", "fit it to the view"], ["Mod+S", "save the lineup"], ["Del", "remove the selected card"], ...PANEL_KEYS],
  },
  org: {
    what: "Your company of agents in Paperclip: an org chart with goals, issues, heartbeats and budgets. Halo's lineups become its agents.",
    steps: [
      ["Turn Org mode on", "The toolbar's Org mode button (or /org on, halo paperclip on). Off is the default: nothing runs on a heartbeat."],
      ["Get Paperclip running", "Without it the canvas offers Install Paperclip (Node 24 or newer); once it runs, pick the company in the toolbar."],
      ["Read the boxes", "Each card is an agent: title, role, adapter, status and spend against its budget. A box holds one manager's reports; the top box is Leadership."],
      ["Change who reports to whom", "Drop a card into another box, or onto a card; Studio asks first, then updates Paperclip."],
      ["Work with an agent", "Select a card: Agent (budget, wake, pause), Issues, its Paperclip page, and Company (sync a lineup into the company)."],
    ],
    keys: [["Alt+3", "Org"], ["A", "lay the canvas out (click the canvas first)"], ["F", "fit it to the view"], ...PANEL_KEYS],
  },
  design: {
    what: "Prototypes, pages, decks and logos made by your own apps. A project is a folder of artboards under ~/.halo/design/<slug>/, and every turn saves a new version.",
    steps: [
      ["Open a project", "Make one in the left rail (N) or pick one."],
      ["Say what to design", "Type it in the Chat tab and press Enter: one turn, its cost shown as it streams."],
      ["Look and compare", "Each artboard is a card: drag it by its title, switch the device size, slide back through its versions."],
      ["Comment", "C pins a comment on a frame; Send comments turns the pins into one turn. K asks a second model to critique."],
      ["Tune without a model", "Knobs move spacing, colours and sizes; the Contrast table checks text against its background."],
      ["Hand it off", "Export writes a folder, HTML, PNG, SVG or PDF; Handoff bundles it for a Halo or Claude Code session."],
      ["Render pictures", "The palette's Media commands pop the ComfyUI panels over the canvas."],
    ],
    keys: [["Alt+4", "Design"], ["N", "new project (click the canvas first)"], ["C", "comment tool"], ["V", "3 directions"], ["K", "critique"], ["E", "export"], ...PANEL_KEYS],
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
};
