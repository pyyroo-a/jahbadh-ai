import { describe, expect, it } from "vitest";
import type { FeedItem, Rejection } from "../api/types";
import raw from "../../../data/showcase/match-042/desk.json?raw";
import { refereeTally } from "./referee";

const showcase = (JSON.parse(raw) as { items: FeedItem[] }).items;

describe("refereeTally", () => {
  it("tallies the showcase exactly like the desk CLI did", () => {
    const t = refereeTally(showcase);
    expect(t.drafted).toBe(83);
    expect(t.passedFirst).toBe(43);
    expect(t.byLayer).toEqual({ deterministic: 31, semantic: 26, persona: 39, localization: 12 });
  });

  it("counts rejections that arrived later with an extra combo", () => {
    const late = { claim_id: "x:c1", text: "t", layer: "localization", reasons: ["r"], attempt: 0, persona: "casual", language: "ar" } as Rejection;
    const item = { moment: { id: "x" }, stats: { drafted: 2, passed_first: 1 }, rejections: [late] } as unknown as FeedItem;
    expect(refereeTally([item])).toEqual({ drafted: 2, passedFirst: 1, byLayer: { deterministic: 0, semantic: 0, persona: 0, localization: 1 } });
  });
});
