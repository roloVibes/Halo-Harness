// The section a page opens on, from its `?mode=` and from the section this browser saved (lib/store.ts
// initialSection). 3.3.13.0 R2: a pack's own section is `<pack id>--<section id>` and opens while its pack runs (the
// served page names those, lib/boot.ts); a word a core section had before it went to a pack (`design`) opens the
// pack's section while the pack runs, else Session with one line saying how to turn the pack on (studio/modes.py
// moved_line says the same in the terminal).
import { bootPackSections } from "./boot";

export const MOVED_SECTIONS: Record<string, { pack: string; section: `${string}--${string}` }> = {
  design: { pack: "design", section: "design--design" },
};

export function movedLine(word: string): string {
  const m = MOVED_SECTIONS[word];
  if (!m) return "";
  return `${word[0].toUpperCase()}${word.slice(1)} is the ${m.pack} pack now: halo pack install ${m.pack}, then halo pack enable ${m.pack} --grant-all`;
}

const MODE_RE = /[?&]mode=([a-z][a-z0-9-]*(?:--[A-Za-z0-9][A-Za-z0-9_-]*)?)(?=&|#|$)/;
const running = (id: string) => bootPackSections().some((s) => s.id === id);

/** A known section id for `word` ('' for none): a core one, a running pack's, or a moved word's pack section. */
export function sectionFor(word: string, core: readonly string[]): string {
  if (core.includes(word)) return word;
  if (word.includes("--")) return running(word) ? word : "";
  const m = MOVED_SECTIONS[word];
  return m ? (running(m.section) ? m.section : "session") : "";
}

/** `?mode=` as the section it opens ('' when it names none) and, for a moved word whose pack is off, its line. */
export function askedSection(core: readonly string[]): { section: string; note: string } {
  const word = (typeof location !== "undefined" && MODE_RE.exec(location.search)?.[1]) || "";
  const section = sectionFor(word, core);
  const m = MOVED_SECTIONS[word];
  return { section, note: m && section === "session" ? movedLine(word) : "" };
}
