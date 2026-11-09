// api.lib.workspace (3.3.13.0 R2, extension API 1.2): the shell's panel workspace for a page that wants panels --
// `<Workspace section={api.section} specs={...} />` draws PanelSpecs on the 24-column grid with the shell's drag,
// resize, strips, pop-out and saved layout (per section id); showPanel / hidePanel / focusPanel move one.
export { Workspace } from "../lib/workspace/Workspace";
export { focusPanel, hidePanel, layoutStore, patchPanel, showPanel } from "../lib/workspace/persist";
export type { Face, PanelLayout, PanelSpec } from "../lib/workspace/types";
export { settle, useStateMotion, type MotionState } from "../lib/motion"; // a panel's motion (styles/motion.css)
