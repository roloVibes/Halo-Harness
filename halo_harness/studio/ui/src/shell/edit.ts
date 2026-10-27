// Open an edit target (3.1.1.0 R3): Studio is the one editor of bios and
// lineups, and the terminal opens it on the thing to edit. A target is
// bio:<name> (Roles, the Bios panel on that bio's form), lineup:<name> (Roles,
// that lineup open, the Inspector on its Lineup tab) or team (the Team
// section). It arrives two ways: `?edit=<target>` in the page URL (`halo
// studio --edit`, `halo agents edit`, the TUI's `e` and `/edit`), and a
// `focus` frame on the live feed when a second `halo studio --edit` finds this
// Studio running (studio/focus_api.py): every open page opens the target.
// 3.1.4.0 R2: a frame with no edit target but a `mode` opens that section --
// Session on its `session` (`/studio`, `halo studio --session`); the URL's
// `?mode=session&session=` is read by routes/session/store.ts itself.
// 3.3.0.0 R4: Setup's doors (`?mode=setup&first=1`, `&block=team`, and a frame
// `{mode: "setup", block, first}`) go to routes/setup/door.ts.
import { onEvent } from "../lib/events";
import { goSection, SECTION_IDS, type SectionId } from "../lib/store";
import { openSession } from "../routes/session/store";
import { applyDoor, doorFromUrl } from "../routes/setup/door";
import { start } from "../lib/start";
import { focusPanel, layoutStore, patchPanel } from "../lib/workspace/persist";
import { openBio } from "../routes/roles/bioActions";
import { roles, setView } from "../routes/roles/store";
import { openLineup, startRoles } from "../routes/roles/sync";

export type EditTarget = { kind: "bio" | "lineup" | "team"; name: string; text: string };

const NAME = /^[A-Za-z0-9][A-Za-z0-9_.-]*$/;

/** `bio:<name>` | `lineup:<name>` | `team`, as studio/edit_target.py writes them; null for anything else. */
export function parseEdit(text: string | null | undefined): EditTarget | null {
  const t = (text || "").trim();
  if (t === "team") return { kind: "team", name: "", text: t };
  const m = /^(bio|lineup):(.+)$/.exec(t);
  if (!m || !NAME.test(m[2])) return null;
  return { kind: m[1] as "bio" | "lineup", name: m[2], text: t };
}

/** Run `fn` once the section's panels are laid out (a page that just loaded mounts them a moment later). */
function whenLaidOut(section: string, fn: () => void, tries = 60): void {
  if (layoutStore(section).get().layout || tries <= 0) fn();
  else window.setTimeout(() => whenLaidOut(section, fn, tries - 1), 50);
}

function showPanel(id: string): void {
  whenLaidOut("roles", () => {
    patchPanel("roles", id, { collapsed: false, face: "detail" }, false);
    focusPanel("roles", id);
  });
}

/** Open the target: switch to its section and open the bio form, the lineup's inspector or the Team. */
export async function applyEdit(target: EditTarget): Promise<void> {
  if (start.get().open && !start.get().running) start.update(() => ({ open: false })); // the overlay waits; nothing is dismissed
  if (target.kind === "team") {
    goSection("team");
    return;
  }
  goSection("roles");
  roles.update(() => ({ editing: target.text }));
  setView("workspace"); // the Start view would hide the panels
  startRoles();
  try {
    if (target.kind === "bio") {
      await openBio(target.name);
      showPanel("roles-bios");
    } else {
      await openLineup(target.name);
      roles.update(() => ({ tab: "lineup" }));
      showPanel("roles-inspector");
    }
  } finally {
    roles.update(() => ({ editing: "" }));
  }
}

let installed = false;

/** On load: `?edit=` in the URL; from then on, every `focus` frame. */
export function installEdit(): void {
  if (installed) return;
  installed = true;
  const asked = parseEdit(new URLSearchParams(location.search).get("edit"));
  if (asked) void applyEdit(asked);
  const door = doorFromUrl(); // 3.3.0.0 R4: `?mode=setup&first=1` (halo init) or `&block=team` (halo setup team)
  if (door) applyDoor(door);
  onEvent("focus", (f) => {
    const d = (f.data || {}) as { edit?: string; mode?: string; session?: string; block?: string; first?: boolean };
    const target = parseEdit(String(d.edit || ""));
    const mode = String(d.mode || "") as SectionId;
    if (target) void applyEdit(target);
    else if (mode === "setup") applyDoor({ block: String(d.block || ""), first: !!d.first });
    else if (mode === "session") openSession({ session: String(d.session || "") });
    else if ((SECTION_IDS as string[]).includes(mode)) goSection(mode);
    else return;
    try {
      window.focus();
    } catch {
      /* a browser may keep its window where it is */
    }
  });
}
