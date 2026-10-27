// The command palette (Ctrl/Cmd+K): a centered glass box with a mono prompt,
// fuzzy matches grouped by kind, keyboard-first (arrows, Enter, Esc).
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Kbd, Surface } from "../lib/ui";
import { studio, useStore } from "../lib/store";
import { commands, fuzzy, type Command } from "./commands";
import { sections } from "../routes";
import { packGroups } from "../routes/packs/registry";
import { packs } from "../routes/packs/store";

// 3.1.6.0 R6: the section groups in the registry's order (before, Roles, Design and Team sorted above Go to);
// 3.2.0.0 R3: the packs' groups after the sections'
const groupOrder = () => ["Go to", "Help", ...sections().map((s) => s.title), ...packGroups(packs.get().reg), "Media", "View", "Layout", "Open"];

export function Palette() {
  const open = useStore(studio, (s) => s.paletteOpen);
  const section = useStore(studio, (s) => s.section);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const close = () => studio.update(() => ({ paletteOpen: false }));

  const matches = useMemo(() => {
    if (!open) return [] as Command[];
    const order = groupOrder();
    const scored = commands()
      .map((c) => ({ c, s: Math.max(fuzzy(q, c.label), fuzzy(q, c.group + " " + c.label) - 1) }))
      .filter((x) => x.s >= 0);
    if (q.trim()) scored.sort((a, b) => b.s - a.s);
    else scored.sort((a, b) => order.indexOf(a.c.group) - order.indexOf(b.c.group));
    return scored.map((x) => x.c);
  }, [open, q, section]);

  useEffect(() => {
    if (open) {
      setQ("");
      setSel(0);
      window.setTimeout(() => input.current?.focus(), 0);
    }
  }, [open]);
  useEffect(() => setSel(0), [q]);
  useEffect(() => {
    list.current?.querySelector<HTMLElement>(`[data-index="${sel}"]`)?.scrollIntoView({ block: "nearest" });
  }, [sel]);

  if (!open) return null;
  const run = (c?: Command) => {
    if (!c || c.disabled) return; // 3.3.2.0 R2: a disabled entry's hint says why; Enter leaves the palette open
    close();
    c.run();
  };
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowDown") setSel((n) => Math.min(matches.length - 1, n + 1));
    else if (e.key === "ArrowUp") setSel((n) => Math.max(0, n - 1));
    else if (e.key === "Enter") run(matches[sel]);
    else if (e.key === "Escape") close();
    else return;
    e.preventDefault();
  };

  // grouped in display order, keeping one running index for keyboard selection
  const groups: { name: string; items: { c: Command; i: number }[] }[] = [];
  matches.forEach((c, i) => {
    let g = groups.find((x) => x.name === c.group);
    if (!g) groups.push((g = { name: c.group, items: [] }));
    g.items.push({ c, i });
  });

  return (
    <div className="scrim scrim-top" onPointerDown={(e) => e.target === e.currentTarget && close()}>
      <div className="palette" role="dialog" aria-modal="true" aria-label="Command palette" data-testid="palette">
        <Surface className="palette-surface">
          <div className="palette-prompt">
            <span className="palette-caret mono" aria-hidden="true">
              &gt;
            </span>
            <input
              ref={input}
              className="palette-input mono"
              placeholder="Type a command or a section"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={onKey}
              aria-label="Command"
              aria-controls="palette-list"
              aria-activedescendant={matches[sel] ? "cmd-" + matches[sel].id : undefined}
            />
            <Kbd keys="Esc" />
          </div>
          <div className="palette-list" id="palette-list" role="listbox" ref={list}>
            {groups.map((g) => (
              <div key={g.name} className="palette-group" role="group" aria-label={g.name}>
                <div className="palette-group-name mono">{g.name.toUpperCase()}</div>
                {g.items.map(({ c, i }) => (
                  <div
                    key={c.id}
                    id={"cmd-" + c.id}
                    role="option"
                    aria-selected={i === sel}
                    aria-disabled={c.disabled || undefined}
                    data-index={i}
                    className={"palette-item" + (i === sel ? " on" : "")}
                    onPointerMove={() => setSel(i)}
                    onClick={() => run(c)}
                  >
                    <span className="palette-label">{c.label}</span>
                    {c.hint && <span className="palette-hint">{c.hint}</span>}
                    {c.kbd && <Kbd keys={c.kbd} />}
                  </div>
                ))}
              </div>
            ))}
            {!matches.length && <div className="palette-none">Nothing matches "{q}".</div>}
          </div>
        </Surface>
      </div>
    </div>
  );
}
