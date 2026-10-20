// The Analyst view's Referee box: how this match's drafts fared. These are counts of the desk's own checks, not
// football numbers, so the browser can add them up.

import type { FeedItem, Rejection } from "../api/types";

export type RefereeTally = { drafted: number; passedFirst: number; byLayer: Record<Rejection["layer"], number> };

export function refereeTally(items: FeedItem[]): RefereeTally {
  const byLayer: RefereeTally["byLayer"] = { deterministic: 0, semantic: 0, persona: 0, localization: 0 };
  let drafted = 0, passedFirst = 0;
  for (const item of items) {
    drafted += item.stats.drafted ?? 0;
    passedFirst += item.stats.passed_first ?? 0;
    for (const r of item.rejections) byLayer[r.layer] += 1;
  }
  return { drafted, passedFirst, byLayer };
}
