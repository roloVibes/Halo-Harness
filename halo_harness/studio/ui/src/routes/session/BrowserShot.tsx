// 3.6.0.6 W: the page's picture in a Browser step's detail (the click, not the hover; Live's rows and Agents -> Live
// share ToolRow). Fetched with the token header from the one read-only route for the session's own attachments, shown
// at the detail's width in its own shape (the room is the browser's 1280 x 800 until the picture says its own); a
// click on it opens it whole in a tab of its own. Studio's page allows pictures from itself and data: only (server.py
// SHELL_CSP), so the picture is shown as data:; the tab that opens it whole takes a blob: address of its own.
import { useEffect, useState } from "react";
import { token } from "../../lib/api";
import { picRoute } from "./browserPic";

type Got = { url: string; src: string; bytes: number; type: string; w: number; h: number } | { error: string } | null;

export function BrowserShot({ path }: { path: string }) {
  const [got, setGot] = useState<Got>(null);
  useEffect(() => {
    let url = "";
    let gone = false;
    fetch(new URL(picRoute(path), location.origin + "/"), { headers: { Authorization: "Bearer " + token() } })
      .then(async (res) => {
        if (!res.ok) throw new Error(`${res.status}`);
        const blob = await res.blob();
        const src = await new Promise<string>((ok, bad) => {
          const r = new FileReader();
          r.onload = () => ok(String(r.result || ""));
          r.onerror = () => bad(r.error);
          r.readAsDataURL(blob);
        });
        url = URL.createObjectURL(blob);
        if (gone) URL.revokeObjectURL(url);
        else setGot({ url, src, bytes: blob.size, type: blob.type, w: 0, h: 0 });
      })
      .catch((e) => !gone && setGot({ error: String(e?.message || e) }));
    return () => {
      gone = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [path]);
  if (got && "error" in got) return null;  // a picture since removed (the newest 20 are kept): the text is the detail
  const ok = got && "url" in got ? got : null;
  return (
    <div className="slv-shot" style={{ aspectRatio: ok && ok.w ? `${ok.w} / ${ok.h}` : "1280 / 800" }}>
      {ok && (
        <img src={ok.src} alt="the page as it showed after this step" data-testid="session-live-shot" data-bytes={ok.bytes} data-type={ok.type}
             title="Open the picture whole" onClick={() => window.open(ok.url, "_blank")}
             onLoad={(e) => setGot({ ...ok, w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })} />
      )}
    </div>
  );
}
