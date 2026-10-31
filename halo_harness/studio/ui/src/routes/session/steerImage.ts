// The steer's image (3.3.6.0 R6, rolo: "have models visually see them? like from a copy paste into the session"):
// Ctrl+V with an image on the clipboard, or a file dropped on the steer, becomes the chip under the box (its name,
// w x h, size); one image per steer, 5 MB at most (the rule agent/image_attach.py holds). The Screenshot button
// (LiveHead.tsx) puts the harness's own capture there instead. When the session's model cannot see (GET
// sessions/<sid>/eyes), the chip carries the offer's line and its three choices; Send posts
// `fleet/<harness>/<sid>/command {cmd: steer, text, image | image_path, eyes}` -- the session builds the same WIRE
// and LOG blocks the TUI's paste builds, and its log keeps the image's path only (studio/session_eyes_api.py).
import { api } from "../../lib/api";
import { createStore, toast, useStore } from "../../lib/store";
import { sessionCommand } from "../fleet/actions";

export const MAX_BYTES = 5 * 1024 * 1024;
export type EyesChoice = { id: "lane" | "describe" | "send"; label: string; what: string; disabled?: boolean };
export type Offer = { offer: boolean; line: string; choices: EyesChoice[]; sees?: { value: boolean | null; truth?: string | null; source?: string } };
export type SteerImage = { name: string; media_type: string; bytes: number; width?: number | null; height?: number | null;
  data_b64?: string; path?: string; from: "paste" | "drop" | "screenshot" };
type State = { img: SteerImage | null; error: string; offer: Offer | null; eyes: string; sid: string; busy: boolean };

export const steerImage = createStore<State>({ img: null, error: "", offer: null, eyes: "", sid: "", busy: false });
export const useSteerImage = <S,>(pick: (s: State) => S): S => useStore(steerImage, pick);

export function kb(n: number): string {
  return n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`;
}

function dims(url: string): Promise<{ w: number; h: number } | null> {
  return new Promise((done) => {
    const im = new Image();
    im.onload = () => done({ w: im.naturalWidth, h: im.naturalHeight });
    im.onerror = () => done(null);
    im.src = url;
  });
}

function readB64(file: Blob): Promise<string> {
  return new Promise((done, fail) => {
    const r = new FileReader();
    r.onload = () => done(String(r.result || "").split(",", 2)[1] || "");
    r.onerror = () => fail(r.error);
    r.readAsDataURL(file);
  });
}

async function offerFor(sid: string, model: string | null | undefined): Promise<void> {
  if (!model) return;
  try {
    const o = await api.get<Offer>(`sessions/${encodeURIComponent(sid)}/eyes?model=${encodeURIComponent(model)}`);
    const first = o.offer ? o.choices.find((c) => !c.disabled)?.id || "send" : "";
    steerImage.update((s) => (s.sid === sid ? { offer: o, eyes: first } : {}));
  } catch {
    /* the chip works without the offer: the session asks itself */
  }
}

/** A pasted or dropped file: checked (an image, 5 MB at most), read, measured, the chip set. */
export async function takeFile(file: File, sid: string, model: string | null | undefined, from: "paste" | "drop"): Promise<boolean> {
  if (!/^image\/(png|jpeg|gif|webp)$/.test(file.type)) {
    steerImage.update(() => ({ error: `${file.name || "that file"} is not a png, jpeg, gif or webp image` }));
    return false;
  }
  if (file.size > MAX_BYTES) {
    steerImage.update(() => ({ error: `image is ${file.size} bytes, over the 5 MB limit` }));
    return false;
  }
  const data_b64 = await readB64(file);
  const d = await dims(`data:${file.type};base64,${data_b64}`);
  steerImage.update(() => ({ img: { name: file.name || "pasted.png", media_type: file.type, bytes: file.size, width: d?.w, height: d?.h,
                                     data_b64, from }, error: "", offer: null, eyes: "", sid }));
  await offerFor(sid, model);
  return true;
}

/** The first image file a clipboard or a drop carries, if any. */
export function imageFile(items: DataTransfer | null): File | null {
  for (const f of Array.from(items?.files || [])) if (f.type.startsWith("image/")) return f;
  for (const it of Array.from(items?.items || [])) if (it.kind === "file" && it.type.startsWith("image/")) return it.getAsFile();
  return null;
}

/** The Screenshot button: one capture of the harness's own display into the session's images folder. */
export async function takeScreenshot(hid: string, sid: string, model: string | null | undefined): Promise<boolean> {
  steerImage.update(() => ({ busy: true, error: "" }));
  const r = await sessionCommand(hid, sid, "screenshot", { target: "screen" });
  steerImage.update(() => ({ busy: false }));
  const got = r.result as { path?: string; name?: string; width?: number; height?: number; bytes?: number } | undefined;
  if (!r.ok || !got?.path) return false;
  steerImage.update(() => ({ img: { name: got.name || "shot.png", media_type: "image/png", bytes: got.bytes || 0, width: got.width,
                                     height: got.height, path: got.path, from: "screenshot" }, error: "", offer: null, eyes: "", sid }));
  await offerFor(sid, model);
  return true;
}

export function clearImage(): void {
  steerImage.update(() => ({ img: null, error: "", offer: null, eyes: "" }));
}

export function chooseEyes(id: string): void {
  steerImage.update(() => ({ eyes: id }));
}

/** Send the steer with its image to the session (the chip clears on success). */
export async function sendWithImage(hid: string, sid: string, text: string): Promise<boolean> {
  const { img, eyes } = steerImage.get();
  if (!img) return false;
  const image = img.path ? { image_path: img.path } : { image: { media_type: img.media_type, data_b64: img.data_b64, name: img.name } };
  const r = await sessionCommand(hid, sid, "steer", { text, ...image, ...(eyes ? { eyes } : {}) });
  if (r.ok) {
    toast(`Sent with ${img.name}: the session reads it with your steer`, "done");
    clearImage();
  }
  return r.ok;
}
