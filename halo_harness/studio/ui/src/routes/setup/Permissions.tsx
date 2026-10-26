// setup-permissions (3.3.0.0 R1): the wizard's four permission modes as radio
// rows, each with its note (init_cli._PERMISSION_MODE_ROWS); Save writes
// `permission_mode` in ~/.halo/config.json, the mode every new session starts
// in (Shift+Tab still cycles it inside a session).
import { BlockFoot, useLoadState, Waiting } from "./BlockFoot";
import { NONE, pick, shownOf, useSetup } from "./store";

export function PermissionsDetail() {
  const { ready, error } = useLoadState();
  const modes = useSetup((s) => s.data?.permission_modes || NONE);
  const shown = useSetup((s) => shownOf(s, "permission_mode"));
  const saved = useSetup((s) => s.data?.permission_mode || "");
  if (!ready) return <Waiting error={error} />;
  return (
    <div className="su-block" data-testid="setup-permissions">
      <p className="su-lead muted">
        The mode every new session starts in. {saved ? <>Saved: <b className="mono">{saved}</b>.</> : "Nothing saved yet: a session reads settings.json's defaultMode, else default."}
      </p>
      <div className="su-radios" role="radiogroup" aria-label="Permission mode">
        {modes.map((m) => (
          <label key={m.id} className="su-radio" data-on={shown === m.id || undefined} data-testid="setup-mode" data-id={m.id}>
            <input type="radio" name="setup-mode" checked={shown === m.id} onChange={() => pick("permission_mode", m.id)} data-testid="setup-mode-input" data-id={m.id} />
            <span className="su-radio-text">
              <span className="su-radio-label mono">{m.label}</span>
              <span className="su-radio-note muted">{m.note}</span>
            </span>
          </label>
        ))}
      </div>
      <BlockFoot block="permission_mode" what="halo config set permission_mode <mode>" />
    </div>
  );
}

export function PermissionsGlance() {
  const saved = useSetup((s) => s.data?.permission_mode || "");
  return (
    <div className="glance">
      <div className="glance-kicker mono">PERMISSIONS</div>
      <div className="glance-text">{saved || "not set"}</div>
      <div className="glance-hint">permission_mode in config.json</div>
    </div>
  );
}
