import "./lib/owner"; // 3.3.14.0 R1 (#4): first of all, it takes the owner salt off the page before anything else runs
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/motion.css";
import "./styles/shell.css";
import "./styles/workspace.css";
import "./styles/orchestra.css";
import "./styles/orchestra-file.css";
import "./styles/orchestra-plan.css";
import "./styles/start-view.css";
import "./styles/media.css";
import "./styles/help.css";
import "./styles/fleet.css";
import "./styles/fleet-agent.css";
import "./styles/fleet-panels.css";
import "./styles/fleet-panels2.css";
import "./styles/local-traffic.css"; // 3.3.4.0 R5: the Ollama steward panel; 3.3.16.0 R2: a host's traffic and fit on Local -> Hosts
import "./styles/fleet-caps.css";
import "./styles/fleet-mission.css";
import "./styles/fleet-mission2.css";
import "./styles/shared.css";
import "./styles/roles.css";
import "./styles/roles-panels.css";
import "./styles/roles-inspector.css"; // 3.3.16.0 R1b: the inspector's summary, Edit rows and one block's page
import "./styles/disk-note.css";
import "./styles/coach.css";
import "./styles/start.css";
import "./styles/session.css";
import "./styles/model-select.css";
import "./styles/holo.css";
import "./styles/session-live.css";
import "./styles/session-target.css";
import "./styles/prompt.css"; // 3.3.11.0 R1: Session's Prompt panel
import "./styles/roles-live.css"; // 3.3.11.0 R2: Roles Live, New session, the no-terminal line
import "./styles/agents.css"; // 3.3.16.0 R1: Agents' bar (Cast | Runs | Live), the owns line, a lane's claims
import "./styles/agents-live.css"; // 3.3.16.0 R2: Live's fleet scope, its inspector, the Attention chip, Setup -> Machines
import "./styles/workflows.css"; // 3.3.16.0 R3: Agents -> Workflows, the board of squares; a square's Live node
import "./styles/packs.css";
import "./styles/manager.css";
import "./styles/setup.css";
import "./styles/setup-providers.css";
import "./styles/setup-pages.css"; // 3.3.1.0 R1
import "./styles/settings.css"; // 3.3.3.0 R2
import "./styles/themes.css"; // 3.3.12.0 R1: the theme menu's swatches and Settings -> Themes
import "./styles/local.css"; // 3.3.5.0 R1
import "./styles/local-pages.css"; // 3.3.5.0 R1
import "./styles/local-library.css"; // 3.3.5.0 R2
import "./styles/local-control.css"; // 3.3.5.0 R3
import "./styles/local-hf.css"; // 3.3.5.0 R5
import "./styles/model-card.css"; // 3.3.5.0 R0b: the model card and the fit meter
import "./styles/model-probe.css"; // 3.3.6.0 R1: the battery's blocks, chips and progress strip
import "./styles/local-search.css"; // 3.3.6.0 R2: the search's strip, presets, truth marks, verdicts and cost
import "./styles/local-logs.css"; // 3.3.6.0 R3: Local -> Logs and the fit badge's evidence chip
import "./styles/model-measured.css"; // 3.3.6.0 R4: the KV dial, the dialect block, the shelf, Why this answer?
import "./styles/local-bench.css"; // 3.3.6.0 R5: Benchmarks: the speed cards, the tuning report, the changes, the scope pick
import "./styles/local-guards.css"; // 3.3.7.0 R4: the foreign line, the refresh lines, the Adviser
import "./styles/local-steward.css"; // 3.3.7.0 R5: the Steward page's chat box and model picker
import "./styles/local-pool.css"; // 3.3.8.0 R1: Local -> Pool, the members, the scan, the recommendation, the Pool badge
import "./styles/local-voice.css"; // 3.3.9.0 R3: Local -> Voice, the speech servers, Talk, the turns
import "./styles/nodes.css"; // 3.3.15.0 L1: the Instrument look's map nodes and edges (after fleet.css and roles-live.css)
import "./styles/instrument.css"; // 3.3.15.0 L1: the kit's pieces whose CSS lived elsewhere (fit meter, the Dialog's cost block)
import "./styles/model-takes.css"; // 3.3.15.0 R2: what a model takes, the picker's one-line rows (after model-card.css)
import "./styles/hover-card.css"; // 3.3.16.1: the one hover card (lib/ui/HoverCard.tsx)
import "./styles/textbox.css"; // 3.3.15.0 R3: the one text box (lib/ui/TextBox.tsx), after every section's sheet
import { App } from "./App";
import { installLib } from "./packlib";

installLib(); // 3.3.13.0 R2: a pack's bundle takes the shell's React and parts from here (packlib/index.ts)
document.documentElement.dataset.theme = document.documentElement.dataset.theme || "instrument"; // 3.3.15.0 R4: unset is instrument
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
