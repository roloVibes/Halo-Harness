// "How this works" for the current section: what it is, the numbered steps,
// the section's panels with their one-line `about`, and the keys. Opened from
// the ? beside the section tabs, the palette (Help: how <section> works) and
// `?`. 3.3.2.0 R1: nothing opens it on its own (the first-visit welcome is gone
// for every section); its KEYS list the section's Alt+N first and the shell's
// own keys last (F Focus, the rail's chevron), since the rail rows print no
// shortcut. 3.1.1.0 R1: the WORDS row links each glossary word the section
// uses into the Glossary. A section with no panels (Setup's pages) lists its
// steps and keys only.
import { Button, Dialog, Kbd } from "../lib/ui";
import { closeHelp, studio, useStore } from "../lib/store";
import { openGlossary } from "../lib/glossary";
import { sectionDef } from "../routes";
import { SECTION_HELP } from "../routes/sectionHelp";
import { packHelp } from "../routes/packs/registry";

/** 3.3.2.0 R1: Focus, in every section's list: F, or Shift+F where the section's own F follows or fits. */
function focusKey(keys: [string, string][]): [string, string] {
  const taken = keys.some(([k]) => k === "F" || k.startsWith("F "));
  return taken ? ["Shift+F", "Focus: hide the rail, the inspector and the status bar"] : ["F", "Focus: hide the rail, the inspector and the status bar (Shift+F too)"];
}

export function SectionHelp() {
  const help = useStore(studio, (s) => s.help);
  if (!help) return null;
  const def = sectionDef(help.section);
  const copy = SECTION_HELP[def.id] ?? packHelp(def); // 3.2.0.0 R3: a pack's section
  const panels = def.panels.filter((p) => p.about);
  const own: [string, string][] = def.kbd ? [[def.kbd, def.title], ...copy.keys] : copy.keys; // 3.1.6.0 R6: the section's own key from the registry
  const keys: [string, string][] = [...own, focusKey(copy.keys)];
  const footer = (
    <>
      <span className="section-help-note muted">
        Press <Kbd keys="?" /> any time for this page. The full guide: docs/STUDIO.md.
      </span>
      <Button variant="primary" onClick={closeHelp} data-testid="section-help-ok">
        Close
      </Button>
    </>
  );
  return (
    <Dialog
      open
      onClose={closeHelp}
      title={`How ${def.title} works`}
      kicker={`${def.title.toUpperCase()} · ${def.blurb.toUpperCase()}`}
      className="section-help"
      testid="section-help"
      footer={footer}
    >
      <div className="section-help-body">
        <p className="section-help-what">{copy.what}</p>
        <ol className="fl-explain section-help-steps">
          {copy.steps.map(([title, text], i) => (
            <li key={title}>
              <span className="fl-explain-n mono">{i + 1}</span>
              <span>
                <b>{title}</b>
                <span className="fl-explain-text">{text}</span>
              </span>
            </li>
          ))}
        </ol>
        <div className="section-help-terms" aria-label="Words">
          <span className="rail-label mono">WORDS</span>
          {copy.terms.map((w) => (
            <button
              key={w}
              className="og-chip section-help-term"
              data-testid="help-term"
              title={`What "${w}" means (the Glossary)`}
              onClick={() => {
                closeHelp();
                openGlossary(w);
              }}
            >
              {w}
            </button>
          ))}
        </div>
        <div className="section-help-cols">
          {panels.length > 0 && (
          <section aria-label="Panels">
            <div className="rail-label mono">PANELS</div>
            <ul className="section-help-list">
              {panels.map((p) => (
                <li key={p.id}>
                  <b>{p.title}</b>
                  {p.optional ? <span className="badge">palette</span> : null}
                  <span className="muted">{p.about}</span>
                </li>
              ))}
            </ul>
            <p className="section-help-tip muted">
              Click a panel to work in it. Its title bar has one Compact / Expand toggle and a ... menu: Float, Collapse, Reset, Settings, Help.
            </p>
          </section>
          )}
          <section aria-label="Keys">
            <div className="rail-label mono">KEYS</div>
            <ul className="section-help-list section-help-keys">
              {keys.map(([k, text]) => (
                <li key={k}>
                  <Kbd keys={k} />
                  <span className="muted">{text}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </Dialog>
  );
}
