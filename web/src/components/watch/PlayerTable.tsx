import { useState } from "react";
import type { MatchInfo, PlayerRow } from "../../api/types";
import { sortPlayers } from "../../state/players";

type Key = keyof PlayerRow;
const COLUMNS: { key: Key; label: string; show: (r: PlayerRow) => string }[] = [
  { key: "xgi", label: "xGI", show: (r) => r.xgi.toFixed(2) },
  { key: "goals", label: "G", show: (r) => String(r.goals) },
  { key: "assists", label: "A", show: (r) => String(r.assists) },
  { key: "shots", label: "Shots", show: (r) => String(r.shots) },
  { key: "ball_wins", label: "Ball wins", show: (r) => String(r.ball_wins) },
  { key: "yellow_cards", label: "Cards", show: (r) => r.red_cards ? `${r.yellow_cards} Y, ${r.red_cards} R` : r.yellow_cards ? `${r.yellow_cards} Y` : "" },
  { key: "minutes", label: "Mins", show: (r) => String(Math.round(r.minutes)) },
];

type Props = { info: MatchInfo; rows: PlayerRow[]; followed: string | null; onFollow: (playerId: string) => void };

/** Every player who has been on, sortable by any column; a click follows that player. */
export default function PlayerTable({ info, rows, followed, onFollow }: Props) {
  const [sort, setSort] = useState<{ key: Key; dir: "asc" | "desc" }>({ key: "xgi", dir: "desc" });
  const sorted = sortPlayers(rows, sort.key, sort.dir);
  const by = (key: Key) => setSort(sort.key === key ? { key, dir: sort.dir === "desc" ? "asc" : "desc" } : { key, dir: "desc" });
  return (
    <table className="numbers players">
      <thead>
        <tr>
          <th><button className="link" onClick={() => by("name")}>Player</button></th>
          {COLUMNS.map((c) => (
            <th key={c.key} aria-sort={sort.key === c.key ? (sort.dir === "desc" ? "descending" : "ascending") : undefined}>
              <button className="link" onClick={() => by(c.key)}>{c.label}</button>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sorted.map((r) => (
          <tr key={r.player_id} className={r.player_id === followed ? "followed" : undefined} onClick={() => onFollow(r.player_id)}>
            <td className={r.team_id === info.home.id ? "home" : "away"}>{r.player_id === followed ? "★ " : ""}{r.name}</td>
            {COLUMNS.map((c) => <td key={c.key}>{c.show(r)}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
