// The line over a form when its file moved on disk (3.2.2.0 R6, disk.ts):
// "<name> changed on disk" with Reload (the file's version, the draft
// dropped) and Keep mine (the draft stays; Save writes it over the file), or
// "<name> was deleted on disk" -- with the draft kept, Keep mine (Save puts
// it back) and Close; with nothing unsaved the form has closed already and
// the line points at the list. Tokens only (styles/disk-note.css).
import { Button } from "../../lib/ui";
import { closeBio, closeLineup, reloadBio, reloadLineup } from "./disk";
import { roles, useRoles, type DiskNote as Note } from "./store";

type Props = {
  note: Note | null;
  /** The name open in the form now ("" when it closed). */
  open: string;
  what: "lineup" | "bio";
  reload: () => void;
  keep: () => void;
  close: () => void;
  testid: string;
};

function Line({ note, open, what, reload, keep, close, testid }: Props) {
  if (!note) return null;
  const still = note.name === open;
  const text = !note.gone
    ? `${note.name} changed on disk: a session or the terminal saved it while you were editing.`
    : still
      ? `${note.name} was deleted on disk. Your edits are still here: Save puts the ${what} back.`
      : `${note.name} was deleted on disk. Pick another ${what} from the list.`;
  return (
    <div className="rdn mono" role="status" data-testid={testid} data-name={note.name} data-gone={note.gone ? "" : undefined}>
      <span className="rdn-text">{text}</span>
      <span className="rdn-acts">
        {!note.gone && (
          <Button size="sm" variant="primary" onClick={reload} data-testid={`${testid}-reload`} title={`Read ${note.name} again from its file (your unsaved edits are dropped)`}>Reload</Button>
        )}
        {(!note.gone || still) && (
          <Button size="sm" variant="ghost" onClick={keep} data-testid={`${testid}-keep`} title="Keep editing your version; Save writes it to the file">Keep mine</Button>
        )}
        {note.gone && (
          <Button size="sm" variant="ghost" onClick={still ? close : keep} data-testid={`${testid}-close`}>{still ? "Close it" : "OK"}</Button>
        )}
      </span>
    </div>
  );
}

/** Over the Inspector; `list`: over the Lineups list, only once the open lineup went (the form closed). */
export function LineupDiskNote({ list }: { list?: boolean }) {
  const note = useRoles((s) => s.diskLineup);
  const open = useRoles((s) => s.name);
  if (list && (!note?.gone || note.name === open)) return null;
  return (
    <Line note={note} open={open} what="lineup" testid={list ? "roles-disk-lineup-list" : "roles-disk-lineup"} reload={() => void reloadLineup()}
          keep={() => roles.update(() => ({ diskLineup: null }))} close={closeLineup} />
  );
}

/** Over the bio form (and the Bios list once the open bio went). */
export function BioDiskNote() {
  const note = useRoles((s) => s.diskBio);
  const open = useRoles((s) => s.bio);
  return (
    <Line note={note} open={open} what="bio" testid="roles-disk-bio" reload={() => void reloadBio()}
          keep={() => roles.update(() => ({ diskBio: null }))} close={closeBio} />
  );
}
