// The Glossary dialog (3.1.1.0 R1): every word Halo uses, each expandable to
// its one paragraph (docs/GLOSSARY.md through GET /api/glossary). Opened
// from the ? menu, the palette (Help: glossary) and the term links on each
// section's "How this works" page, which open it on that word.
import { useEffect, useRef } from "react";
import { Button, Dialog } from "../lib/ui";
import { useStore } from "../lib/store";
import { closeGlossary, glossary } from "../lib/glossary";

export function Glossary() {
  const open = useStore(glossary, (s) => s.open);
  const focus = useStore(glossary, (s) => s.focus);
  const words = useStore(glossary, (s) => s.words);
  const loaded = useStore(glossary, (s) => s.loaded);
  const error = useStore(glossary, (s) => s.error);
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open || !focus || !loaded) return;
    list.current?.querySelector(`[data-word="${CSS.escape(focus)}"]`)?.scrollIntoView({ block: "center" });
  }, [open, focus, loaded]);
  if (!open) return null;
  return (
    <Dialog
      open
      onClose={closeGlossary}
      title="Glossary"
      kicker="EVERY WORD · ONE PARAGRAPH"
      className="glossary"
      testid="glossary"
      footer={
        <>
          <span className="muted glossary-note">
            The same text: <code>halo explain &lt;word&gt;</code> and <code>/explain</code> in the TUI (docs/GLOSSARY.md).
          </span>
          <Button variant="primary" onClick={closeGlossary}>
            Close
          </Button>
        </>
      }
    >
      <div className="glossary-list" ref={list}>
        {error && <p className="og-problems">Studio could not read the glossary: {error}</p>}
        {!loaded && !error && <p className="muted mono">reading the glossary...</p>}
        {words.map((w) => (
          <details key={w.word} className="glossary-item" data-word={w.word} data-testid="glossary-word" open={w.word === focus || undefined}>
            <summary className="glossary-term">{w.word}</summary>
            <p className="glossary-text">{w.text}</p>
          </details>
        ))}
      </div>
    </Dialog>
  );
}
