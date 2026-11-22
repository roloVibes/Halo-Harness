// What Up / Down do in the Prompt panel's box (3.6.0.11, the owner: "The up button should bring you to the start of
// your prompt. If it's long I'm over holding done the left button"): the terminal's rule 1:1 (tui/widgets/input.py
// action_cursor_up / action_cursor_down, app.py history_walking). Up: not on the first line, the browser's own move; on
// the first line with the caret not at 0, the caret goes to 0 and nothing is recalled; at 0 (an empty box is at 0),
// the older sent prompt. While a recalled prompt stands untouched with the caret at its end, Up on the first line
// recalls the next older one at once. Down is the mirror: the browser's own move, then to the very end, then the newer
// prompt. Pure (node-tested).

export type ArrowMove = "native" | "start" | "end" | "older" | "newer";

/** `walking`: the box shows the prompt Up / Down recalled, untouched, the caret at its end (`isWalking`). */
export function arrowMove(key: string, text: string, start: number, end: number, walking: boolean): ArrowMove {
  if (key === "ArrowUp") {
    if (text.slice(0, start).includes("\n")) return "native";
    return walking || (start === 0 && end === 0) ? "older" : "start";
  }
  if (text.slice(end).includes("\n")) return "native";
  return walking || (start === text.length && end === text.length) ? "newer" : "end";
}

/** Does the box show `recalled` untouched with the caret at its end? */
export const isWalking = (text: string, start: number, end: number, recalled: string | undefined): boolean =>
  recalled !== undefined && text === recalled && start === text.length && end === text.length;
