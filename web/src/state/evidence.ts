// What a claim stands on: the events and metrics it cites, and what became of each rejected draft.

import type { Claim, EventLine, FeedItem, Metric, Rejection } from "../api/types";

export type Selection = { momentId: string; claimId: string } | null;

/** The claim's events and metrics in the order it cites them. Events the stream hasn't reached yet are skipped. */
export function evidenceOf(item: FeedItem, claim: Claim, eventsById: Record<number, EventLine>):
  { events: EventLine[]; metrics: Metric[] } {
  const metrics = new Map(item.metrics.map((m) => [m.id, m]));
  return {
    events: claim.event_ids.map((id) => eventsById[id]).filter((e): e is EventLine => e !== undefined),
    metrics: claim.metric_ids.map((id) => metrics.get(id)).filter((m): m is Metric => m !== undefined),
  };
}

export const evidenceCount = (claim: Claim) => claim.event_ids.length + claim.metric_ids.length;

/** A writer's draft the Referee turned down was rewritten if its claim published, dropped if not. A persona or
 *  translation rejection means that version fell back to an earlier one. */
export function rejectionStatus(item: FeedItem, r: Rejection): "rewritten" | "dropped" | "fell back" {
  if (r.layer === "persona" || r.layer === "localization") return "fell back";
  return item.claims.some((c) => c.id === r.claim_id) ? "rewritten" : "dropped";
}
