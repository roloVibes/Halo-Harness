// Buttons: primary (the one obvious action), default, ghost, danger. An
// optional `kbd` shows its shortcut inside the button.
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Kbd } from "./Kbd";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "default" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  kbd?: string;
  icon?: ReactNode;
};

export function Button({ variant = "default", size = "md", kbd, icon, className, children, type, ...rest }: Props) {
  return (
    <button type={type ?? "button"} className={`btn btn-${variant} btn-${size}${className ? " " + className : ""}`} {...rest}>
      {icon}
      {children && <span className="btn-label">{children}</span>}
      {kbd && <Kbd keys={kbd} className="btn-kbd" />}
    </button>
  );
}
