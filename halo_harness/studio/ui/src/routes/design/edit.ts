// Direct text edits (3.0.7.0 R3b). A prototype's current version is framed
// with `?edit=pick` (studio/design_api_edit.py): a double-click on a text in
// it posts `halo-design-pick` with where that text sits. Studio opens its
// own inline editor on the card there (store `editing`); Save reads the
// page's source, changes that one text node (found by its element path and
// node index, or else by its text when that is unique), and posts the page
// to `text-edit`, which saves it as a new version. Esc or Cancel drops it.
import { ApiError } from "../../lib/api";
import { toast } from "../../lib/store";
import { design, fileUrl } from "./store";
import { call, reload } from "./sync";
import type { TextPick } from "./types";

const msg = (e: unknown) => (e instanceof ApiError ? e.problems[0] || e.message : String(e));
const num = (v: unknown) => (typeof v === "number" && isFinite(v) ? v : 0);
let listening = false;

function onMessage(ev: MessageEvent): void {
  const d = ev.data as Record<string, unknown> | null;
  if (!d || d.type !== "halo-design-pick" || !Array.isArray(d.path) || typeof d.text !== "string") return;
  const frames = document.querySelectorAll<HTMLIFrameElement>('[data-testid="design-artboard"] iframe');
  const frame = [...frames].find((f) => f.contentWindow === ev.source);
  const aid = frame?.closest<HTMLElement>('[data-testid="design-artboard"]')?.dataset.id;
  if (!aid || !d.text.trim()) return;
  const pick: TextPick = { aid, path: d.path.map((n) => Math.max(0, Math.floor(num(n)))), node: Math.floor(num(d.node ?? -1)), text: d.text,
                           tag: String(d.tag || "text"), x: num(d.x), y: num(d.y), w: num(d.w), h: num(d.h) };
  design.update(() => ({ editing: pick, sel: aid, pinAt: null, pinOpen: "" }));
}

/** Listen for the frames' double-clicks (once). */
export function listenEdits(): void {
  if (listening) return;
  listening = true;
  window.addEventListener("message", onMessage);
}

export const cancelEdit = () => design.update(() => ({ editing: null }));

function textNodes(root: Node): Text[] {
  const out: Text[] = [];
  const walk = root.ownerDocument!.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) if (!/^(script|style)$/i.test(n.parentNode?.nodeName || "")) out.push(n as Text);
  return out;
}

/** The text node `p` names in the parsed source: by its path, else the one node holding exactly its text. */
export function findText(doc: Document, p: Pick<TextPick, "path" | "node" | "text">): Text | null {
  const want = p.text.trim();
  let el: Element | null = doc.body;
  for (const i of p.path) el = el ? el.children[i] || null : null;
  if (el) {
    const n = p.node >= 0 ? el.childNodes[p.node] : [...el.childNodes].find((c) => c.nodeType === 3 && c.nodeValue?.trim());
    if (n && n.nodeType === 3 && n.nodeValue?.trim() === want) return n as Text;
  }
  const same = doc.body ? textNodes(doc.body).filter((t) => t.nodeValue?.trim() === want) : [];
  return same.length === 1 ? same[0] : null;
}

/** The page `src` with the picked text replaced by `text` (its surrounding spaces kept). */
export function editedPage(src: string, p: Pick<TextPick, "path" | "node" | "text">, text: string): string | null {
  const doc = new DOMParser().parseFromString(src, "text/html");
  const node = findText(doc, p);
  if (!node) return null;
  const v = node.nodeValue || "";
  node.nodeValue = (/^\s*/.exec(v)?.[0] || "") + text.trim() + (/\s*$/.exec(v)?.[0] || "");
  return `<!doctype ${doc.doctype?.name || "html"}>\n` + doc.documentElement.outerHTML;
}

/** Save the open editor's text as a new version of its artboard. */
export async function saveText(text: string): Promise<void> {
  const s = design.get();
  const e = s.editing;
  if (!e) return;
  if (!text.trim() || text.trim() === e.text.trim()) return cancelEdit();
  design.update(() => ({ busy: "text" }));
  try {
    const res = await fetch(fileUrl(s.slug, e.aid, "index.html", 0, Date.now()), { cache: "no-store" });
    if (!res.ok) throw new Error(`could not read ${e.aid}'s page (HTTP ${res.status})`);
    const html = editedPage(await res.text(), e, text);
    if (!html) throw new Error("That text is drawn by the page's own script, not written in its source: change it with a turn instead");
    const r = await call<{ versions: [string, number][] }>("POST", "text-edit", { artboard: e.aid, html });
    const made = (r.versions || []).find(([a]) => a === e.aid);
    design.update((x) => ({ editing: null, bust: { ...x.bust, [e.aid]: (x.bust[e.aid] || 0) + 1 } }));
    toast(made ? `Text saved as ${e.aid} v${made[1]}` : "No text changed", "done");
    await reload();
  } catch (err) {
    toast(msg(err), "error", 6000);
  } finally {
    design.update(() => ({ busy: "" }));
  }
}
