import { useEffect, useState, type ReactNode } from "react";
import { getPlayers, type RunKind } from "../../api/client";
import type { MatchInfo, PlayerRow } from "../../api/types";
import type { DeskState } from "../../state/desk";
import { WATCH_LABELS } from "../../state/labels";
import { spotlightChips } from "../../state/players";
import PlayerCards from "../watch/PlayerCards";
import PlayerTable from "../watch/PlayerTable";

const SETTLE_MS = 300;

type Props = {
  desk: DeskState;
  info: MatchInfo;
  phone: boolean;
  clock: number;
  runId: string | null;
  runKind: RunKind;
  followed: string | null;
  onFollow: (playerId: string) => void;
  tactical: ReactNode;
  feed: ReactNode;
};

/** The fantasy player's view: every player's numbers, the spotlights, and the followed player on the pitch. */
export default function PlayerWatchLayout({ desk, info, phone, clock, runId, runKind, followed, onFollow, tactical, feed }: Props) {
  const [rows, setRows] = useState<PlayerRow[]>([]);
  const asOf = Math.min(5400, Math.floor(clock / 60) * 60);       // once per match minute, like the follow panel
  useEffect(() => {             // wait for the clock to settle, so a skip doesn't ask once for every minute it passes
    let gone = false;
    const timer = setTimeout(() => {
      getPlayers(info.match_id, asOf, runId, runKind).then((r) => { if (!gone) setRows(r); }).catch(() => undefined);
    }, SETTLE_MS);
    return () => { gone = true; clearTimeout(timer); };
  }, [info.match_id, asOf, runId, runKind]);
  const chips = spotlightChips(desk.items);
  const spotlights = chips.length > 0 && (
    <div className="chips">
      {chips.map((c) => (
        <button key={c.momentId} className="pill" onClick={() => onFollow(c.player_id)}>{c.label}</button>
      ))}
    </div>
  );
  if (phone) {
    return (
      <main className="phone-stack">
        <PlayerCards info={info} rows={rows} followed={followed} onFollow={onFollow} />
        {spotlights}
        {tactical}
        {feed}
      </main>
    );
  }
  return (
    <main className="columns">
      <section className="column watch">
        <h2>{WATCH_LABELS.table}</h2>
        <PlayerTable info={info} rows={rows} followed={followed} onFollow={onFollow} />
        {spotlights}
      </section>
      {tactical}
      {feed}
    </main>
  );
}
