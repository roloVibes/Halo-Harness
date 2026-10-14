// Orchestra: the placeholder this round (R4 fills it). Its panels show the
// workspace pattern R4 builds on: the placeholder (idle breathing), the live
// feed and the attached sessions, each with a Glance and an Expand face.
import { Button, Empty, Kbd } from "../../lib/ui";
import { goSection, studio, useStore } from "../../lib/store";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { FeedDetail, FeedGlance, SessionsDetail, SessionsGlance, useFeedMotion, useSessionsMotion } from "./FeedPanels";

function Placeholder() {
  const sessions = useStore(studio, (s) => s.feed.sessions.length);
  return (
    <Empty
      icon={<span className="orbit" aria-hidden="true" />}
      title="Orchestra arrives in R4"
      body={
        <>
          The run board for your agents lands here: lanes, claims, the live run grid and the report.{" "}
          {sessions ? `${sessions} live session${sessions === 1 ? "" : "s"} already feed it.` : "Live sessions will feed it."} Until then,
          build a lineup in Roles.
        </>
      }
      action={
        <Button variant="primary" size="lg" onClick={() => goSection("roles")} kbd="Alt+2">
          Open Roles
        </Button>
      }
    />
  );
}

function PlaceholderSettings() {
  return (
    <p className="muted">
      Nothing to set yet. Press <Kbd keys="Mod+K" /> for every command.
    </p>
  );
}

const idle = (): MotionState => "idle";

export const orchestraPanels: PanelSpec[] = [
  {
    id: "board",
    title: "Orchestra",
    x: 0,
    y: 0,
    w: 16,
    h: 0,
    minW: 8,
    minH: 24,
    glance: Placeholder,
    settings: PlaceholderSettings,
    useMotion: idle,
    testid: "orchestra-root",
  },
  {
    id: "feed",
    title: "Live feed",
    x: 16,
    y: 0,
    w: 8,
    h: 30,
    glance: FeedGlance,
    detail: FeedDetail,
    useMotion: useFeedMotion,
  },
  {
    id: "sessions",
    title: "Sessions",
    x: 16,
    y: 30,
    w: 8,
    h: 26,
    glance: SessionsGlance,
    detail: SessionsDetail,
    useMotion: useSessionsMotion,
  },
];

export function Orchestra() {
  return <Placeholder />;
}
