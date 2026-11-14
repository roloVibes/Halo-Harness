// The session's todo plan on the lit Map (3.6.0.0 R4b, R4's gap 3): the list main keeps with its TodoWrite tool arrives
// on the live feed as a `todos` frame (tools/todowrite.py; studio/feed_kinds.py asks for it) -- kept here per session,
// the newest list main sent. The top line says "plan: 3 of 7 done"; the drawer lists it. Live's plan under the tree
// (the lineup's blocks) is not this and is not carried over.
import { onEvent, type FeedFrame } from "../../../lib/events";
import { createStore, useStore } from "../../../lib/store";

export type Todo = { content: string; status: string; activeForm?: string };
export const todos = createStore<{ by: Record<string, Todo[]> }>({ by: {} });
export const useTodos = (sid: string): Todo[] | undefined => useStore(todos, (s) => (sid ? s.by[sid] : undefined));

function take(f: FeedFrame): void {
  const sid = f.session_id || "";
  const list = (f.data || {}).todos;
  if (!sid || !Array.isArray(list) || (f.agent_id && f.agent_id !== "main")) return; // main's plan, not a helper's
  const clean = list.filter((t): t is Todo => !!t && typeof (t as Todo).content === "string")
    .map((t) => ({ content: String(t.content), status: String(t.status || "pending"), activeForm: t.activeForm ? String(t.activeForm) : undefined }));
  todos.update((s) => ({ by: { ...s.by, [sid]: clean } }));
}

let bound = false;
export function startTodos(): void {
  if (bound) return;
  bound = true;
  onEvent("todos", take);
}

/** "plan: 3 of 7 done" ("" with no plan). */
export function planWords(list: Todo[] | undefined): string {
  if (!list || !list.length) return "";
  return `plan: ${list.filter((t) => t.status === "completed").length} of ${list.length} done`;
}
