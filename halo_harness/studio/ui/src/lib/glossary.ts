// The glossary (3.1.1.0 R1): the words Halo uses, one paragraph each, served
// by GET /api/glossary from docs/GLOSSARY.md (the same text `halo explain`
// prints). Loaded once, on the first open; `openGlossary(word)` opens the
// dialog (shell/Glossary.tsx) with that word expanded.
import { call } from "./api";
import { createStore } from "./store";

export type GlossaryWord = { word: string; text: string };

type GlossaryState = {
  open: boolean;
  focus: string | null;
  words: GlossaryWord[];
  loaded: boolean;
  error: string;
};

export const glossary = createStore<GlossaryState>({ open: false, focus: null, words: [], loaded: false, error: "" });

let loading = false;

export async function loadGlossary(): Promise<void> {
  if (loading || glossary.get().loaded) return;
  loading = true;
  try {
    const data = await call<{ words: GlossaryWord[] }>("GET", "glossary");
    glossary.update(() => ({ words: Array.isArray(data.words) ? data.words : [], loaded: true, error: "" }));
  } catch (e) {
    glossary.update(() => ({ error: e instanceof Error ? e.message : String(e) }));
  } finally {
    loading = false;
  }
}

export function openGlossary(word: string | null = null): void {
  glossary.update(() => ({ open: true, focus: word }));
  void loadGlossary();
}

export function closeGlossary(): void {
  glossary.update(() => ({ open: false, focus: null }));
}
