// The words the desk shows for its switches and checks.

import type { Language, Persona, Rejection } from "../api/types";

export const PERSONAS: { key: Persona; label: string }[] = [
  { key: "pundit", label: "Studio pundit" }, { key: "casual", label: "Casual fan" }, { key: "fantasy", label: "Fantasy" },
];

export const LANGUAGES: { key: Language; label: string }[] = [
  { key: "en", label: "EN" }, { key: "ar", label: "AR" }, { key: "es", label: "ES" },
];

export const LAYER_LABELS: Record<Rejection["layer"], string> = {
  deterministic: "Number and ID check",
  semantic: "Referee judge",
  persona: "Persona re-check",
  localization: "Translation check",
};

export const COMBO_NOTICES = {
  limit: "This live match already has its two extra versions.",
  finished: "This live match has ended, so there's nothing new to add.",
  failed: "That version couldn't be added just now. Please try again.",
};

export const NOTES: Record<string, string> = {
  "persona fallback": "Shown in the pundit's words",
  "english fallback": "Shown in English",
  "raw translation": "Machine translation",
};

export const TACTICAL_CARD = { title: "Tactical view", hint: "Shapes, heatmaps and evidence. Tap to open." };

export const FEED_LABELS = {
  happening: "What's happening",
  more: (n: number) => `Show ${n} more ${n === 1 ? "event" : "events"}`,
};

/** Shown in live and ingest mode, where the desk's lines take a minute or two. */
export const SPEED_NOTE = "Quick lines arrive straight away. The desk's checked lines land a minute or two after each moment.";
