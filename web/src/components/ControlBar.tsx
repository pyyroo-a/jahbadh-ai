import { useState } from "react";
import type { MatchInfo } from "../api/types";
import { INGEST_LABELS, SLOWDOWN } from "../state/labels";

export type Source =
  | { kind: "replay"; matchId: string; speed: number; fromT: number; seen: number }   // seen: last moment skipped to
  | { kind: "live"; runId: string }
  | { kind: "ingest"; runId: string };

type Props = {
  source: Source;
  info: MatchInfo | null;
  liveMode: boolean;               // the server has live mode switched on
  liveRemaining: number;
  ingestOn: boolean;               // the server takes outside events, so the demo feed can run
  nextMoment: number | null;       // replay: the next moment's time after the clock
  thinking: number;                // moments the desk is working on now
  notice: string | null;           // the last live answer, e.g. the daily-limit line
  onSpeed: (speed: number) => void;
  onSkip: () => void;
  onRunLive: () => void;
  onWatchFeed: () => void;
  onSpotlight: (playerId: string) => void;
  onBackToReplay: () => void;
  children?: React.ReactNode;      // the recap button
};

const SPEEDS = [1, 6, 20];

export default function ControlBar(p: Props) {
  const [player, setPlayer] = useState("");
  const live = p.source.kind === "live";
  return (
    <div className="controlbar">
      <span className="badge">{live ? "Live · the agents are working now"
        : p.source.kind === "ingest" ? INGEST_LABELS.badge : "Replay · precomputed by the real desk"}</span>
      {p.source.kind === "replay" && (
        <>
          <div className="pills" role="group" aria-label="Speed">
            {SPEEDS.map((s) => (
              <button key={s} className={p.source.kind === "replay" && p.source.speed === s ? "pill on" : "pill"}
                onClick={() => p.onSpeed(s)}>{s}x</button>
            ))}
          </div>
          <button className="pill" disabled={p.nextMoment === null} onClick={p.onSkip}>Skip to next moment</button>
          {p.liveMode && (
            <>
              <button className="pill accent" disabled={p.liveRemaining <= 0} onClick={p.onRunLive}>Run a fresh match</button>
              <span className="muted">{p.liveRemaining} live {p.liveRemaining === 1 ? "run" : "runs"} left today</span>
            </>
          )}
          {p.ingestOn && <button className="pill accent" onClick={p.onWatchFeed}>{INGEST_LABELS.button}</button>}
        </>
      )}
      {live && (
        <>
          <button className="pill" onClick={p.onSkip}>Skip to next moment</button>
          {p.info && (
            <>
              <select aria-label="Spotlight a player" value={player} onChange={(e) => setPlayer(e.target.value)}>
                <option value="">Spotlight a player</option>
                {[p.info.home, p.info.away].map((t) => (
                  <optgroup key={t.id} label={t.name}>
                    {[...t.players].sort((a, b) => a.shirt - b.shirt).map((x) => (
                      <option key={x.id} value={x.id}>{x.name} (#{x.shirt})</option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <button className="pill" disabled={!player} onClick={() => p.onSpotlight(player)}>Spotlight a player</button>
            </>
          )}
          <button className="pill" onClick={p.onBackToReplay}>Back to the replay</button>
        </>
      )}
      {p.source.kind === "ingest" && (
        <>
          <span className="muted">{INGEST_LABELS.note}</span>
          <button className="pill" onClick={p.onBackToReplay}>Back to the replay</button>
        </>
      )}
      {p.children}
      {live && p.thinking > 0 && (
        <span className="muted">{SLOWDOWN.controlNote}</span>
      )}
      {p.notice && <span className="muted">{p.notice}</span>}
    </div>
  );
}
