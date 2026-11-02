// Local -> Voice (3.3.9.0 R3; docs/STUDIO-local-voice.md, docs/VOICE.md): talk to a Halo session and hear it answer.
// The speech servers and the catalog (VoiceServers.tsx), Talk with this browser's microphone and the session's own
// loop (VoiceTalk.tsx), the last turns' latency cards, `halo voice stats` and the devices (VoiceTurns.tsx). The page
// reads GET local/voice on open and every 15 s while it shows (voicestore.ts); Talk's `talk` frames come over the
// Studio feed. The glasses note: the phone app is the reader's -- the host's voice door is the contract it talks to.
import { useEffect } from "react";
import { VoiceServers } from "./VoiceServers";
import { VoiceTalk } from "./VoiceTalk";
import { VoiceTurns } from "./VoiceTurns";
import { loadVoice, REFRESH_MS, startVoiceFeed, useVoice } from "./voicestore";

export function VoicePage() {
  const error = useVoice((v) => v.error);
  useEffect(() => {
    void loadVoice(true);
    const off = startVoiceFeed();
    const id = window.setInterval(() => {
      if (!document.hidden) void loadVoice();
    }, REFRESH_MS);
    return () => {
      window.clearInterval(id);
      off();
    };
  }, []);
  return (
    <div className="lc-pool lc-voice" data-testid="local-voice">
      <p className="mono vc-note" data-testid="voice-glasses-note">
        Meta glasses: no phone app ships with Halo. The contract is here -- the halo host's voice door (POST
        /host/v1/voice/turn, docs/VOICE-glasses.md) takes one utterance and streams the reply's audio back; the app that
        carries the glasses' microphone to it is yours to build. `halo voice client --host pc` is its reference.
      </p>
      {error && <p className="mono lc-said" data-testid="voice-error">{error}</p>}
      <VoiceTalk />
      <VoiceServers />
      <VoiceTurns />
    </div>
  );
}
