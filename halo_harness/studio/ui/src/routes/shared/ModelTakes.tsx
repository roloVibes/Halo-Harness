// What a model takes (3.3.15.0 R2, "the picker says what a model takes"): one tag group wherever a model is picked
// in Studio -- the model select (Orchestra's goal and workflow forms, Roles' Assignment, strip, tiers and bio form),
// Session's new-session select, Roles' picker table (its TAKES column), Setup's default model, Settings' model rows.
// The words come from the row the API already sends (`takes`, studio/model.py -> halo_harness/model_takes.py, the
// same words the terminal's /model picker shows in its takes= column). Owner feedback 2026-11-09 ("the chips"):
// one line, fixed-height tags (styles/model-takes.css), a fixed order -- the inputs (vision, audio, video, pdf), what
// it makes (image), then tools and think -- at most six, then "+n"; a text-only model reads "text in" once and an
// unknown one "?" (both muted), never an empty cell. The ranked "best at" kinds are not tags: the honest line is the
// group's title and the picker's detail line. The Local library rows keep their own capability chips with their
// truth glyphs (local/LibraryRowBits.tsx CapMarks).

export type TakesFields = {
  ref?: string;
  takes?: string[] | null;
  /** The Models panel's rows carry `{line, kinds}`; Setup's and the new-session rows carry the line itself. */
  best_at?: { line?: string } | string | null;
  line?: string | null;
};

const ORDER = ["vision", "audio", "video", "pdf", "image", "tools", "think"];
const INPUTS = new Set(["vision", "audio", "video", "pdf"]);
export const MAX_TAGS = 6;

/** The honest line of a row, whichever shape it came in. */
export const honestLine = (r: TakesFields | null | undefined): string =>
  !r ? "" : typeof r.best_at === "string" ? r.best_at : r.best_at?.line || r.line || "";

/** "text,vision,pdf,tools" for a title or an option's line; "?" when nothing is stated. */
export const takesText = (r: TakesFields | null | undefined): string => (r?.takes?.length ? r.takes.join(",") : "?");

/** The tags in their fixed order: [word, muted]; "text in" / "?" lead when no other input is stated. */
export function tagsOf(takes: string[] | null | undefined): [string, boolean][] {
  const words = takes?.length ? takes : ["?"];
  const known = ORDER.filter((w) => words.includes(w)).map((w): [string, boolean] => [w, false]);
  if (known.some(([w]) => INPUTS.has(w))) return known;
  return [[words.includes("?") ? "?" : "text in", true], ...known];
}

export function ModelTakes({ row }: { row?: TakesFields | null }) {
  if (!row) return null;
  const tags = tagsOf(row.takes);
  const shown = tags.slice(0, MAX_TAGS);
  const more = tags.length - shown.length;
  const line = honestLine(row);
  const title = line || (tags[0][0] === "?" ? "the catalog states no inputs for this model" : "what the catalog states it takes");
  return (
    <span className="mtakes" data-testid="model-takes" data-ref={row.ref} data-takes={(row.takes?.length ? row.takes : ["?"]).join(",")}
          title={title}>
      {shown.map(([t, muted]) => (
        <span key={t} className="mtakes-tag mono" data-take={t} data-muted={muted || undefined}>{t}</span>
      ))}
      {more > 0 && <span className="mtakes-tag mono" data-more={more} data-muted>+{more}</span>}
    </span>
  );
}
