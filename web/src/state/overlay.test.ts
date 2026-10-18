import { describe, expect, it } from "vitest";
import type { OverlayCue } from "../api/types";
import { activeCues, tickingClock } from "./overlay";

const cue = (match_time: number, duration_s: number, id = `cue-${match_time}`): OverlayCue => ({
  id, match_time, minute: Math.floor(match_time / 60) + 1, type: "goal", team_id: "NBR", player_id: null, value: null,
  unit: null, text: { en: "GOAL", ar: "هدف", es: "GOL" }, duration_s, event_ids: [], metric_ids: [], source: "event",
  synthetic: false, precomputed: true,
});

describe("activeCues", () => {
  it("shows a cue only while it is on air", () => {
    expect(activeCues([cue(100, 10)], 99)).toEqual([]);
    expect(activeCues([cue(100, 10)], 105)).toHaveLength(1);
    expect(activeCues([cue(100, 10)], 110)).toEqual([]);
  });

  it("puts the newest first and keeps at most two on screen", () => {
    const cues = [cue(100, 30, "a"), cue(105, 30, "b"), cue(110, 30, "c"), cue(200, 5, "later")];
    expect(activeCues(cues, 112).map((c) => c.id)).toEqual(["c", "b"]);
  });
});

describe("tickingClock", () => {
  it("runs on in real time at the stream's speed between messages", () => {
    expect(tickingClock(25, 1000, 1000, 6)).toBe(25);
    expect(tickingClock(25, 1000, 2500, 6)).toBe(34);          // 1.5 s of real time at 6x
  });

  it("never runs more than a minute past the last message, and stops at full time", () => {
    expect(tickingClock(25, 0, 60_000, 6)).toBe(85);
    expect(tickingClock(5390, 0, 60_000, 6)).toBe(5400);
    expect(tickingClock(100, 0, 60_000, 6, false)).toBe(100);  // the stream has ended
  });
});
