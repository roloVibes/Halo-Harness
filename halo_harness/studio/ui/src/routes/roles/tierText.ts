// The words the Roles canvas shows for a tier (3.1.6.0 R1): its trigger chip
// (`every 30m`, `on file src/`, the same text `halo teams show` prints,
// teams_tier_fields.trigger_text) and where a card's model comes from (the
// card pill's title; the order is teams_yaml.member_model's).
import type { TierTrigger } from "./types";

export const TRIGGER_KINDS = ["schedule", "file_change", "event", "message"] as const;

/** `every 30m`, `cron 0 9 * * 1`, `on file src/`, `on event turn_done`, `on message from worker`. */
export function triggerText(t: TierTrigger | null | undefined): string {
  if (!t) return "";
  if (t.on === "schedule") return t.every ? `every ${t.every}` : `cron ${t.cron || "?"}`;
  if (t.on === "file_change") return `on file ${(t.paths || []).join(", ") || "?"}`;
  if (t.on === "event") return `on event ${t.name || "?"}`;
  if (t.on === "message") return `on message from ${t.from || "?"}`;
  return "";
}

/** The one field each trigger kind needs, as the Trigger form shows and edits it. */
export function triggerField(t: TierTrigger | null | undefined): string {
  if (!t) return "";
  if (t.on === "schedule") return t.every || t.cron || "";
  if (t.on === "file_change") return (t.paths || []).join(", ");
  return (t.on === "event" ? t.name : t.from) || "";
}

/** The trigger the form's three fields make (null: "none"). A schedule field with spaces is a cron line. */
export function makeTrigger(kind: string, field: string, prompt: string, model = ""): TierTrigger | null {
  const v = field.trim();
  if (!TRIGGER_KINDS.includes(kind as (typeof TRIGGER_KINDS)[number])) return null;
  const t: TierTrigger = { on: kind as TierTrigger["on"] };
  if (kind === "schedule") {
    if (/\s/.test(v)) t.cron = v;
    else t.every = v;
  } else if (kind === "file_change") t.paths = v.split(",").map((p) => p.trim()).filter(Boolean);
  else if (kind === "event") t.name = v;
  else t.from = v;
  t.prompt = prompt.trim();
  if (model) t.model = model;
  return t;
}

/** Where the card's model comes from, for its pill's title. */
export function sourceText(src: string | undefined, bio: string): string {
  if (!src) return "";
  if (src === "card") return "this card's own model";
  if (src === "bio") return `bio ${bio || "?"}'s own model`;
  if (src.startsWith("tier:")) return `tier ${src.slice(5)}'s model`;
  if (src === "session") return `the session's model (bio ${bio || "?"} says default)`;
  return "a fallback model";
}
