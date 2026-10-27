// The door into Settings (3.3.3.0 R2, studio/settings_door.py): `halo settings
// fleet` opens `?mode=settings&group=fleet`. The group word leaves the address
// once read (a reload opens the page remembered; the token in the fragment
// stays), as Setup's `block=` does (routes/setup/door.ts). A Studio page
// already open gets the same as a `focus` frame {mode: "settings", group}
// (shell/edit.ts). Nothing opens over the page: the group's page is the room.
import { goSection } from "../../lib/store";
import { goto } from "./pages";
import { startSettings } from "./store";

export type Door = { group?: string };

/** Open Settings the way the door asked: the section, then the group's page. */
export function applyDoor(d: Door): void {
  startSettings();
  goSection("settings");
  if (d.group) goto(d.group);
}

/** The page's own address: `?mode=settings&group=<id>`, the group read once and dropped. */
export function doorFromUrl(): Door | null {
  if (typeof location === "undefined") return null;
  const q = new URLSearchParams(location.search);
  if (q.get("mode") !== "settings" || !q.has("group")) return null;
  const d: Door = { group: q.get("group") || "" };
  q.delete("group");
  try {
    const rest = q.toString();
    history.replaceState(history.state, "", location.pathname + (rest ? `?${rest}` : "") + location.hash);
  } catch {
    /* a browser that keeps the address as it is: the word is read again on a reload */
  }
  return d;
}
