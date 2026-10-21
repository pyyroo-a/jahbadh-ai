import { describe, expect, it } from "vitest";
import type { EventLine, FeedItem, Moment } from "../api/types";
import { info } from "../test-fixtures";
import {
  type ReplayInputs, freshGoal, goalChips, goalOfItem, newestUnwatched, pickReplay, stepMs,
} from "./goals";

const line = (id: number, type: EventLine["type"], t: number, team = "NBR", player: string | null = "NBR-9"): EventLine => ({
  id, t, minute: Math.min(90, Math.floor(t / 60) + 1), type, team_id: team, player_id: player, related_player_id: null,
  x: 50, y: 34, end_x: null, end_y: null, outcome: null, xg: null, speed_kmh: null, lines: { en: "", ar: "", es: "" },
});

const goalItem = (kind: Moment["kind"], eventIds: number[]): FeedItem => ({
  moment: { id: `${kind}-1`, kind, t: 900, team_id: "NBR", player_id: null, event_ids: eventIds, label: "" },
  claims: [], renders: [], rejections: [], metrics: [], stats: {}, latency_s: 0,
});

describe("goalChips", () => {
  it("names each goal by its minute and the scorer's last name, in match order", () => {
    const events = [line(1, "PASS", 100), line(2, "GOAL", 880), line(3, "GOAL", 2800, "RMU", "RMU-33")];
    expect(goalChips(events, info)).toEqual([
      { goalId: 2, minute: 15, teamId: "NBR", label: "15' 9" },
      { goalId: 3, minute: 47, teamId: "RMU", label: "47' 33" },
    ]);
  });

  it("uses the team when the scorer isn't on either team sheet", () => {
    expect(goalChips([line(2, "GOAL", 880, "NBR", "NBR-99")], info)[0].label).toBe("15' NBR");
  });
});

describe("freshGoal", () => {
  const goal = line(2, "GOAL", 900);

  it("keeps a goal fresh for a minute of match time", () => {
    expect(freshGoal([goal], 950)).toBe(goal);
    expect(freshGoal([goal], 961)).toBeNull();
  });

  it("picks the newest of two fresh goals", () => {
    const later = line(5, "GOAL", 930, "RMU", "RMU-33");
    expect(freshGoal([goal, later], 940)).toBe(later);
  });

  it("finds nothing without a goal", () => {
    expect(freshGoal([line(1, "PASS", 900)], 900)).toBeNull();
  });
});

describe("goalOfItem", () => {
  const shot = line(1, "SHOT", 900), goal = line(2, "GOAL", 900);
  const byId = { 1: shot, 2: goal };

  it("finds a goal moment's own goal", () => {
    expect(goalOfItem(goalItem("goal", [1, 2]), byId)).toBe(goal);
  });

  it("ignores every other kind of moment", () => {
    expect(goalOfItem(goalItem("big_chance", [1]), byId)).toBeNull();
  });

  it("gives nothing when the goal hasn't arrived", () => {
    expect(goalOfItem(goalItem("goal", [1, 2]), { 1: shot })).toBeNull();
  });
});

describe("stepMs", () => {
  it("keeps short moves at 0.8 s a step and long ones at about 7 s in all", () => {
    expect([stepMs(1), stepMs(10), stepMs(20)]).toEqual([800, 600, 350]);
  });
});

describe("newestUnwatched", () => {
  const chips = goalChips([line(2, "GOAL", 880), line(3, "GOAL", 2800, "RMU", "RMU-33")], info);

  it("gives the newest goal until it is watched", () => {
    expect(newestUnwatched(chips, new Set())?.goalId).toBe(3);
  });

  it("gives nothing once the newest is watched, even if an older one isn't", () => {
    expect(newestUnwatched(chips, new Set([3]))).toBeNull();
  });
});

describe("pickReplay", () => {
  const base: ReplayInputs = {
    request: null, lineGoal: null, lineDone: false, fresh: null, watched: new Set(), overview: true, phone: false,
  };

  it("plays a chip the viewer tapped before anything else", () => {
    expect(pickReplay({ ...base, request: 7, lineGoal: 8, fresh: 9 })).toBe(7);
  });

  it("plays a selected goal line until it has finished", () => {
    expect(pickReplay({ ...base, lineGoal: 8, overview: false })).toBe(8);
    expect(pickReplay({ ...base, lineGoal: 8, lineDone: true, overview: false })).toBeNull();
  });

  it("plays a fresh goal by itself only on the overview, on a wide screen, once", () => {
    expect(pickReplay({ ...base, fresh: 9 })).toBe(9);
    expect(pickReplay({ ...base, fresh: 9, overview: false })).toBeNull();
    expect(pickReplay({ ...base, fresh: 9, phone: true })).toBeNull();
    expect(pickReplay({ ...base, fresh: 9, watched: new Set([9]) })).toBeNull();
  });
});
