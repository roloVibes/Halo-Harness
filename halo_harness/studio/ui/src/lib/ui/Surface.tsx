// A static glass surface with HUD corner brackets (the look of a workspace
// panel, for things that do not move: the Inspector, dialogs, the palette).
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
