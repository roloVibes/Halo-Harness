// The Roles section's own keys (3.0.7.0 R2), while Roles is on screen:
// Ctrl+Z undoes the last lineup edit, Ctrl+Shift+Z (or Ctrl+Y) redoes it,
// Mod+S saves the lineup. Inside a text box the box keeps its own undo. The
// canvas takes A, F, + / -, the arrows and Delete when it has the focus
// (Canvas.tsx); J / K, Space, P and F for the live agents are the shell's
// hop keys (routes/fleet/hop.ts).
import { useEffect } from "react";
import { studio } from "../../lib/store";
import { redo, save, undo } from "./actions";
import { roles } from "./store";

const TYPING = "input, textarea, select, [contenteditable]";

export function useRolesKeys(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || studio.get().section !== "roles" || studio.get().paletteOpen || roles.get().dialog) return;
      const mod = e.ctrlKey || e.metaKey;
      if (!mod || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === "s") {
        e.preventDefault();
        if (roles.get().dirty) void save();
        return;
      }
      if ((e.target as HTMLElement | null)?.closest?.(TYPING)) return;
      if ((k === "z" && e.shiftKey) || k === "y") {
        if (redo()) e.preventDefault();
      } else if (k === "z") {
        if (undo()) e.preventDefault();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
