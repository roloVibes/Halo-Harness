// 3.6.0.25 G: an agent of a Claude Code session Halo only shows (kind `guest`), as every card draws it: its cost reads
// "not known" (Claude Code keeps its own count and Halo does not read it), and the card's controls are off with the
// watch-only line as their title. Pure: node runs it in the tests (tests/test_studio_prompt_words.py).
import { cost } from "../orchestra/format";
import { GUEST_LINE, isGuest, NOT_KNOWN } from "../session/promptWords";

type Kinded = { kind?: string | null } | null | undefined;

/** An agent's cost on a card: "not known" in a Claude Code session, else its figure. */
export const agentCost = (session: Kinded, usd: number | null | undefined): string => (isGuest(session) ? NOT_KNOWN : cost(usd));

/** Why a card's controls are off in a Claude Code session (their title), else undefined. */
export const watchWhy = (session: Kinded): string | undefined => (isGuest(session) ? GUEST_LINE : undefined);
