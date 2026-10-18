import type { Claim, EventLine, FeedItem, Language, Persona } from "../api/types";
import { claimText } from "../state/desk";
import { evidenceCount, evidenceOf } from "../state/evidence";
import { NOTES } from "../state/labels";

type Props = {
  item: FeedItem;
  claim: Claim;
  persona: Persona;
  language: Language;
  selected: boolean;
  eventsById: Record<number, EventLine>;
  onSelect: () => void;
};

export default function ClaimCard({ item, claim, persona, language, selected, eventsById, onSelect }: Props) {
  const shown = claimText(item, claim.id, persona, language);
  const n = evidenceCount(claim);
  const evidence = selected ? evidenceOf(item, claim, eventsById) : null;
  return (
    <div className={selected ? "claim selected" : "claim"} role="button" tabIndex={0} aria-pressed={selected}
      onClick={onSelect} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onSelect())}>
      <p dir={shown.dir}>{shown.text}</p>
      {shown.note && NOTES[shown.note] && <div className="note">{NOTES[shown.note]}</div>}
      <div className="ok">✓ Verified by the Referee · {n} evidence {n === 1 ? "item" : "items"}</div>
      {evidence && (
        <div className="evidence">
          <b>Why we can say this</b>
          <div>
            {evidence.events.map((e) => (
              <span key={e.id} className="chip"><span dir={language === "ar" ? "rtl" : "ltr"}>{e.minute}' {e.lines[language]}</span></span>
            ))}
            {evidence.metrics.map((m) => <span key={m.id} className="chip metric">{m.name.replaceAll("_", " ")}</span>)}
          </div>
        </div>
      )}
    </div>
  );
}
