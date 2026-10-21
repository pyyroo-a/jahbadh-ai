import { useState } from "react";
import type { FeedItem, Language, MetricChoice, Persona } from "../api/types";
import { type DeskState, rejectionsFor } from "../state/desk";
import { SLOWDOWN, speedNote } from "../state/labels";
import type { Selection } from "../state/evidence";
import { type Mode, rankClaims, recapOrder } from "../state/personal";
import { isSlowed, landedAt, stepChips } from "../state/slowdown";
import ClaimCard from "./ClaimCard";
import RejectedDraft from "./RejectedDraft";
import ThinkingCard from "./ThinkingCard";

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
  calm?: boolean;                           // the Fan view: rejected drafts stay folded
  detail?: boolean;                         // the Analyst view: drafts open, figures and citations on show
  reorder?: (items: FeedItem[]) => FeedItem[];   // Player watch: lines about your players first
  title?: string;
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

export function Moment({ item, persona, language, selection, onSelect, waiting, desk, mode, choices, calm, detail }: Omit<Props, "notice"> & { item: FeedItem }) {
  const [open, setOpen] = useState(false);
  const drafts = rejectionsFor(item, persona, language);
  const folded = calm ? 0 : detail ? drafts.length : 1;
  const shownDrafts = open ? drafts : drafts.slice(0, folded);
  const ranked = desk.info ? rankClaims(item, mode, desk.info, desk.eventsById, choices)
    : item.claims.map((claim) => ({ claim, focus: false }));
  const label = badge(mode, desk, choices);
  const landed = desk.info && desk.info.mode !== "replay" ? landedAt(desk, item.moment.id) : null;
  return (
    <article className="moment">
      <div className="tag">{item.moment.label}</div>
      {landed !== null && <div className="note landed">{SLOWDOWN.landed(landed)}</div>}
      {waiting(item) && <div className="note">Getting this ready for you...</div>}
      {ranked.map(({ claim: c, focus }) => {
        const selected = selection?.momentId === item.moment.id && selection.claimId === c.id;
        return (
          <ClaimCard key={c.id} item={item} claim={c} persona={persona} language={language} selected={selected}
            focus={focus ? label : null} dimmed={mode.kind !== "all" && !focus} eventsById={desk.eventsById} info={desk.info} detail={detail}
            onSelect={() => onSelect(selected ? null : { momentId: item.moment.id, claimId: c.id })} />
        );
      })}
      {shownDrafts.map((r, i) => <RejectedDraft key={`${r.claim_id}-${r.layer}-${r.attempt}-${i}`} item={item} rejection={r} />)}
      {drafts.length > folded && (
        <button className="link" onClick={() => setOpen(!open)}>
          {open ? (calm ? "Hide the rejected drafts" : "Hide the other rejected drafts")
            : `Show ${drafts.length - folded} ${calm ? "" : "more "}rejected ${drafts.length - folded === 1 ? "draft" : "drafts"}`}
        </button>
      )}
    </article>
  );
}

export default function DeskFeed(props: Props) {
  const { desk, notice } = props;
  // The full-time recaps lead (a favourite club's own first), then everything else, newest first.
  const recaps = recapOrder(desk.items, props.mode);
  const byTime = [...recaps, ...[...desk.items].reverse().filter((i) => !recaps.includes(i))];
  const newestFirst = props.reorder ? props.reorder(byTime) : byTime;
  return (
    <section className="column feed">
      <h2>{props.title ?? "Desk feed"}</h2>
      {desk.info && speedNote(desk.info) && <div className="note">{speedNote(desk.info)}</div>}
      {notice && <div className="note">{notice}</div>}
      {desk.thinking.map((m) => (
        <ThinkingCard key={m.id} moment={m} detailed={props.persona !== "casual"}
          holding={isSlowed(desk) && (desk.pace?.holding ?? []).includes(m.id)}
          chips={desk.info && desk.info.mode !== "replay" ? stepChips(desk.steps[m.id] ?? []) : []} />
      ))}
      {newestFirst.map((item) => <Moment key={item.moment.id} {...props} item={item} />)}
    </section>
  );
}
