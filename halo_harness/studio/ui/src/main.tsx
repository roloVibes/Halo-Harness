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
import "./styles/fleet-caps.css";
import "./styles/fleet-mission.css";
import "./styles/fleet-mission2.css";
import "./styles/shared.css";
import "./styles/design.css";
import "./styles/design-thread.css";
import "./styles/roles.css";
import "./styles/roles-panels.css";
import "./styles/team.css";
import "./styles/team-panels.css";
import "./styles/coach.css";
import "./styles/start.css";
import "./styles/session.css";
import { App } from "./App";

document.documentElement.dataset.theme = document.documentElement.dataset.theme || "dark";
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
