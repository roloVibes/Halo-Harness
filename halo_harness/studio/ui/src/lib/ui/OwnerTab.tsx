// "Make this tab yours" (3.6.0.6 P, lib/ownerTab.ts): the one sentence and the one button, drawn in the notice row at
// the top of a tab that can only look (from the first draw: lib/owner.ts knows at boot, so nothing moves) and in the one
// toast of a refused write (lib/ui/Toast.tsx). The button reloads the tab for the person's own press only
// (`isTrusted`): a script's click does nothing, and a script's reload would get no proof anyway. 3.6.0.6 PF: the sentence
// is the case's (lib/owner.ts `viewOnly`), read again when the key changes (a new Studio address entered over the tab).
import { useSyncExternalStore, type MouseEvent } from "react";
import { onTokenChange, token } from "../api";
import { viewOnly } from "../owner";
import { MAKE_YOURS, MAKE_YOURS_HOVER, TAB_LINE } from "../ownerTab";
import { Button } from "./Button";

function yours(e: MouseEvent<HTMLButtonElement>): void {
  // reload(true) bypasses the cache: Firefox then sends `Cache-Control: no-cache`, which the server's reload rule takes
  // (its plain reload looks exactly like a link); Chrome, Edge and Safari ignore the argument
  // (tests/test_studio_owner_tab_firefox.py)
  if (e.nativeEvent.isTrusted) (location.reload as (forceGet?: boolean) => void).call(location, true);
}

/** "" when this tab can change things now, else why it can only look; drawn again when the key changes. */
export function useViewOnly(): string {
  return useSyncExternalStore(onTokenChange, () => viewOnly(token()));
}

export function OwnerTabSays() {
  const line = useViewOnly() || TAB_LINE; // a refused write's toast on a tab that thought it could: the link case
  return (
    <>
      <span className="owner-tab-line" data-testid="owner-tab-line">{line}</span>
      <Button size="sm" onClick={yours} title={MAKE_YOURS_HOVER} data-testid="owner-tab-yours">{MAKE_YOURS}</Button>
    </>
  );
}

export function OwnerTabRow() {
  if (!useViewOnly()) return null;
  return (
    <div className="owner-tab-row" role="note" data-testid="owner-tab-row">
      <OwnerTabSays />
    </div>
  );
}
