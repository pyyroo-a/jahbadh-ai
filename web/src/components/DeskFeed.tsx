import { useState } from "react";
import type { FeedItem, Language, MetricChoice, Persona } from "../api/types";
import { type DeskState, rejectionsFor } from "../state/desk";
import type { Selection } from "../state/evidence";
import { type Mode, rankClaims, recapOrder } from "../state/personal";
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
  mode: Mode;
  choices: MetricChoice[];
};

function badge(mode: Mode, desk: DeskState, choices: MetricChoice[]): string | null {
  const players = desk.info ? [...desk.info.home.players, ...desk.info.away.players] : [];
  switch (mode.kind) {
    case "all": return null;
    case "club": return "Your club";
    case "player": return `Following ${players.find((p) => p.id === mode.playerId)?.name ?? mode.playerId}`;
    case "metric": return `Tracks ${choices.find((c) => c.key === mode.key)?.label ?? mode.key}`;
  }
}

function Moment({ item, persona, language, selection, onSelect, waiting, desk, mode, choices }: Omit<Props, "notice"> & { item: FeedItem }) {
  const [open, setOpen] = useState(false);
  const drafts = rejectionsFor(item, persona, language);
  const shownDrafts = open ? drafts : drafts.slice(0, 1);
  const ranked = desk.info ? rankClaims(item, mode, desk.info, desk.eventsById, choices)
    : item.claims.map((claim) => ({ claim, focus: false }));
  const label = badge(mode, desk, choices);
  return (
    <article className="moment">
      <div className="tag">{item.moment.label}</div>
      {waiting(item) && <div className="note">Getting this ready for you...</div>}
      {ranked.map(({ claim: c, focus }) => {
        const selected = selection?.momentId === item.moment.id && selection.claimId === c.id;
        return (
          <ClaimCard key={c.id} item={item} claim={c} persona={persona} language={language} selected={selected}
            focus={focus ? label : null} dimmed={mode.kind !== "all" && !focus} eventsById={desk.eventsById}
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
  // The full-time recaps lead (a favourite club's own first), then everything else, newest first.
  const recaps = recapOrder(desk.items, props.mode);
  const newestFirst = [...recaps, ...[...desk.items].reverse().filter((i) => !recaps.includes(i))];
  return (
    <section className="column feed">
      <h2>Desk feed</h2>
      {notice && <div className="note">{notice}</div>}
      {desk.thinking.map((m) => <div key={m.id} className="thinking">The desk is thinking about {m.label}...</div>)}
      {newestFirst.map((item) => <Moment key={item.moment.id} {...props} item={item} />)}
    </section>
  );
}
