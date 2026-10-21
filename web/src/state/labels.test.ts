import { describe, expect, it } from "vitest";
import { info } from "../test-fixtures";
import { SLOWDOWN, STEP_LABELS, speedNote } from "./labels";

describe("speedNote", () => {
  it("says nothing in replay, where every line is ready", () => {
    expect(speedNote(info)).toBeNull();
  });

  it("says live slows down at each key moment", () => {
    expect(speedNote({ ...info, mode: "live", speed: 6 })).toBe(
      "Quick lines arrive straight away. At each key moment the match slows to real time while the desk writes " +
      "and checks its line, so it lands within about a minute of the moment.");
  });

  it("keeps the note without a number for an outside feed, whose pace the server doesn't set", () => {
    expect(speedNote({ ...info, mode: "ingest", speed: 1 })).toBe(
      "Quick lines arrive straight away. The desk's checked lines land a minute or two after each moment.");
  });
});

describe("the slow-down copy", () => {
  it("stamps the match clock a line landed at", () => {
    expect(SLOWDOWN.landed(3356)).toBe("Checked, landed at 55:56");
    expect(SLOWDOWN.landed(65)).toBe("Checked, landed at 1:05");
  });

  it("says which moment the desk is checking, and why the match is slower", () => {
    expect(SLOWDOWN.checking("15' Goal for Northbridge FC (Kian Jansen)"))
      .toBe("The desk is checking 15' Goal for Northbridge FC (Kian Jansen).");
    expect(SLOWDOWN.pill).toBe("1x · desk checking");
    expect(SLOWDOWN.bannerSub).toBe("Slowed so the desk can write and check its line");
    expect(SLOWDOWN.checkingSub)
      .toBe("The match is slowed to real time so its agents can write and check the line before play moves on.");
  });

  it("names every desk step", () => {
    expect(Object.keys(STEP_LABELS).sort())
      .toEqual(["analyst", "publish", "recheck", "referee", "rewrite", "tactical", "writer"]);
    expect(STEP_LABELS.recheck).toBe("Referee again");
  });

  it("uses no em or en dashes", () => {
    const copy = [SLOWDOWN.pill, SLOWDOWN.banner, SLOWDOWN.bannerSub, SLOWDOWN.checking("x"), SLOWDOWN.checkingSub,
      SLOWDOWN.landed(3356), ...Object.values(STEP_LABELS), speedNote({ ...info, mode: "live" }) ?? ""];
    for (const text of copy) expect(text).not.toMatch(/[–—]/);
  });
});

describe("the live control bar note", () => {
  it("says the match slows for the desk, not that the feed runs behind", () => {
    expect(SLOWDOWN.controlNote).toBe("At each key moment the match slows to real time while the desk checks its line.");
  });
});
