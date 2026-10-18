// How a computed metric reads on a tile: its value as the desk writes it, a plain name, and who and when.

import type { MatchInfo, Metric } from "../api/types";

const LABELS: Record<string, string> = {
  field_tilt: "Field tilt", ppda: "PPDA", momentum: "Momentum (home share)", xg_total: "xG",
  player_impact: "xG involvement", heatmap: "Heatmap", average_positions: "Average positions",
  zone_overloads: "Overload", pass_network: "Pass links", shot_map: "Shots", match_stats: "Match stats",
  attacking_sides: "Attacking side", midfield_control: "Midfield control",
};
const SHARES = new Set(["share", "home_share", "share_of_seconds"]);
const COUNTS = new Set(["shots", "players", "edges", "samples", "passes", "goals", "cards", "touches", "events"]);

function value(v: number | null, unit: string): string {
  if (v === null) return "no data";
  if (SHARES.has(unit)) return `${Math.round(v * 100)}%`;
  if (unit === "xG" || unit === "xGI") return v.toFixed(2);
  if (unit === "passes/def_action") return v.toFixed(1);
  if (unit === "m") return `${v.toFixed(1)} m`;
  if (unit === "km") return `${v.toFixed(1)} km`;
  if (unit === "km/h") return `${v.toFixed(1)} km/h`;
  if (COUNTS.has(unit)) return String(Math.round(v));
  return v.toFixed(2);                                 // never round a real fraction down to "0"
}

function subjectName(subject: string, info: MatchInfo): string {
  if (subject === "MATCH") return "Both teams";
  for (const team of [info.home, info.away]) {
    if (team.id === subject) return team.name;
    const p = team.players.find((x) => x.id === subject);
    if (p) return p.name;
  }
  return subject;
}

/** Broadcast minutes for a window [start, end): 0-600 reads 1' to 10'. */
function minutes([start, end]: [number, number]): string {
  const a = Math.floor(start / 60) + 1, b = Math.min(90, Math.floor((end - 1) / 60) + 1);
  return b > a ? `${a}' to ${b}'` : `${a}'`;
}

export function formatMetric(m: Metric, info: MatchInfo): { value: string; label: string; sub: string } {
  return {
    value: value(m.value, m.unit),
    label: LABELS[m.name] ?? m.name.replaceAll("_", " "),
    sub: `${subjectName(m.subject, info)} · ${minutes(m.window)}`,
  };
}
