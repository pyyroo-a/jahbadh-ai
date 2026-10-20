// Player watch: the player table's order, the spotlight chips and which desk lines come first.

import type { FeedItem, PlayerRow } from "../api/types";

/** Stable, and a missing value (no passes yet) always sorts last. */
export function sortPlayers(rows: PlayerRow[], key: keyof PlayerRow, dir: "asc" | "desc"): PlayerRow[] {
  const sign = dir === "asc" ? 1 : -1;
  return rows.map((r, i) => ({ r, i })).sort((a, b) => {
    const x = a.r[key], y = b.r[key];
    if (x === null || y === null) return x === y ? a.i - b.i : x === null ? 1 : -1;
    const cmp = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
    return cmp ? sign * cmp : a.i - b.i;
  }).map((x) => x.r);
}

/** One chip per precomputed or requested spotlight, in desk order. */
export function spotlightChips(items: FeedItem[]): { player_id: string; momentId: string; label: string }[] {
  return items.filter((i) => i.moment.kind === "spotlight" && i.moment.player_id)
    .map((i) => ({ player_id: i.moment.player_id as string, momentId: i.moment.id,
      label: i.moment.label.replace(/^Spotlight: /, "") }));
}

/** Moments with a line about the followed player first; everything else keeps its order. */
export function followFirst(items: FeedItem[], about: (item: FeedItem) => boolean): FeedItem[] {
  return [...items.filter(about), ...items.filter((i) => !about(i))];
}
