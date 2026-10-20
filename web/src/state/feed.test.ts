import { describe, expect, it } from "vitest";
import type { EventLine, FeedItem } from "../api/types";
import { weaveFeed } from "./feed";

const ev = (id: number, t: number) => ({ id, t, minute: Math.floor(t / 60) + 1 }) as EventLine;
const item = (id: string, t: number) => ({ moment: { id, t } }) as FeedItem;
const keys = (entries: ReturnType<typeof weaveFeed>) =>
  entries.map((e) => (e.kind === "event" ? `e${e.event.id}` : e.item.moment.id));

describe("weaveFeed", () => {
  it("weaves desk lines right after their own event, newest first", () => {
    const events = [ev(1, 10), ev(2, 25), ev(3, 40), ev(4, 885)];
    const items = [item("card-25", 25), item("goal-885", 885)];
    expect(keys(weaveFeed(events, items, 50))).toEqual(["goal-885", "e4", "e3", "card-25", "e2", "e1"]);
  });

  it("keeps only the latest events but every desk line", () => {
    const events = [ev(1, 10), ev(2, 25), ev(3, 40), ev(4, 885)];
    const items = [item("card-25", 25), item("goal-885", 885)];
    expect(keys(weaveFeed(events, items, 2))).toEqual(["goal-885", "e4", "e3", "card-25"]);
  });
});
