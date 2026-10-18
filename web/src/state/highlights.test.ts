import { describe, expect, it } from "vitest";
import type { FeedItem, MomentKind, RenderedClaim } from "../api/types";
import { highlights } from "./highlights";

const kindOf = (id: string) => id.split("-")[0] as MomentKind;
const tOf = (id: string) => Number(id.split("-").at(-1));
const item = (id: string, renders: RenderedClaim[] = []): FeedItem => ({
  moment: { id, kind: kindOf(id), t: tOf(id), team_id: null, player_id: null, event_ids: [], label: id },
  claims: [{ id: `${id}:c1`, text: `first ${id}`, metric_ids: [], event_ids: [], figures: [] },
    { id: `${id}:c2`, text: `second ${id}`, metric_ids: [], event_ids: [], figures: [] }],
  renders, rejections: [], metrics: [], stats: {}, latency_s: 1,
});
const emptyItem = (id: string): FeedItem => ({ ...item(id), claims: [] });

describe("highlights", () => {
  it("builds the strip from approved commentary only", () => {
    const strip = highlights([item("card-25"), item("goal-885"), emptyItem("goal-1317"), item("formation_change-3600")], "pundit", "en");
    expect(strip.map((h) => h.momentId)).toEqual(["goal-885", "formation_change-3600"]);
    expect(strip[0]).toEqual({ momentId: "goal-885", minute: 15, kind: "goal", text: "first goal-885", dir: "ltr" });
  });

  it("keeps match order and speaks the viewer's language", () => {
    const ar: RenderedClaim = { claim_id: "goal-885:c1", persona: "casual", language: "ar", text: "هدف", note: null };
    const strip = highlights([item("substitution-3600"), item("goal-885", [ar])], "casual", "ar");
    expect(strip.map((h) => [h.momentId, h.minute, h.dir])).toEqual([["goal-885", 15, "rtl"], ["substitution-3600", 61, "ltr"]]);
    expect(strip[0].text).toBe("هدف");
  });
});
