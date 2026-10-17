// design-assets (3.0.7.0 R3): the project's assets/ folder, the files a turn
// is told to use. Add files (a file picker) or drop them on the panel: they
// upload as the classic page did (base64 over `POST assets`) and their path
// goes into the message box. Click a row to put its path there; Download
// saves the file through the /design-files/<slug>/_assets/ route.
import { useRef, useState, type DragEvent } from "react";
import { Button, Empty } from "../../lib/ui";
import { addToDraft, upload } from "./actions";
import { assetUrl, kb, useDesign } from "./store";

const files = (ev: DragEvent) => (ev.dataTransfer && [...ev.dataTransfer.types].includes("Files") ? [...ev.dataTransfer.files] : null);

export function AssetsDetail() {
  const assets = useDesign((s) => s.assets);
  const slug = useDesign((s) => s.slug);
  const busy = useDesign((s) => s.busy === "upload");
  const [over, setOver] = useState(false);
  const pick = useRef<HTMLInputElement>(null);
  if (!slug) return <Empty title="No project open" body="Open a project to add the files its turns may use." />;
  return (
    <div className="das" data-over={over || undefined}
         onDragOver={(e) => files(e) && (e.preventDefault(), setOver(true))}
         onDragLeave={() => setOver(false)}
         onDrop={(e) => {
           setOver(false);
           const fs = files(e);
           if (fs?.length) (e.preventDefault(), void upload(fs));
         }}>
      <div className="das-bar">
        <Button size="sm" disabled={busy} onClick={() => pick.current?.click()} data-testid="design-asset-add">Add files...</Button>
        <span className="muted das-hint">or drop them here</span>
        <input ref={pick} type="file" multiple hidden onChange={(e) => {
          const fs = [...(e.target.files || [])];
          e.target.value = "";
          if (fs.length) void upload(fs);
        }} />
      </div>
      {assets.length ? (
        <ul className="das-list">
          {assets.map((a) => (
            <li key={a.name} className="das-row" data-testid="design-asset">
              <button className="das-pick" onClick={() => addToDraft(`Use ${a.path} `)} title={`Put ${a.path} in the message box`}>
                {a.thumb ? <img src={a.thumb} alt="" /> : <i className="das-kind mono">{a.kind}</i>}
                <span className="das-name">{a.name}</span>
                <small className="mono muted">{kb(a.size)}</small>
              </button>
              <a className="btn btn-ghost btn-sm" href={assetUrl(slug, a.name)} download={a.name} data-testid="design-asset-download">
                <span className="btn-label">Download</span>
              </a>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted das-empty">No assets yet: logos, photos, fonts or captures for the turns to use.</p>
      )}
    </div>
  );
}

export function AssetsGlance() {
  const n = useDesign((s) => s.assets.length);
  return (
    <div className="glance">
      <div className="glance-kicker mono">ASSETS</div>
      <div className="glance-text">{n ? `${n} file${n === 1 ? "" : "s"}` : "none yet"}</div>
    </div>
  );
}
