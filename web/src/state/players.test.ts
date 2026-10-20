import { describe, expect, it } from "vitest";
import type { FeedItem, PlayerRow } from "../api/types";
import raw from "../../../data/showcase/match-042/desk.json?raw";
import { followFirst, sortPlayers, spotlightChips } from "./players";

const showcase = (JSON.parse(raw) as { items: FeedItem[] }).items;
const row = (player_id: string, xgi: number, pass_speed_avg: number | null = 50) =>
  ({ player_id, name: player_id, xgi, pass_speed_avg }) as PlayerRow;

describe("sortPlayers", () => {
  it("sorts by any column and keeps ties in order", () => {
    const rows = [row("a", 1), row("b", 2), row("c", 1)];
    expect(sortPlayers(rows, "xgi", "desc").map((r) => r.player_id)).toEqual(["b", "a", "c"]);
    expect(sortPlayers(rows, "xgi", "asc").map((r) => r.player_id)).toEqual(["a", "c", "b"]);
  });

  it("puts missing values last either way", () => {
    const rows = [row("a", 1, null), row("b", 1, 40), row("c", 1, 60)];
    expect(sortPlayers(rows, "pass_speed_avg", "desc").map((r) => r.player_id)).toEqual(["c", "b", "a"]);
    expect(sortPlayers(rows, "pass_speed_avg", "asc").map((r) => r.player_id)).toEqual(["b", "c", "a"]);
  });
});

describe("spotlightChips", () => {
  it("makes one chip per spotlight", () => {
    expect(spotlightChips(showcase).map((c) => c.label)).toEqual([
      "Omar Rasmus (most expected goal involvement)", "Kofi Moreau (most progressive passes)", "Quinn Yilmaz (most ball wins)",
    ]);
  });
});

describe("followFirst", () => {
  it("puts moments with a line about the followed player first and keeps the rest in order", () => {
    const items = [{ moment: { id: "a" } }, { moment: { id: "b" } }, { moment: { id: "c" } }] as FeedItem[];
    const about = (i: FeedItem) => i.moment.id === "c";
    expect(followFirst(items, about).map((i) => i.moment.id)).toEqual(["c", "a", "b"]);
  });
});
