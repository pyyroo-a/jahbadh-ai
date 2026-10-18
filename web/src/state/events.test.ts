import { describe, expect, it } from "vitest";
import type { EventLine, EventType } from "../api/types";
import { visibleEvents } from "./events";

const ev = (id: number, type: EventType): EventLine => ({
  id, t: id, minute: 1, type, team_id: "NBR", player_id: null, related_player_id: null, x: 0, y: 0,
  end_x: null, end_y: null, outcome: true, xg: null, lines: { en: "", ar: "", es: "" },
});
const pass = (id: number) => ev(id, "PASS");
const goal = (id: number) => ev(id, "GOAL");

describe("visibleEvents", () => {
  it("keeps highlighted passes even in key-events mode", () => {
    expect(visibleEvents([pass(2), goal(213)], "key", new Set([2])).map((e) => e.id)).toEqual([213, 2]);
    expect(visibleEvents([pass(2), goal(213)], "key", new Set()).map((e) => e.id)).toEqual([213]);
  });

  it("shows everything newest first in all-events mode, up to the limit", () => {
    const events = [ev(1, "KICKOFF"), pass(2), ev(3, "TACKLE"), goal(4)];
    expect(visibleEvents(events, "all", new Set()).map((e) => e.id)).toEqual([4, 3, 2, 1]);
    expect(visibleEvents(events, "all", new Set(), 2).map((e) => e.id)).toEqual([4, 3]);
  });

  it("never drops a highlighted event past the limit", () => {
    const events = [pass(1), pass(2), pass(3), pass(4)];
    expect(visibleEvents(events, "all", new Set([1]), 2).map((e) => e.id)).toEqual([4, 3, 1]);
  });
});
