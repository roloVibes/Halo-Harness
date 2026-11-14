// useBreakpoint() (3.6.0.0 R0a, rule R9): the window's width class. "wide" (1440 and up): a drawer per side;
// "mid" (1100-1439): one drawer at a time, beside the main thing; "narrow" (760-1099): one drawer, floating over the
// main thing with a close; "phone" (under 760): the same, and the rail is a menu (the shell's `data-bp`).
import { useEffect, useState } from "react";
import { BP_MID, BP_PHONE, BP_WIDE } from "./types";

export type Breakpoint = "wide" | "mid" | "narrow" | "phone";

export function breakpointOf(width: number): Breakpoint {
  if (width >= BP_WIDE) return "wide";
  if (width >= BP_MID) return "mid";
  if (width >= BP_PHONE) return "narrow";
  return "phone";
}

const now = () => breakpointOf(typeof window === "undefined" ? BP_WIDE : window.innerWidth);

export function useBreakpoint(): Breakpoint {
  const [bp, setBp] = useState<Breakpoint>(now);
  useEffect(() => {
    const on = () => setBp(now());
    window.addEventListener("resize", on);
    on();
    return () => window.removeEventListener("resize", on);
  }, []);
  return bp;
}

/** Drawers float over the main thing (narrow and phone). */
export const floats = (bp: Breakpoint) => bp === "narrow" || bp === "phone";
