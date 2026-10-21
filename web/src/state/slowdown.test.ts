import { describe, expect, it } from "vitest";
import type { Moment, StepUpdate } from "../api/types";
import { info } from "../test-fixtures";
import { initialDesk, type DeskState } from "./desk";
import { clockSpeed, holdingMoment, isSlowed, landedAt, stepChips } from "./slowdown";

const moment = (id: string, t: number): Moment =>
  ({ id, kind: "goal", t, team_id: "NBR", player_id: null, event_ids: [], label: `${id} label` });
const live = { ...info, mode: "live" as const, speed: 6 };
const desk = (extra: Partial<DeskState>): DeskState => ({ ...initialDesk, info: live, ...extra });
const step = (s: StepUpdate["step"], t = 900): StepUpdate => ({ moment_id: "goal-885", step: s, t });

describe("isSlowed", () => {
  it("is true while the pace is under the match speed", () => {
    expect(isSlowed(desk({ pace: { t: 885, speed: 1, holding: ["goal-885"] } }))).toBe(true);
    expect(isSlowed(desk({ pace: { t: 940, speed: 6, holding: [] } }))).toBe(false);
  });

  it("is false after the end and in replay", () => {
    expect(isSlowed(desk({ pace: { t: 885, speed: 1, holding: ["a"] }, ended: { reason: "full_time" } }))).toBe(false);
    expect(isSlowed({ ...initialDesk, info })).toBe(false);
  });
});

describe("holdingMoment", () => {
  it("names the earliest moment still holding", () => {
    const a = moment("goal-885", 885), b = moment("card-900", 900);
    const s = desk({ thinking: [a, b], pace: { t: 900, speed: 1, holding: ["goal-885", "card-900"] } });
    expect(holdingMoment(s)).toEqual(a);
    expect(holdingMoment(desk({ thinking: [a] }))).toBeNull();
  });
});

describe("clockSpeed", () => {
  it("follows the pace, else the match speed", () => {
    expect(clockSpeed(desk({ pace: { t: 885, speed: 1, holding: ["a"] } }))).toBe(1);
    expect(clockSpeed(desk({}))).toBe(6);
    expect(clockSpeed(initialDesk)).toBe(6);
  });
});

describe("landedAt", () => {
  it("reads the publish step's time", () => {
    expect(landedAt(desk({ steps: { "goal-885": [step("analyst", 900), step("publish", 941)] } }), "goal-885")).toBe(941);
    expect(landedAt(desk({ steps: { "goal-885": [step("analyst", 900)] } }), "goal-885")).toBeNull();
    expect(landedAt(desk({}), "goal-885")).toBeNull();
  });
});

describe("stepChips", () => {
  it("shows the five base steps for a clean moment", () => {
    expect(stepChips([step("analyst"), step("tactical"), step("writer"), step("referee")])).toEqual([
      { step: "analyst", done: true }, { step: "tactical", done: true }, { step: "writer", done: true },
      { step: "referee", done: true }, { step: "publish", done: false },
    ]);
  });

  it("puts a rewrite and the second check in place", () => {
    const chips = stepChips([step("analyst"), step("tactical"), step("writer"), step("referee"), step("rewrite")]);
    expect(chips.map((c) => c.step)).toEqual(["analyst", "tactical", "writer", "referee", "rewrite", "recheck", "publish"]);
    expect(chips.map((c) => c.done)).toEqual([true, true, true, true, true, false, false]);
  });
});
