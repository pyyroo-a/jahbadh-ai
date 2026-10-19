import { describe, expect, it } from "vitest";
import type { Claim, EventLine, FeedItem, MatchInfo, MatchState, Metric, MetricChoice, Player, Team } from "../api/types";
import { claimTags, formatSeriesValue, metricSeries, rankClaims, recapOrder, seriesLabel } from "./personal";

const player = (id: string, name: string): Player =>
  ({ id, team_id: id.slice(0, 3), name, shirt: Number(id.slice(4)), role: "ST", starter: true });
const team = (id: string, name: string, players: Player[]): Team => ({
  id, name, formation: "4-3-3", players, tactics: { press_height: 0.5, width: 0.5, tempo: 0.5, directness: 0.5 },
});
const info: MatchInfo = {
  match_id: "match-042", mode: "replay", speed: 6, precomputed: true, model: null, created: null, moment_times: [],
  home: team("NBR", "Northbridge FC", [player("NBR-9", "Kian Jansen")]),
  away: team("RMU", "Rivermouth United", [player("RMU-33", "Omar Rasmus"), player("RMU-4", "Tomas Lindqvist")]),
};
const ev = (id: number, team_id: string, player_id: string | null, related: string | null = null): EventLine => ({
  id, t: id, minute: 1, type: "TACKLE", team_id, player_id, related_player_id: related, x: 0, y: 0,
  end_x: null, end_y: null, outcome: true, xg: null, speed_kmh: null, lines: { en: "", ar: "", es: "" },
});
const eventsById = { 1: ev(1, "NBR", "NBR-9"), 2: ev(2, "RMU", "RMU-4", "NBR-9"), 3: ev(3, "RMU", null) };
const metric = (id: string, name: string, subject: string): Metric => ({
  id, name, subject, window: [0, 600], value: 0.5, unit: "share", evidence_event_ids: [], evidence_frames: null,
  data: {}, note: null,
});
const claim = (id: string, event_ids: number[], metric_ids: string[]): Claim =>
  ({ id, text: id, event_ids, metric_ids, figures: [] });
const metrics = [metric("impact:RMU-33", "player_impact", "RMU-33"), metric("tilt:NBR", "field_tilt", "NBR"),
  metric("stats:MATCH", "match_stats", "MATCH"), metric("rhythm:MATCH", "game_rhythm", "MATCH")];
const item: FeedItem = {
  moment: { id: "goal-1317", kind: "goal", t: 1317, team_id: "RMU", player_id: "RMU-33", event_ids: [], label: "goal" },
  claims: [claim("c1", [1], []), claim("c2", [], ["impact:RMU-33"]), claim("c3", [], ["tilt:NBR"])],
  renders: [], rejections: [], metrics, stats: {}, latency_s: 1,
};
const choices: MetricChoice[] = [
  { key: "rhythm", label: "Game rhythm", state_field: "rhythm", metric_names: ["game_rhythm"] },
  { key: "xg", label: "xG", state_field: "xg", metric_names: ["xg_total", "shot_map", "player_impact"] },
];

describe("claimTags", () => {
  it("tags a claim with its teams and players", () => {
    const tackle = claimTags(item, claim("x", [2], []), info, eventsById);
    expect(tackle.teams).toEqual(new Set(["RMU", "NBR"]));
    expect(tackle.players).toEqual(new Set(["RMU-4", "NBR-9"]));
    const viaPlayer = claimTags(item, item.claims[1], info, eventsById);
    expect(viaPlayer.teams).toEqual(new Set(["RMU"]));
    expect(viaPlayer.players).toEqual(new Set(["RMU-33"]));
    expect(viaPlayer.metrics).toEqual(new Set(["player_impact"]));
  });

  it("counts the whole match as both clubs and a team event without a player as its team", () => {
    expect(claimTags(item, claim("m", [], ["stats:MATCH"]), info, eventsById).teams).toEqual(new Set(["NBR", "RMU"]));
    expect(claimTags(item, claim("f", [3], []), info, eventsById).teams).toEqual(new Set(["RMU"]));
    expect(claimTags(item, claim("late", [999], []), info, eventsById).teams).toEqual(new Set());
  });
});

