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
import "./styles/fleet-ollama.css"; // 3.3.4.0 R5: the Ollama steward panel
import "./styles/fleet-caps.css";
import "./styles/fleet-mission.css";
import "./styles/fleet-mission2.css";
import "./styles/shared.css";
import "./styles/design.css";
import "./styles/design-thread.css";
import "./styles/roles.css";
import "./styles/roles-panels.css";
import "./styles/disk-note.css";
import "./styles/team.css";
import "./styles/team-panels.css";
import "./styles/coach.css";
import "./styles/start.css";
import "./styles/session.css";
import "./styles/model-select.css";
import "./styles/holo.css";
import "./styles/session-live.css";
import "./styles/session-target.css";
import "./styles/packs.css";
import "./styles/manager.css";
import "./styles/setup.css";
import "./styles/setup-providers.css";
import "./styles/setup-pages.css"; // 3.3.1.0 R1
import "./styles/settings.css"; // 3.3.3.0 R2
import "./styles/local.css"; // 3.3.5.0 R1
import "./styles/local-pages.css"; // 3.3.5.0 R1
import "./styles/local-library.css"; // 3.3.5.0 R2
import "./styles/local-control.css"; // 3.3.5.0 R3
import "./styles/local-hf.css"; // 3.3.5.0 R5
import "./styles/model-card.css"; // 3.3.5.0 R0b: the model card and the fit meter
import "./styles/model-probe.css"; // 3.3.6.0 R1: the battery's blocks, chips and progress strip
import { App } from "./App";

document.documentElement.dataset.theme = document.documentElement.dataset.theme || "dark";
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
