// 3.6.0.11 SM: Agents -> Map says which map new sessions run. The select at the top left only opens a map; when the
// open map is not the one new sessions run, the line "New sessions do not run on {open}; they run on {next}." stands
// with [Run new sessions on {open}] (data-testid map-use-this), which does what the switch does (mapSwitch.ts setUse;
// on Auto, where no switch is drawn, it takes crew.map out). MapBar's TopLine draws it in place of its sentence,
// AutoPlan under M1; each reserves the room of the line from the first draw (`room`, measured in a hidden twin).
import { Button } from "../../../lib/ui";
import { useMap } from "./mapStore";
import { setUse } from "./mapSwitch";
import { notNextLine, notNextWords, useThisLabel } from "./truth";

/** The open map's line ("" when new sessions run it, or before its detail is read) and the form its room holds. */
export function useNotNext(): { name: string; line: string; room: string } {
  const name = useMap((s) => (s.listed && s.detail ? s.name : ""));
  const scope = useMap((s) => s.detail?.scope || s.scope || "");
  const next = useMap((s) => s.next);
  const none = useMap((s) => s.nextNone);
  const line = notNextLine(name, scope, next, none);
  return { name, line, room: line || (name ? notNextWords(name, null) : "") };
}

/** The button; `twin` draws its unseen copy for the room's measure (never focused, never pressed). */
export function UseThis({ name, twin = false }: { name: string; twin?: boolean }) {
  if (twin) return <button type="button" tabIndex={-1} className="btn btn-default btn-sm"><span className="btn-label">{useThisLabel(name)}</span></button>;
  return <Button size="sm" data-testid="map-use-this" onClick={() => void setUse(true)}>{useThisLabel(name)}</Button>;
}
