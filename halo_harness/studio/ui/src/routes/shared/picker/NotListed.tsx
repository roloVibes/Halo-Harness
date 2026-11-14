// The picker's last row, always (3.4.1.3): "use a reference that is not listed". It opens a small field with the
// format hint and checks what is typed as it is typed (GET models/check: the session's own route parser, no
// network); a prefix Halo does not know says which ones exist. Use it (or Enter) only once the parser accepts it.
import { useEffect, useRef, useState } from "react";
import { api } from "../../../lib/api";
import { Button } from "../../../lib/ui";

type Check = { ok: boolean; ref: string; line: string; prefixes: string[] };

export function NotListed({ tid, onPick, seed, open, setOpen }: {
  tid: string; onPick: (ref: string) => void; seed: string; open: boolean; setOpen: (v: boolean) => void;
}) {
  const [text, setText] = useState("");
  const [check, setCheck] = useState<Check | null>(null);
  const box = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!open) return;
    setText((t) => t || seed);
    window.setTimeout(() => box.current?.focus({ preventScroll: true }), 0);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps -- the seed is read once, when it opens
  useEffect(() => {
    const ref = text.trim();
    if (!open || !ref) {
      setCheck(null);
      return undefined;
    }
    let live = true;
    const t = window.setTimeout(() => {
      api.get<Check>(`models/check?ref=${encodeURIComponent(ref)}`).then(
        (c) => live && setCheck(c),
        (e) => live && setCheck({ ok: false, ref, line: e instanceof Error ? e.message : String(e), prefixes: [] }),
      );
    }, 200);
    return () => {
      live = false;
      window.clearTimeout(t);
    };
  }, [text, open]);
  const ok = !!check?.ok && check.ref === text.trim();
  const use = () => ok && (onPick(text.trim()), setText(""), setOpen(false));
  if (!open) {
    return (
      <button type="button" className="mpk-notlisted og-link mono" onClick={() => setOpen(true)} data-testid={`${tid}-not-listed`}
              title="For the rare model the catalog lacks: type its reference; Halo checks it as you type">
        use a reference that is not listed...
      </button>
    );
  }
  return (
    <div className="mpk-typed" data-testid={`${tid}-typed-box`}>
      <div className="mpk-typed-row">
        <input ref={box} className="input mono" value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} autoComplete="off"
               onKeyDown={(e) => {
                 if (e.key === "Enter") (e.preventDefault(), use());
                 if (e.key === "Escape") (e.preventDefault(), e.stopPropagation(), setOpen(false));
               }}
               placeholder="or:vendor/model · ol:name:tag · dbx:endpoint" aria-label="A reference that is not listed" data-testid={`${tid}-typed`} />
        <Button size="sm" disabled={!ok} onClick={use} data-testid={`${tid}-typed-use`}>Use it</Button>
        <button type="button" className="og-link mono" onClick={() => setOpen(false)}>cancel</button>
      </div>
      <div className="mpk-typed-line mono" data-ok={check ? check.ok || undefined : undefined} data-testid={`${tid}-typed-check`}>
        {!text.trim() ? "the prefix says the provider: or: dbx: ant: oai: ol: hf: xp: cp: local:" : !check ? "checking..." : check.line}
      </div>
    </div>
  );
}
