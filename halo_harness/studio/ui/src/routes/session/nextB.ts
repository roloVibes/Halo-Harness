// R4: {B}, the map new sessions use, for the words shown while no session is open (the Start view, the Live drawer's
// Empty). With no session open no row carries it and a row heard earlier may be stale, so it is the server's: one read of
// GET crew/maps (`next`) after the first draw (R28: nothing is fetched before it) and again whenever a map or config file
// moves (Agents -> Map's "New sessions run on", a Builder card, `halo config set crew.map` in a terminal). Undefined
// until the first read answers (the words' room is held, never a {B} that may be false); a read that fails keeps what
// was read before, else what this page last heard (pick.ts knownNext), else none set.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { onFilesChanged } from "../../lib/filesLive";
import { knownNext } from "./pick";

export function useNextB(): string | null | undefined {
  const [b, setB] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    const read = () => void api.get<{ next?: string | null }>("crew/maps").then(
      (d) => live && setB(d.next || null),
      () => live && setB((was) => (was !== undefined ? was : knownNext()?.b ?? null)));
    read();
    const off = onFilesChanged(["maps", "config"], read);
    return () => {
      live = false;
      off();
    };
  }, []);
  return b;
}
