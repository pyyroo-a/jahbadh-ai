import { useState, type ReactNode } from "react";
import type { Language } from "../../api/types";
import type { DeskState } from "../../state/desk";
import { visibleEvents } from "../../state/events";
import { weaveFeed } from "../../state/feed";
import { FEED_LABELS, SPEED_NOTE } from "../../state/labels";
import MomentumBar from "../MomentumBar";
import TacticalCard from "../TacticalCard";

const STEP = 12;

type Props = {
  desk: DeskState;
  language: Language;
  tactical: ReactNode;                    // the tactical view, folded into a card
  tacticalOpen: boolean;                  // open it while a desk line's evidence is on the pitch
  renderItem: (item: DeskState["items"][number]) => ReactNode;
};

/** The casual fan on a phone: momentum, the folded tactical view, then one woven feed of desk lines and events. */
export default function FanLayout({ desk, language, tactical, tacticalOpen, renderItem }: Props) {
  const [limit, setLimit] = useState(STEP);
  const keyEvents = visibleEvents(desk.events, "key", new Set(), desk.events.length).reverse();
  const entries = weaveFeed(keyEvents, desk.items, limit);
  const more = Math.min(STEP, keyEvents.length - limit);
  return (
    <main className="phone-stack">
      {desk.info && <MomentumBar info={desk.info} momentum={desk.state?.momentum ?? null} />}
      <TacticalCard forcedOpen={tacticalOpen}>{tactical}</TacticalCard>
      <section className="column happening">
        <h2>{FEED_LABELS.happening}</h2>
        {desk.info && desk.info.mode !== "replay" && <div className="note">{SPEED_NOTE}</div>}
        {desk.thinking.map((m) => <div key={m.id} className="thinking">The desk is thinking about {m.label}...</div>)}
        {entries.map((e) => e.kind === "desk"
          ? <div key={e.item.moment.id}>{renderItem(e.item)}</div>
          : (
            <div key={e.event.id} className="happening-event">
              <span className="event-minute">{e.event.minute}'</span>
              <span dir={language === "ar" ? "rtl" : "ltr"}>{e.event.lines[language]}</span>
            </div>
          ))}
        {more > 0 && (
          <button className="link" onClick={() => setLimit(limit + STEP)}>{FEED_LABELS.more(more)}</button>
        )}
      </section>
    </main>
  );
}
