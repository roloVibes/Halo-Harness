// A header menu's open state (Header.tsx, ThemeMenu.tsx): closes on Esc and on a press outside its box.
import { useEffect, useRef, useState } from "react";

export function useMenu() {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const off = (e: Event) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !box.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("pointerdown", off);
    window.addEventListener("keydown", off);
    return () => {
      window.removeEventListener("pointerdown", off);
      window.removeEventListener("keydown", off);
    };
  }, [open]);
  return { open, setOpen, box };
}
