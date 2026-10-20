// The phone's "What's happening" list: events and desk lines woven into one feed.

import type { EventLine, FeedItem } from "../api/types";

export type FeedEntry = { kind: "event"; event: EventLine } | { kind: "desk"; item: FeedItem };

/** Newest first. A desk line sorts just after its own moment's event, so it reads right above it. Only the latest
 * `limit` events are kept, but every desk line is. */
export function weaveFeed(events: EventLine[], items: FeedItem[], limit: number): FeedEntry[] {
  const kept = events.slice(Math.max(0, events.length - limit));
  const entries = [
    ...kept.map((event) => ({ at: event.t, entry: { kind: "event", event } as FeedEntry })),
    ...items.map((item) => ({ at: item.moment.t + 0.5, entry: { kind: "desk", item } as FeedEntry })),
  ];
  return entries.sort((a, b) => b.at - a.at).map((x) => x.entry);
}
