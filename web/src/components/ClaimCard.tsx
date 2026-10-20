import type { Claim, EventLine, FeedItem, Language, MatchInfo, Persona } from "../api/types";
import { claimText } from "../state/desk";
import { evidenceCount, evidenceOf } from "../state/evidence";
import { figureSegments } from "../state/figures";
import { formatMetric } from "../state/format";
import { NOTES } from "../state/labels";

type Props = {
  item: FeedItem;
  claim: Claim;
  persona: Persona;
  language: Language;
  selected: boolean;
  focus: string | null;           // the mode's badge, e.g. "Your club"
  dimmed: boolean;
  eventsById: Record<number, EventLine>;
  info: MatchInfo | null;
  onSelect: () => void;
  detail?: boolean;               // the Analyst view: figures highlighted and the cited metrics named
};

export default function ClaimCard({ item, claim, persona, language, selected, focus, dimmed, eventsById, info, onSelect, detail }: Props) {
  const shown = claimText(item, claim.id, persona, language);
  const n = evidenceCount(claim);
  const evidence = selected ? evidenceOf(item, claim, eventsById) : null;
  return (
    <div className={["claim", selected && "selected", dimmed && "dimmed"].filter(Boolean).join(" ")} role="button" tabIndex={0} aria-pressed={selected}
      onClick={onSelect} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onSelect())}>
      {focus && <div className="focus-badge">{focus}</div>}
      <p dir={shown.dir}>{detail
        ? figureSegments(shown.text, claim.figures).map((s, i) => s.figure ? <mark key={i} className="figure">{s.text}</mark> : s.text)
        : shown.text}</p>
      {shown.note && NOTES[shown.note] && <div className="note">{NOTES[shown.note]}</div>}
      <div className="ok">✓ Verified by the Referee · {n} evidence {n === 1 ? "item" : "items"}</div>
      {detail && info && claim.metric_ids.length > 0 && (
        <div className="cites">Cites {claim.metric_ids.map((id) => {
          const m = item.metrics.find((x) => x.id === id);
          return m ? formatMetric(m, info).label : id;
        }).join(", ")}</div>
      )}
      {evidence && (
        <div className="evidence">
          <b>Why we can say this</b>
          <div>
            {evidence.events.map((e) => (
              <span key={e.id} className="chip"><span dir={language === "ar" ? "rtl" : "ltr"}>{e.minute}' {e.lines[language]}</span></span>
            ))}
            {evidence.metrics.map((m) => {
              const f = info ? formatMetric(m, info) : null;
              return <span key={m.id} className="chip metric">{f ? `${f.label} ${f.value}` : m.name}</span>;
            })}
          </div>
        </div>
      )}
    </div>
  );
}
