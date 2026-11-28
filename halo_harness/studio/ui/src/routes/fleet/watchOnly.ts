// 3.6.0.25 G: an agent of a Claude Code session Halo only shows (kind `guest`), as every card draws it: its cost reads
// "not known" (Claude Code keeps its own count and Halo does not read it), and the card's controls are off with the
// watch-only line as their title. 3.6.0.26 H: a hand-out worker's row (agent kind `halo-worker`) is Halo's own: its
// numbers show and its Stop works (it stops that job); its other controls stay off. Pure: node runs it in the tests
// (tests/test_studio_prompt_words.py).
import { cost, short } from "../orchestra/format";
import { GUEST_LINE, isGuest, NOT_KNOWN } from "../session/promptWords";

type Kinded = { kind?: string | null } | null | undefined;

export const WORKER_LINE = "a hand-out takes Stop only: Halo runs it for this Claude Code session";

/** A hand-out worker's row in a Claude Code session (guest/hand_out.py): Halo runs it. */
export const isWorker = (agent: Kinded): boolean => String(agent?.kind || "") === "halo-worker";

/** An agent's cost on a card: "not known" in a Claude Code session (a worker's own figure shows), else its figure. */
export const agentCost = (session: Kinded, usd: number | null | undefined, agent?: Kinded): string =>
  isGuest(session) && !isWorker(agent) ? NOT_KNOWN : cost(usd);

/** Why a card's controls are off in a Claude Code session (their title), else undefined. */
export const watchWhy = (session: Kinded, agent?: Kinded): string | undefined =>
  !isGuest(session) ? undefined : isWorker(agent) ? WORKER_LINE : GUEST_LINE;

/** Why a card's Stop is off: a worker's Stop works; every other agent of a Claude Code session is watch only. */
export const stopWhy = (session: Kinded, agent?: Kinded): string | undefined => (isWorker(agent) ? undefined : watchWhy(session));

/** The pinned stream's meta line: the agent's state, its cost (agentCost), its harness's name cut to 16. */
export const pipMeta = (session: Kinded, state: string | null | undefined, usd: number | null | undefined,
                        harness: string | null | undefined, agent?: Kinded): string =>
  `${state ?? ""} · ${agentCost(session, usd, agent)} · ${short(harness || "", 16)}`;
