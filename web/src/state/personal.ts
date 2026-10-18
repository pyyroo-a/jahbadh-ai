// Personalisation without the model: tag the claims the Referee already approved, put the viewer's focus first,
// and read the numbers the server already computed. Nothing is hidden and nothing new is written.

import type { Claim, EventLine, FeedItem, MatchInfo, MatchState, MetricChoice } from "../api/types";

export type Mode =
  | { kind: "all" }
  | { kind: "club"; teamId: string }
  | { kind: "player"; playerId: string }
  | { kind: "metric"; key: string };

export type Tags = { teams: Set<string>; players: Set<string>; metrics: Set<string> };

function teamOf(info: MatchInfo): Map<string, string> {
  return new Map([...info.home.players, ...info.away.players].map((p) => [p.id, p.team_id]));
}

/** Which clubs, players and metric names a claim is about, from what it cites. */
export function claimTags(item: FeedItem, claim: Claim, info: MatchInfo, eventsById: Record<number, EventLine>): Tags {
  const team = teamOf(info);
  const tags: Tags = { teams: new Set(), players: new Set(), metrics: new Set() };
  const addPlayer = (id: string | null) => {
    if (!id) return;
    tags.players.add(id);
    const club = team.get(id);
    if (club) tags.teams.add(club);
  };
  for (const id of claim.event_ids) {
    const e = eventsById[id];
    if (!e) continue;                                  // not streamed yet
    if (!e.player_id) tags.teams.add(e.team_id);       // a formation or tactic change belongs to its team
    addPlayer(e.player_id);
    addPlayer(e.related_player_id);
  }
  const byId = new Map(item.metrics.map((m) => [m.id, m]));
  for (const id of claim.metric_ids) {
    const m = byId.get(id);
    if (!m) continue;
    tags.metrics.add(m.name);
    if (m.subject === "MATCH") [info.home.id, info.away.id].forEach((t) => tags.teams.add(t));
    else if (m.subject === info.home.id || m.subject === info.away.id) tags.teams.add(m.subject);
    else addPlayer(m.subject);
  }
  return tags;
}

export function inFocus(tags: Tags, mode: Mode, choices: MetricChoice[] = []): boolean {
  switch (mode.kind) {
    case "all": return false;
    case "club": return tags.teams.has(mode.teamId);
    case "player": return tags.players.has(mode.playerId);
    case "metric": {
      const names = choices.find((c) => c.key === mode.key)?.metric_names ?? [];
      return names.some((n) => tags.metrics.has(n));
    }
  }
}

/** Focused claims first, each group in its original order. Every claim is still there. */
export function rankClaims(item: FeedItem, mode: Mode, info: MatchInfo, eventsById: Record<number, EventLine>,
  choices: MetricChoice[] = []): { claim: Claim; focus: boolean }[] {
  const ranked = item.claims.map((claim) => ({ claim, focus: inFocus(claimTags(item, claim, info, eventsById), mode, choices) }));
  return [...ranked.filter((r) => r.focus), ...ranked.filter((r) => !r.focus)];
}

/** One number per minute for a metric choice. Per-club numbers (xG, PPDA, pass difficulty) need the club. */
export function metricSeries(states: MatchState[], key: string, teamId?: string): { t: number; v: number | null }[] {
  return states.map((s) => {
    switch (key) {
      case "xg": return { t: s.t, v: teamId ? s.xg[teamId] ?? null : null };
      case "ppda": return { t: s.t, v: teamId ? s.ppda[teamId] ?? null : null };
      case "pass_difficulty": return { t: s.t, v: teamId ? s.pass_difficulty[teamId] ?? null : null };
      case "field_tilt": return { t: s.t, v: s.field_tilt };
      case "momentum": return { t: s.t, v: s.momentum };
      case "rhythm": return { t: s.t, v: s.rhythm?.value ?? null };
      default: return { t: s.t, v: null };
    }
  });
}

export const PER_CLUB = new Set(["xg", "ppda", "pass_difficulty"]);

/** What a one-line (not per-club) number means. */
export function seriesLabel(key: string, info: MatchInfo): string {
  if (key === "rhythm") return "Possession changes a minute";
  return `${info.home.name}'s share`;              // field tilt and momentum are the home team's share
}

export function formatSeriesValue(key: string, v: number | null): string {
  if (v === null) return "no data";
  if (key === "field_tilt" || key === "momentum") return `${Math.round(v * 100)}%`;
  if (key === "xg" || key === "pass_difficulty") return v.toFixed(2);
  return v.toFixed(1);
}

/** The full-time recaps: a favourite club's own recap first, then full time, then the other club's. */
export function recapOrder(items: FeedItem[], mode: Mode): FeedItem[] {
  const fullTime = items.filter((i) => i.moment.kind === "full_time");
  const recaps = items.filter((i) => i.moment.kind === "team_recap");
  if (mode.kind !== "club") return [...fullTime, ...recaps];
  const mine = recaps.filter((i) => i.moment.team_id === mode.teamId);
  return [...mine, ...fullTime, ...recaps.filter((i) => i.moment.team_id !== mode.teamId)];
}
