// The highlights strip: the first approved line of every big moment, in match order. No model call.

import type { FeedItem, Language, MomentKind, Persona } from "../api/types";
import { claimText } from "./desk";

export const HIGHLIGHT_KINDS: MomentKind[] = ["goal", "big_chance", "formation_change", "substitution", "tactic_change"];
const KINDS = new Set(HIGHLIGHT_KINDS);

export type Highlight = { momentId: string; minute: number; kind: MomentKind; text: string; dir: "rtl" | "ltr" };

export function highlights(items: FeedItem[], persona: Persona, language: Language): Highlight[] {
  return items
    .filter((i) => KINDS.has(i.moment.kind) && i.claims.length > 0)
    .sort((a, b) => a.moment.t - b.moment.t)
    .map((i) => {
      const shown = claimText(i, i.claims[0].id, persona, language);
      return {
        momentId: i.moment.id, minute: Math.min(90, Math.floor(i.moment.t / 60) + 1), kind: i.moment.kind,
        text: shown.text, dir: shown.dir,
      };
    });
}
