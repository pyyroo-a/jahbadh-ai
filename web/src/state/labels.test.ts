import { describe, expect, it } from "vitest";
import { info } from "../test-fixtures";
import { speedNote } from "./labels";

describe("speedNote", () => {
  it("says nothing in replay, where every line is ready", () => {
    expect(speedNote(info)).toBeNull();
  });

  it("puts the live delay in match minutes at the match's speed", () => {
    expect(speedNote({ ...info, mode: "live", speed: 6 })).toBe(
      "Quick lines arrive straight away. The desk's checked lines take about a minute to write and check, " +
      "which is about 6 match minutes at 6x, so they land a little after the moment they describe.");
    expect(speedNote({ ...info, mode: "live", speed: 3 })).toContain("about 3 match minutes at 3x");
  });

  it("keeps the note without a number for an outside feed, whose pace the server doesn't set", () => {
    expect(speedNote({ ...info, mode: "ingest", speed: 1 })).toBe(
      "Quick lines arrive straight away. The desk's checked lines land a minute or two after each moment.");
  });
});
