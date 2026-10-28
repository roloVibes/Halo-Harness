// The door into Local (3.3.5.0 R1, studio/local_door.py): `halo local hosts`
// opens `?mode=local&page=hosts`. The page word leaves the address once read (a
// reload opens the page remembered; the token in the fragment stays), as
// Settings' `group=` does (routes/settings/door.ts). A Studio page already open
// gets the same as a `focus` frame {mode: "local", page} (shell/edit.ts).
// Nothing opens over the page: the page is the room.
import { goSection } from "../../lib/store";
import { goto, pageOf } from "./pages";
import { startLocal } from "./store";

export type Door = { page?: string };

/** Open Local the way the door asked: the section, then the page. */
export function applyDoor(d: Door): void {
  startLocal();
  goSection("local");
  const p = pageOf(d.page || "");
  if (p) goto(p);
}

/** The page's own address: `?mode=local&page=<id>`, the page read once and dropped. */
export function doorFromUrl(): Door | null {
  if (typeof location === "undefined") return null;
  const q = new URLSearchParams(location.search);
  if (q.get("mode") !== "local" || !q.has("page")) return null;
  const d: Door = { page: q.get("page") || "" };
  q.delete("page");
  try {
    const rest = q.toString();
    history.replaceState(history.state, "", location.pathname + (rest ? `?${rest}` : "") + location.hash);
  } catch {
    /* a browser that keeps the address as it is: the word is read again on a reload */
  }
  return d;
}
