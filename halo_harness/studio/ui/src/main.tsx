import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/motion.css";
import "./styles/shell.css";
import "./styles/workspace.css";
import "./styles/orchestra.css";
import "./styles/orchestra-file.css";
import "./styles/flow.css";
import "./styles/flow-start.css";
import "./styles/media.css";
import { App } from "./App";

document.documentElement.dataset.theme = document.documentElement.dataset.theme || "dark";
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
