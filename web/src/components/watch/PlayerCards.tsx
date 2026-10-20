import type { MatchInfo, PlayerRow } from "../../api/types";

type Props = { info: MatchInfo; rows: PlayerRow[]; followed: string | null; onFollow: (playerId: string) => void };

/** The phone's player table: a row of cards to swipe through; a tap follows that player. */
export default function PlayerCards({ info, rows, followed, onFollow }: Props) {
  return (
    <div className="player-cards" aria-label="Players">
      {rows.map((r) => (
        <button key={r.player_id} className={r.player_id === followed ? "player-card followed" : "player-card"}
          onClick={() => onFollow(r.player_id)}>
          <b className={r.team_id === info.home.id ? "home" : "away"}>{r.player_id === followed ? "★ " : ""}{r.name}</b>
          <span>xGI {r.xgi.toFixed(2)} · {r.goals} G · {r.assists} A</span>
          <span className="muted">{r.shots} shots · {Math.round(r.minutes)}'</span>
        </button>
      ))}
    </div>
  );
}
