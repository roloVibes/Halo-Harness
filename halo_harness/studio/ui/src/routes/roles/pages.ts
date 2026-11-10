// 3.3.16.0 R1b: which page the inspector shows. The Lineup tab (and the Assignment tab with no card) opens on the
// lineup's summary; Edit on a row opens that one block (`page`); a selected card opens on its summary and Edit opens
// its slot or its model. `pageFor` says whose page it is (`lineup:<name>`, `card:<id>`), so opening another lineup or
// clicking another card lands on its summary; a tab switch does too (store.setTab). Esc or Back closes the page; a
// draft edit stays in the draft (Save / Revert as before).
import { roles, useRoles } from "./store";

const lineupKey = (name: string) => `lineup:${name}`;
const cardKey = (sel: string) => `card:${sel}`;

/** The lineup block open on its page, or "" (the summary). */
export const useLineupPage = () => useRoles((s) => (s.name && s.pageFor === lineupKey(s.name) ? s.page : ""));

/** The card page open (slot | model), or "" (the card's summary). */
export const useCardPage = () => useRoles((s) => (s.sel && s.pageFor === cardKey(s.sel) ? s.page : ""));

export const openLineupPage = (page: string) => roles.update((s) => ({ page, pageFor: lineupKey(s.name) }));
export const openCardPage = (page: string) => roles.update((s) => ({ page, pageFor: cardKey(s.sel) }));
export const closePage = () => roles.update(() => ({ page: "", pageFor: "" }));
