import { useState } from "react";
import type { FeedItem, Language, Persona } from "../api/types";
import { claimText } from "../state/desk";
import { type Mode, recapOrder } from "../state/personal";

type Props = {
  items: FeedItem[];
  mode: Mode;
  persona: Persona;
  language: Language;
  onPick: (momentId: string, claimId: string) => void;
};

function Lines({ item, persona, language, onPick }: Omit<Props, "items" | "mode"> & { item: FeedItem }) {
  return (
    <>
      {item.claims.map((c) => {
        const shown = claimText(item, c.id, persona, language);
        return (
          <button key={c.id} className="recap-line" dir={shown.dir} onClick={() => onPick(item.moment.id, c.id)}>
            {shown.text}
          </button>
        );
      })}
    </>
  );
}

export default function RecapPanel({ items, mode, persona, language, onPick }: Props) {
  const [open, setOpen] = useState(false);
  const ready = items.some((i) => i.moment.kind === "full_time");
  const recaps = recapOrder(items, mode);              // a favourite club's own recap first
  const spotlights = items.filter((i) => i.moment.kind === "spotlight");
  const pick = (momentId: string, claimId: string) => { setOpen(false); onPick(momentId, claimId); };
  return (
    <>
      <button className="pill accent" disabled={!ready} onClick={() => setOpen(true)}>Full-time recap</button>
      {open && (
        <div className="recap-backdrop" onClick={() => setOpen(false)}>
          <section className="recap" role="dialog" aria-label="Full-time recap" onClick={(e) => e.stopPropagation()}>
            <div className="column-head">
              <h2>Full-time recap</h2>
              <button className="link" onClick={() => setOpen(false)}>Close</button>
            </div>
            {recaps.map((item) => (
              <article key={item.moment.id} className="moment">
                <div className="tag">{item.moment.label}</div>
                <Lines item={item} persona={persona} language={language} onPick={pick} />
              </article>
            ))}
            {spotlights.length > 0 && <h3>Player spotlights</h3>}
            {spotlights.map((item) => (
              <article key={item.moment.id} className="moment">
                <div className="tag">{item.moment.label}</div>
                <Lines item={item} persona={persona} language={language} onPick={pick} />
              </article>
            ))}
          </section>
        </div>
      )}
    </>
  );
}
