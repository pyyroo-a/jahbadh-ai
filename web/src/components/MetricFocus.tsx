import type { FeedItem, Language, MatchInfo, MatchState, MetricChoice, Persona } from "../api/types";
import { claimText } from "../state/desk";
import { PER_CLUB, formatSeriesValue, metricSeries, seriesLabel } from "../state/personal";
import Sparkline, { type Line } from "./analyst/Sparkline";


type Props = {
  info: MatchInfo;
  choice: MetricChoice;
  states: MatchState[];
  pinned: { item: FeedItem; claimId: string }[];
  persona: Persona;
  language: Language;
  onPick: (momentId: string, claimId: string) => void;
};

export default function MetricFocus({ info, choice, states, pinned, persona, language, onPick }: Props) {
  const lines: Line[] = PER_CLUB.has(choice.key)
    ? [{ label: info.home.name, colour: "var(--home)", points: metricSeries(states, choice.key, info.home.id) },
      { label: info.away.name, colour: "var(--away)", points: metricSeries(states, choice.key, info.away.id) }]
    : [{ label: seriesLabel(choice.key, info), colour: "var(--home)", points: metricSeries(states, choice.key) }];
  return (
    <section className="metric-focus">
      <h3>{choice.label}</h3>
      <div className="stat-row">
        {lines.map((l) => (
          <div key={l.label} className="stat big">
            <b style={{ color: l.colour }}>{formatSeriesValue(choice.key, l.points.at(-1)?.v ?? null)}</b>{l.label}
          </div>
        ))}
      </div>
      <Sparkline lines={lines} />
      {choice.key === "rhythm" && states.at(-1)?.rhythm && (
        <div className="note">Last 10 minutes: {String(states.at(-1)?.rhythm?.data.label)}</div>
      )}
      {choice.key === "pass_difficulty" && <div className="note">Pass difficulty comes from the simulator's pass odds.</div>}
      {!pinned.length && <div className="note">No desk line cites {choice.label} yet.</div>}
      {pinned.map(({ item, claimId }) => {
        const shown = claimText(item, claimId, persona, language);
        return (
          <button key={claimId} className="pinned" dir={shown.dir} onClick={() => onPick(item.moment.id, claimId)}>
            <span className="tag">{item.moment.label}</span>{shown.text}
          </button>
        );
      })}
    </section>
  );
}
