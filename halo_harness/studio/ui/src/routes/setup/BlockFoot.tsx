// The foot every Setup block ends with (3.3.0.0 R1): Save and Revert, the
// block's own line ("saved", "1 changed" or "problem") and, under them, the
// lines its last Save answered (what was written, or why nothing was).
import { Button } from "../../lib/ui";
import { blockWord, changed, revert, save, useSetup, type BlockId } from "./store";

export function BlockFoot({ block, label = "Save", what }: { block: BlockId; label?: string; what: string }) {
  const busy = useSetup((s) => s.busy);
  const dirty = useSetup((s) => changed(s, block));
  const word = useSetup((s) => blockWord(s, block));
  const last = useSetup((s) => s.last[block]);
  return (
    <div className="su-foot" data-testid="setup-foot" data-block={block}>
      <div className="su-foot-row">
        <Button variant="primary" size="sm" disabled={!!busy || !dirty} onClick={() => void save(block)} title={what} data-testid="setup-save" data-block={block}>
          {busy === block ? "Saving..." : label}
        </Button>
        <Button variant="ghost" size="sm" disabled={!!busy || !dirty} onClick={() => revert(block)} data-testid="setup-revert" data-block={block}>
          Revert
        </Button>
        <span className="su-word mono" data-word={word} data-testid="setup-word" data-block={block}>
          {word}
        </span>
      </div>
      {last && last.lines.length > 0 && (
        <pre className="su-lines mono" data-ok={last.ok || undefined} data-testid="setup-lines" data-block={block}>
          {last.lines.join("\n")}
        </pre>
      )}
    </div>
  );
}

/** A block's body until the state arrives, or when it could not be read. */
export function useLoadState(): { ready: boolean; error: string } {
  const loaded = useSetup((s) => s.loaded);
  const data = useSetup((s) => !!s.data);
  const error = useSetup((s) => s.error);
  return { ready: loaded && data, error };
}

export function Waiting({ error }: { error: string }) {
  return error ? (
    <p className="su-error" data-testid="setup-error">
      Studio could not read the setup: {error}
    </p>
  ) : (
    <div className="og-wait mono muted">reading the setup...</div>
  );
}
