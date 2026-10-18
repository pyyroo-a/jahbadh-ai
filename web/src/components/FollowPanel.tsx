import { useEffect, useState } from "react";
import { ApiError, getFollow, spotlight } from "../api/client";
import type { FeedItem, Language, MatchInfo, Persona, PlayerFollow } from "../api/types";
import { claimText } from "../state/desk";

type Props = {
  info: MatchInfo;
  playerId: string;
  clock: number;
  runId: string | null;
  items: FeedItem[];
  persona: Persona;
  language: Language;
  onFollow: (f: PlayerFollow | null) => void;
};

const num = (v: unknown, digits: number, unit = "") =>
  typeof v === "number" ? `${v.toFixed(digits)}${unit}` : "no data";

export default function FollowPanel({ info, playerId, clock, runId, items, persona, language, onFollow }: Props) {
  const [follow, setFollow] = useState<PlayerFollow | null>(null);
  const [asked, setAsked] = useState<string | null>(null);
  const asOf = Math.min(5400, Math.floor(clock / 60) * 60);      // the start of the current match minute
  const player = [...info.home.players, ...info.away.players].find((p) => p.id === playerId);

  useEffect(() => {          // once per match minute: the numbers only change that often on screen
    let gone = false;
    getFollow(info.match_id, playerId, asOf, runId)
      .then((f) => { if (!gone) { setFollow(f); onFollow(f); } })
      .catch(() => { if (!gone) { setFollow(null); onFollow(null); } });
    return () => { gone = true; };
  }, [info.match_id, playerId, runId, asOf, onFollow]);

  useEffect(() => () => onFollow(null), [onFollow]);

  const spotlights = items.filter((i) => i.moment.kind === "spotlight" && i.moment.player_id === playerId);
  const ask = () => runId && spotlight(runId, playerId)
    .then(() => setAsked("The desk is on it. The spotlight lands in the feed shortly."))
    .catch((e) => setAsked(e instanceof ApiError ? e.detail : "The desk couldn't take that request."));

  const physical = follow?.physical.data ?? {};
  return (
    <section className="follow">
      <h3>Following {player?.name ?? playerId}{follow && !follow.on_pitch ? " · not on the pitch" : ""}</h3>
      <div className="stat-row">
        <div className="stat"><b>{num(physical.distance_km, 1, " km")}</b>Distance</div>
        <div className="stat"><b>{num(physical.top_speed_kmh, 1, " km/h")}</b>Top speed</div>
        <div className="stat"><b>{num(follow?.impact.value, 2)}</b>xG involvement</div>
        <div className="stat"><b>{num(follow?.passing.value, 2)}</b>Pass difficulty</div>
        <div className="stat"><b>{num(follow?.impact.data.touches, 0)}</b>Touches</div>
      </div>
      <div className="note">Distance and speed come from the simulated tracking data.</div>
      {spotlights.flatMap((i) => i.claims.map((c) => {
        const shown = claimText(i, c.id, persona, language);
        return <p key={c.id} className="spotlight-line" dir={shown.dir}>{shown.text}</p>;
      }))}
      {runId && info.mode === "live" && <button className="pill" onClick={ask}>Spotlight this player</button>}
      {asked && <div className="note">{asked}</div>}
    </section>
  );
}
