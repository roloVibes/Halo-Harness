// When the Live column follows its newest row (3.3.0.0 R6, the owner: "that
// scroller in the session tab can lose where you were steering in real
// time"). It follows unless you scrolled up or the Steer field has the
// keyboard (`composing`); then new rows append below without moving the view
// and the pill counts them ("N new rows · follow"; a click, or Escape out of
// the field, follows again). The target row is scrolled into view once when
// you choose it, and while a target you chose is held, following never
// pushes its row out of view: the column stops there instead (until you
// follow again: the pill, Escape out of the field, Follow or a scroll to
// the newest row let it go).
import { useLayoutEffect, type RefObject } from "react";
import type { LiveLine } from "../shared/liveFeed";
import { followAgain, pauseFollow } from "./steer";
import { sess, useSession } from "./store";

export type Follow = { following: boolean; fresh: number; onScroll: () => void };

export function useFollow(scroller: RefObject<HTMLDivElement | null>, shown: LiveLine[]): Follow {
  const follow = useSession((s) => s.follow);
  const composing = useSession((s) => s.composing);
  const holding = useSession((s) => s.hold);
  const chosenAt = useSession((s) => s.chosenAt);
  const pausedAt = useSession((s) => s.pausedAt);
  const following = follow && !composing;
  useLayoutEffect(() => {
    const el = scroller.current;
    if (!el || !following) return;
    el.scrollTop = el.scrollHeight;
    const row = holding ? el.querySelector<HTMLElement>("[data-target]") : null;
    if (!row) return;
    const top = row.getBoundingClientRect().top - el.getBoundingClientRect().top;
    if (top < 0) {
      el.scrollTop += top - 8;
      pauseFollow();
    }
  }, [shown, following, holding, scroller]);
  useLayoutEffect(() => {
    if (chosenAt) scroller.current?.querySelector<HTMLElement>("[data-target]")?.scrollIntoView({ block: "nearest" });
  }, [chosenAt, scroller]);
  const onScroll = () => {
    const el = scroller.current;
    if (!el) return;
    const bottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    if (!bottom && follow) pauseFollow();
    else if (bottom && !follow && !sess.get().composing) followAgain(); // you scrolled to the newest row yourself
  };
  return { following, fresh: following ? 0 : shown.filter((l) => l.n > pausedAt).length, onScroll };
}
