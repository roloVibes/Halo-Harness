// api.lib.kbd and api.lib.commands (3.3.13.0 R2, extension API 1.2): a pack page's keys and palette lines, gone
// when the page goes (call what they return in the function mount returns).
//
//   kbd("Mod+Enter", (e) => send())                       a key anywhere on the page; Mod is Ctrl (Cmd on a Mac).
//        A key a text field, a panel or a dialog already took is left to it; the section keys and Mod+K stay the shell's.
//   commands(() => [{id, label, hint?, run}])            lines in the palette (Mod+K), in a group named for the pack,
//        read each time the palette opens.
export type PackCommand = { id: string; label: string; hint?: string; run: () => void };
type Provider = { group: string; fn: () => PackCommand[] };

const providers = new Set<Provider>();
const SHELL = /^(Alt\+[0-9]|Mod\+K)$/i;

function matches(combo: string, e: KeyboardEvent): boolean {
  const parts = combo.split("+").map((p) => p.trim().toLowerCase());
  const key = parts.pop() || "";
  const want = { mod: parts.includes("mod"), alt: parts.includes("alt"), shift: parts.includes("shift") };
  if (want.mod !== (e.ctrlKey || e.metaKey) || want.alt !== e.altKey || want.shift !== e.shiftKey) return false;
  return e.key.toLowerCase() === key || e.code.toLowerCase() === "key" + key || e.code.toLowerCase() === key;
}

export function kbd(combo: string, run: (e: KeyboardEvent) => void): () => void {
  if (SHELL.test(combo.trim())) return () => undefined;
  const onKey = (e: KeyboardEvent) => {
    if (e.defaultPrevented || !matches(combo, e)) return;
    e.preventDefault();
    run(e);
  };
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}

export function commandsFor(pack: string) {
  return (fn: () => PackCommand[]): (() => void) => {
    const p: Provider = { group: `pack ${pack}`, fn };
    providers.add(p);
    return () => void providers.delete(p);
  };
}

/** Every line the pack pages registered, for the palette (shell/commands.ts). */
export function packPageCommands(): { id: string; group: string; label: string; hint?: string; run: () => void }[] {
  const out: { id: string; group: string; label: string; hint?: string; run: () => void }[] = [];
  for (const p of providers) {
    try {
      for (const c of p.fn()) out.push({ ...c, id: `page-${c.id}`, group: p.group });
    } catch (e) {
      console.error(`${p.group}: its palette lines threw`, e);
    }
  }
  return out;
}
