// A goal's build-up as a TV-style replay: the arrows draw one after another, the step list lights up in time,
// and the finished move holds for a moment. The server picked the steps; this only draws them, with CSS.

import type { CSSProperties } from "react";
import type { EventLine, Language, MatchInfo } from "../api/types";
import type { ReplayStep } from "../pitch/layers";
import { HOLD_MS } from "../state/goals";
import { GOAL_LABELS } from "../state/labels";

const at = (i: number, ms: number): CSSProperties => ({ animationDelay: `${i * ms}ms`, animationDuration: `${ms}ms` });
const side = (info: MatchInfo, team: string) => (team === info.home.id ? "home" : "away");

/** The arrows, drawn inside the pitch's SVG. */
export function ReplayDrawing({ steps, info, ms }: { steps: ReplayStep[]; info: MatchInfo; ms: number }) {
  return (
    <g className="replay">
      {steps.map((s, i) => {
        const team = side(info, s.team);
        return (
          <g key={s.id} className="replay-step" style={at(i, ms)}>
            {s.kind === "point"
              ? <circle cx={s.x1} cy={s.y1} r={0.9} className={`replay-point ${team}`} />
              : <line x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} pathLength={1} style={at(i, ms)}
                  className={`replay-${s.kind} ${team}`} markerEnd={`url(#replay-${s.kind === "shot" ? "shot" : team})`} />}
            {s.kind === "shot" && <circle cx={s.x1} cy={s.y1} r={0.7} className="replay-shot-spot" />}
            {s.shirt && (
              <g>
                <circle cx={s.x1} cy={s.y1} r={1.5} className={`replay-who ${team}`} />
                <text x={s.x1} y={s.y1 + 0.6} className="replay-who-label">{s.shirt}</text>
              </g>
            )}
          </g>
        );
      })}
    </g>
  );
}

type StepsProps = { steps: EventLine[]; language: Language; ms: number; note?: string | null; onDone: () => void };

/** The numbered steps under the pitch. A hidden hold element ends after the last step plus HOLD_MS. */
export function ReplaySteps({ steps, language, ms, note, onDone }: StepsProps) {
  return (
    <div className="replay-list">
      {note && <div className="note">{note}</div>}
      <ol className="replay-steps">
        {steps.map((s, i) => (
          <li key={s.id} style={at(i, ms)}>
            <b>{i + 1}</b> <span dir={language === "ar" ? "rtl" : "ltr"}>{s.lines[language]}</span>
          </li>
        ))}
      </ol>
      {steps.length === 1 && <div className="note">{GOAL_LABELS.noBuildUp}</div>}
      <span className="replay-hold" aria-hidden="true" style={{ animationDuration: `${steps.length * ms + HOLD_MS}ms` }}
        onAnimationEnd={onDone} />
    </div>
  );
}
