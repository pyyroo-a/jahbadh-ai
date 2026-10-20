import type { Language, MatchInfo, OverlayCue } from "../api/types";

type ToggleProps = { on: boolean; onToggle: () => void; feedUrl: string | null };

/** The switch for the preview, plus the raw feed a graphics system would read. */
export default function OverlayPreview({ on, onToggle, feedUrl }: ToggleProps) {
  return (
    <div className="overlay-controls">
      <button className={on ? "pill on" : "pill"} aria-pressed={on} onClick={onToggle}>Broadcast overlay preview</button>
      {feedUrl && <a className="link" href={feedUrl} target="_blank" rel="noreferrer">Overlay feed (JSON)</a>}
    </div>
  );
}

type ThirdsProps = { cues: OverlayCue[]; language: Language; info: MatchInfo };

/** The cues on air right now, drawn as lower-thirds over the pitch. */
export function LowerThirds({ cues, language, info }: ThirdsProps) {
  return (
    <div className="lower-thirds" aria-live="polite">
      {cues.map((c) => (
        <div key={c.id} className="lower-third"
          style={{ borderColor: c.team_id === info.away.id ? "var(--away)" : c.team_id ? "var(--home)" : "var(--amber)" }}>
          <span className="lower-third-minute">{c.minute}'</span>
          <span dir={language === "ar" ? "rtl" : "ltr"}>{c.text[language]}</span>
          {c.synthetic && <span className="lower-third-tag">Simulated</span>}
        </div>
      ))}
    </div>
  );
}
