// A keyboard hint: "Ctrl+K" renders as two keys. On a Mac, Ctrl reads as Cmd.
const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || "");

export function keyLabel(k: string): string {
  if (k === "Mod") return isMac ? "⌘" : "Ctrl";
  if (k === "Alt" && isMac) return "⌥";
  if (k === "Shift" && isMac) return "⇧";
  return k;
}

export function Kbd({ keys, className }: { keys: string; className?: string }) {
  const parts = keys.split("+").map((k) => keyLabel(k.trim()));
  return (
    <span className={"kbd-group" + (className ? " " + className : "")} aria-label={parts.join(" ")}>
      {parts.map((p, i) => (
        <kbd key={i} className="kbd">
          {p}
        </kbd>
      ))}
    </span>
  );
}
