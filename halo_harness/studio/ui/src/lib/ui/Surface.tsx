// A static surface in the panel frame's look (the Inspector, dialogs, the
// palette): 3.3.15.0 L1, the Instrument look -- solid `surface`, a 1 px hairline,
// the panel radius, no shadow, and the four corner ticks (10 x 1 px in the
// accent at the top left and the bottom right, drawn by `.glass` in
// styles/base.css); the `.hud-brackets` child turns them to the text colour
// where the frame is the selected one. The workspace panel's three faces
// (glance, detail, strip) are lib/workspace/Panel.tsx's.
import type { HTMLAttributes, ReactNode } from "react";
import type { MotionState } from "../motion";
type Props = HTMLAttributes<HTMLDivElement> & { motion?: MotionState; children?: ReactNode };
export function Surface({ motion = "none", className, children, ...rest }: Props) {
  return (
    <div className={"glass surface" + (className ? " " + className : "")} data-motion={motion} {...rest}>
      <span className="hud-brackets" aria-hidden="true" />
      {children}
    </div>
  );
}
