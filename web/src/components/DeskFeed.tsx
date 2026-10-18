import { useState } from "react";
import type { FeedItem, Language, Persona } from "../api/types";
import { type DeskState, rejectionsFor } from "../state/desk";
import type { Selection } from "../state/evidence";
import ClaimCard from "./ClaimCard";
import RejectedDraft from "./RejectedDraft";

type Props = {
  desk: DeskState;
  persona: Persona;
  language: Language;
  selection: Selection;
  onSelect: (s: Selection) => void;
  waiting: (item: FeedItem) => boolean;      // live: this combo was asked for and hasn't arrived yet
  notice: string | null;
};

function Moment({ item, persona, language, selection, onSelect, waiting, desk }: Omit<Props, "notice"> & { item: FeedItem }) {
  const [open, setOpen] = useState(false);
  const drafts = rejectionsFor(item, persona, language);
  const shownDrafts = open ? drafts : drafts.slice(0, 1);
  return (
    <article className="moment">
      <div className="tag">{item.moment.label}</div>
      {waiting(item) && <div className="note">Getting this ready for you...</div>}
      {item.claims.map((c) => {
        const selected = selection?.momentId === item.moment.id && selection.claimId === c.id;
        return (
          <ClaimCard key={c.id} item={item} claim={c} persona={persona} language={language} selected={selected}
            eventsById={desk.eventsById}
            onSelect={() => onSelect(selected ? null : { momentId: item.moment.id, claimId: c.id })} />
        );
      })}
      {shownDrafts.map((r, i) => <RejectedDraft key={`${r.claim_id}-${r.layer}-${r.attempt}-${i}`} item={item} rejection={r} />)}
      {drafts.length > 1 && (
        <button className="link" onClick={() => setOpen(!open)}>
          {open ? "Hide the other rejected drafts" : `Show ${drafts.length - 1} more rejected ${drafts.length === 2 ? "draft" : "drafts"}`}
        </button>
      )}
    </article>
  );
}

export default function DeskFeed(props: Props) {
  const { desk, notice } = props;
  const newestFirst = [...desk.items].reverse();
  return (
    <section className="column feed">
      <h2>Desk feed</h2>
      {notice && <div className="note">{notice}</div>}
      {desk.thinking.map((m) => <div key={m.id} className="thinking">The desk is thinking about {m.label}...</div>)}
      {newestFirst.map((item) => <Moment key={item.moment.id} {...props} item={item} />)}
    </section>
  );
}