describe("rankClaims", () => {
  it("puts the club's claims first and hides nothing", () => {
    const ranked = rankClaims(item, { kind: "club", teamId: "RMU" }, info, eventsById);
    expect(ranked.map((r) => r.claim.id)).toEqual(["c2", "c1", "c3"]);
    expect(ranked).toHaveLength(item.claims.length);
    expect(ranked.map((r) => r.focus)).toEqual([true, false, false]);
  });

  it("follows a player and a metric, and keeps everyone's order unchanged", () => {
    expect(rankClaims(item, { kind: "player", playerId: "NBR-9" }, info, eventsById).map((r) => r.claim.id))
      .toEqual(["c1", "c2", "c3"]);
    expect(rankClaims(item, { kind: "metric", key: "xg" }, info, eventsById, choices).map((r) => [r.claim.id, r.focus]))
      .toEqual([["c2", true], ["c1", false], ["c3", false]]);
    expect(rankClaims(item, { kind: "all" }, info, eventsById).map((r) => [r.claim.id, r.focus]))
      .toEqual([["c1", false], ["c2", false], ["c3", false]]);
  });
});

describe("metricSeries", () => {
  const state = (t: number, extra: Partial<MatchState>): MatchState => ({
    t, minute: t / 60 + 1, score: {}, xg: { NBR: 0, RMU: 0 }, momentum: null, field_tilt: null, ppda: {}, shape: {},
    formations: {}, rhythm: null, pass_difficulty: {}, pass_speed: {}, ...extra,
  });
  const states = [state(0, {}), state(60, { xg: { NBR: 0.1, RMU: 0.4 }, field_tilt: 0.62 }),
    state(120, { rhythm: { ...metrics[3], value: 3.8 }, ppda: { NBR: null, RMU: 9.5 } })];

  it("builds a metric line from the states", () => {
    expect(metricSeries(states, "xg", "RMU")).toEqual([{ t: 0, v: 0 }, { t: 60, v: 0.4 }, { t: 120, v: 0 }]);
    expect(metricSeries(states, "field_tilt")).toEqual([{ t: 0, v: null }, { t: 60, v: 0.62 }, { t: 120, v: null }]);
    expect(metricSeries(states, "rhythm").map((p) => p.v)).toEqual([null, null, 3.8]);
    expect(metricSeries(states, "ppda", "NBR").map((p) => p.v)).toEqual([null, null, null]);
    expect(metricSeries(states, "xg").map((p) => p.v)).toEqual([null, null, null]);     // a per-club number needs a club
  });

  it("writes the value the way the desk does", () => {
    expect(formatSeriesValue("field_tilt", 0.539)).toBe("54%");
    expect(formatSeriesValue("xg", 1.789)).toBe("1.79");
    expect(formatSeriesValue("ppda", 9.46)).toBe("9.5");
    expect(formatSeriesValue("rhythm", 3.8)).toBe("3.8");
    expect(formatSeriesValue("momentum", null)).toBe("no data");
  });

  it("says what the number is", () => {
    expect(seriesLabel("field_tilt", info)).toBe("Northbridge FC's share");
    expect(seriesLabel("momentum", info)).toBe("Northbridge FC's share");
    expect(seriesLabel("rhythm", info)).toBe("Possession changes a minute");
  });
});

describe("recapOrder", () => {
  const recap = (id: string, kind: FeedItem["moment"]["kind"], team_id: string | null): FeedItem =>
    ({ ...item, moment: { ...item.moment, id, kind, team_id, t: 5400 } });
  const items = [recap("spotlight-RMU-33", "spotlight", "RMU"), recap("team_recap-NBR", "team_recap", "NBR"),
    recap("team_recap-RMU", "team_recap", "RMU"), recap("full_time-5400", "full_time", null), item];

  it("orders recaps for a favourite club", () => {
    expect(recapOrder(items, { kind: "club", teamId: "RMU" }).map((i) => i.moment.id))
      .toEqual(["team_recap-RMU", "full_time-5400", "team_recap-NBR"]);
    expect(recapOrder(items, { kind: "all" }).map((i) => i.moment.id))
      .toEqual(["full_time-5400", "team_recap-NBR", "team_recap-RMU"]);
  });
});
