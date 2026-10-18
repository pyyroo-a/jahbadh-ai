// Shared test data for the pitch and format tests: a tiny two-club match.

import type { MatchInfo, Metric, Player, Team } from "./api/types";

const player = (id: string, shirt: number): Player =>
  ({ id, team_id: id.slice(0, 3), name: `Player ${shirt}`, shirt, role: "CM", starter: true });
const team = (id: string, name: string, players: Player[]): Team => ({
  id, name, formation: "4-3-3", players, tactics: { press_height: 0.5, width: 0.5, tempo: 0.5, directness: 0.5 },
});

export const info: MatchInfo = {
  match_id: "match-042", mode: "replay", speed: 6, precomputed: true, model: null, created: null, moment_times: [],
  home: team("NBR", "Northbridge FC", [player("NBR-9", 9), player("NBR-10", 10), player("NBR-4", 4)]),
  away: team("RMU", "Rivermouth United", [player("RMU-33", 33), player("RMU-4", 4)]),
};

export const metric = (name: string, subject: string, data: Record<string, unknown> = {}, value: number | null = 1,
  unit = "x", window: [number, number] = [0, 600]): Metric => ({
  id: `${name}:${subject}:${window[0]}-${window[1]}`, name, subject, window, value, unit, evidence_event_ids: [],
  evidence_frames: null, data, note: null,
});
