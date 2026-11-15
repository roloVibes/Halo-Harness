// Open an edit target (3.1.1.0 R3; 3.6.0.0 R5: the three tabs): Studio is the one editor of agents, workflows and maps,
// and the terminal opens it on the thing to edit. A target is agent:<name> (Agents -> 1 · Agents, that agent's form),
// workflow:<name> (2 · Workflows, its form) or map:<name> (3 · Map, that map). The old forms -- bio:<name>,
// lineup:<name>[:<block>], team -- open the tab that replaced them (bio: 1 · Agents; lineup and team: 3 · Map) with the
// old files' one line ("lineups and bios are no longer read"). It arrives two ways: `?edit=<target>` in the page URL
// (`halo studio --edit`, `halo agents edit`, the TUI's `/edit`), and a `focus` frame on the live feed when a second
// `halo studio --edit` finds this Studio running (studio/focus_api.py): every open page opens the target.
// 3.1.4.0 R2: a frame with no edit target but a `mode` opens that section -- Session on its `session` (`/studio`, `halo
// studio --session`). 3.3.0.0 R4: Setup's doors go to routes/setup/door.ts; 3.3.3.0 R2: Settings' to
// routes/settings/door.ts; 3.3.5.0 R1: Local's to routes/local/door.ts. A frame's `mode` of roles, orchestra or team
// (and `{mode: "agents", view}`) opens Agents on its tab (lib/agentsDoor.ts). 3.3.11.0 R1: `?prompt=1` (and a session
// frame's `prompt: true`) opens Session's Prompt panel, the keyboard in its box.
import { onEvent } from "../lib/events";
import { AGENTS_DOORS, viewOf } from "../lib/agentsDoor";
import { goSection, SECTION_IDS, toast, type SectionId } from "../lib/store";
import { openSession } from "../routes/session/store";
import { openPrompt, promptAsked } from "../routes/session/promptStore";
import { applyDoor, doorFromUrl } from "../routes/setup/door";
import { applyDoor as applySettingsDoor, doorFromUrl as settingsDoorFromUrl } from "../routes/settings/door";
import { applyDoor as applyLocalDoor, doorFromUrl as localDoorFromUrl } from "../routes/local/door";
import { openAgent } from "../routes/crew/store";
import { openFlow } from "../routes/crew/flows/flowStore";
import { openMap } from "../routes/crew/map/mapStore";

export type EditTarget = { kind: "agent" | "workflow" | "map" | "bio" | "lineup" | "team"; name: string; text: string };
/** The old forms' one line (3.6.0.0 R5; studio/edit_target.py OLD_LINE says the same in the terminal). */
export const OLD_EDIT_LINE = "Lineups and bios are no longer read: agents, workflows and maps live in ~/.halo/crew/";

const NAME = /^[A-Za-z0-9][A-Za-z0-9_.-]*$/;

/** `agent:<name>` | `workflow:<name>` | `map:<name>`, or an old form (`bio:<name>`, `lineup:<name>[:<block>]`, `team`),
 *  as studio/edit_target.py writes them; null for anything else. */
export function parseEdit(text: string | null | undefined): EditTarget | null {
  const t = (text || "").trim();
  if (t === "team") return { kind: "team", name: "", text: t };
  const m = /^(agent|workflow|map|bio|lineup):([^:]+)(?::[a-z]+)?$/.exec(t);
  if (!m || !NAME.test(m[2])) return null;
  return { kind: m[1] as EditTarget["kind"], name: m[2], text: t };
}

/** Open the target: Agents on its tab, the thing open in it (an old form: the tab that replaced it, and the line). */
export async function applyEdit(target: EditTarget): Promise<void> {
  if (target.kind === "agent" || target.kind === "bio") {
    goSection("agents", "crew");
    if (target.kind === "agent") await openAgent(target.name);
  } else if (target.kind === "workflow") {
    goSection("agents", "workflows");
    await openFlow(target.name);
  } else {
    goSection("agents", "map");
    if (target.kind === "map") await openMap(target.name);
  }
  if (target.kind === "bio" || target.kind === "lineup" || target.kind === "team") toast(OLD_EDIT_LINE, "info", 8000);
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
  const settingsDoor = settingsDoorFromUrl(); // 3.3.3.0 R2: `?mode=settings&group=fleet` (halo settings fleet)
  if (settingsDoor) applySettingsDoor(settingsDoor);
  const localDoor = localDoorFromUrl(); // 3.3.5.0 R1: `?mode=local&page=hosts` (halo local hosts)
  if (localDoor) applyLocalDoor(localDoor);
  if (promptAsked()) openPrompt(); // 3.3.11.0 R1: `?mode=session&session=<sid>&prompt=1`
  onEvent("focus", (f) => {
    const d = (f.data || {}) as { edit?: string; mode?: string; view?: string; session?: string; block?: string; first?: boolean; group?: string; page?: string; prompt?: boolean };
    const target = parseEdit(String(d.edit || ""));
    const mode = String(d.mode || "") as SectionId;
    if (target) void applyEdit(target);
    else if (mode === "setup") applyDoor({ block: String(d.block || ""), first: !!d.first });
    else if (mode === "settings") applySettingsDoor({ group: String(d.group || "") });
    else if (mode === "local") applyLocalDoor({ page: String(d.page || "") });
    else if (mode === "session") (openSession({ session: String(d.session || "") }), d.prompt && openPrompt());
    else if ((SECTION_IDS as string[]).includes(mode) || AGENTS_DOORS[mode]) goSection(mode, mode === "agents" ? viewOf(String(d.view || "")) || undefined : undefined);
    else return;
    try {
      window.focus();
    } catch {
      /* a browser may keep its window where it is */
    }
  });
}
