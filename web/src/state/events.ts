// Which events the stream panel lists.

import type { EventLine, EventType } from "../api/types";

export const KEY_TYPES: EventType[] = [
  "KICKOFF", "GOAL", "SHOT", "CARD", "FOUL", "SUBSTITUTION", "FORMATION_CHANGE", "TACTIC_CHANGE", "PERIOD_END",
];
const KEY = new Set<EventType>(KEY_TYPES);

/** Newest first, at most `limit`, but a highlighted event (the selected claim's evidence) is always listed. */
export function visibleEvents(events: EventLine[], mode: "key" | "all", highlighted: Set<number>, limit = 200): EventLine[] {
  const shown: EventLine[] = [];
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    const lit = highlighted.has(e.id);
    if (lit || ((mode === "all" || KEY.has(e.type)) && shown.length < limit)) shown.push(e);
  }
  return shown;
}
