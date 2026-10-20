// Which layout each persona gets: the persona changes the screen as well as the words.

import type { Persona } from "../api/types";

export type Layout = "fan" | "analyst" | "watch";

export function layoutFor(persona: Persona): Layout {
  return persona === "casual" ? "fan" : persona === "pundit" ? "analyst" : "watch";
}

/** Phones get their own arrangement under this width. */
export const PHONE_QUERY = "(max-width: 767px)";
